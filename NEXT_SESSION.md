# Next session — handoff

Status as of 2026-06-10. **The protocol RE is COMPLETE** — every item in
VERIFY.md is live-verified except JieLi RCSP auth (only needed for OTA, brick
risk, intentionally skipped). Read `VERIFY.md` + `PROTOCOL.md` for the full
picture; orientation in `CLAUDE.md`. Library lives in `shining_helmet/`.

## What works (all verified on the real helmet)
- Connect (no auth), screen on/off, brightness, flip, sync-time, graffiti,
  per-pixel draw, factory reset.
- **Stills + animated GIFs**: `client.show_image(anything)` — multi-block upload
  (4096-byte blocks, READY/SAVED ack gating) verified with an 11 KB 3-block
  animation. Persists across disconnect.
- **Live streaming ~7.7 fps**: `client.graffiti(True)` + `client.screencast(frame)`
  per frame (type-00 path, 48×12 PNG). Ephemeral; stored GIF returns on close.
- 11 unit tests pass (`pytest -q`).

## Key operational knowledge
- brightness: 0–4 = identical readable floor (never fully dark), saturates ~192.
- flip: 0 = normal, any nonzero = 180°. Binary.
- idx/ftype in upload header: keep 0 (nonzero ftype is acked but doesn't display).
- reset (`04 00 03 80`): restores factory animations, clears user image. Safe.
- **Use acknowledged writes everywhere** (client does) — write-without-response
  drops frames silently.
- The VENDOR APP's multi-block upload is broken (chunks at MTU instead of MTU−3);
  our implementation is the only thing that can push animations to this helmet.

## Live-playback toolkit (built 2026-06-10)
`client.stream(frames, fps=, colors=, loops=, close_graffiti=)` plays any
iterable of PIL frames via screencast; `client.screencast(frame, colors=)` does
one frame. Frame helpers in `images`: `text_frame`, `scroll_frames` (crisp,
thresholded — no AA shadows), `iter_video_frames` (GIF/WebP/APNG),
`iter_mp4_frames` (needs imageio). Demos in `examples/` (see examples/README.md):
`live_text`, `live_effects` (plasma/fire/matrix/rainbow/sparkle/wipe),
`live_slideshow`, `live_video`, `live_showcase`.

**Live-fps insight (important):** screencast throughput is bounded by PNG size ÷
MTU (≈509 B/write), NOT the device ack. A full-color 48×12 frame ≈1 KB (2-3
writes ≈5 fps); quantized to 8 colors ≈430 B (1 write ≈**11-12 fps**). So
`screencast`/`stream` take `colors=` (effects default 8). `screencast` chunks at
negotiated MTU−3 automatically. wait_ack=False doesn't speed things up (writes,
not acks, are the limit) but avoids the ~0.5 s ack wait on the last frame.

## Possible next steps (product work, not RE)
1. **Burning Man app**: show controller on `shining_helmet` — playlists, live
   audio-reactive effects (extend live_effects), Pi deployment. The streaming
   toolkit above is the foundation.
2. MP4 playback: `pip install imageio imageio-ffmpeg` enables `live_video.py x.mp4`.
3. BLOG.md: update with the multi-block + vendor-app-bug story + the live
   screencast/fps findings.
4. Cloud catalog (Heaton) via mitmproxy — still optional/unneeded.
5. OTA / JieLi RCSP auth — only if firmware mods ever wanted. Brick risk.

## Gotchas (unchanged)
- Uploads MUST be GIF (PNG only works on the screencast path).
- Panel reverts to stored GIF on disconnect/graffiti-close; uploads persist.
- After a connection drop, a rescan can transiently miss the device — retry.
- Helmet = `SCR-DEFC35` / `92:33:6F:DE:FC:35`.
- **Stored file cap = 40960 B** (10×4096). 40961 is rejected at block 1 with
  status 0. Byte cap, not frame cap. Upload ≈2.4 KB/s → a full file takes ~16 s.

## Raspberry Pi (Linux/BlueZ) port (2026-08-12)
First run on the Pi found a real cross-platform bug, now fixed in
`client.py:connect()`/`_negotiate_mtu()`: on BlueZ, `BleakClient.mtu_size`
silently stays at the connection default (23) unless something forces a real
ATT MTU exchange first — the PC testing so far was apparently on a backend
(Windows/macOS) that negotiates automatically, so this never showed up before.
Without the exchange, every multi-chunk write (image upload, screencast)
chunked at 20 bytes instead of ~509 — a **~25x** increase in BLE round-trips.
Symptom was dramatic: `live_effects.py plasma --seconds 8` took **88s real
time** instead of ~8-12s. Fix: `connect()` now calls the bleak BlueZ backend's
private `_acquire_mtu()` right after connecting (before `start_notify`), which
reliably yields `mtu_size=512` on this helmet; confirmed by timing the same
plasma run at **12.4s** after the fix. Verified via `upload_test.py` too
(`MTU: 512` in its printed diagnostics). Note: the *other*, more "official"-
looking fix — reading `characteristic.max_write_without_response_size`
instead of `mtu_size` — turned out to be a dead end here: that BlueZ D-Bus
property is a stale snapshot from connection time and does **not** update
after `_acquire_mtu()` runs, so it kept reporting 20 even once the real MTU
was 512. Don't try that route again without re-verifying on hardware.
Bluetooth stack on this Pi: BlueZ 5.82, onboard UART HCI (`hci0`,
`88:A2:9E:E9:DC:8B`), no `sudo`/`rfkill` issues, `bleak` needed a venv
(`.venv/`) due to Debian trixie's PEP 668 externally-managed-environment
restriction — `pip install -e ".[images]"` inside it; `numpy` (used by
`live_effects.py` but not in `pyproject.toml`) had to be installed separately.

## Physical mounting orientation — flip=1 now baked in (2026-08-12)
As actually mounted on the helmet, the panel's native `flip=0` state renders
**upside-down** (confirmed live with `examples/upload_test.py`'s corner-marker
test pattern: flip=0 → full 180° rotation, flip=1 → upright). This is a
mounting fact about this physical unit, not a protocol default, so it's
applied automatically rather than left as a manual step: `ShiningHelmet.__init__`
now takes `flip: Optional[int] = C.DEFAULT_FLIP` (`constants.DEFAULT_FLIP = 1`),
and `connect()` sends it right after MTU negotiation, before returning. Pass
`flip=None` (or `flip=0`) to `ShiningHelmet()` to skip/override — e.g. if a
different physically-mounted unit needs the untouched state. Also confirmed:
flip is a **device-persisted** setting — it survived a full disconnect/
reconnect cycle without us resending it, so this only needed fixing once in
code, not per-session (worth re-checking after a full power cycle, unverified
whether it survives that).

## Open work — the interaction-prompt show (2026-07-25)
`examples/live_prompts.py` (matrix rain + "ASK ME ANYTHING" / "I NEED A HUG"
prompts) runs live and saves. Currently on the helmet: `matrix_rain.gif`
(rain only, 25.3 s loop, 40889 B — regenerate with `--rain-only --fps 10
--density 0.6`).

1. **TEXT LEGIBILITY (blocker, next up).** On the panel the prompts read blurry:
   the area around the glyphs isn't erased, so rain/previous content mushes into
   the letters. Fix candidates, in order: (a) don't composite text over rain at
   all — blank the frame, hold text on solid black (`--dim 0` already does this
   for saves; make it the default for text segments); (b) add a 1-px black
   outline / knockout box around glyph pixels so nothing touches the strokes;
   (c) check whether the screencast path itself ghosts between frames (push an
   all-black frame before each text frame and see if it sharpens) — if the panel
   ghosts, that's a device property to design around, not a renderer bug.
2. `TODO(verify:gif-frame-delays)` — does the panel honor per-frame GIF delays?
   `encode_gif_sequence(collapse=True)` counts on it to fit long shows.
   **Correction (2026-08-12):** the old fallback advice "if it re-times, pass
   collapse=False" is impossible. Pillow's GIF writer merges identical
   consecutive frames and sums their durations on its own, unconditionally —
   `optimize=`/`disposal=` don't disable it — so `collapse=False` returns
   byte-identical output (pinned by `tests/test_images.py`). If the panel turns
   out to re-time frames, the real fix is a uniform delay with *slightly
   differing* repeated frames.
3. Rain loop seam: columns jump back to frame-0 positions each loop. Seamless
   loop would need the rain state to match at frame 0 and frame N.
4. Rain was retuned 2026-07-25 after it read as slow: speed is now **px/frame**
   (1.3-2.8, was 0.4-1.2 → a drop took 1-3 s to fall 12 px), white-hot head,
   square tail falloff. Also fixed a real bug — idle columns were only respawned
   inside the `if on[x]` branch, so the rain **thinned out and died** over a long
   loop. If it still looks slow on the panel, that means the device re-times GIF
   frames and the lever is `--rain-speed 2,4`, not `--fps`.
