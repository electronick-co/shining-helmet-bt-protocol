"""Command-line interface:  shining-helmet <command> [options]

Examples:
  shining-helmet scan
  shining-helmet on
  shining-helmet brightness 200
  shining-helmet image logo.png
  shining-helmet off
"""
from __future__ import annotations
import argparse
import asyncio
import logging

from .client import ShiningHelmet


async def _run(args):
    if args.cmd == "scan":
        for addr, name in await ShiningHelmet.discover(timeout=args.timeout):
            print(f"{addr}  {name}")
        return

    async with ShiningHelmet(address=args.address, timeout=args.timeout) as h:
        if args.cmd == "on":
            await h.power(True)
        elif args.cmd == "off":
            await h.power(False)
        elif args.cmd == "brightness":
            await h.set_brightness(args.value)
        elif args.cmd == "flip":
            await h.flip(args.value)
        elif args.cmd == "synctime":
            await h.sync_time()
        elif args.cmd == "image":
            await h.show_image(args.path)            # VERIFIED: GIF upload, fast + persistent
        elif args.cmd == "draw":
            await h.draw_image(args.path)            # per-pixel path (slow, ephemeral)
        else:
            raise SystemExit(f"unknown command {args.cmd}")


def main():
    p = argparse.ArgumentParser(prog="shining-helmet")
    p.add_argument("--address", help="BLE address (default: auto-discover by name)")
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    sub.add_parser("on")
    sub.add_parser("off")
    sub.add_parser("synctime")
    b = sub.add_parser("brightness"); b.add_argument("value", type=int)
    f = sub.add_parser("flip"); f.add_argument("value", type=int, nargs="?", default=0)
    im = sub.add_parser("image"); im.add_argument("path")   # GIF upload (recommended)
    dr = sub.add_parser("draw"); dr.add_argument("path")    # per-pixel draw
    args = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
