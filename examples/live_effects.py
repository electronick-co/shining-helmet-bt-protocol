"""Live generative EFFECTS on the helmet (numpy-driven, via screencast).

Effects: plasma, fire, matrix (digital rain), rainbow (scrolling hue),
sparkle, wipe. Each runs for --seconds.

Examples:
    python examples/live_effects.py plasma
    python examples/live_effects.py fire --seconds 15 --fps 20
    python examples/live_effects.py all                       # cycle through all
"""
from __future__ import annotations
import argparse
import asyncio
import math

import numpy as np
from PIL import Image

from shining_helmet import ShiningHelmet, constants as C

W, H = C.WIDTH, C.HEIGHT
EFFECTS = ["plasma", "fire", "matrix", "rainbow", "sparkle", "wipe"]


def _img(arr):  # arr: HxWx3 uint8
    return Image.fromarray(arr, "RGB")


def _hsv_to_rgb(h, s, v):
    # vectorized; h,s,v in [0,1] arrays -> uint8 HxWx3
    i = (h * 6).astype(int) % 6
    f = (h * 6) - (h * 6).astype(int)
    p = v * (1 - s); q = v * (1 - f * s); t = v * (1 - (1 - f) * s)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)


def gen(effect):
    """Return a function(t_frame:int)->PIL.Image for the named effect."""
    xs, ys = np.meshgrid(np.arange(W), np.arange(H))
    if effect == "plasma":
        def f(t):
            v = (np.sin(xs / 4.0 + t * 0.15)
                 + np.sin(ys / 3.0 + t * 0.12)
                 + np.sin((xs + ys) / 5.0 + t * 0.1)
                 + np.sin(np.sqrt((xs - W / 2) ** 2 + (ys - H / 2) ** 2) / 3.0 - t * 0.2))
            hue = (v + 4) / 8.0
            return _img(_hsv_to_rgb(hue % 1.0, np.full_like(hue, 0.9),
                                    np.full_like(hue, 1.0)))
        return f
    if effect == "fire":
        # one extra row below the panel holds the heat source; visible rows are
        # the top H of the buffer (cooler as you go up).
        state = {"buf": np.zeros((H + 1, W), float)}
        def f(t):
            buf = state["buf"]
            buf[-1] = 0.7 + 0.3 * np.random.rand(W)        # hot source row
            new = np.empty_like(buf)
            new[-1] = buf[-1]
            new[:-1] = (buf[1:] + np.roll(buf[:-1], 1, 1)
                        + np.roll(buf[:-1], -1, 1) + buf[:-1]) / 4.04
            # random cooling breaks the smooth banding into flicker
            new[:-1] -= np.random.rand(H, W) * 0.05
            np.clip(new, 0, 1, out=new)
            state["buf"] = new
            heat = np.clip(new[:H], 0, 1)                    # bottom row = new[H-1], hot
            r = np.clip(heat * 3, 0, 1)
            g = np.clip(heat * 3 - 1, 0, 1)
            b = np.clip(heat * 3 - 2, 0, 1)
            return _img((np.stack([r, g, b], -1) * 255).astype(np.uint8))
        return f
    if effect == "matrix":
        # each column is a falling drop with a head + fading tail; it respawns
        # at the top as soon as its tail clears the bottom, so density stays up.
        cols = {"y": np.random.uniform(0, H, W),
                "sp": 0.4 + np.random.rand(W) * 0.8,
                "tail": np.random.randint(4, H, W)}
        def f(t):
            arr = np.zeros((H, W, 3), np.uint8)
            cols["y"] += cols["sp"]
            for x in range(W):
                head = cols["y"][x]
                tail = cols["tail"][x]
                for k in range(tail):
                    yy = int(head) - k
                    if 0 <= yy < H:
                        if k == 0:
                            arr[yy, x] = (200, 255, 200)        # bright head
                        else:
                            g = int(max(0, 255 * (1 - k / tail)))
                            arr[yy, x] = (0, g, 0)
                if int(head) - tail >= H:                       # fully off bottom
                    cols["y"][x] = np.random.uniform(-H, 0)
                    cols["sp"][x] = 0.4 + np.random.rand() * 0.8
                    cols["tail"][x] = np.random.randint(4, H)
            return _img(arr)
        return f
    if effect == "rainbow":
        def f(t):
            hue = ((xs / W) + t * 0.03) % 1.0
            return _img(_hsv_to_rgb(hue, np.ones_like(hue), np.ones_like(hue)))
        return f
    if effect == "sparkle":
        def f(t):
            arr = (np.random.rand(H, W, 1) > 0.92) * np.random.randint(
                80, 256, (H, W, 3))
            return _img(arr.astype(np.uint8))
        return f
    if effect == "wipe":
        def f(t):
            arr = np.zeros((H, W, 3), np.uint8)
            pos = int((math.sin(t * 0.1) * 0.5 + 0.5) * W)
            hue = (t * 0.02) % 1.0
            col = _hsv_to_rgb(np.array([[hue]]), np.array([[1.0]]),
                              np.array([[1.0]]))[0, 0]
            arr[:, :pos] = col
            return _img(arr)
        return f
    raise ValueError(effect)


async def play(h, effect, seconds, fps, no_ack, colors=None):
    f = gen(effect)
    n = int(seconds * fps)
    frames = (f(i) for i in range(n))
    print(f">>> {effect}: {n} frames @ {fps} fps (~{seconds}s)")
    await h.stream(frames, fps=fps, wait_ack=not no_ack, colors=colors,
                   close_graffiti=False)


async def run(args):
    effects = EFFECTS if args.effect == "all" else [args.effect]
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        for e in effects:
            await play(h, e, args.seconds, args.fps, args.no_ack, args.colors)
        await h.graffiti(False)
    print("done.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("effect", choices=EFFECTS + ["all"])
    p.add_argument("--address", default=None)
    p.add_argument("--seconds", type=float, default=10.0)
    p.add_argument("--fps", type=float, default=20.0)
    p.add_argument("--colors", type=int, default=None,
                   help="palette size; default AUTO (full color, quantized only "
                        "if needed to fit one write). 0=force truecolor, N=force N")
    p.add_argument("--no-ack", action="store_true", default=True)
    p.add_argument("--ack", dest="no_ack", action="store_false",
                   help="wait for per-frame ack (slower, guarantees no drops)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
