# Reverse-engineering a Bluetooth LED helmet (so I can draw on my own head)

*Draft blog post — technical write-up of how I took control of an "SLShining" LED
bike helmet for a Burning Man art project.*

---

## The setup

I have a bike helmet with a small **48×12 RGB LED matrix** on it. It's sold as
"SLShining" and is driven by an Android app called **Shining Display**: you pick
animated patterns, flip the display, adjust brightness, and there's a "graffiti"
mode where you finger-paint pixels live. Cute — but I don't want to be tethered to
a phone app at the playa. I want to script it: push my own animations, react to
sensors, sync several helmets. So I set out to reverse-engineer the protocol.

Everything below was done against **hardware I own**, for interoperability. The
goal was never to attack anyone's infrastructure — just to talk to my own helmet.

## Step 1 — Capture the Bluetooth traffic

Android has a built-in **Bluetooth HCI snoop log**. Enable it in Developer Options,
do a representative session in the app (turn on/off, flip, pick a pattern, finger-
paint a bunch of white lines, turn off), then pull the bug report. I exported the
snoop log to JSON with `tshark` and ended up with ~1,600 BLE ATT packets.

A quick tally showed the shape of things:
- ~1,500 **ATT Write Commands** (`0x52`) — the phone talking to the helmet.
- A handful of **notifications** (`0x1b`) — the helmet talking back.
- Almost everything went to two GATT handles.

## Step 2 — Find the structure

Two characteristics carried all the action:
- A **write** characteristic (vendor service `0x00FA`, char `0xFA02`) — commands.
- A **notify** characteristic (`0xFA03`) — acknowledgements.

The small messages had an obvious framing once I lined them up:

```
[length] [0x00] [command] [sub] [args…]
```

For example `05 00 07 01 01` and `05 00 07 01 00` toggled in pairs — that's the
screen power on/off, and it matched exactly when I'd tapped the on/off button.
`05 00 06 80 00`, repeated a few times, lined up with my display flips.

Then the fun part. A cluster of 11-byte writes looked like this:

```
0b 00 05 01 00 ff ff ff 2e 00 2c
└┘ len        └ cmd     └RGB──┘ └X┘└Y┘└seq┘
```

`ff ff ff` is **white** — and I'd painted my graffiti in white. The next two bytes
walked 0…47 and 0…11. That's a **48×12 pixel grid** — the resolution of the
display. I was watching my own finger-painting, one pixel per packet. The last
byte was a rolling counter that only advanced on a genuinely new pixel (it repeated
when my finger lingered on the same spot).

## Step 3 — The helmet displays actual image files

The big packets (up to ~495 bytes) had a give-away signature: `47 49 46 38 37 61`
= **`GIF87a`**. The "predefined patterns" aren't a custom format — the app uploads
ordinary **GIF and PNG files** (48×12), fragmented across BLE writes and reassembled
on the device. I carved them straight out of the capture and rendered them: the
pattern I'd selected was an animated *two hearts + smiling mouth*. The graffiti
snapshots showed my white rows being painted in, then some color-fills.

So the protocol has two modes: **stream individual pixels** (graffiti) or **upload
a whole image/animation**. Each upload is prefixed with a small header containing
the file length and a **CRC32** checksum.

## Step 4 — The authentication wall (and why it didn't matter)

There was a second service, `0xAE00`, with a little handshake at connection time:
16-byte blobs going back and forth, and — amusingly — the literal ASCII string
**`pass`**. This looked like encryption, and I couldn't derive the key from the
capture alone. Time to look at the app.

### Getting the app

Since the app was installed on my phone, I pulled it straight off the device over
adb (no sketchy download sites needed):

```
adb shell pm path com.shiningdisplay.shiningdisplay
adb pull /data/app/.../base.apk
```

### Decompiling

The app is **React Native**, and the JS is compiled to **Hermes bytecode**
(`index.android.bundle`). I decompiled it with the open-source
[`hermes-dec`](https://github.com/P1sec/hermes-dec) and got readable pseudo-JS. The
command builders were all right there, named helpfully:

- `sendTool_syncTime` → `[0b 00 01 80 yy mm dd wd hh mm ss]` (so the frame I first
  guessed was a "hello" was actually setting the clock — `1a 06 09 …` = 2026-06-09).
- `sendTool_light` → `[05 00 04 80 brightness]`
- `sendTool_direction` → `[05 00 06 80 dir]` (flip)
- `sendTool_sendDiyCMD` → `[05 00 04 01 on]` (open/close the graffiti canvas)
- `sendTool_sendDiyData` → the draw-pixel frame, built via `hexToRGBA`
- `getSendData` → the image-upload header, with a textbook `CRC32_CCITT_FALSE`.

That confirmed the entire display protocol from the source, not just inference.

### The auth, solved

The native library was the tell: `libjl_ota_auth.so`, and a Java package
`com.jieli.jl_bt_ota`. **JieLi (杰理)** is a hugely common Chinese Bluetooth SoC
vendor, and this is their stock SDK. The auth is JieLi's **RCSP authentication** —
a challenge/response keyed by a 16-byte "link key", handled in native code
(`getRandomAuthData` / `getEncryptedAuthData` / `setLinkKey`). The `pass` string?
Just JieLi's hardcoded "auth OK" marker (`getAuthOkData()` literally returns
`{2, 'p','a','s','s'}`).

I decompiled the DEX with **jadx** to find what key the app installs… and the
punchline is: **it never calls `setLinkKey` at all.** It uses the JieLi native
default, and—critically—**the authentication only gates OTA firmware updates.** The
display service (`0x00FA`) doesn't check it.

So the entire crypto wall was irrelevant to my goal. The right move in
reverse-engineering is often to *test the assumption* rather than grind through the
hard path.

## Step 5 — Talking to the helmet for real

I wrote a tiny Python client with [`bleak`](https://github.com/hbldh/bleak)
(cross-platform BLE). Scan found `SCR-DEFC35` instantly. I connected, subscribed to
the notify characteristic, and—without any authentication—sent:

```python
FA02 = "0000fa02-0000-1000-8000-00805f9b34fb"
await c.write_gatt_char(FA02, bytes([5,0,7,1,1]), response=False)      # screen ON
await c.write_gatt_char(FA02, bytes([5,0,4,0x80,0xC0]), response=False) # brightness
await c.write_gatt_char(FA02, bytes([5,0,4,1,1]), response=False)       # graffiti open
# draw one white pixel at (x,y) with a rolling sequence byte:
await c.write_gatt_char(FA02, bytes([11,0,5,1,0, 255,255,255, x,y, seq]), response=False)
```

The helmet **acknowledged every command** with exactly the notification bytes I'd
seen in the original capture. I filled the whole 48×12 matrix pixel by pixel and
drew solid color bars. It works — full control, no app, no cloud, no auth.

## What I learned / takeaways

- **Capture first, decompile second.** Packet captures get you 80% of a protocol and
  tell you *what to look for* in the binary.
- **Length-prefixed TLV framing** (`[len][00][cmd][sub][args]`) is everywhere in
  cheap BLE gadgets. Once you spot it, the rest falls out.
- **Recognize the silicon.** `libjl_ota_auth.so` → JieLi → a known, documented SDK.
  Identifying the vendor SDK turned a scary crypto handshake into a footnote.
- **Test the security boundary before defeating it.** The auth looked essential; it
  guarded nothing I cared about.
- A mild security note for fellow makers: this display channel is **unauthenticated**,
  so anyone in BLE range can push frames to the helmet. Fun for art, worth knowing.

## Prior art — and why this is a different beast

Before publishing I went looking: had someone already done this? The answer is a
useful "yes, but for the cousin device." The same vendor — **Heaton** (the helmet's
cloud lives at `manage.heaton.com.cn`) — also makes the well-known **"Shining Mask"**,
the LED *face mask* you've seen at Halloween. That one has been thoroughly
reverse-engineered:

- [`GoneUp/mask-go`](https://github.com/GoneUp/mask-go) — Go controller
- [`shawnrancatore/shining-mask`](https://github.com/shawnrancatore/shining-mask) — CircuitPython + Wii Nunchuck
- [`adrihd/ShiningAppMask-ReverseEngineering`](https://github.com/adrihd/ShiningAppMask-ReverseEngineering)
- [a detailed protocol gist by Staars](https://gist.github.com/Staars/71e63e4bdefc7e3fd22377bf9c50ac12)
- even a [2025 article in *The Register*](https://www.theregister.com/2025/10/30/halloween_hacking_led_masks)

Here's the thing: **none of it applies to this helmet.** The mask and the helmet are
different products on different protocols, despite the shared vendor:

| | Public "Shining Mask" work | This "Shining Display" helmet |
|---|---|---|
| App | `cn.com.heaton.shiningmask` | `com.shiningdisplay.shiningdisplay` |
| Characteristics | 128-bit `d44bc439-…-92541612960x` | 16-bit `0x00FA` / `0xFA01–03` (+ JieLi `0xAE00`) |
| Encryption | **AES-128-ECB**, fixed published key | **none** on the display channel |
| Commands | ASCII-ish `DATS`/`IMAG`/`ANIM`/`LIGHT`/`REOK` | binary `[len,0,cmd,sub,…]` |
| Image upload | custom column bitmap, 16 px tall | **GIF/PNG files**, CRC32 header, **48×12** |
| Chipset | (not identified as JieLi) | **JieLi (杰理)** |

So the older mask wraps everything in AES with a key the community long ago
extracted; this newer helmet drops the AES on the display entirely and instead
leans on the JieLi stack — where the auth that *does* exist only guards firmware
updates, not the screen. I couldn't find any public write-up of *this* protocol
(JieLi `0x00FA` service, binary framing, GIF/PNG upload, 48×12). If you know of one,
I'd love to hear it — but as far as I can tell, this post is the first.

The one thing that *does* rhyme with other gear: cheap BLE LED panels in the
iDotMatrix / generic-sign family also use **chunked image upload with a CRC32**,
which is exactly what I found here. That upload design seems to be a shared trait of
this class of hardware, just never documented for the helmet.

## Protocol cheat-sheet

| What | Bytes (to char `0xFA02`, write-without-response) |
|---|---|
| Screen on / off | `05 00 07 01 01` / `05 00 07 01 00` |
| Brightness (0–255) | `05 00 04 80 BB` |
| Flip / rotate | `05 00 06 80 DIR` |
| Graffiti mode open / close | `05 00 04 01 01` / `05 00 04 01 00` |
| Draw pixel | `0b 00 05 01 00 RR GG BB XX YY SEQ` (X 0–47, Y 0–11) |
| Sync clock | `0b 00 01 80 YY MON DAY WD HH MM SS` |
| Image upload | `[len4][crc32-4][idx2][type1]` header + GIF/PNG (48×12) |

Display: **48×12 RGB**, service `0x00FA` (write `0xFA02`, notify `0xFA03`).
Auth on `0xAE00` is JieLi RCSP — only needed for firmware, not the display.

*Next up: a clean driver library, the image/animation upload path, and syncing a
few of these across a group of bikes. See you in the dust.*
