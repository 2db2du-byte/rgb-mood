# rgb-mood 🦝 lights that listen

Your PC's RGB lights, but with a pulse. Two moods, picked automatically:

- **Music playing:** the ARGB lights thump with the bass of whatever comes out of your speakers. Spotify, YouTube,
  a game, your neighbour's opinion of your playlist. The colour drifts slowly around the rainbow.
- **Quiet for a few seconds:** they glow by the hottest chip (CPU or GPU). Blue when cool (40 °C and under),
  purple when it's working, red when it's cooking (85 °C and up). It breathes faster as it gets hotter.
- **RAM:** stays one solid colour (default blue), or flip `RAM_VU = True` and it becomes a VU meter.

It starts when you say so and stops when you say so. **Nothing starts at boot.**

## How it works

- **Hearing:** `pw-record` grabs the monitor of your default speakers (PipeWire), 30 times a second. numpy does an
  FFT and pulls out the bass (20-160 Hz). Auto-gain, so quiet songs and loud ones both get a show.
- **Temperature:** `k10temp` from `/sys/class/hwmon` (AMD CPUs) and `nvidia-smi` (NVIDIA cards).
- **Lights:** the [OpenRGB](https://openrgb.org) SDK server on 127.0.0.1, driven by `openrgb-python`.

## Honest status

Tested on my own rig: it hears the audio and drives the **motherboard ARGB headers and the RAM** through OpenRGB.
My case fans aren't wired to the motherboard's ARGB header yet (they hang off the case's own RGB controller),
so the full-case demo is coming. If your fans already plug into the motherboard ARGB header, you're ahead of me.

## Setup (Linux with PipeWire)

```bash
sudo apt install openrgb pipewire-bin          # pw-record comes with PipeWire
mkdir -p ~/AI/apps/rgb-mood && cp rgb_mood.py ~/AI/apps/rgb-mood/
python3 -m venv ~/AI/apps/rgb-mood/.venv
~/AI/apps/rgb-mood/.venv/bin/pip install -r requirements.txt
cp rgb-mood ~/.local/bin/ && chmod +x ~/.local/bin/rgb-mood
```

OpenRGB needs permission to talk to your RAM and motherboard (its udev rules, and `i2c-dev` for RAM).
See the OpenRGB docs for your board.

```bash
rgb-mood on       # start the OpenRGB server + the light show (until reboot or `off`)
rgb-mood off      # stop; motherboard goes back to its own rainbow
rgb-mood status
```

Knobs live at the top of `rgb_mood.py`: `ARGB_LEDS`, `MUSIC_ON` (how loud counts as music), `COOL` / `HOT`,
`RAM_VU`, `RAM_BLUE`.

One GPU. Zero dollars. Zero excuses. All free: OpenRGB, PipeWire, Python, numpy.

## License

MIT. Built by Rabbid Raccoon with Claude. Use it, change it, share it.
