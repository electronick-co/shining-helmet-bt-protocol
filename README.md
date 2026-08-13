# shining-helmet

Drive **SLShining** BLE LED-matrix helmets (48×12 RGB, the "Shining Display" app)
from Python — no vendor app, no cloud account, no pairing dance. Cross-platform
via [`bleak`](https://github.com/hbldh/bleak): Windows, macOS, and Linux/BlueZ
including Raspberry Pi.

```python
import asyncio
from shining_helmet import ShiningHelmet

async def main():
    async with ShiningHelmet() as h:        # auto-discovers by name prefix "SCR-"
        await h.power(True)
        await h.set_brightness(0xA0)
        await h.show_image("logo.png")      # stored, survives disconnect

asyncio.run(main())
```

This repo is both the library and the write-up of the reverse-engineering that
produced it. The full wire protocol is documented in
[PROTOCOL.md](https://github.com/electronick-co/shining-helmet-bt-protocol/blob/main/PROTOCOL.md);
what is confirmed on real hardware versus still open is tracked in
[VERIFY.md](https://github.com/electronick-co/shining-helmet-bt-protocol/blob/main/VERIFY.md).

## Install

```bash
pip install "shining-helmet[images]"    # images extra pulls in Pillow
pip install shining-helmet              # core only: control commands, no image support
pip install "shining-helmet[video]"     # adds imageio for MP4/MOV playback
```

Python 3.11+.

## What it can do

Everything below is verified against a real helmet (`SCR-DEFC35`).

| | |
|---|---|
| **Control** | power, brightness, 180° flip, clock sync, factory reset |
| **Still images** | any image → 48×12, uploaded and stored on the device |
| **Animated GIFs** | multi-block upload with ack gating, up to 40960 bytes |
| **Live streaming** | ~8 fps full-frame video via the screencast path |
| **Per-pixel drawing** | direct pixel writes on the live canvas |

### Display an image or animation (persistent)

`show_image` accepts a path or a `PIL.Image`, resizes to 48×12, encodes as GIF
and uploads it. It persists across disconnect and power-cycle, so this is what
you want for content the helmet should just keep playing.

```python
await h.show_image("sunset.png")        # still
await h.show_image("rainbow.gif")       # animated — all frames kept
```

The device stores at most **40960 bytes** (ten 4096-byte blocks). Upload runs at
roughly 2.4 KB/s, so a full-size file takes about 16 seconds.
`upload_bytes` raises `ValueError` before sending anything if you exceed it.

### Live streaming

Open the graffiti canvas and push frames. Ephemeral — the stored GIF returns
when you close it.

```python
from shining_helmet import images

frames = images.scroll_frames("BURNING MAN 2026", color=(0, 255, 180))
await h.stream(frames, fps=12)          # generators stream lazily
```

Throughput is bounded by **PNG size ÷ MTU** (one BLE write per ~509 bytes), not
by the device ack — so frame content, not the protocol, sets your frame rate.
Measured on hardware: sparse frames (text, sparkle) reach 8–11 fps, dense
full-color frames (plasma) around 7 fps.

`screencast(frame)` pushes a single frame. Both take `colors=`: the default
(`None`) keeps full color and quantizes only as much as needed to stay at one
write per frame, which is the right choice almost always. Forcing `colors=8` can
*backfire* on smooth gradients, where dithering makes the PNG larger than the
true-color original.

`stream` only materializes its input when `loops > 1`, so an endless generator
(a live effect, an audio-reactive source) streams forever rather than hanging.

### Frame helpers

`shining_helmet.images` renders content sized for a 12-pixel-tall panel:

- `text_frame(text)` / `fit_text_frame(text)` — centered text, the latter sized as large as fits
- `scroll_frames(text)` — a marquee generator
- `iter_video_frames(src)` — animated GIF/WebP/APNG frames
- `iter_mp4_frames(path)` — MP4/MOV (needs the `video` extra)
- `encode_gif_sequence(frames)` — generated frames → one animated GIF for upload

Text is rendered **thresholded**, not antialiased: grey edge pixels are
unreadable at this size.

### Per-pixel drawing

```python
await h.graffiti(True)
await h.draw_pixel(10, 5, (255, 0, 0))
await h.graffiti(False)
```

Slow (~13 s for a full frame) and ephemeral — use it for live doodling, not for
displaying content.

## CLI

```bash
shining-helmet scan
shining-helmet on
shining-helmet brightness 200
shining-helmet image logo.png
shining-helmet off
```

## Raspberry Pi

- Needs BlueZ: `sudo apt install bluetooth bluez`, service running.
- Add your user to the `bluetooth` group to avoid running as root.
- A Pi Zero 2 W / 3 / 4 onboard radio is fine for BLE.
- Raspberry Pi OS Bookworm ships Python 3.11, which meets the floor.

## Gotchas worth knowing

- **Uploads must be GIF.** A PNG upload is acked but displays blank. `show_image`
  handles this; only `upload_bytes` lets you get it wrong.
- **Writes must be acknowledged.** Write-without-response silently drops frames
  and pixels. The client uses `response=True` everywhere.
- **Brightness saturates.** 0–4 are an identical readable floor (the panel never
  goes fully dark — use `power(False)`), and ~192–255 are indistinguishable.
  Useful range is roughly 8–192.
- **Flip is binary.** 0 is normal, any nonzero value is 180°. No mirror modes.
- **The display channel is unauthenticated** — see Security below.

## How it works

BLE GATT, two vendor services. Display and control live on `0x00FA`: write
commands to `0xFA02`, acks arrive as notifications on `0xFA03`. Frames are
`[len, 0x00, cmd, sub, args…]`.

The `0xAE00` service is JieLi RCSP authentication, and it gates **only OTA
firmware updates** — not the display. No authentication is needed for anything
this library does.

The protocol was recovered from an Android HCI snoop capture cross-referenced
against the vendor app's decompiled Hermes bytecode. The capture is included as
[`test1_bluetoothdebug_helmet.json`](https://github.com/electronick-co/shining-helmet-bt-protocol/blob/main/test1_bluetoothdebug_helmet.json)
so the findings are independently checkable; `parse_protocol.py` turns it into an
annotated timeline.

One finding worth flagging: **the vendor app's own animated-GIF upload is
broken.** It chunks block writes at the negotiated MTU instead of MTU−3, losing
three bytes per chunk and corrupting every multi-block transfer. As far as we can
tell this library is the only working animated-GIF uploader for these devices.

## Security

The display channel accepts commands from anyone in BLE range, with no pairing
or authentication. Anyone nearby can drive your panel. That is a property of the
device, not of this library — plan for it if you are wearing one somewhere
crowded.

Do not attempt OTA or firmware writes. That path *is* authentication-gated, it is
not implemented here, and the bricking risk is real.

## Repo layout

```
shining_helmet/       the library
examples/             live effects, text, slideshow, video, showcase
tests/                protocol + encoder tests (no hardware needed)
PROTOCOL.md           full wire-protocol spec
VERIFY.md             what is hardware-confirmed vs open
BLOG.md               write-up draft
parse_protocol.py     capture -> annotated timeline
extract_images.py     carve uploaded frames out of the capture
decoded/              carved images + rendered previews
```

## Legal

Reverse-engineered for interoperability with hardware we own. No vendor code,
binaries, or assets are redistributed here — the APKs, their decompilation, and
`libjl_ota_auth.so` are deliberately excluded from this repository. Findings are
documented in prose and reimplemented from scratch.

Not affiliated with or endorsed by SLShining, Heaton, or JieLi.

## License

MIT — see [LICENSE](https://github.com/electronick-co/shining-helmet-bt-protocol/blob/main/LICENSE).
