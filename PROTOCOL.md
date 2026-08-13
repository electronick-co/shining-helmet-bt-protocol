# SLShining / "Shining Display" helmet — BLE protocol (reverse-engineered)

Source: `test1_bluetoothdebug_helmet.json` (tshark JSON export of an Android HCI
snoop log). Device `SCR-DEFC35` (BD_ADDR `92:33:6f:de:fc:35`), phone = Motorola
Razr 2025. All traffic is BLE **ATT**; nothing is at the link layer that matters.

Display is a **48 × 12 RGB LED matrix** (0x30 × 0x0c) — confirmed both by the GIF
logical-screen descriptor and by every uploaded PNG being 48×12.

---

## 1. GATT layout

Two vendor services. Handles are from this capture (re-discover at runtime; use
the UUIDs as the stable key).

| Service | Char UUID | Handle | Properties | Role |
|---|---|---|---|---|
| **0x00FA** (data/control) | **0xFA01** | `0x0006` | Write / WriteNoResp | **commands + image uploads (phone → helmet)** |
| 0x00FA | 0xFA02 | `0x0008` | — | (has 0x2901 user-desc) |
| 0x00FA | **0xFA03** | `0x0009` | Notify (CCCD `0x000a`) | **status / acks (helmet → phone)** |
| **0xAE00** (auth) | **0xAE01** | `0x0082` | Write | **auth challenge (phone → helmet)** |
| 0xAE00 | **0xAE02** | `0x0084` | Notify (CCCD `0x0085`) | **auth response (helmet → phone)** |

Connection bring-up: enable notifications on `0xFA03` and `0xAE02` (write `0x0001`
to their CCCDs), run the auth handshake on the AE service, then drive everything
else over `0xFA01` / `0xFA03`.

---

> **UPDATE — confirmed from the app source.** The `Shining Display` app
> (`com.shiningdisplay.shiningdisplay`) is a **React Native / Hermes** app. The
> JS bundle was decompiled and the protocol below is now verified against the
> app's own command builders (`sendTool_*`). Cloud/API vendor is **Heaton**
> (`manage.heaton.com.cn`). The BLE chipset is **JieLi (杰理)** — the native lib
> `libjl_ota_auth.so` + Java package `com.jieli.jl_bt_ota` (class `RcspAuth`)
> handle the auth. See §2 and §7.

## 2. Authentication handshake (service 0xAE00) — JieLi RCSP auth

Short, typed messages. Byte 0 is a **type tag**; the 16-byte blobs look like an
AES-ECB challenge/response with a fixed app key (typical of these LED-matrix
products). The literal token `"pass"` is sent **both directions** as the
confirmation step.

```
phone → AE01:  00 c9e9436b91afb363e8a1fc83ffe743af      type00 + 16B challenge
helmet→ AE02:  01 e46df90fbb0d11f64609d1f11c9b8466      type01 + 16B response
phone → AE01:  02 70 61 73 73                            type02 + "pass"
helmet→ AE02:  00 d34964ba118e0970f325e7c451560f8d      type00 + 16B
phone → AE01:  01 25b4bda4e89ab42aa250a5708a627362      type01 + 16B
helmet→ AE02:  02 70 61 73 73                            type02 + "pass"   (auth OK)
phone → AE01:  fedcba c0 0300 0637 ffffffff 00 ef        "fedcba" framed cmd
helmet→ AE02:  fedcba 00 0300 3e00 37 02 00 20 05 ...    framed reply, embeds the
                                                          device MAC 92:33:6f:de:fc:35
```

**This is JieLi's standard RCSP authentication**, not a custom scheme:
- Native lib `lib/arm64-v8a/libjl_ota_auth.so` exports JNI methods on
  `com.jieli.jl_bt_ota.impl.RcspAuth`:
  - `getRandomAuthData()` → the `00 + 16B` random the phone sends (challenge).
  - `getEncryptedAuthData([B)[B` → encrypts data with the **link key** (the crypto
    is inside the native lib).
  - `setLinkKey([B)I` → installs the 16-byte link key used by the cipher.
- The handshake is a two-way **challenge/response keyed by the 16-byte link key**,
  so it **cannot be replayed** (the random changes every session). To talk to the
  helmet you must reproduce the JieLi auth with the correct key. `0xAE00`/`0xAE01`/
  `0xAE02` are JieLi's stock BLE service/char UUIDs.
- `fe dc ba …` is the **JieLi RCSP packet framing** (sync `0xFEDCBA`), used for the
  first post-auth command (it carried the device MAC back).
- **Easiest path to auth:** reuse JieLi's own `jl_bt_ota` SDK (the whole thing is
  bundled in the APK) or its open-source equivalents — it performs `RcspAuth`
  automatically. If the app never calls `setLinkKey` with a custom value, the SDK
  default key is used and any JieLi-SDK client authenticates.
- **To extract the exact link key:** decompile the DEX with jadx and read the
  caller of `RcspAuth`/`setLinkKey` (it's a smali `byte[]` literal, not a string,
  so `strings` won't surface it), or disassemble `getEncryptedAuthData` in the
  arm64 `.so`. The LED data channel (0x00FA) itself is **not encrypted** — once
  auth passes, the §3/§4 commands are plaintext.

---

## 3. Control frame format (service 0x00FA)

All small commands on `0xFA01` (write) and the status notifications on `0xFA03`
share one framing:

```
[len:1] [0x00] [cmd:1] [arg bytes ...]
   └ len = total frame length, including this byte
```

### Commands (phone → write char) — verified from `sendTool_*` builders

Builder source: `assets/index.android.bundle` (Hermes), methods on the BLE tool class.

| builder | bytes | meaning |
|---|---|---|
| `sendTool_syncTime` | `[0b,00,01,80, yy,mon,day,week,hr,min,sec]` | **set clock**. Capture `0b0001801a060902110109` = 2026(`1a`)-06-09, 17:01:09. (This is what I first mislabeled "HELLO".) |
| `sendTool_reset` | `[04,00,03,80]` | **reset** |
| `sendTool_light` | `[05,00,04,80, brightness]` | **brightness** (cmd `04`, sub `0x80`) |
| `sendTool_sendDiyCMD` | `[05,00,04,01, on]` | **graffiti canvas open(`1`)/close(`0`)** (cmd `04`, sub `01`) — logged "diy画布命令". Brackets the drawing session. |
| `sendTool_direction` | `[05,00,06,80, dir]` | **flip / rotate** — capture `0500068000` |
| `sendTool_sendDiyData` | `[0b,00,05,01, a1, RR,GG,BB, X, Y, seq]` | **draw one pixel** (see below) — logged "sendDiyData" |
| `sendTool_level` | `[lenLo,lenHi, cmd,sub, a1, ...data]` | variable-length cmd, **2-byte LE length** header |

General framing = `[len, 0x00, cmd, sub, args...]` (`len` is the low byte; the
variable-length builder uses a 2-byte LE length). `0x07` (`05 00 07 01 vv`) seen
toggling on/off in the capture is the **screen on/off**, but I did not pin its
exact builder in the bundle — confirm by testing `vv`=`01`/`00`.

Correlation with the test session (relative seconds):
- `1535–1541` six `cmd07` toggles → *"turned on and off several times"*.
- `1583–1590` four `cmd06 80` → *"flipped the display"*.
- `1647` GIF + `1687` PNG upload → *"selected predefined patterns"* (pushes the
  image to the helmet). The predefined one decoded to an animated 3-frame
  "two hearts + smiling mouth".
- `1740` `cmd04 01 01` … draw pixels … `1836` `cmd04 01 00` → the **graffiti
  session** (mode enter → strokes → exit).
- `1842` `cmd07 01 00` → *"turned off again"*.

### Draw-pixel command (cmd 0x05)

```
0b 00 05 01 00 | RR GG BB | XX | YY | SS
 │  │  │  │  │    └color    │    │    └ rolling point counter (low 8 bits;
 │  │  │  │  └ 0x00 (fixed) │    │      +1 per new point, repeats if the same
 │  │  │  └ 0x01 (fixed; pixel/brush mode?)  point is re-sent — finger drag)
 │  │  └ cmd = draw          │    └ YY = row    0..0x0b  (0–11)
 │  └ 0x00                   └ XX = column 0..0x2f  (0–47)
 └ len = 11
```

- `RR GG BB` = 24-bit color. Seen: `ffffff` white (the white finger-painting),
  plus `ff0000`/`ffa200`/`ffff00`/`00ff00`/`0000ff`/`ff00ff` (red/orange/yellow/
  green/blue/magenta color tests at the end of the session).
- `SS` is a sequence counter, not a checksum (verified: it equals the pixel index,
  holds steady on repeated points, and is not any sum/xor of the frame). The device
  almost certainly tolerates any value here.

While drawing, the app *also* periodically uploads a full-canvas **48×12 PNG**
snapshot over `0xFA01` (see §4) — so the helmet is kept in sync both per-pixel and
per-frame. You can drive the display with **either** mechanism alone.

### Status notifications (helmet → 0xFA03)

Same framing, echoed back as acks/status:

| bytes | meaning |
|---|---|
| `05 00 07 01 01` | power state = on (ack of cmd07) |
| `05 00 06 80 01` | flip ack |
| `05 00 04 01 01` | draw-mode ack |
| `05 00 tt 00 ss` | **upload status** — see below |
| `0b 00 01 80 01 04 01 17 02 00 01` | reply to HELLO — version/info |

**Upload status notifications** (decoded from the app's `responseObj` enum and
VERIFIED live during multi-block upload): `05 00 <type:2 LE> <status>`, where
`type` echoes the upload header's content-type byte (0 = screencast, 1 = GIF,
2 = picture) and `status` is:

| status | name | meaning |
|---|---|---|
| 0 | Error | CRC mismatch / bad data → resend current block |
| 1 | **Able/READY** | block received → send the next block |
| 2 | SpaceError | device storage full → abort |
| 3 | **SaveSuccess** | whole file received & stored (final ack) |
| 4 | TimeOut | device-side timeout |

So `05 00 01 00 01` = "GIF block received, continue", `05 00 01 00 03` = "GIF
saved". The previously-mysterious "periodic" `05 00 02 00 03` was simply the
SaveSuccess ack for type-2 (picture/PNG) uploads.

---

## 4. Image upload (service 0x00FA, char 0xFA01)

The app uploads a complete image (PNG or GIF) for predefined patterns and for
canvas snapshots. The file is fragmented across multiple ATT writes (≤495 B each,
i.e. ATT_MTU-limited) and the helmet reassembles by length. Each upload ends with
a `05 00 00 00 01` ACK on 0xFA03.

**Header — VERIFIED byte-for-byte against the capture AND live, 16 bytes per block:**

```
[total:2 LE] [type] 00 [flag:1] [file_len:4 LE] [crc32:4 LE] [idx:2 LE] [ftype:1] | <payload>
   total       = byte count of THIS block message = 16 + this block's payload
   type        = content type: 0x01 GIF (display content), 0x02 picture (PNG asset)
   flag        = 0x00 first block, 0x02 continuation blocks
   file_len    = length of the WHOLE file (repeated in every block header)
   crc32       = standard CRC-32 (poly 0xEDB88320, == zlib.crc32) over the WHOLE file, LE
   idx, ftype  = 0 in all captures (meaning TODO:upload-idx-type)
```
Example (capture frame 4364, a 321-byte GIF): header
`51 01 01 00 00 41 01 00 00 6f 0e da 59 00 00 00` then `GIF87a…`. Reproduced exactly
by `protocol.upload_header(321, 0x59da0e6f, total_packet_len=337)`.

**Multi-block transfer — VERIFIED LIVE 2026-06-10** (decoded from the app's
`getSendData`/`sendWithData`, implemented in `protocol.upload_blocks` +
`client.upload_bytes`):

1. Cut the file into **4096-byte blocks**; each block gets its own 16-byte header
   (so a full block message is 4112 bytes — the `0x1010` seen in the capture).
2. Write each block in ≤(ATT_MTU−3) slices to `0xFA02`; slices after the header
   carry raw file bytes (no per-slice framing).
3. After each block, **wait for `05 00 <type> 00 01`** (READY) before sending the
   next. After the last block the helmet sends **`05 00 <type> 00 03`**
   (SaveSuccess). Status 0 = resend block, 2 = storage full.

Live result: an 11 KB / 3-block animated GIF uploaded with READY acks after
blocks 1–2 and SaveSuccess after block 3; the panel plays the animation.

> **Why the vendor app couldn't do this:** in the capture, every multi-block
> attempt stalls and retries — the app cut its chunks at ATT_MTU (498) instead of
> ATT_MTU−3 (495), so the BLE stack silently truncated 3 bytes per full chunk
> (24 bytes per block). The helmet kept waiting for the missing bytes and never
> acked. Animated-GIF upload from the official app was simply broken; the
> protocol itself works fine.

**Format MUST be GIF.** VERIFIED live: a GIF upload renders and **persists**; an
identically-framed PNG upload is *accepted* (acked `05 00 01 00 03`) but the
panel shows **blank**. A 48×12 GIF is ~110–330 B per frame → stills fit in one
block; animations span several.

#### Max stored file = 40960 bytes — VERIFIED LIVE 2026-07-25 (by bisection)

The device stores a file of **at most `40960` B = 10 × 4096-byte blocks**
(`constants.MAX_UPLOAD_BYTES`). Bisected with zero-padded GIFs (a decoder ignores
bytes after the `0x3B` trailer, so padding probes the length check without
changing content):

| file_len | result |
|---|---|
| 36864, 38912, **40960** | uploads, `SaveSuccess` |
| **40961** and up | **rejected at block 1** with status **0** |

Notes:
- Rejection is **status 0 (Error), not 2 (SpaceError)**, and it comes back
  *before any payload is stored* — the helmet pre-checks the `file_len` declared
  in the first block header, then NAKs every retry. `upload_bytes` now fails fast
  on oversize input instead of burning three retries.
- It is a **byte cap, not a frame cap**: a 600-frame animation at 22 KB stores
  and plays; 1200 frames failed only because it encoded to 44.6 KB. A 288-frame
  / 40750 B show uploaded fine.
- **Upload throughput ≈ 2.4 KB/s** (acked writes, 480-byte slices), so a
  cap-filling 40 KB file takes ~16 s to transfer.
- Per-frame GIF delays are preserved in the stored file (durations 100–2500 ms in
  one 40750 B upload) — TODO(verify:gif-frame-delays) whether the panel honors
  variable delays or re-times every frame equally.

### Type-00 "screencast" (投屏) — live frame push, VERIFIED LIVE 2026-06-10

A separate, lighter path (app: `sendTool_toupingWithData`) used for streaming the
graffiti canvas. 9-byte header, **PNG** payload, no CRC:

```
[total:2 LE = len+9] 00 00 00 [len:4 LE] | <48×12 PNG>
```

Ack: `05 00 00 00 01` (~130 ms after the frame). Behavior:
- renders **instantly**; with graffiti mode OPEN the frame persists until the
  next one; with graffiti CLOSED it shows ~0.5 s and the stored animation resumes
- ack-gated streaming sustains **~7.7 fps** → this is the live-animation path:
  `graffiti(True)`, then `client.screencast(frame)` per frame
- ephemeral: never written to storage (disconnect/close → stored GIF returns)
- **PNG must be true-color (RGB).** VERIFIED live: an indexed/palette-mode
  (PNG color type 3) frame is accepted but renders BLANK; the same image as RGB
  renders fine. So to shrink a frame, reduce distinct colors but keep RGB mode
  (`images.encode_png` quantizes then converts back to RGB).
- **throughput is bounded by PNG size ÷ MTU**, not the ack: one BLE write per
  ~(MTU−3) bytes. A dense full-color frame ≈1 KB (2-3 writes ≈5 fps); reduced to
  ≈470 B it's one write ≈11-12 fps. `images.encode_png_fit` reduces colors only
  as much as needed to keep a frame at one write.

> Display behavior: the panel reverts to its stored default animation when the BLE
> link drops or graffiti mode closes. A `show_image` GIF upload sets the persistent
> displayed image; per-pixel graffiti draws are live-only.
>
> Per-pixel draws must use **acknowledged writes** (ATT Write Request). Fire-and-
> forget write-without-response overruns the device and drops most pixels.

---

## 5. What you can do right now (no crypto needed for the data channel)

1. Connect, subscribe to `0xFA03` and `0xAE02` notifications.
2. Run the AE handshake. If a clean replay of the captured `0x0082` writes is
   rejected (challenges are likely nonce/AES based), you must recover the AES key
   from the app APK. Capture suggests `"pass"` is the shared token.
3. Power on:  write `05 00 07 01 01` to `0xFA01`.
4. Show an image: upload a 48×12 PNG with the 9-byte header to `0xFA01`.
5. Live draw: `05 00 04 01 01` (enter), then stream
   `0b 00 05 01 00 RRGGBB XX YY SS` per pixel, then `05 00 04 01 00` (exit).
6. Flip: `05 00 06 80 00`.  Power off: `05 00 07 01 00`.

## 6. Open items / to finish offline
- **JieLi link key** for the 0xAE00 RCSP auth. Get it by decompiling the DEX with
  jadx (read the `RcspAuth`/`setLinkKey` caller — it's a smali `byte[]`), or by
  disassembling `getEncryptedAuthData` in `libjl_ota_auth.so`. Alternatively skip
  RE and drive auth with the bundled JieLi `jl_bt_ota` SDK.
- Exact builder for the `0x07` screen on/off command (behaviorally confirmed).
- `sendTool_direction` arg values for each rotation/mirror state (only `0x00` seen).
- Meaning of periodic `05 00 0x 00 03` status frames (battery? brightness?).

## 7. Tooling / artifacts pulled from the device
- `apk/shiningdisplay_base.apk` (+ `_arm64.apk` native split) — the app, pulled via
  adb from the connected Razr.
- `apk/extracted/index.android.bundle` — Hermes bytecode; `decompiled.js` (23 MB) —
  decompiled with `hermes-dec` (`pip install hermes-dec`).
- `apk/extracted/libjl_ota_auth.so` — JieLi auth native lib.
- `apk/extracted/dex/classes*.dex` — Java/Kotlin (contains `com.jieli.jl_bt_ota`).
- Protocol builders live in `decompiled.js` around lines 254000–256000
  (`sendTool_*`, `getSendData`, `cmdIndexCount`, `CRC32_CCITT_FALSE`).

## Repro tooling in this folder
- `parse_protocol.py` — full annotated timeline → `decoded/timeline.txt`.
- `extract_images.py` — carves uploaded images → `decoded/img_*.png|gif`.
- `decoded/drawing_frames.png`, `decoded/gif_frames.png` — rendered previews.
