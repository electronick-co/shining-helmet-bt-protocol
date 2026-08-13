"""MATRIX RAIN + interaction prompts — the "talk to me" helmet show.

Digital rain runs as the connective tissue; every few seconds it condenses into
a random invitation for the people looking at you: ask me a question, hug me,
tell me something. You can't see the panel (it's on your head) — they can, so
the messages are aimed at them.

Prompt bank lives in PROMPTS below (edit freely). Long lines scroll as a
marquee, short ones decode in place out of the rain and hold.

Examples:
    python examples/live_prompts.py                       # run until Ctrl-C
    python examples/live_prompts.py --seconds 60 --rain 2,4
    python examples/live_prompts.py --only ask --color 0,255,120
    python examples/live_prompts.py --preview demo.gif    # no hardware needed
"""
from __future__ import annotations
import argparse
import asyncio
import itertools
import random
import time
from collections import deque

import numpy as np
from PIL import Image

from shining_helmet import ShiningHelmet, images, constants as C

W, H = C.WIDTH, C.HEIGHT

# --- the prompt bank -------------------------------------------------------
# Grouped so you can run a subset with --only. Keep them SHORT: anything wider
# than the panel scrolls, which takes time; <=8 chars fills the panel big.
PROMPTS = {
    "ask": [
        "ASK ME ANYTHING",
        "ASK ME WHY I'M HERE",
        "ASK ME ABOUT THE HELMET",
        "ASK ME FOR A SECRET",
        "ASK ME THE WEIRDEST THING",
        "ASK ME WHAT I'M AFRAID OF",
        "ASK ME MY NAME",
        "ASK ME WHAT I BUILT",
        "ASK ME FOR ADVICE",
        "ASK ME A HARD QUESTION",
    ],
    "act": [
        "I NEED A HUG",
        "HUG?",
        "HIGH FIVE",
        "DANCE WITH ME",
        "SAY HI",
        "TALK TO ME",
        "WALK WITH ME",
        "MAKE ME LAUGH",
    ],
    "play": [
        "TELL ME A JOKE",
        "TELL ME A SECRET",
        "GIVE ME A NICKNAME",
        "TELL ME YOUR NAME",
        "TEACH ME A WORD",
        "SING AT ME",
        "TELL ME SOMETHING TRUE",
        "DARE ME",
    ],
}


class Rain:
    """Matrix digital rain as raw HxWx3 arrays (so text can be composited over
    it). A white-hot head with a green fading tail per column, respawning at the
    top once it clears the bottom.

    Speed is in **pixels per frame**, deliberately, not pixels per second: this
    panel is only 12 px tall and it is not settled whether the device honors
    per-frame GIF delays, so apparent speed has to come from the step size. At
    0.4-1.2 px/frame (the first cut) a drop took 1-3 s to fall 12 px and read as
    sluggish; the 1.3-2.8 default crosses in ~4-9 frames.
    """

    def __init__(self, density: float = 0.75, speed=(1.3, 2.8), tail=(4, 10),
                 glitch: float = 0.03):
        self.lo, self.hi = speed
        self.tmin, self.tmax = tail
        self.glitch = glitch
        self.y = np.random.uniform(-H, H, W)
        self.sp = self._speeds(W)
        self.tail = np.random.randint(self.tmin, self.tmax, W)
        # some columns sit idle so the rain isn't a solid wall
        self.on = np.random.rand(W) < density
        self.density = density

    def _speeds(self, n):
        return self.lo + np.random.rand(n) * (self.hi - self.lo)

    def _spawn(self, x):
        """Start a fresh drop just above the top of the panel."""
        self.y[x] = np.random.uniform(-4, -1)
        self.sp[x] = self._speeds(1)[0]
        self.tail[x] = np.random.randint(self.tmin, self.tmax)
        self.on[x] = True

    def step(self) -> np.ndarray:
        arr = np.zeros((H, W, 3), np.uint8)
        self.y += self.sp
        for x in range(W):
            if not self.on[x]:
                # Idle columns MUST get a chance to restart, or the rain thins
                # out and dies: an earlier version only respawned inside the
                # active branch, so every column that went idle stayed idle and
                # a long loop faded to black.
                if np.random.rand() < 0.18 * self.density:
                    self._spawn(x)
                continue
            head, tail = int(self.y[x]), self.tail[x]
            for k in range(tail):
                yy = head - k
                if 0 <= yy < H:
                    if k == 0:
                        arr[yy, x] = (255, 255, 255)        # white-hot head
                    elif k == 1:
                        arr[yy, x] = (140, 255, 160)        # pale green behind it
                    else:
                        # square falloff: bright near the head, dark fast
                        f = (1 - (k - 1) / tail) ** 2
                        arr[yy, x] = (0, int(230 * f), int(40 * f))
                    if k > 1 and np.random.rand() < self.glitch:
                        arr[yy, x] = (170, 255, 180)        # flickering glyph
            if head - tail >= H:                     # tail cleared the bottom
                if np.random.rand() < self.density:
                    self._spawn(x)                   # straight into a new drop
                else:
                    self.on[x] = False               # rest a while (see above)
        return arr


def text_mask(frame) -> np.ndarray:
    """Boolean HxW (or Hxany-width) mask of the lit glyph pixels of a frame."""
    return np.array(frame.convert("L")) > 127


def compose(rain: np.ndarray, mask: np.ndarray, color, dim: float) -> Image.Image:
    """Text (in `color`) over rain dimmed to `dim`, rain suppressed under glyphs."""
    arr = (rain * dim).astype(np.uint8)
    arr[mask] = color
    return Image.fromarray(arr, "RGB")


def decode_frames(rain: Rain, mask, color, n: int, dim: float):
    """Reveal the text out of the noise: glyph pixels flicker in with rising
    probability, stray rain-green pixels flicker around them and die off."""
    for i in range(n):
        p = (i + 1) / n
        shown = mask & (np.random.rand(H, W) < p ** 1.5)
        noise = (np.random.rand(H, W) < 0.10 * (1 - p)) & ~mask
        arr = (rain.step() * dim).astype(np.uint8)
        arr[noise] = (0, 200, 0)
        arr[shown] = color
        yield Image.fromarray(arr, "RGB")


def hold_frames(rain: Rain, mask, color, n: int, dim: float):
    for _ in range(n):
        yield compose(rain.step(), mask, color, dim)


def rain_frames(rain: Rain, n: int):
    for _ in range(n):
        yield Image.fromarray(rain.step(), "RGB")


def scroll_frames(rain: Rain, strip_mask: np.ndarray, color, step: int, dim: float):
    """Marquee the text mask right-to-left over the rain."""
    total = strip_mask.shape[1] + W
    for off in range(-W, total, step):
        win = np.zeros((H, W), bool)
        src_a, src_b = max(0, off), min(strip_mask.shape[1], off + W)
        if src_b > src_a:
            dst = src_a - off
            win[:, dst:dst + (src_b - src_a)] = strip_mask[:, src_a:src_b]
        yield compose(rain.step(), win, color, dim)


def word_frames(rain: Rain, text: str, color, args):
    """Word-by-word: each word decodes out of the rain, big and centered, and
    holds. Punchier than a marquee — a passer-by can read it in one glance."""
    words = text.split()
    for i, word in enumerate(words):
        mask = text_mask(images.fit_text_frame(word, color=(255, 255, 255)))
        last = i == len(words) - 1
        yield from decode_frames(rain, mask, color, max(2, int(args.fps * 0.15)),
                                 args.dim)
        hold = args.word_hold * (2.2 if last else 1.0)
        yield from hold_frames(rain, mask, color, int(args.fps * hold), args.dim)


def build_prompt_frames(rain: Rain, text: str, color, args):
    """Frames for one prompt. Short enough to fit → decode in place and hold.
    Otherwise word-flash or marquee (`auto` mixes them so the show varies)."""
    strip = images.render_text_strip(text, color=(255, 255, 255),
                                     font_size=args.font_size)
    if strip.width <= W and args.mode != "scroll":         # fits: flash it big
        mask = text_mask(images.fit_text_frame(text, color=(255, 255, 255)))
        yield from decode_frames(rain, mask, color, int(args.fps * 0.5), args.dim)
        yield from hold_frames(rain, mask, color, int(args.fps * args.hold), args.dim)
        return
    mode = args.mode
    if mode == "auto":
        mode = "scroll" if random.random() < args.scroll_mix else "words"
    if mode == "scroll":
        yield from scroll_frames(rain, text_mask(strip), color, args.step, args.dim)
    else:
        yield from word_frames(rain, text, color, args)


def pick(bank, recent):
    """Random prompt, avoiding anything shown in the last few rounds."""
    fresh = [p for p in bank if p not in recent] or list(bank)
    choice = random.choice(fresh)
    recent.append(choice)
    return choice


def show_iter(args):
    """Yield (frame, label) for the whole show — hardware-independent, so the
    live run and --preview render exactly the same thing."""
    bank = [p for k, v in PROMPTS.items()
            if not args.only or k in args.only for p in v]
    if not bank:
        raise SystemExit(f"no prompts for --only {args.only}")
    rain = Rain(density=args.density,
                speed=tuple(float(x) for x in args.rain_speed.split(",")),
                tail=tuple(int(x) for x in args.rain_tail.split(",")),
                glitch=args.rain_glitch)
    recent = deque(maxlen=max(1, len(bank) // 3))
    color = tuple(int(x) for x in args.color.split(","))
    lo, hi = (float(x) for x in args.rain.split(","))
    if args.rain_only:                       # plain digital rain, no prompts
        while True:
            yield Image.fromarray(rain.step(), "RGB"), None
    while True:
        secs = random.uniform(lo, hi)
        for fr in rain_frames(rain, int(secs * args.fps)):
            yield fr, None
        text = pick(bank, recent)
        for fr in build_prompt_frames(rain, text, color, args):
            yield fr, text


async def run(args):
    frames = show_iter(args)
    deadline = time.monotonic() + args.seconds if args.seconds else None
    interval = 1.0 / args.fps
    shown = None

    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        if args.brightness is not None:
            await h.set_brightness(args.brightness)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        loop = asyncio.get_event_loop()
        n = 0
        try:
            for frame, label in frames:
                if label and label != shown:
                    shown, _ = label, print(f"  >> {label}")
                elif label is None:
                    shown = None
                t0 = loop.time()
                await h.screencast(frame, wait_ack=False, colors=args.colors)
                n += 1
                dt = interval - (loop.time() - t0)
                if dt > 0:
                    await asyncio.sleep(dt)
                if deadline and time.monotonic() >= deadline:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            await h.screencast(images.text_frame(""), wait_ack=False)
            await h.graffiti(False)
    print(f"done - {n} frames.")


def render_preview(args):
    """Write the show to a scaled-up GIF so it can be reviewed without the helmet."""
    n = int((args.seconds or 20) * args.fps)
    out = []
    for i, (frame, _) in enumerate(show_iter(args)):
        if i >= n:
            break
        out.append(frame.resize((W * args.scale, H * args.scale), Image.NEAREST))
    out[0].save(args.preview, save_all=True, append_images=out[1:],
                duration=int(1000 / args.fps), loop=0)
    print(f"wrote {args.preview} ({len(out)} frames @ {args.fps} fps)")


def build_gif(args, seconds: float):
    """Encode `seconds` of the show as an upload-ready 48x12 GIF. Seeded, so the
    same args always produce the same show (and a longer render shares the
    shorter one's prefix — which is what makes the fit search below stable)."""
    random.seed(args.seed)
    np.random.seed(args.seed)
    n = int(seconds * args.fps)
    frames = (fr for fr, _ in itertools.islice(show_iter(args), n))
    return images.encode_gif_sequence(frames, fps=args.fps, colors=args.colors or 8)


def save_gif(args):
    """Write a GIF the helmet can STORE and play standalone (no laptop).

    The device caps a stored file at C.MAX_UPLOAD_BYTES (40960 B), so when the
    requested length doesn't fit, bisect for the longest show that does.
    """
    want = args.seconds or 60.0
    gif = build_gif(args, want)
    secs = want
    if len(gif) > C.MAX_UPLOAD_BYTES:
        lo, hi = 2.0, want                  # lo fits (assumed), hi does not
        for _ in range(7):
            mid = (lo + hi) / 2
            cand = build_gif(args, mid)
            if len(cand) <= C.MAX_UPLOAD_BYTES:
                lo, secs, gif = mid, mid, cand
            else:
                hi = mid
    with open(args.save, "wb") as fh:
        fh.write(gif)
    pct = 100 * len(gif) / C.MAX_UPLOAD_BYTES
    print(f"wrote {args.save}: {len(gif)} B ({pct:.0f}% of the {C.MAX_UPLOAD_BYTES} B cap), "
          f"{secs:.1f}s of show @ {args.fps} fps")
    if secs < want - 0.5:
        print(f"  (trimmed from {want:.0f}s to fit - rain is the expensive part; "
              f"try --dim 0 --rain 1,2 --density 0.5 --fps 10 for more show time)")
    print(f"  upload it with: shining-helmet image {args.save}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--seconds", type=float, default=0,
                   help="total runtime; 0 = until Ctrl-C (preview default 20)")
    p.add_argument("--rain", default="2.5,5",
                   help="LO,HI seconds of pure rain between prompts")
    p.add_argument("--hold", type=float, default=2.0,
                   help="seconds a short prompt stays up")
    p.add_argument("--mode", choices=["auto", "words", "scroll"], default="auto",
                   help="how long prompts are shown (auto mixes both)")
    p.add_argument("--word-hold", type=float, default=0.45,
                   help="seconds per word in word-flash mode")
    p.add_argument("--scroll-mix", type=float, default=0.35,
                   help="fraction of long prompts that scroll instead of flash")
    p.add_argument("--step", type=int, default=2, help="marquee px per frame")
    p.add_argument("--fps", type=float, default=14.0)
    p.add_argument("--colors", type=int, default=8,
                   help="palette size (8 keeps frames to one BLE write)")
    p.add_argument("--color", default="255,255,255", help="text R,G,B")
    p.add_argument("--dim", type=float, default=0.30,
                   help="rain brightness behind text (0-1)")
    p.add_argument("--density", type=float, default=0.75, help="rain column density")
    p.add_argument("--rain-speed", default="1.3,2.8",
                   help="LO,HI fall speed in PIXELS PER FRAME (panel is 12 px "
                        "tall, so 1.0-2.4 crosses it in ~0.3-0.6s)")
    p.add_argument("--rain-tail", default="4,10", help="MIN,MAX tail length in px")
    p.add_argument("--rain-glitch", type=float, default=0.03,
                   help="per-pixel chance of a bright flickering glyph in a tail")
    p.add_argument("--font-size", type=int, default=11)
    p.add_argument("--brightness", type=int, default=200)
    p.add_argument("--only", nargs="*", choices=sorted(PROMPTS),
                   help="limit to these prompt groups")
    p.add_argument("--rain-only", action="store_true",
                   help="digital rain with no prompts (clean loop to store)")
    p.add_argument("--seed", type=int, default=0,
                   help="RNG seed for --save/--preview (same seed = same show)")
    p.add_argument("--preview", metavar="OUT.GIF",
                   help="render an upscaled GIF to review on screen (no helmet)")
    p.add_argument("--scale", type=int, default=8, help="preview upscale factor")
    p.add_argument("--save", metavar="OUT.GIF",
                   help="write a 48x12 GIF to UPLOAD to the helmet (plays "
                        "standalone, no laptop); trimmed to the 40 KB device cap")
    args = p.parse_args()
    if args.preview:
        render_preview(args)
    elif args.save:
        save_gif(args)
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
