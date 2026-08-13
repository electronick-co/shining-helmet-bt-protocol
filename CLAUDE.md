# CLAUDE.md — SLShining helmet BLE reverse-engineering

Project notes for working in this folder. For the full wire-protocol spec see
**`PROTOCOL.md`**; this file is the operational/orientation doc.

## What this is
Reverse-engineering the Bluetooth LE control of an **SLShining** bike helmet that
has a **48×12 RGB LED matrix** display, normally driven by the Android app
**"Shining Display"** (`com.shiningdisplay.shiningdisplay`). Part of the
*BurningManHelmet26* art project. Goal: control the helmet directly from our own
code instead of the vendor app.

**Status: achieved.** We can drive the display (power, brightness, flip, per-pixel
graffiti draw, clock) directly from Python over BLE, with no authentication needed.

## Key findings (TL;DR)
- Transport: BLE GATT. Two vendor services:
  - **`0x00FA`** = display/control. Write to char **`0xFA02`** (write-no-response),
    notifications/acks on **`0xFA03`**.
  - **`0xAE00`** = JieLi auth (`0xAE01` write / `0xAE02` notify).
- Device: `SCR-DEFC35`, BD_ADDR `92:33:6F:DE:FC:35`.
- App stack: **React Native (Hermes)**; SoC: **JieLi (杰理)**; cloud vendor: **Heaton**.
- **Auth (`com.jieli.jl_bt_ota` `RcspAuth`) only gates OTA firmware updates — NOT the
  display channel.** The app never sets a custom link key (uses the JieLi native
  default), and `"pass"` is just JieLi's hardcoded auth-OK marker. We never needed it:
  the `0x00FA` channel accepts commands unauthenticated. Confirmed live on the helmet.
- Control framing: `[len, 0x00, cmd, sub, args…]`. Draw pixel =
  `0b 00 05 01 00 RR GG BB XX YY SEQ` (X 0–47, Y 0–11, SEQ = rolling counter).
  Image upload = GIF/PNG (48×12) with a 12-byte header incl. CRC32. See PROTOCOL.md.

## File layout
```
test1_bluetoothdebug_helmet.json   # original Android HCI snoop capture (tshark JSON)
PROTOCOL.md                        # full protocol spec (authoritative)
CLAUDE.md                          # this file
BLOG.md                            # public blog-post draft

parse_protocol.py                  # capture -> annotated timeline (decoded/timeline.txt)
extract_images.py                  # carve uploaded GIF/PNG frames from the capture
decoded/                           # carved images + rendered previews

ble_scan.py                        # scan for the helmet
ble_probe.py                       # connect, enumerate GATT, send test commands
ble_fill.py                        # fill screen cycling R/G/B/W (per-pixel)
ble_bars.py                        # draw 3 vertical bars R|G|B
ble_off.py                         # turn the screen off

apk/                               # pulled app + RE artifacts (see below)
tools/                             # portable JDK + jadx (decompiler)
```

### apk/ artifacts
```
shiningdisplay_base.apk            # the app (pulled via adb from the phone)
shiningdisplay_arm64.apk           # native libs split
shineapp_base.apk                  # a second related app (unused)
extracted/index.android.bundle     # Hermes bytecode (RN JS bundle)
extracted/decompiled.js            # decompiled JS (hermes-dec) — protocol builders
                                   #   live ~lines 254000-256000 (sendTool_*, getSendData,
                                   #   cmdIndexCount, CRC32_CCITT_FALSE)
extracted/libjl_ota_auth.so        # JieLi auth native lib
extracted/dex/classes*.dex         # Java/Kotlin DEX
jadx_out/sources/                  # jadx-decompiled Java (com.jieli.jl_bt_ota, etc.)
```

## Environment / setup
- **Python 3** with `bleak` (BLE), `pillow` (image rendering): `pip install bleak pillow`
- **adb** (Google platform-tools) — already on PATH; phone was connected via USB.
- **Hermes decompiler**: `pip install hermes-dec` → `hbc-decompiler <bundle> out.js`
- **APK decompiler**: portable Temurin JRE 21 + jadx in `tools/` (no admin install).
  Run: `set JAVA_HOME=...\tools\jdk\jdk-21...-jre & tools\jadx\bin\jadx.bat -d out app.apk`

## How to drive the helmet (quick start)
1. `python ble_scan.py` → confirm `SCR-DEFC35` is advertising.
2. `python ble_probe.py` → connect, dump GATT, send sanity commands, watch acks.
3. `python ble_bars.py` / `ble_fill.py` → visible patterns.
4. `python ble_off.py` → screen off.

Write characteristic = `0000fa02-0000-1000-8000-00805f9b34fb`, write **without
response**. Subscribe to `0000fa03-...` for acks. Commands (bytes):
- screen on/off: `05 00 07 01 01` / `...00`
- brightness:    `05 00 04 80 <0..255>`
- flip:          `05 00 06 80 <dir>`
- graffiti mode: `05 00 04 01 01` (open) / `...00` (close)
- draw pixel:    `0b 00 05 01 00 RR GG BB XX YY SEQ`
- sync time:     `0b 00 01 80 yy mon day weekday hh mm ss`

## Safety / etiquette notes
- This is our own device; RE was for interoperability with hardware we own.
- The display channel is unauthenticated — anyone in BLE range can drive it. Keep
  that in mind for the Burning Man deployment (others could push frames).
- Don't attempt OTA/firmware writes blindly — that path *is* JieLi-auth gated and
  bricking risk is real.

## Status & next steps
- **Protocol RE is COMPLETE (2026-06-10).** Library `shining_helmet/` does
  everything: stills + **animated GIFs** (multi-block upload with ack gating),
  **live streaming ~7.7 fps** via the type-00 screencast path, brightness/flip/
  reset, all live-verified. 11/11 tests pass.
- Notable: the vendor app's own animated-GIF upload is broken (MTU off-by-3
  chunking bug) — our implementation is the only working uploader for this device.
- **To resume work, read `NEXT_SESSION.md`** — remaining items are product work
  (Burning Man show controller), not RE. `VERIFY.md` has the full verified list.
