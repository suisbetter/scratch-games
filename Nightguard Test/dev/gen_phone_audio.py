"""Generate the Phone Guy voice clips for the Nightguard Test.

Each clip is synthesized with Microsoft's neural AI voice (edge-tts), slowed
slightly, then run through a telephone bandpass (~300 Hz-3.4 kHz) so it sounds
like FNAF's phone calls (voice on a landline), and encoded as a small 48 kHz
mp3 (lameenc). Outputs land in dev/phone_audio/ as phone_<key>.mp3 plus a
manifest.json describing each clip for install_phone_guy.py.
"""
import asyncio
import json
import os

import edge_tts
import lameenc
import numpy as np
import scipy.signal
import soundfile

VOICE = "en-US-GuyNeural"
RATE = "-10%"
VOLUME = "+0%"
TARGET_RATE = 48000
BIT_RATE = 96
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phone_audio")

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


def telephone_telephone(data, sr):
    b, a = scipy.signal.butter(2, [300, 3400], btype="bandpass", fs=sr)
    return scipy.signal.lfilter(b, a, data)


async def synthesize(text):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, volume=VOLUME)
    with tempfile_at() as path:
        await communicate.save(path)
        samples, sr = soundfile.read(path)
        return samples, sr


class tempfile_at:
    """Minimal temp-file helper so edge_tts has a .mp3 path to write to."""

    def __init__(self):
        import tempfile

        self.path = os.path.join(tempfile.gettempdir(), "pg_voice.mp3")

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        if os.path.exists(self.path):
            os.remove(self.path)
        return False


def encode_mp3(pcm16, rate):
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(BIT_RATE)
    encoder.set_in_sample_rate(rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(pcm16.tobytes()) + encoder.flush()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {"voice": VOICE, "rate": str(RATE), "sample_rate": TARGET_RATE, "clips": {}}
    for key, display, text in CLIPS:
        out_name = f"phone_{key}.mp3"
        out_path = os.path.join(OUT_DIR, out_name)
        raw, src_rate = asyncio.run(synthesize(text))  # float in [-1, 1]
        mono = raw if raw.ndim == 1 else np.mean(raw, axis=1)
        mono = scipy.signal.resample_poly(mono, TARGET_RATE, src_rate)
        filtered = telephone_telephone(mono, TARGET_RATE)
        filtered = np.clip(filtered, -1.0, 1.0)
        pcm = np.int16(np.round(filtered * 32767))
        mp3_bytes = encode_mp3(pcm, TARGET_RATE)
        with open(out_path, "wb") as f:
            f.write(mp3_bytes)
        duration = pcm.shape[0] / TARGET_RATE
        manifest["clips"][key] = {
            "name": display,
            "file": out_name,
            "duration_s": round(duration, 2),
            "sample_count": int(pcm.shape[0]),
        }
        print(f"wrote {out_name}: {duration:.2f}s, {len(mp3_bytes)} bytes")
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest written to {OUT_DIR}/manifest.json")


if __name__ == "__main__":
    main()