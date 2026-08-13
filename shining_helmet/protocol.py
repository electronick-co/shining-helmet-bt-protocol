"""Pure protocol helpers — build the byte frames. No BLE, no I/O, fully testable.

Every builder returns the exact `bytes` to write to CHAR_WRITE (0xFA02), with
write-without-response. Framing: [len, 0x00, cmd, sub, args...].
"""
from __future__ import annotations
import datetime as _dt
import zlib
from . import constants as C


def _frame(cmd_sub, *args: int) -> bytes:
    """Assemble [len, 0x00, cmd, sub, *args]; len = total length (low byte)."""
    cmd, sub = cmd_sub
    body = bytes([cmd, sub, *args])
    total = 2 + len(body)  # len byte + pad byte + body
    return bytes([total & 0xFF, C.FRAME_PAD]) + body


# ---------------------------------------------------------------- control cmds
def screen(on: bool) -> bytes:
    """Turn the panel on/off.  VERIFIED."""
    return _frame(C.CMD_SCREEN, 1 if on else 0)


def brightness(level: int) -> bytes:
    """Set brightness, 0..255. VERIFIED LIVE 2026-06-10 (labeled sweep):
    - 0..4 are identical: a still-readable MINIMUM (panel never goes dark —
      use screen(False) for off)
    - perceptible steps through the mid-range (coarse internal quantization)
    - ~192..255 indistinguishable (saturates) -> practical range ~8..192
    """
    return _frame(C.CMD_BRIGHTNESS, level & 0xFF)


def flip(direction: int = 0) -> bytes:
    """Flip / rotate the display. VERIFIED LIVE 2026-06-10:
    0 = normal, any nonzero value (1/2/3 tested) = 180° rotation. Binary
    flip only — no mirror modes. State persists across flips of content.
    """
    return _frame(C.CMD_DIRECTION, direction & 0xFF)


def graffiti(open_: bool) -> bytes:
    """Open/close the live per-pixel 'graffiti' canvas.  VERIFIED."""
    return _frame(C.CMD_GRAFFITI, 1 if open_ else 0)


def reset() -> bytes:
    """Factory-reset the stored content. VERIFIED LIVE 2026-06-10: restores the
    built-in factory animations (replacing any user-uploaded image), acks
    `05 00 03 80 01`, connection stays up, no reboot.
    """
    return _frame(C.CMD_RESET)


def sync_time(when: _dt.datetime | None = None) -> bytes:
    """Set the device clock.  VERIFIED.
    Layout: [0b,00,01,80, yy, mon, day, weekday, hh, mm, ss]
    weekday = isoweekday() % 7  (Sun=0), matches the capture.
    """
    t = when or _dt.datetime.now()
    return _frame(
        C.CMD_SYNC_TIME,
        t.year % 100, t.month, t.day, t.isoweekday() % 7, t.hour, t.minute, t.second,
    )


def draw_pixel(x: int, y: int, rgb, seq: int) -> bytes:
    """Draw one pixel inside graffiti mode.  VERIFIED.
    Layout: [0b,00,05,01, 0x00, R,G,B, X, Y, SEQ]
      - X 0..WIDTH-1, Y 0..HEIGHT-1
      - byte after sub is 0x00 in every capture (layer/flag?) -> kept 0
      - SEQ: rolling counter, +1 per *new* pixel (repeat same pixel -> reuse seq)
    TODO(verify:draw-orientation) confirm X/Y origin/axis + that RGB order is R,G,B
    on the physical panel (webcam check pending).
    """
    r, g, b = rgb
    if not (0 <= x < C.WIDTH and 0 <= y < C.HEIGHT):
        raise ValueError(f"pixel out of range: ({x},{y}) for {C.WIDTH}x{C.HEIGHT}")
    cmd, sub = C.CMD_DRAW
    return bytes([0x0B, C.FRAME_PAD, cmd, sub, 0x00, r & 0xFF, g & 0xFF, b & 0xFF,
                  x & 0xFF, y & 0xFF, seq & 0xFF])


# ---------------------------------------------------------------- image upload
def crc32(data: bytes) -> int:
    """Standard CRC-32 (poly 0xEDB88320, init/xorout 0xFFFFFFFF) == zlib.crc32.
    The app's `CRC32_CCITT_FALSE` builds exactly this table despite the name.
    """
    return zlib.crc32(data) & 0xFFFFFFFF


UPLOAD_HEADER_LEN = 16
UPLOAD_BLOCK_SIZE = 4096   # payload bytes per block; device ACKs each block

# Outer content-type byte (header byte 2). From the app: 1 for sendTypePlayGif,
# 2 for everything else (pictures). The device echoes it in the status
# notification `05 00 <type> 00 <status>`.
TYPE_GIF = 0x01
TYPE_PICTURE = 0x02


def upload_header(payload_len: int, crc: int, *, total_packet_len: int,
                  flag: int = 0x00, idx: int = 0, ftype: int = 0,
                  content_type: int = TYPE_GIF) -> bytes:
    """Build the 16-byte upload header. VERIFIED against the capture:

        [total:2 LE] [type] 00 [flag:1] [file_len:4 LE] [crc32:4 LE] [idx:2 LE] [ftype:1]

      - total    = byte count of THIS block message (16 + this block's payload).
      - type     = TYPE_GIF (1) for display GIFs, TYPE_PICTURE (2) for PNG assets.
      - flag     = 0x00 first block, 0x02 continuation block (app getSendData).
      - file_len = length of the WHOLE file, crc32 = CRC of the WHOLE file
        (same values repeated in every block header).
      - idx/ftype: keep 0 for display content. VERIFIED live: nonzero idx
        renders normally (bookkeeping only); nonzero ftype is acked
        SaveSuccess but does NOT display.
    """
    return (total_packet_len.to_bytes(2, "little")
            + bytes([content_type & 0xFF, 0x00, flag & 0xFF])
            + (payload_len & 0xFFFFFFFF).to_bytes(4, "little")
            + (crc & 0xFFFFFFFF).to_bytes(4, "little")
            + (idx & 0xFFFF).to_bytes(2, "little") + bytes([ftype & 0xFF]))


def screencast_message(file_bytes: bytes) -> bytes:
    """Type-00 'screencast' (投屏) message — 9-byte header + image payload:

        [total:2 LE = len+9] 00 00 00 [len:4 LE] | <payload>

    Decoded from the app's sendTool_toupingWithData; the app streams 48x12 PNG
    canvas snapshots this way during graffiti mode, acked `05 00 00 00 01`
    (type 0, status READY). No CRC, no idx/ftype.

    VERIFIED LIVE 2026-06-10: renders instantly. With graffiti CLOSED the frame
    shows ~0.5 s then the stored animation resumes; with graffiti OPEN it stays
    until the next frame / graffiti close. Ack-gated streaming reaches ~7.7 fps
    (~130 ms/frame) — good enough for live animation.
    """
    n = len(file_bytes)
    return ((n + 9).to_bytes(2, "little") + bytes([0x00, 0x00, 0x00])
            + n.to_bytes(4, "little") + file_bytes)


def upload_blocks(file_bytes: bytes, *, content_type: int = TYPE_GIF,
                  idx: int = 0, ftype: int = 0,
                  block_size: int = UPLOAD_BLOCK_SIZE):
    """Split a file into upload block messages (16-byte header + <=4096 payload).

    Decoded from the app (getSendData + the outer wrapper) and pinned to the
    capture: the first block of the 20047-byte GIF is exactly
    `10 10 01 00 00 4f 4e 00 00 53 43 3a 4b 00 00 00` + payload — total 0x1010
    = 4112 = 16 + 4096. Every block repeats the whole-file len/CRC; flag is 0 on
    the first block and 2 on continuations.

    Each returned block must be written in MTU-sized chunks, then the sender
    WAITS for a status notification `05 00 <type> 00 <status>`:
    status 1 (READY) -> send next block; 3 (SAVED) -> done (after last block);
    2 = storage full; 0 = error/CRC -> resend block.

    VERIFIED LIVE 2026-06-10: a 3-block (11 KB) animated GIF uploaded with READY
    acks per block + SaveSuccess at the end, and the panel plays it. (The vendor
    app's own multi-block sends were corrupted by an MTU off-by-3 bug, which is
    why the capture never shows a successful one.)
    """
    n = len(file_bytes)
    crc = crc32(file_bytes)
    blocks = []
    for off in range(0, max(n, 1), block_size):
        chunk = file_bytes[off:off + block_size]
        hdr = upload_header(n, crc, total_packet_len=UPLOAD_HEADER_LEN + len(chunk),
                            flag=0x00 if off == 0 else 0x02,
                            idx=idx, ftype=ftype, content_type=content_type)
        blocks.append(hdr + chunk)
    return blocks
