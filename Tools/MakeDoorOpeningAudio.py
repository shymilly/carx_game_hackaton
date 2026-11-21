"""Render the original one-shot door effects at 48 kHz, mono."""

from array import array
from math import exp, sin, tau
from pathlib import Path
from random import Random
import wave

RATE = 48000
DESTINATION = Path(__file__).resolve().parents[1] / "Resources/Audio/Doors"


def strike(t, onset, frequencies, decay):
    elapsed = t - onset
    if elapsed < 0:
        return 0
    attack = min(elapsed / .0007, 1)
    harmonics = sum(sin(tau * frequency * elapsed) / (i + 1)
                    for i, frequency in enumerate(frequencies))
    return attack * exp(-elapsed * decay) * harmonics


def render(name, duration, tones, hinge, seed):
    rng = Random(seed)
    slow_noise = 0
    filtered = 0
    phase = 0
    samples = []
    for frame in range(round(duration * RATE)):
        t = frame / RATE
        noise = rng.uniform(-1, 1)
        slow_noise += .042 * (noise - slow_noise)
        filtered += .27 * (noise - filtered)
        latch = .6 * strike(t, .014, tones, 94) + .28 * strike(t, .050, tones[1:], 116)
        latch += .27 * (filtered - slow_noise) * exp(-220 * abs(t - .018))
        t_slide = (t - .058) / (duration - .058)
        glide = max(0, sin(min(1, max(0, t_slide)) * tau * .5)) ** 1.45
        phase += tau * hinge * (1 + .14 * sin(t * 39) - .16 * t_slide + .20 * slow_noise) / RATE
        swing = glide * (.15 * slow_noise + .047 * sin(phase) + .016 * sin(phase * 2.01))
        settle = .055 * strike(t, duration - .087, tones[:2], 125)
        fade = min(1, (duration - t) / .023)
        samples.append((latch + swing + settle) * fade)
    gain = .60 / max(abs(sample) for sample in samples)
    with wave.open(str(DESTINATION / (name + ".wav")), "wb") as output:
        output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        output.writeframes(array("h", (round(value * gain * 32767) for value in samples)).tobytes())


if __name__ == "__main__":
    DESTINATION.mkdir(parents=True, exist_ok=True)
    render("S_WoodenDoorOpen", .56, (117, 401, 835, 1538), 183, 94)
    render("S_EntryDoorOpen", .30, (144, 494, 1170, 2210), 268, 96)
    render("S_FridgeDoorOpen", .44, (103, 265, 603, 1093), 90, 98)
