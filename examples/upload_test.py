"""Hardware validation harness for the unverified bits — run with the panel in view.

It (1) builds a deliberately ASYMMETRIC, color-coded 48x12 test image so that
orientation, axis direction and RGB byte order are all readable at a glance, then
(2) shows it via the VERIFIED per-pixel path, and (3) tries the UNVERIFIED bulk
upload path while dumping every notification with timestamps.

Usage:
    python examples/upload_test.py                 # draw, then upload, then report
    python examples/upload_test.py --mode draw     # only the verified per-pixel path
    python examples/upload_test.py --mode upload    # only the bulk-upload path
    python examples/upload_test.py --image foo.png  # use your own 48x12 image

What to look at (and then tick boxes in VERIFY.md):
  * orientation/axis  -> the "F" must read upright & forward (not mirrored/rotated)
  * RGB byte order    -> top-left dot RED, top-right GREEN, bottom-left BLUE,
                         bottom-right WHITE. If red/blue look swapped, order is BGR.
  * verify:image-upload -> does the bulk upload render the SAME image as draw mode?
  * verify:upload-ack  -> watch the notification dump for per-packet acks
"""
from __future__ import annotations
import argparse
import asyncio
import os
import time

from shining_helmet import ShiningHelmet, constants as C

OUT_IMG = os.path.join(os.path.dirname(__file__), "..", "decoded", "test_orientation.png")


def build_test_pixels():
    """Return (flat WIDTH*HEIGHT [(r,g,b)], path-to-png). Needs Pillow."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 0))
    d = ImageDraw.Draw(im)
    # corner markers (unambiguous orientation + RGB-order check)
    im.putpixel((0, 0), (255, 0, 0))                      # top-left    RED
    im.putpixel((C.WIDTH - 1, 0), (0, 255, 0))            # top-right   GREEN
    im.putpixel((0, C.HEIGHT - 1), (0, 0, 255))           # bottom-left BLUE
    im.putpixel((C.WIDTH - 1, C.HEIGHT - 1), (255, 255, 255))  # bottom-right WHITE
    # an asymmetric "F" in the middle (orange) — reveals mirror/rotation
    col = (255, 160, 0)
    for y in range(2, 10):
        d.point((20, y), fill=col)            # vertical stem
    for x in range(20, 28):
        d.point((x, 2), fill=col)             # top bar
    for x in range(20, 26):
        d.point((x, 5), fill=col)             # middle bar
    os.makedirs(os.path.dirname(OUT_IMG), exist_ok=True)
    im.save(OUT_IMG)
    px = im.load()
    pixels = [px[x, y] for y in range(C.HEIGHT) for x in range(C.WIDTH)]
    return pixels, OUT_IMG


async def run(args):
    # capture notifications passively, with timestamps
    notes = []
    t0 = time.monotonic()

    async with ShiningHelmet(address=args.address) as h:
        h.notify_handlers.append(
            lambda b: notes.append((round(time.monotonic() - t0, 3), b.hex())))

        if args.image:
            from shining_helmet import images
            pixels = images.load_frame(args.image)
            img_path = args.image
        else:
            pixels, img_path = build_test_pixels()
            print(f"generated test image -> {img_path}")

        await h.sync_time()
        await h.power(True)
        await h.set_brightness(0xC0)

        if args.mode in ("draw", "both"):
            print(">>> DRAW path (verified). Watch the panel.")
            await h.graffiti(True)
            await asyncio.sleep(0.3)
            h.reset_seq()
            from shining_helmet import images
            writes, h._seq = images.frame_to_draw_writes(pixels, h._seq)
            for w in writes:
                await h._write(w, response=True)   # acknowledged: avoids pixel dropout
            # NOTE: leave graffiti OPEN while observing — closing it reverts the
            # panel to the stored default animation.
            print("    draw done — confirm orientation + RGB order now (graffiti kept open).")
            await asyncio.sleep(args.pause)
            await h.graffiti(False)

        if args.mode in ("upload", "both"):
            print(">>> UPLOAD path (UNVERIFIED — TODO:image-upload). Watch + note acks.")
            try:
                print("    MTU:", getattr(h._client, "mtu_size", "?"))
            except Exception:
                pass
            before = len(notes)
            try:
                await h.upload_image(img_path)
            except Exception as e:
                print("    upload raised:", e)
            await asyncio.sleep(args.pause)
            print(f"    notifications during upload: {len(notes) - before}")

        await asyncio.sleep(0.5)

    print("\n=== notification log (t, hex) ===")
    for t, hexs in notes:
        print(f"  {t:7.3f}  {hexs}")
    if not notes:
        print("  (none)")
    print("\nReminder: update VERIFY.md / PROTOCOL.md with what you observed.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--mode", choices=["draw", "upload", "both"], default="both")
    p.add_argument("--image", default=None, help="use your own 48x12 image instead of the generated one")
    p.add_argument("--pause", type=float, default=4.0, help="seconds to hold each result for the webcam")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
