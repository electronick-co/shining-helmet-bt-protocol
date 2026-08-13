# shining-helmet

Control SLShining / **"Shining Display"** BLE LED-matrix helmets (48×12 RGB) from
Python — no vendor app, no cloud, no auth. Cross-platform via
[`bleak`](https://github.com/hbldh/bleak): works on **PC (Windows/macOS)** and
**Raspberry Pi / Linux (BlueZ)**.

> Status: **early draft (0.1.0)**. Core display commands are verified on hardware;
> the bulk image-upload path is decoded but not yet validated — see
> [`VERIFY.md`](VERIFY.md). Protocol details in [`PROTOCOL.md`](PROTOCOL.md).

## Install
```bash
pip install -e ".[images]"     # editable, with Pillow for image support
# or, once published:  pip install shining-helmet[images]
```

### Raspberry Pi notes
- Needs BlueZ (`sudo apt install bluetooth bluez`) and the `bluetooth` service running.
- First run may need elevated perms; add your user to the `bluetooth` group to avoid sudo.
- A Pi Zero 2 W / 3 / 4 onboard radio is fine for BLE.

## Quick start
```python
import asyncio
from shining_helmet import ShiningHelmet

async def main():
    async with ShiningHelmet() as h:        # auto-discovers by name prefix "SCR-"
        await h.sync_time()
        await h.power(True)
        await h.set_brightness(0xC0)
        await h.draw_image("logo.png")      # verified per-pixel path
asyncio.run(main())

asyncio.run(main())
```

## CLI
```bash
shining-helmet scan
shining-helmet on
shining-helmet brightness 200
shining-helmet flip 0
shining-helmet image logo.png
shining-helmet off
```

## Layout
- `shining_helmet/protocol.py` — pure frame builders (no I/O, unit-tested)
- `shining_helmet/client.py` — async BLE client (`ShiningHelmet`)
- `shining_helmet/images.py` — image → pixels / upload bytes (needs Pillow)
- `shining_helmet/auth.py` — JieLi RCSP auth stub (only needed for OTA)
- `shining_helmet/cli.py` — `shining-helmet` command
- `VERIFY.md` — what's confirmed vs. open (every open item has a `TODO(verify:…)` tag)

## Safety
This display channel is unauthenticated — anyone in BLE range can drive the panel.
Don't attempt OTA/firmware writes without a confirmed, recoverable flow.
