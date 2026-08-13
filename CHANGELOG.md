# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-08-12

First release intended for publication. The 0.1.0 packaging never shipped
anywhere, and everything below has been verified against real hardware.

### Added
- **Animated GIF upload** — multi-block transfer with per-block READY/SAVED ack
  gating (`upload_bytes`), so animations can be stored on the device. The vendor
  app cannot do this: it chunks at the negotiated MTU instead of MTU−3 and
  corrupts every multi-block transfer.
- **Live streaming** via the type-00 screencast path — `screencast(frame)` for a
  single frame and `stream(frames, fps=…)` for a sequence, reaching 7–11 fps
  depending on frame density.
- **Frame helpers** in `images`: `text_frame`, `fit_text_frame`, `scroll_frames`,
  `iter_video_frames`, `iter_mp4_frames`, `encode_gif_sequence`, `encode_png_fit`.
  Text renders thresholded rather than antialiased, which is what makes it
  legible on a 12-pixel-tall panel.
- `ShiningHelmet.reset()` — restores the factory animations. The protocol builder
  existed and was hardware-verified, but no client method exposed it.
- `MAX_UPLOAD_BYTES` (40960) is now checked before transmitting, so an oversize
  file fails immediately with a clear `ValueError` instead of being rejected by
  the device after three wasted retries.
- `py.typed` marker — the annotations now reach consumers.
- `video` extra for MP4/MOV playback.

### Fixed
- **`stream()` hung forever on an endless generator.** It materialized its input
  with `list(frames)` unconditionally; it now only does so when `loops > 1`, so
  generators stream lazily. This is what makes live effects and other unbounded
  sources usable.
- Replaced deprecated `asyncio.get_event_loop()` with `get_running_loop()`.
- `stream()`'s docstring claimed `loops` was ignored for generators and that a
  callable could be passed. Neither was true.
- All one-shot commands now use acknowledged writes. Write-without-response drops
  frames silently — observed live, with `flip()` restores lost twice.

### Changed
- **Requires Python 3.11+** (was an untested `>=3.9` claim).
- Version is now single-sourced from package metadata and cannot drift from
  `pyproject.toml`.
- `README_LIB.md` merged into `README.md`.
- Packaging metadata completed: trove classifiers, SPDX license expression,
  bundled `LICENSE`, and real project URLs.

## [0.1.0] — 2026-06-09

Initial internal version. Control commands (power, brightness, flip, sync-time,
graffiti, per-pixel draw) and single-packet still-image upload. Never published.
