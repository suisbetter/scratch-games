"""Update the PhoneGuy sprite's sound entries in nightguard_extract/project.json
to point at newly regenerated clips (e.g. after re-running gen_phone_audio.py
with a different voice/effect).

The sprite's blocks reference sounds by NAME (via sound_sounds_menu shadow
fields), so only the sounds[] metadata -- assetId / md5ext / sampleCount / rate
-- changes, plus the staged files lying around in dev/phone_audio/. The id
dedupe from install_phone_guy.py is untouched here.

Run after `python gen_phone_audio.py` and before `python repack_sb3.py`.
"""
import glob
import json
import os

WORK = "nightguard_extract"
PROJECT = os.path.join(WORK, "project.json")
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phone_audio")


def main():
    data = json.load(open(PROJECT, encoding="utf-8"))
    manifest = json.load(open(os.path.join(AUDIO_DIR, "manifest.json"), encoding="utf-8"))
    clips = manifest["clips"]

    pg = next(t for t in data["targets"] if t["name"] == "PhoneGuy")

    new_md5s = set()
    for key, meta in clips.items():
        staged = meta["md5ext"]
        new_md5s.add(staged)
        digest = staged[: -len(".mp3")]
        src = os.path.join(AUDIO_DIR, meta["file"])
        assert os.path.exists(src), f"missing clip {src}"
        target = next(
            (s for s in pg["sounds"] if s["name"] == meta["name"]), None
        )
        if target is None:
            raise AssertionError(f"PhoneGuy has no sound named {meta['name']!r}")
        old = target["md5ext"]
        target.update(
            {
                "assetId": digest,
                "dataFormat": "mp3",
                "rate": int(manifest["effect"]["resample_hz"]),
                "sampleCount": int(meta["sample_count"]),
                "md5ext": staged,
            }
        )
        print(f"{key:9s} {old} -> {staged} ({meta['duration_s']}s)")

    # Drop stale md5-named staged files (old clips from a previous generation)
    for p in glob.glob(os.path.join(AUDIO_DIR, "[0-9a-f]" * 32 + ".mp3")):
        name = os.path.basename(p)
        if name not in new_md5s:
            os.remove(p)
            print(f"removed stale staged asset {name}")

    json.dump(data, open(PROJECT, "w", encoding="utf-8"), indent=2)
    print(f"updated {len(clips)} sound entries in {PROJECT}")


if __name__ == "__main__":
    main()