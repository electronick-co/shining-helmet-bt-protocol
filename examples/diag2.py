"""Test whether acknowledged writes (response=True) fix the scattered-dots dropout.
Fills the screen GREEN with reliable writes, leaves graffiti open, holds.
Usage: python examples/diag2.py [response|slow]"""
import asyncio, sys, time
from shining_helmet import ShiningHelmet, constants as C, protocol

async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "response"
    color = (0, 255, 0)
    t0 = time.monotonic()
    async with ShiningHelmet() as h:
        h.notify_handlers.append(lambda b: print(f"   NOTIFY {round(time.monotonic()-t0,3):7.3f}  {b.hex()}"))
        await h.power(True); await asyncio.sleep(0.4)
        await h.set_brightness(0xC0); await asyncio.sleep(0.4)
        await h.graffiti(True); await asyncio.sleep(0.8)
        print(f"fill GREEN mode={mode}")
        seq = 0
        n = 0
        for y in range(C.HEIGHT):
            for x in range(C.WIDTH):
                w = protocol.draw_pixel(x, y, color, seq)
                if mode == "response":
                    await h._write(w, response=True)        # ATT Write Request (acked, paced)
                else:  # slow write-without-response
                    await h._write(w, response=False)
                    await asyncio.sleep(0.02)
                seq += 1; n += 1
        print(f"sent {n} pixels; holding 12s — watch the panel")
        await asyncio.sleep(12)
        print("done")

asyncio.run(main())
