# Verification checklist

Tracks what's confirmed vs. open in the `shining_helmet` library. Each open item
has a `TODO(verify:<id>)` tag grep-able in the source. Tick items as they're
validated on hardware.

## ✅ Verified (live on SCR-DEFC35 + decompiled app)
- [x] GATT: write `0xFA02`, notify `0xFA03`, service `0x00FA`
- [x] Display channel needs **no auth**
- [x] `screen` on/off — `05 00 07 01 vv`
- [x] `brightness` frame — `05 00 04 80 BB` (ack received)
- [x] `flip` frame — `05 00 06 80 dir` (ack received)
- [x] `graffiti` open/close — `05 00 04 01 vv`
- [x] `draw_pixel` frame — `0b 00 05 01 00 RRGGBB X Y SEQ`
- [x] `sync_time` frame — `0b 00 01 80 yy mon day wd hh mm ss`
- [x] **draw-orientation**: X/Y origin & axes CORRECT, RGB order is R,G,B (no swap)
- [x] **draw needs acknowledged writes** (`response=True`); fire-and-forget drops
      most pixels (scattered dots). Per-pixel draw is slow (~13 s/full frame) and
      **ephemeral** — reverts to the stored default animation on disconnect / when
      graffiti is closed.
- [x] **image-upload (single packet, GIF)** renders + persists. Header VERIFIED
      byte-for-byte incl. CRC32: `[total:2 LE] 01 00 [flag:1=00] [len:4 LE]
      [crc32:4 LE] [idx:2=00] [ftype:1=00]` + payload. Device replies `05 00 01 00 03`.
- [x] **format must be GIF** — a PNG upload is accepted (`05 00 01 00 03`) but the
      panel shows **blank**. `images.encode_gif()` / `client.show_image()` handle this.
- [x] **multi-block upload (animated GIFs)** — VERIFIED LIVE 2026-06-10. File cut
      into 4096-byte blocks, each with the 16-byte header (total=4112=`0x1010` for
      a full block; flag 0 first / 2 continuation; whole-file len+CRC in every
      header). Device sends `05 00 01 00 01` (READY) per block, `05 00 01 00 03`
      (SaveSuccess) after the last. 3-block 11 KB animation played + persisted.
      NOTE: the vendor app's own multi-block sends were corrupted (chunked at MTU
      instead of MTU−3, −3 bytes/chunk) — official animated upload never worked.
- [x] **max stored file = 40960 B (10 × 4096 blocks)** — VERIFIED LIVE 2026-07-25
      by bisection with zero-padded GIFs: 40960 saves, **40961 is rejected at
      block 1 with status 0** (Error, *not* 2/SpaceError) — the helmet pre-checks
      the header's `file_len`. It's a BYTE cap, not a frame cap (600 frames / 22 KB
      fine; 1200 frames failed only at 44.6 KB). Upload throughput ≈ 2.4 KB/s, so
      a full 40 KB file takes ~16 s. `constants.MAX_UPLOAD_BYTES`; `upload_bytes`
      raises ValueError before sending anything.
- [x] **upload acks / status notifications** — decoded from app `responseObj` +
      confirmed live: `05 00 <type:2 LE> <status>`; type echoes the header's
      content-type byte (0 screencast / 1 GIF / 2 picture); status 0=error,
      1=ready-for-next-block, 2=storage-full, 3=save-success, 4=timeout.
- [x] **type-00 screencast path** — VERIFIED LIVE 2026-06-10. 9-byte header
      `[total:2 LE] 00 00 00 [len:4 LE]` + 48×12 PNG to `0xFA02`; ack
      `05 00 00 00 01` (~130 ms). Renders instantly; graffiti CLOSED → shows
      ~0.5 s then stored animation resumes; graffiti OPEN → persists until next
      frame. Ack-gated streaming = **~7.7 fps** → the live-animation path:
      `graffiti(True)` + `client.screencast(frame)` per frame.

- [x] **brightness range** — VERIFIED LIVE 2026-06-10 (labeled sweep, value shown
      on-panel): 0–4 identical readable minimum (never fully dark — use screen-off
      for that); coarse steps through mid-range; 192–255 indistinguishable.
      Practical range ≈ 8–192.
- [x] **flip values** — VERIFIED LIVE 2026-06-10: `0` = normal, `1`/`2`/`3` all =
      180° rotation (binary flip, no mirror modes).
- [x] **write reliability** — write-without-response control frames can DROP
      silently (flip(0) restore lost twice). Client now sends all one-shot
      commands with response=True (matches the draw-pixel finding).

- [x] **upload idx/ftype** — VERIFIED LIVE 2026-06-10: `idx=5` upload renders
      normally (no observable effect — app-side bookkeeping only). `ftype=7`
      upload is acked SaveSuccess but does NOT display (stored elsewhere /
      dropped). Always use idx=0, ftype=0 for display content.
- [x] **reset** — VERIFIED LIVE 2026-06-10: `04 00 03 80` restores the factory
      animations (clears the user-stored image). Ack `05 00 03 80 01`;
      connection stays up; no reboot. Safe.

## ☐ Open — tagged in code
| tag | where | what to confirm |
|---|---|---|
| `verify:auth` | auth.py | JieLi RCSP — only relevant if OTA firmware update is ever attempted (brick risk; not needed for display control) |
| `verify:gif-frame-delays` | images.encode_gif_sequence | whether the panel honors **per-frame** GIF delays or re-times all frames equally. A 288-frame file with 100–2500 ms delays uploaded and plays; needs an eyeball to confirm the long holds actually hold. Matters because `encode_gif_sequence` collapses held frames to save bytes. |

**Everything needed for the Burning Man deployment is verified.**

## Practical guidance learned
- **To display arbitrary content: use `show_image()` (GIF upload).** Works for
  stills AND animated GIFs (multi-block verified). Fast and persistent. The
  per-pixel `draw_image()` is only for live doodling.
- `encode_gif()` keeps all frames of an animated source; `upload_bytes()` handles
  block ACK gating automatically.

## How to verify on the Raspberry Pi
1. `pip install -e ".[images]"`
2. `shining-helmet scan` → confirm the helmet shows up under BlueZ.
3. Run each open item's matching example/command and observe (webcam helps).
4. Tick the box, drop the `TODO(verify:...)` tag, update PROTOCOL.md if behavior differs.
