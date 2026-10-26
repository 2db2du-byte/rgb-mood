#!/usr/bin/env python3
"""rgb-mood: Rabbid's PC lights follow the music, or the temperature when it's quiet (2026-10-26).

Talks to the OpenRGB server on 127.0.0.1:6742 (rgb-mood starts it). Every frame:
  - Music playing (sound coming out of the default speakers): the motherboard ARGB plugs pulse
    with the bass, the colour drifting slowly around the rainbow.
  - Quiet for a few seconds: they glow a calm colour from the hottest chip,
    blue when cool (40 C and under), purple when working, red when hot (85 C and up).
The RAM stays solid blue: Rabbid's call (2026-10-26). Set RAM_VU = True to make it a VU meter instead.
The motherboard plugs only light fans once CyberPower's RGB controller sync wire is plugged in.
Run it with the `rgb-mood` command (on / off / status); it never starts at boot.
"""
import colorsys
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

FPS = 30
RATE = 44100
CHUNK = RATE // FPS
ARGB_LEDS = 40          # LEDs we drive on each motherboard ARGB plug (3 fans x ~8-12, plus spare)
MUSIC_ON = 0.004        # loudness that counts as "music is playing"
QUIET_SECONDS = 4       # this long under MUSIC_ON goes back to temperature mode
COOL, HOT = 40.0, 85.0  # temperature range mapped blue -> red
RAM_VU = False          # Rabbid wants the RAM solid blue
RAM_BLUE = RGBColor(0, 0, 255)


class Audio(threading.Thread):
    """Listens to what the speakers are playing (the default output's monitor), keeps the latest levels."""

    def __init__(self):
        super().__init__(daemon=True)
        self.level = self.bass = 0.0

    def run(self):
        cmd = ["pw-record", "-P", "{ stream.capture.sink=true }", "--format", "s16", "--rate", str(RATE),
               "--channels", "1", "--latency", "20ms", "-"]
        while True:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            window = np.hanning(CHUNK)
            freqs = np.fft.rfftfreq(CHUNK, 1 / RATE)
            low = (freqs > 20) & (freqs < 160)
            while True:
                raw = proc.stdout.read(CHUNK * 2)
                if len(raw) < CHUNK * 2:
                    break
                x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
                self.level = float(np.sqrt(np.mean(x * x)))
                spectrum = np.abs(np.fft.rfft(x * window))
                self.bass = float(spectrum[low].mean() / CHUNK * 8)
            proc.kill()
            self.level = self.bass = 0.0
            time.sleep(2)  # the audio server went away; try again


def chip_temp():
    """The hotter of the CPU and the graphics card, in C."""
    temps = []
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if (hw / "name").read_text().strip() == "k10temp":
                temps.append(int((hw / "temp1_input").read_text()) / 1000)
        except (OSError, ValueError):
            pass
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=3).stdout
        temps.append(float(out.split()[0]))
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return max(temps) if temps else COOL


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, max(0.0, min(1.0, v)))
    return RGBColor(int(r * 255), int(g * 255), int(b * 255))


def temp_color(t, now):
    """Blue at COOL, purple in the middle, red at HOT, breathing gently."""
    k = max(0.0, min(1.0, (t - COOL) / (HOT - COOL)))
    hue = (0.62 + 0.38 * k) % 1.0          # 0.62 blue -> 0.8 purple -> 1.0 red
    breathe = 0.65 + 0.35 * (0.5 + 0.5 * np.sin(now * (0.8 + 2.5 * k)))
    return hsv(hue, 1.0, breathe)


def vu_meter(n, level):
    """RAM bar: how many LEDs are lit follows the volume, green at the bottom, red at the top."""
    lit = min(n, int(level * n * 1.15 + 0.5))
    out = []
    for i in range(n):
        if i < lit:
            out.append(hsv(0.33 * (1 - i / max(1, n - 1)), 1.0, 1.0))
        else:
            out.append(RGBColor(0, 0, 0))
    return out


def main():
    client = OpenRGBClient("127.0.0.1", 6742, "rgb-mood")
    ram = [d for d in client.devices if "DRAM" in d.name]
    if not RAM_VU:
        for d in ram:
            d.set_mode("static")
            d.set_color(RAM_BLUE)
        ram = []
    boards = [d for d in client.devices if d.type.name == "MOTHERBOARD"]
    for d in ram + boards:
        d.set_mode("direct")
    for b in boards:
        for z in b.zones:
            if len(z.leds) != ARGB_LEDS:
                z.resize(ARGB_LEDS)
    client.update()
    boards = [d for d in client.devices if d.type.name == "MOTHERBOARD"]

    audio = Audio()
    audio.start()
    peak, last_loud, hue = 0.02, 0.0, 0.0
    temp, temp_at = chip_temp(), 0.0
    beat = 0.0
    while True:
        now = time.time()
        level, bass = audio.level, audio.bass
        if level > MUSIC_ON:
            last_loud = now
        music = now - last_loud < QUIET_SECONDS
        if music:
            peak = max(level, peak * 0.995, 0.02)   # auto-gain: adapts to quiet songs and loud ones
            norm = level / peak
            beat = max(bass / max(peak, 1e-6) * 0.6, beat * 0.82)  # punchy attack, smooth fall
            hue += 0.0015 + 0.004 * norm
            for d in ram:
                d.set_colors(vu_meter(len(d.leds), norm), fast=True)
            pulse = hsv(hue, 1.0, 0.25 + 0.75 * min(1.0, beat))
            for b in boards:
                b.set_color(pulse, fast=True)
        else:
            if now - temp_at > 2:
                temp, temp_at = chip_temp(), now
            c = temp_color(temp, now)
            for d in ram + boards:
                d.set_color(c, fast=True)
        time.sleep(max(0.0, 1 / FPS - (time.time() - now)))


if __name__ == "__main__":
    main()
