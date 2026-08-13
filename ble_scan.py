import asyncio
from bleak import BleakScanner

TARGET_NAME_HINT = ("SCR", "DEFC35", "SLShin", "SCR-DEFC35")
TARGET_ADDR = "92:33:6f:de:fc:35"

async def main():
    print("scanning 12s...")
    devs = await BleakScanner.discover(timeout=12.0, return_adv=True)
    rows = []
    for d, adv in devs.values():
        name = d.name or adv.local_name or ""
        rows.append((adv.rssi, d.address, name, list(adv.service_uuids)))
    rows.sort(reverse=True)
    for rssi, addr, name, uuids in rows:
        flag = ""
        if any(h.lower() in (name or "").lower() for h in TARGET_NAME_HINT) or addr.lower()==TARGET_ADDR.lower():
            flag = "  <<< LIKELY HELMET"
        print(f"{rssi:4d} dBm  {addr}  {name!r}  {uuids}{flag}")

asyncio.run(main())
