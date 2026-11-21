"""Original 1994-inspired instrumental loop and scene sounds."""
from array import array
from math import exp, pi, sin, tau
from pathlib import Path
from random import Random
import wave


RATE = 22050
OUT = Path(__file__).resolve().parents[1] / "Resources/Audio/ActOne"
OUT.mkdir(parents=True, exist_ok=True)


def save(name, samples, rate=RATE):
    pcm = array("h", (round(32767 * max(-1, min(1, sample))) for sample in samples))
    with wave.open(str(OUT / (name + ".wav")), "wb") as result:
        result.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        result.writeframes(pcm.tobytes())


def sound(name, duration, sample):
    random = Random(name)
    save(name, (sample(i / RATE, random.uniform(-1, 1)) for i in range(round(duration * RATE))))


def envelope(t, start, decay):
    d = t - start
    return exp(-d * decay) if d >= 0 else 0


def effects():
    sound("Knock", .72, lambda t, n: sum(envelope(t, k, 45) * (.52 * sin(tau * 103 * (t-k)) + .29*n)
                                         for k in (0,.155,.31)))
    sound("Dial", 2.15, lambda t, n: (.16*sin(tau*440*t)+.11*sin(tau*480*t)) if (t % 1.05) < .46 else n*.004)
    sound("Paper", .51, lambda t, n: .42*n*(sin(pi*min(1,t/.51))**2)*(.45+.55*sin(315*t)**2))
    sound("Radio", .36, lambda t, n: n*.31*(sin(84*t)**2)*exp(-t*8))
    sound("RadioHangup", .47, lambda t, n: .42*n*exp(-t*28)+.21*sin(tau*175*t)*exp(-t*17))
    sound("Lighter", .65, lambda t, n: .31*n*(envelope(t,.07,75)+envelope(t,.28,240)))
    sound("Impact", .42, lambda t, n: .42*sin(2*pi*(86*t-68*t*t))*exp(-t*19)+.34*n*exp(-t*56))
    sound("Shot", .63, lambda t, n: .78*n*exp(-t*21)+.23*sin(2*pi*(120*t-35*t*t))*exp(-t*24))
    sound("Badge", .62, lambda t, n: .41*(sin(tau*812*t)+.3*sin(tau*1354*t))*exp(-t*13)+.18*n*exp(-t*83))
    sound("Wood", .53, lambda t, n: .23*n*exp(-t*8)+.26*sin(2*pi*(102*t+79*t*t))*exp(-t*11))
    sound("TapeClick", .45, lambda t, n: .22*n*exp(-t*16)+.51*sin(tau*214*t)*exp(-t*55))
    sound("StepClick", .23, lambda t, n: .34*sin(tau*980*t)*exp(-t*29)+.13*n*exp(-t*27))
    sound("Alarm", 1.72, lambda t, n: (.18*sin(tau*685*t)+.16*sin(tau*843*t))*(1.0 if t% .51<.28 else .02))
    filtered = 0
    def rain(t, n):
        nonlocal filtered
        filtered = .77*filtered + .23*n
        return .35*filtered + .02*sin(tau*21*t)*sin(t)
    sound("Rain", 8, rain)


def music():
    bpm = 94
    beat = 60 / bpm
    length = 32 * beat
    random = Random(944)
    chords = ((45,52,57,60,64,67,64,60), (41,48,53,57,60,64,60,57),
              (48,55,60,64,67,71,67,64), (43,50,55,59,62,67,62,59))
    notes = [2**((midi-69)/12) * 440 for chord in chords for midi in chord]
    samples = []
    for i in range(round(length*RATE)):
        t = i/RATE
        eighth = int(t/(beat*.5))
        note = notes[eighth % len(notes)]
        pick = t - eighth*beat*.5
        guitar = (.25*sin(tau*note*pick)+.16*sin(tau*2*note*pick)+.07*sin(tau*4*note*pick))*exp(-pick*5)
        pulse=(t%beat)/beat
        bass_freq=notes[(eighth//8%4)*8]*.5
        bass=.20*sin(tau*bass_freq*t)*exp(-pulse*2.8)
        n=random.uniform(-1,1)
        hats=.09*n*exp(-pick*72)
        kick=.28*sin(2*pi*(72*pulse-.55*pulse*pulse))*exp(-pulse*20) if int(t/beat)%2==0 else 0
        snare=.15*n*exp(-pulse*34) if int(t/beat)%2 else 0
        fade=min(1,t/.027,(length-t)/.027)
        samples.append((guitar+bass+hats+kick+snare)*fade*.64)
    save("Music90",samples)


if __name__=="__main__":
    effects()
    music()
