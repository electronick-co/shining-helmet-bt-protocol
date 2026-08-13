import asyncio, sys
from bleak import BleakClient

ADDR = "92:33:6F:DE:FC:35"

def u(short): return f"0000{short}-0000-1000-8000-00805f9b34fb"
FA02 = u("fa02"); FA03 = u("fa03"); FA01 = u("fa01")
AE01 = u("ae01"); AE02 = u("ae02")

notifs = []
def mk_cb(tag):
    def cb(_h, data):
        notifs.append((tag, bytes(data)))
        print(f"   NOTIFY[{tag}] {bytes(data).hex()}")
    return cb

def frame_synctime():
    import datetime
    t = datetime.datetime.now()
    wk = t.isoweekday() % 7
    return bytes([11,0,1,0x80, t.year%100, t.month, t.day, wk, t.hour, t.minute, t.second])

def frame_light(b):      return bytes([5,0,4,0x80, b & 0xff])
def frame_screen(on):    return bytes([5,0,7,1, 1 if on else 0])
def frame_graffiti(on):  return bytes([5,0,4,1, 1 if on else 0])
def frame_draw(r,g,b,x,y,seq): return bytes([11,0,5,1,0, r,g,b, x,y, seq & 0xff])

async def main():
    print(f"connecting to {ADDR} ...")
    async with BleakClient(ADDR, timeout=20) as c:
        print("connected:", c.is_connected)
        # enumerate
        write_char = None
        for s in c.services:
            print(f"service {s.uuid}")
            for ch in s.characteristics:
                print(f"   char {ch.uuid}  props={','.join(ch.properties)}  handle=0x{ch.handle:04x}")
                if s.uuid.lower().startswith("0000fa00") and ("write-without-response" in ch.properties or "write" in ch.properties):
                    write_char = write_char or ch
        # subscribe notifications
        for cu in (FA03, AE02):
            try:
                await c.start_notify(cu, mk_cb(cu[4:8])); print("subscribed", cu[4:8])
            except Exception as e:
                print("notify fail", cu[4:8], e)
        # choose write characteristic
        wc = None
        for cand in (FA02, FA01):
            ch = c.services.get_characteristic(cand)
            if ch: wc = cand; break
        if wc is None and write_char: wc = write_char.uuid
        print("WRITE CHAR ->", wc)
        if not wc:
            print("no writable FA char found"); return

        async def send(name, payload, resp=False):
            print(f"-> {name}: {payload.hex()}")
            try:
                await c.write_gatt_char(wc, payload, response=resp)
            except Exception as e:
                print("   WRITE ERROR:", e)
            await asyncio.sleep(1.2)

        # ---- try commands WITHOUT auth ----
        await send("syncTime", frame_synctime())
        await send("screen_on", frame_screen(True))
        await send("brightness_0x60", frame_light(0x60))
        await send("graffiti_open", frame_graffiti(True))
        # draw a short white horizontal line on row 0
        for i in range(0, 12):
            await asyncio.sleep(0.05)
            try: await c.write_gatt_char(wc, frame_draw(255,255,255, i, 0, i), response=False)
            except Exception as e: print("draw err", e); break
        print("drew row0 white 0..11")
        await asyncio.sleep(1.0)
        await send("graffiti_close", frame_graffiti(False))
        await asyncio.sleep(1.5)
        print(f"\nTOTAL NOTIFICATIONS: {len(notifs)}")

asyncio.run(main())
