"""Generate the Phone Guy voice clips for the Nightguard Test with ElevenLabs.

Voice: 'Chris - Charming, Down-to-Earth' (iP95p4xoKVk53GoZ742B), an
ElevenLabs platform premade voice -- the closest one the free tier can
actually synthesize to FNAF's Phone Guy (middle-aged American male, casual,
conversational, down-to-earth). The closer library clones ('Plain', 'Ben -,
Deep, Warm, Conversational', etc.) all require a paid plan via the API
("Free users cannot use library voices via the API").

Processing pipeline (makes the TTS audio sound like a man calling in on a
worn landline, as in the game's night calls):

1. TTS -> decode float mono   (ElevenLabs returns 44.1 kHz mp3)
2. resample to 48 kHz
3. telephone bandpass  ~300-3400 Hz  (voice-band roll-off)
4. add radio static / hiss  -> high-frequency noise floor
5. add sparse vinyl-style crackle pops  (worn recording feel)
6. mild soft-clip + normalise, encode 48 kHz mono mp3 (lameenc)

Outputs land in dev/phone_audio/ as phone_<key>.mp3 (for human inspection)
plus md5-named copies ready for the sb3 zip, and a manifest.json describing
each clip for install_phone_guy.py / swap_phone_sounds.py.

Run after adding your ELEVENLABS_API_KEY to dev/.env (gitignored) and before
`python install_phone_guy.py` / `python repack_sb3.py`.
"""
import hashlib
import json
import os
import shutil

import lameenc
import numpy as np
import requests
import scipy.signal
import soundfile

VOICE_ID = "iP95p4xoKVk53GoZ742B"
VOICE_NAME = "Chris - Charming, Down-to-Earth"
MODEL_ID = "eleven_multilingual_v2"
VOICE_SETTINGS = {
    "stability": 0.6,
    "similarity_boost": 0.8,
    "style": 0.3,
    "use_speaker_boost": True,
}
TARGET_RATE = 48000
BIT_RATE = 96
TELEPHONE_LOW = 300
TELEPHONE_HIGH = 3400
STATIC_GAIN_DB = -30.0  # hiss level relative to voice peak
CRACKLE_GAIN_DB = -36.0  # pop level relative to voice peak
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phone_audio")
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

CLIPS = [
    (
        "greeting",
        "Phone Guy Greeting",
        "Uh, hello? Hello hello! Uh, welcome to your new night shift at Freddy Fazbear's Pizza. "
        "I'm the guy that used to work the night shift. Uh, the animatronics will try to get into "
        "your office, so use the doors and the cameras. And above all, conserve your power. "
        "Uh, good luck out there.",
    ),
    (
        "1am",
        "Phone Guy Hour 1",
        "Uh, one AM. So far, so good. If you hear something shuffling around in the halls, "
        "it's just the animatronics doing their nightly patrol. If any of them stops outside your "
        "door, close it, and leave it closed.",
    ),
    (
        "2am",
        "Phone Guy Hour 2",
        "Uh, quick tip for hour two. The animatronics are attracted to sound and movement. "
        "So keep an eye on the cameras, keep the doors closed when they get close, and don't waste "
        "power on the lights. You need it to last until six AM.",
    ),
    (
        "3am",
        "Phone Guy Hour 3",
        "Uh, three in the morning. They get a lot more active this hour. Uh, you might see one "
        "standing just outside your door. If you do, keep it closed. Just keep it closed.",
    ),
    (
        "4am",
        "Phone Guy Hour 4",
        "Uh, hour four. You're almost there. The animatronics are not allowed to come into the "
        "office, so as long as you keep those doors closed, you'll be fine. Believe me, that makes "
        "it a lot easier to stay relaxed.",
    ),
    (
        "5am",
        "Phone Guy Hour 5",
        "Uh, five AM. One more hour, and you're done for the night. Whatever you do, don't let "
        "the power run out. Whatever you do. Uh, trust me, you do not want to know what happens "
        "when it goes dark.",
    ),
    (
        "w1",
        "Phone Guy Warning 1",
        "Uh, they're heading your way. Close a door, now!",
    ),
    (
        "w2",
        "Phone Guy Warning 2",
        "Uh, I just saw something move near your office. Check your cameras! Now!",
    ),
    (
        "w3",
        "Phone Guy Warning 3",
        "Uh, hey, you've got company in the hall. Keep that door shut!",
    ),
    (
        "w4",
        "Phone Guy Warning 4",
        "Uh, that one outside your door is not there to say hello. Close it!",
    ),
]


def load_key():
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == "ELEVENLABS_API_KEY":
                    return v.strip()
        raise SystemExit("ELEVENLABS_API_KEY not found in dev/.env")
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("set ELEVENLABS_API_KEY (env or dev/.env)")
    return key


def synthesize(text):
    """Call the ElevenLabs API for one clip; return (float samples, sr)."""
    key = load_key()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    r = requests.post(
        url,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": MODEL_ID, "voice_settings": VOICE_SETTINGS},
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"TTS failed ({r.status_code}): {r.text[:300]}")
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pg_tts_tmp.mp3")
    with open(tmp, "wb") as f:
        f.write(r.content)
    try:
        samples, sr = soundfile.read(tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return samples, sr


def telephone_bandpass(data, sr):
    b, a = scipy.signal.butter(2, [TELEPHONE_LOW, TELEPHONE_HIGH], btype="bandpass", fs=sr)
    return scipy.signal.lfilter(b, a, data)


def add_static_and_crackle(data, sr):
    """Radio-hiss + sporadic record pops, scaled to the voice peak."""
    n = data.shape[0]
    peak = float(np.max(np.abs(data), initial=1e-9))

    hiss = np.random.default_rng(0).standard_normal(n)
    b, a = scipy.signal.butter(2, [1500, 9000], btype="bandpass", fs=sr)
    hiss = scipy.signal.lfilter(b, a, hiss)
    if np.max(np.abs(hiss), initial=1e-9) > 0:
        hiss *= (peak * 10 ** (STATIC_GAIN_DB / 20)) / np.max(np.abs(hiss), initial=1e-9)

    crackles = np.zeros(n)
    rng = np.random.default_rng(7)
    pops = int(round(n / sr * 1.2))
    for _ in range(pops):
        if rng.random() < 0.7:
            start = int(rng.integers(0, n))
            dur = int(sr * rng.uniform(0.002, 0.010))
            end = min(start + dur, n)
            if end > start:
                env = np.exp(-np.arange(end - start) / (sr * 0.0015))
                crackles[start:end] += rng.standard_normal(end - start) * env
    if np.max(np.abs(crackles), initial=1e-9) > 0:
        crackles *= (peak * 10 ** (CRACKLE_GAIN_DB / 20)) / np.max(np.abs(crackles), initial=1e-9)

    return np.clip(data + hiss + crackles, -1.0, 1.0)


def encode_mp3(pcm16, rate):
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(BIT_RATE)
    encoder.set_in_sample_rate(rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(pcm16.tobytes()) + encoder.flush()


def md5_bytes(data):
    return hashlib.md5(data).hexdigest()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {
        "provider": "elevenlabs",
        "voice_id": VOICE_ID,
        "voice": VOICE_NAME,
        "model": MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
        "effect": {
            "resample_hz": TARGET_RATE,
            "telephone_bandpass_hz": [TELEPHONE_LOW, TELEPHONE_HIGH],
            "static_gain_db": STATIC_GAIN_DB,
            "crackle_gain_db": CRACKLE_GAIN_DB,
        },
        "clips": {},
    }
    for key, display, text in CLIPS:
        raw, src_rate = synthesize(text)  # float in [-1, 1], possibly stereo
        mono = raw if raw.ndim == 1 else np.mean(raw, axis=1)
        mono = scipy.signal.resample_poly(mono, TARGET_RATE, src_rate)
        filtered = telephone_bandpass(mono, TARGET_RATE)
        finished = add_static_and_crackle(filtered, TARGET_RATE)
        pcm = np.int16(np.round(finished * 32767))
        mp3_bytes = encode_mp3(pcm, TARGET_RATE)

        out_name = f"phone_{key}.mp3"
        out_path = os.path.join(OUT_DIR, out_name)
        with open(out_path, "wb") as f:
            f.write(mp3_bytes)
        digest = md5_bytes(mp3_bytes)
        staged_name = f"{digest}.mp3"
        shutil.copy2(out_path, os.path.join(OUT_DIR, staged_name))

        duration = pcm.shape[0] / TARGET_RATE
        manifest["clips"][key] = {
            "name": display,
            "file": out_name,
            "duration_s": round(duration, 2),
            "sample_count": int(pcm.shape[0]),
            "md5ext": staged_name,
        }
        print(f"wrote {out_name}: {duration:.2f}s, {len(mp3_bytes)} bytes -> {staged_name}")
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest written to {OUT_DIR}/manifest.json")


if __name__ == "__main__":
    main()