"""GATT identifiers, display geometry, and command opcodes.

All values here are VERIFIED from the live device + decompiled app unless tagged
TODO(verify:...). See VERIFY.md for the running checklist of open items.
"""

# ---- Display geometry (VERIFIED) ----
WIDTH = 48
HEIGHT = 12

# ---- GATT (VERIFIED live on SCR-DEFC35) ----
def _u16(short: str) -> str:
    return f"0000{short}-0000-1000-8000-00805f9b34fb"

SERVICE_DISPLAY = _u16("00fa")     # vendor display/control service
CHAR_WRITE = _u16("fa02")          # write / write-without-response  (phone -> helmet)
CHAR_NOTIFY = _u16("fa03")         # notify (acks/status)            (helmet -> phone)

SERVICE_AUTH = _u16("ae00")        # JieLi RCSP auth service (only needed for OTA)
CHAR_AUTH_WRITE = _u16("ae01")
CHAR_AUTH_NOTIFY = _u16("ae02")

# Advertised device name prefix (the captured unit was "SCR-DEFC35")
DEVICE_NAME_PREFIX = "SCR-"

# ---- Command framing ----
# Frame = [len, 0x00, cmd, sub, args...]  (len = total byte length, low byte)
FRAME_PAD = 0x00

# (cmd, sub) pairs. Names from the app's sendTool_* builders.
CMD_SYNC_TIME = (0x01, 0x80)        # VERIFIED
CMD_RESET = (0x03, 0x80)            # TODO(verify:reset) decoded from source, not exercised
CMD_BRIGHTNESS = (0x04, 0x80)       # VERIFIED (ack received); value range TODO(verify:brightness-range)
CMD_GRAFFITI = (0x04, 0x01)         # VERIFIED (open=1 / close=0)
CMD_DIRECTION = (0x06, 0x80)        # VERIFIED ack; arg meaning TODO(verify:flip-values)
CMD_SCREEN = (0x07, 0x01)           # VERIFIED (on=1 / off=0)
CMD_DRAW = (0x05, 0x01)             # VERIFIED (draw one pixel)

# ---- Notifications on CHAR_NOTIFY ----
# Command acks echo the frame, e.g. 05 00 07 01 01 = screen-on ack.
#
# Upload status notifications (decoded from the app's responseObj enum):
#   [05, 00, <content_type:2 LE>, <status>]
# where content_type echoes the upload header's type byte (0=screencast,
# 1=GIF, 2=picture) and status is:
# ---- Upload size cap (VERIFIED live 2026-07-25 by bisection) ----
# The device accepts a stored file of at most 40960 bytes = 10 x 4096-byte
# blocks. 40960 uploads and saves; 40961 is REJECTED at block 1 with status 0
# (not 2/SPACE_FULL) — the helmet pre-checks the file_len declared in the block
# header and refuses before any payload lands. It is a BYTE cap, not a frame
# cap: a 600-frame animation at 22 KB stores fine, 1200 frames only failed
# because it was 44.6 KB.
MAX_UPLOAD_BYTES = 40960

UPLOAD_STATUS_ERROR = 0x00        # error / CRC mismatch -> app resends current block
UPLOAD_STATUS_READY = 0x01        # "able": block received, send the next block
UPLOAD_STATUS_SPACE_FULL = 0x02   # device storage full -> abort
UPLOAD_STATUS_SAVED = 0x03        # whole file saved (final ack; e.g. 05 00 01 00 03)
UPLOAD_STATUS_TIMEOUT = 0x04
