"""Generates sounds/startup.wav, the chime Carbot plays when it boots.

Run from the repository root: python3 tools/make_startup_sound.py
Uses only the standard library, so it runs anywhere; the sound is synthesised here, not sampled from anywhere else.
"""
import math
import os
import struct
import wave

SAMPLE_RATE = 22050
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds", "startup.wav")

# A rising C major arpeggio, each note starting before the previous one fades: (frequency Hz, start s, length s).
NOTES = [
    (523.25, 0.00, 0.30),   # C5
    (659.25, 0.14, 0.30),   # E5
    (783.99, 0.28, 0.30),   # G5
    (1046.50, 0.42, 0.75),  # C6, held
]
# A soft upward sweep under the notes gives it the "powering up" feel.
SWEEP = (180.0, 520.0, 0.0, 0.45)  # from Hz, to Hz, start s, length s
PEAK = 0.45


def envelope(t, length, attack=0.01, release=0.12):
    """Quick attack, gentle exponential decay and a short release so notes start and end without clicks."""
    if t < 0 or t > length:
        return 0.0
    level = min(1.0, t / attack) * math.exp(-2.5 * t / length)
    if t > length - release:
        level *= (length - t) / release
    return level


def tone(frequency, t):
    """A sine with a little second and third harmonic, for a slightly synthetic, robotic timbre."""
    phase = 2 * math.pi * frequency * t
    return math.sin(phase) + 0.3 * math.sin(2 * phase) + 0.15 * math.sin(3 * phase)


def sweep(t):
    fromHz, toHz, start, length = SWEEP
    local = t - start
    if local < 0 or local > length:
        return 0.0
    # Integrate the linearly rising frequency so the phase stays continuous.
    phase = 2 * math.pi * (fromHz * local + (toHz - fromHz) * local * local / (2 * length))
    return 0.35 * math.sin(phase) * envelope(local, length, attack=0.05, release=0.15)


def sample(t):
    value = sweep(t)
    for frequency, start, length in NOTES:
        value += 0.45 * tone(frequency, t - start) * envelope(t - start, length)
    return value


def main():
    duration = max(start + length for _, start, length in NOTES) + 0.05
    samples = [sample(i / SAMPLE_RATE) for i in range(int(duration * SAMPLE_RATE))]

    loudest = max(abs(value) for value in samples)
    scale = PEAK / loudest

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with wave.open(OUTPUT, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(b"".join(struct.pack("<h", int(value * scale * 32767)) for value in samples))

    print("Wrote {} ({:.2f}s)".format(OUTPUT, duration))


if __name__ == "__main__":
    main()
