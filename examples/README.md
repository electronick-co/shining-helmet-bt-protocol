# Examples

Live-playback and validation demos for the SLShining helmet. All connect over
BLE; pass `--address 92:33:6F:DE:FC:35` to skip the scan (or omit to auto-find).

## Live playback (the fun stuff)

Everything here uses the **screencast path** (graffiti mode + per-frame PNG
push). Frames are ephemeral — they play while connected and the panel reverts to
its stored GIF on disconnect.

| script | what it does | example |
|---|---|---|
| `live_text.py` | scrolling marquee or centered static text | `python examples/live_text.py "BURNING MAN 2026" --color 255,140,0` |
| `live_words.py` | word-by-word flash (auto-sized big, blackout blink between) | `python examples/live_words.py OBEY RISE AGAINST THE MACHINE --color 255,30,0` |
| `live_manifesto.py` | choreographed word performance — dynamic pacing (slow words, rapid bursts, stutter-flash, effect interlude, held finale) | `python examples/live_manifesto.py --speed 1.2` |
| `live_prompts.py` | matrix rain + random interaction prompts ("ASK ME ANYTHING", "I NEED A HUG") that decode out of the rain — the wearable "talk to me" show | `python examples/live_prompts.py --seconds 120` |
| `live_effects.py` | generative effects: plasma, fire, matrix, rainbow, sparkle, wipe | `python examples/live_effects.py plasma --seconds 15` |
| `live_slideshow.py` | cycle images with crossfades | `python examples/live_slideshow.py pics/*.png --hold 2 --fade 0.6` |
| `live_video.py` | play animated GIF/WebP/APNG (MP4 with `imageio[ffmpeg]`) | `python examples/live_video.py clip.gif --loops 3` |
| `live_showcase.py` | runs all of the above in one sequence | `python examples/live_showcase.py` |

### Editing the prompt show
`live_prompts.py` keeps its messages in the `PROMPTS` dict at the top (groups
`ask` / `act` / `play`) — edit them freely; `--only ask act` limits which groups
run. Prompts that fit the panel flash whole; longer ones either flash word-by-word
or scroll (`--mode words|scroll|auto`, `--scroll-mix`). Preview the whole show as
a GIF without the helmet: `--preview demo.gif`.

### Saving a show to the helmet (no laptop)
`--save out.gif` writes a 48×12 GIF you can upload with
`shining-helmet image out.gif` — the helmet then plays it standalone, forever,
with nothing connected. The device stores **at most 40960 B** (10 × 4096-byte
blocks; 40961 is rejected — see PROTOCOL.md), so the saver bisects for the
longest show that fits and prints what it had to trim:

```bash
python examples/live_prompts.py --save show.gif --seconds 120
# -> 40507 B (99% of cap), 14.9s of show @ 14 fps
python examples/live_prompts.py --save show.gif --seconds 120 \
       --dim 0 --rain 0.8,1.5 --density 0.5 --fps 10 --word-hold 0.6
# -> 40750 B (99% of cap), 58.2s of show @ 10 fps
```

`--rain-only` stores just the digital rain (what's on the helmet now:
`matrix_rain.gif`, 13.6 s loop, 36777 B). Rain speed is in **pixels per frame**
(`--rain-speed LO,HI`, default `1.3,2.8`) rather than px/sec, because the panel
is 12 px tall and it isn't settled whether the device honors per-frame GIF
delays — so apparent speed has to come from the step size. If motion still looks
slow on the panel, raise it (`--rain-speed 2,4`) rather than raising `--fps`.

Rain is what costs bytes (noise doesn't compress); text held on black costs
almost nothing because `images.encode_gif_sequence` collapses identical
consecutive frames into one long-delay frame. `--seed N` makes a save
reproducible. Live streaming has no such limit — it runs as long as you stay
connected.

### Frame rate & fluidity
Throughput is bounded by **PNG size ÷ MTU** (one BLE write per ~509 bytes), not
the device ack. A full-color 48×12 frame is ~1 KB (2–3 writes ≈ 5 fps); a frame
quantized to 8 colors is ~430 B (1 write ≈ **11–12 fps**). So:
- `live_effects.py` defaults to `--colors 8` and `--fps 20` for fluid motion.
  Use `--colors 0` for true color (slower), or `--ack` to guarantee no dropped
  frames (slower still).
- Effects with small palettes (matrix, text, wipe) are already fast.

## Hardware validation harnesses (protocol verification)

| script | verifies |
|---|---|
| `upload_test.py` | per-pixel draw orientation + single-frame GIF upload |
| `animation_test.py` | multi-block animated-GIF upload (4096-byte blocks + ack gating) |
| `clean_animation.py` | a simple looping rainbow-bar GIF (visual sanity) |
| `screencast_test.py` | the type-00 screencast path (render/persistence/fps) |
| `brightness_flip_test.py`, `brightness_labeled_test.py`, `flip_set.py` | brightness & flip behavior |

All protocol findings from these are recorded in `../VERIFY.md` and `../PROTOCOL.md`.

## Library API used here

```python
from shining_helmet import ShiningHelmet, images

async with ShiningHelmet(address=ADDR) as h:
    await h.power(True)
    # one frame:
    await h.screencast(any_image, colors=8)         # 48x12 PNG, live
    # a sequence (opens graffiti, paces to fps):
    await h.stream(frames, fps=20, colors=8, loops=2, close_graffiti=True)
    # persistent display (survives disconnect):
    await h.show_image(any_image_or_animated_gif)   # GIF upload
```

Frame helpers in `shining_helmet.images`: `text_frame`, `scroll_frames`,
`render_text_strip`, `iter_video_frames`, `iter_mp4_frames`, `encode_png`,
`encode_gif`.
