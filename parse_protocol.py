#!/usr/bin/env python3
"""Parse the SLShining / Shining Display helmet BLE log (tshark JSON export)."""
import json, os, sys

SRC = "test1_bluetoothdebug_helmet.json"
OUTDIR = "decoded"
os.makedirs(OUTDIR, exist_ok=True)

def hx(v):
    return bytes(int(x, 16) for x in v.split(":")) if v else b""

def load():
    d = json.load(open(SRC))
    ev = []
    for p in d:
        L = p["_source"]["layers"]
        att = L.get("btatt")
        if not att:
            continue
        op = att.get("btatt.opcode")
        h = att.get("btatt.handle")
        v = att.get("btatt.value", "")
        t = float(L["frame"]["frame.time_relative"])
        n = int(L["frame"]["frame.number"])
        if op in ("0x52", "0x12"):          # write cmd / write req  (phone -> helmet)
            ev.append((t, n, "TX", h, hx(v)))
        elif op == "0x1b":                  # notification (helmet -> phone)
            ev.append((t, n, "RX", h, hx(v)))
    ev.sort()
    return ev

def is_frame(b):
    # control frame:  [len][00][cmd]...   len == len(b)
    return len(b) >= 3 and b[0] == len(b) and b[1] == 0x00

def reassemble(ev):
    """Reassemble fragmented uploads on the data handle 0x0006.
    A new logical message starts with a control frame [len][00][cmd];
    bytes that are not a fresh frame are continuation of the previous upload."""
    msgs = []          # (t, n, dir, handle, kind, payload)
    cur = None         # active large upload buffer
    for t, n, d, h, b in ev:
        if h != "0x0006":
            msgs.append((t, n, d, h, "ctl?", b))
            continue
        if is_frame(b) and len(b) <= 16:
            if cur:
                msgs.append(cur); cur = None
            msgs.append((t, n, d, h, "ctl", b))
        else:
            # part of / start of a big upload
            if cur and cur[0] == t0_of(cur):
                pass
            if cur is None:
                cur = [t, n, d, h, "upload", bytearray(b)]
            else:
                cur[5].extend(b)
    if cur:
        msgs.append(cur)
    return msgs

def t0_of(c):
    return c[0]

CMDS = {0x01: "HELLO/INFO", 0x04: "CMD04", 0x05: "DRAW_PIXEL",
        0x06: "CMD06", 0x07: "CMD07"}

def main():
    ev = load()
    print(f"# {len(ev)} ATT data/notify packets, span "
          f"{ev[0][0]:.1f}..{ev[-1][0]:.1f}s\n")

    # ---- reassemble & classify ----
    msgs = reassemble(ev)

    # ---- dump GIF uploads ----
    gifn = 0
    timeline = []
    for m in msgs:
        t, n, d, h, kind, b = m[0], m[1], m[2], m[3], m[4], bytes(m[5])
        if kind == "upload":
            idx = b.find(b"GIF8")
            if idx >= 0:
                gif = b[idx:]
                gifn += 1
                fn = os.path.join(OUTDIR, f"upload_{gifn:02d}_f{n}.gif")
                open(fn, "wb").write(gif)
                w = gif[6] | gif[7] << 8
                hgt = gif[8] | gif[9] << 8
                hdr = b[:idx]
                timeline.append((t, f"UPLOAD GIF #{gifn}  {w}x{hgt}px  "
                                    f"total={len(b)}B gif={len(gif)}B  hdr={hdr.hex()}"))
            else:
                timeline.append((t, f"UPLOAD (no GIF magic) {len(b)}B  {b[:24].hex()}"))
        elif kind == "ctl":
            cmd = b[2]
            name = CMDS.get(cmd, f"CMD{cmd:02x}")
            arrow = "->" if d == "TX" else "<-"
            timeline.append((t, f"{arrow} {name:11s} {b.hex()}"))
        else:
            arrow = "->" if d == "TX" else "<-"
            timeline.append((t, f"{arrow} [{h}] {kind} {b[:32].hex()}"))

    # collapse runs of DRAW_PIXEL for readability
    out = []
    i = 0
    tl = timeline
    while i < len(tl):
        line = tl[i][1]
        if "DRAW_PIXEL" in line:
            j = i
            while j < len(tl) and "DRAW_PIXEL" in tl[j][1]:
                j += 1
            # summarize the run
            run = [tl[k][1] for k in range(i, j)]
            colors = {}
            for r in run:
                hexb = r.split()[-1]
                col = hexb[10:16]
                colors[col] = colors.get(col, 0) + 1
            cs = ", ".join(f"#{c}:{n}" for c, n in colors.items())
            out.append((tl[i][0], f"   ...DRAW_PIXEL x{j-i}  colors[{cs}]"))
            i = j
        else:
            out.append(tl[i]); i += 1

    with open(os.path.join(OUTDIR, "timeline.txt"), "w") as f:
        for t, line in out:
            f.write(f"{t:9.3f}  {line}\n")
    for t, line in out:
        print(f"{t:9.3f}  {line}")
    print(f"\n# wrote {gifn} GIFs + timeline.txt to {OUTDIR}/")

if __name__ == "__main__":
    main()
