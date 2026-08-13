"""JieLi RCSP authentication — STUB / NOT IMPLEMENTED.

The display channel (SERVICE_DISPLAY / 0xFA0x) needs NO auth (VERIFIED), so this
module is only relevant if you later want OTA firmware updates over SERVICE_AUTH
(0xAE00 / 0xAE01 / 0xAE02).

Findings so far:
  - Auth = JieLi RCSP (com.jieli.jl_bt_ota.impl.RcspAuth). Native crypto lives in
    libjl_ota_auth.so: getRandomAuthData(), getEncryptedAuthData(data), setLinkKey().
  - The app NEVER calls setLinkKey -> it relies on the JieLi native DEFAULT link key.
  - The ASCII token "pass" (02 70 61 73 73) is just JieLi's hardcoded auth-OK marker.
  - Challenge/response is keyed by a 16-byte link key -> NOT replayable.

To implement (TODO(verify:auth)):
  Option A — reuse the official JieLi SDK (com.jieli.jl_bt_ota) which performs auth
             automatically; only worthwhile from Android/iOS.
  Option B — port the cipher: extract the default key + algorithm from
             libjl_ota_auth.so (arm64 getEncryptedAuthData) and reimplement here.
  References: github.com/Jieli-Tech/Android-JL_OTA , iOS-JL_OTA.

WARNING: do NOT attempt OTA/firmware writes without a confirmed, recoverable
flow — bricking risk is real.
"""

AUTH_OK_MARKER = bytes([0x02, 0x70, 0x61, 0x73, 0x73])  # 02 "pass"  (VERIFIED constant)


class NotImplementedAuth(NotImplementedError):
    pass


async def authenticate(client):  # pragma: no cover - intentional stub
    raise NotImplementedAuth(
        "JieLi RCSP auth not implemented (not needed for the display). See auth.py / VERIFY.md."
    )
