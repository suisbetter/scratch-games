"""Shrink the "A Night at Freddys" sb3 while preserving behavior.

The sb3 currently stores every zip member with STORE (no compression). This
pass does three lossless-of-layout optimizations:

1. Recompress the whole zip with DEFLATE level 9 (project.json, svg and, to a
   lesser extent, wav compress well).
2. Convert large opaque PNG costumes/backdrops to quality-88 JPEG of *identical
   pixel dimensions* (Scratch natively supports jpg costumes; only fully opaque
   images are converted so nothing that relied on transparency breaks).
   Costume names, order, and positions are untouched, so NextCostume /
   SwitchCostumeTo / GoToXY behave exactly as before. The project uses no
   TouchingColor sensing, so the (very slight) lossy pixel change is inert.
3. Re-encode large WAV sounds to 192kbps MP3 at the same sample rate / channel
   count, preserving duration (PlayUntilDone timing is unchanged). Small WAVs
   and MP3s are left alone.

Every asset file is rewritten under its content md5 (like the Scratch editor
does), and project.json's costumes/backdrops/sounds references are remapped in
lockstep, so the editor can still resolve every member.
"""

import hashlib
import io
import json
import os
import subprocess
import zipfile

from PIL import Image

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = None

SB3 = "../sb3/1079847401.sb3"
TMP = SB3 + ".shrunk"
MIN_IMG = 40_000         # only bother re-encoding images >= this size
PNG_TO_JPG_Q = 88
JPG_ACCEPT_RATIO = 0.55  # only take jpeg if it's at most this fraction of png
WAV_TO_MP3_BITRATE = 192
MIN_MP3 = 1_000_000      # transcode mp3s bigger than this
MP3_TO_MP3_BITRATE = 160

TOUCH_COLOR = {"sensing_touching_color", "sensing_color_touching_color"}


def md5(data):
    return hashlib.md5(data).hexdigest()


def transcode_audio(src_bytes, src_fmt, bitrate):
    if FFMPEG is None:
        return None
    try:
        p = subprocess.run(
            [FFMPEG, "-y", "-f", src_fmt, "-i", "-", "-vn",
             "-codec:a", "libmp3lame", "-b:a", "%dk" % bitrate,
             "-f", "mp3", "pipe:1"],
            input=src_bytes, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=300)
    except Exception:
        return None
    if p.returncode != 0 or not p.stdout:
        return None
    return p.stdout


def wav_to_mp3(wav_bytes):
    return transcode_audio(wav_bytes, "wav", WAV_TO_MP3_BITRATE)


def mp3_to_mp3(mp3_bytes):
    return transcode_audio(mp3_bytes, "mp3", MP3_TO_MP3_BITRATE)


def png_to_jpeg_opt(png_bytes):
    try:
        im = Image.open(io.BytesIO(png_bytes))
        im.load()
        rgba = im.convert("RGBA")
        alpha = rgba.getchannel("A")
        if alpha.getextrema()[0] != 255:
            return None, False  # has real transparency; keep as png below
        if rgba.width * rgba.height < 40_000:
            return None, True   # tiny image; jpg barely wins
        buf = io.BytesIO()
        rgba.convert("RGB").save(buf, "JPEG", quality=PNG_TO_JPG_Q, optimize=True,
                                 progressive=True)
        return buf.getvalue(), True
    except Exception:
        return None, False


def png_lossless(png_bytes):
    try:
        im = Image.open(io.BytesIO(png_bytes))
        im.load()
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True, compress_level=9)
        out = buf.getvalue()
        return out if len(out) < len(png_bytes) else png_bytes
    except Exception:
        return png_bytes


def main():
    with zipfile.ZipFile(SB3) as zin:
        pj = json.loads(zin.read("project.json").decode("utf-8"))
        members = {i.filename: i.file_size for i in zin.infolist()}
        asset_data = {f: zin.read(f) for f in members if f != "project.json"}

    # targets that use color sensing keep exact-pixel costumes
    keep_pixels = set()
    for t in pj["targets"]:
        for b in t["blocks"].values():
            if isinstance(b, dict) and b["opcode"] in TOUCH_COLOR:
                keep_pixels.add(t["name"])

    # build remap: old md5ext -> (new md5ext, new data, new dataFormat)
    remap = {}
    stats = {"wav": (0, 0), "jpg": (0, 0), "png_lossless": (0, 0)}
    for name, data in asset_data.items():
        ext = os.path.splitext(name)[1].lower()
        if ext == ".png" and len(data) >= MIN_IMG:
            jpg, opaque = png_to_jpeg_opt(data)
            if jpg is not None and jpg and len(jpg) < len(data) * JPG_ACCEPT_RATIO:
                new = md5(jpg) + ".jpg"
                remap[name] = (new, jpg, "jpg")
                stats["jpg"] = (stats["jpg"][0] + 1, stats["jpg"][1] + len(data) - len(jpg))
                continue
            if jpg is not None:
                opt = png_lossless(data)
                if opt is not data:
                    new = md5(opt) + ".png"
                    remap[name] = (new, opt, "png")
                    stats["png_lossless"] = (
                        stats["png_lossless"][0] + 1,
                        stats["png_lossless"][1] + len(data) - len(opt),
                    )
        elif ext == ".wav" and len(data) >= MIN_IMG:
            mp3 = wav_to_mp3(data)
            if mp3 is not None and len(mp3) < len(data) * 0.8:
                new = md5(mp3) + ".mp3"
                remap[name] = (new, mp3, "mp3")
                stats["wav"] = (stats["wav"][0] + 1, stats["wav"][1] + len(data) - len(mp3))
        elif ext == ".mp3" and len(data) >= MIN_MP3:
            mp3 = mp3_to_mp3(data)
            if mp3 is not None and len(mp3) < len(data) * 0.85:
                new = md5(mp3) + ".mp3"
                remap[name] = (new, mp3, "mp3")
                stats["wav"] = (stats["wav"][0] + 1, stats["wav"][1] + len(data) - len(mp3))

    # rewrite references
    for t in pj["targets"]:
        skip = t["name"] in keep_pixels
        for lst in ("costumes", "backdrops"):
            for item in t.get(lst) or []:
                old = item["md5ext"]
                if skip:
                    continue
                if old in remap:
                    new, data, fmt = remap[old]
                    item["md5ext"] = new
                    item["dataFormat"] = fmt
                    item["assetId"] = md5(data)
        for item in t.get("sounds") or []:
            old = item["md5ext"]
            if old in remap:
                new, data, fmt = remap[old]
                if fmt == "mp3":
                    item["md5ext"] = new
                    item["dataFormat"] = "mp3"
                    item["assetId"] = md5(data)

    new_pj = json.dumps(pj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    orig_total = sum(members.values())
    with zipfile.ZipFile(SB3) as zin, zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        for info in zin.infolist():
            if info.filename == "project.json":
                zout.writestr("project.json", new_pj)
                continue
            if info.filename in remap:
                new, data, _ = remap[info.filename]
                zout.writestr(new, data)
            else:
                zout.writestr(info.filename, zin.read(info.filename))

    print("converted -> %s" % {k: v[0] for k, v in stats.items()})
    print("saved per pass: wav=%.1fMB jpg=%.1fMB png_lossless=%.1fMB"
          % (stats["wav"][1] / 1e6, stats["jpg"][1] / 1e6, stats["png_lossless"][1] / 1e6))

    os.replace(TMP, SB3)
    new_size = os.path.getsize(SB3)
    print("file size: %.1fMB -> %.1fMB  (%.1f%% smaller)"
          % (orig_total / 1e6, new_size / 1e6, 100 * (1 - new_size / orig_total)))

    with zipfile.ZipFile(SB3) as z:
        bad = z.testzip()
        print("zip integrity:", "OK" if bad is None else "CORRUPT: " + str(bad))
        print("entries:", len(z.namelist()))


if __name__ == "__main__":
    main()