"""Diagnostic: figure out what actually makes the panel show our content.
Leaves the panel in graffiti mode with a solid RED fill so it can be observed live.
Usage: python examples/diag.py [red|green|white]
"""
import asyncio, sys, time
from shining_helmet import ShiningHelmet, constants as C

COLORS = {"red": (255,0,0), "green": (0,255,0), "blue": (0,0,255), "white": (255,255,255)}

async def main():
    color = COLORS.get(sys.argv[1] if len(sys.argv) > 1 else "red", (255,0,0))
    t0 = time.monotonic()
    async with ShiningHelmet() as h:
        h.notify_handlers.append(lambda b: print(f"   NOTIFY {round(time.monotonic()-t0,3):7.3f}  {b.hex()}"))
        print("power on"); await h.power(True); await asyncio.sleep(0.5)
        print("brightness"); await h.set_brightness(0xC0); await asyncio.sleep(0.5)
        print("graffiti OPEN"); await h.graffiti(True); await asyncio.sleep(0.8)
        print(f"filling whole screen {color} (graffiti left OPEN)")
        h.reset_seq()
        for y in range(C.HEIGHT):
            for x in range(C.WIDTH):
                await h.draw_pixel(x, y, color)
            await asyncio.sleep(0.02)
        print("fill complete — LEAVING graffiti open; holding 12s, watch the panel")
        await asyncio.sleep(12)
        print("done (not closing graffiti)")

asyncio.run(main())
