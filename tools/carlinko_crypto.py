"""CarLinko remote-control payload crypto (reverse-engineered from app 1.14.10).

The T-Box firmware (>= 2.3.1_051A01R, ~Nov 2026) rejects plain 74xxyy control
commands with a bare "__7404". The official app now sends control commands
AES-encrypted. Scheme (recovered by static RE of libapp.so + verified against
captured plaintext<->ciphertext pairs from a real car):

  frame      = bytes.fromhex(opcode) + VIN.ascii + userId.ascii   (zero-padded
               to a 16-byte multiple -- NOT PKCS7)
  randomHex  = 8 random bytes as 16 hex chars (per command)
  key        = bytes.fromhex("A0F47CB6677BE6A3" + randomHex)       (16 bytes)
  data field = "66" + randomHex + hex( AES-128-ECB(key).encrypt(frame) )

Init commands (2301, 24, 77) are still sent plain; only 74xx actuation
commands are encrypted.

Pure-Python AES (no third-party dep) so the open-source dashboard keeps its
tiny requirements (requests, websocket-client). encrypt_ecb is verified at
import time against a known test vector; build_control_payload is covered by
the captured-pair tests in __main__.
"""
import os

# ---- AES-128 (encrypt only, ECB) -- compact, self-contained -----------------
_SBOX = []
def _init_sbox():
    p = q = 1
    sbox = [0] * 256
    while True:
        # multiply p by 3 in GF(2^8)
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        # divide q by 3
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        q ^= 0x09 if q & 0x80 else 0
        q &= 0xFF
        xf = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) \
               ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4)) ^ 0x63
        sbox[p] = xf & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox
_SBOX = _init_sbox()
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]

def _xtime(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1)

def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return r & 0xFF

def _key_expansion(key):
    assert len(key) == 16
    w = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = list(w[i - 1])
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]                 # RotWord
            temp = [_SBOX[b] for b in temp]            # SubWord
            temp[0] ^= _RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ temp[j] for j in range(4)])
    # round keys as 16-byte blocks
    return [sum((w[r * 4 + c] for c in range(4)), []) for r in range(11)]

def _add_round_key(s, rk):
    return [s[i] ^ rk[i] for i in range(16)]

def _sub_bytes(s):
    return [_SBOX[b] for b in s]

def _shift_rows(s):
    # state is column-major: index = row + 4*col
    o = [0] * 16
    for r in range(4):
        for c in range(4):
            o[r + 4 * c] = s[r + 4 * ((c + r) % 4)]
    return o

def _mix_columns(s):
    o = [0] * 16
    for c in range(4):
        col = s[4 * c:4 * c + 4]
        o[4 * c + 0] = _mul(col[0], 2) ^ _mul(col[1], 3) ^ col[2] ^ col[3]
        o[4 * c + 1] = col[0] ^ _mul(col[1], 2) ^ _mul(col[2], 3) ^ col[3]
        o[4 * c + 2] = col[0] ^ col[1] ^ _mul(col[2], 2) ^ _mul(col[3], 3)
        o[4 * c + 3] = _mul(col[0], 3) ^ col[1] ^ col[2] ^ _mul(col[3], 2)
    return o

def _encrypt_block(block16, round_keys):
    # AES state is column-major: state index = row + 4*col; input byte k -> row k%4, col k//4
    s = _state_from_block(block16)
    s = _add_round_key(s, _state_from_block(round_keys[0]))
    for rnd in range(1, 10):
        s = _sub_bytes(s)
        s = _shift_rows(s)
        s = _mix_columns(s)
        s = _add_round_key(s, _state_from_block(round_keys[rnd]))
    s = _sub_bytes(s)
    s = _shift_rows(s)
    s = _add_round_key(s, _state_from_block(round_keys[10]))
    # back to byte order
    out = [0] * 16
    for k in range(16):
        out[k] = s[(k % 4) + 4 * (k // 4)]
    return bytes(out)

def _state_from_block(block16):
    s = [0] * 16
    for k in range(16):
        s[(k % 4) + 4 * (k // 4)] = block16[k]
    return s

def encrypt_ecb(key, data):
    assert len(data) % 16 == 0
    rk = _key_expansion(key)
    return b"".join(_encrypt_block(data[i:i + 16], rk) for i in range(0, len(data), 16))

# ---- CarLinko payload -------------------------------------------------------
_FIXED_KEY_HEX = "A0F47CB6677BE6A3"

def build_control_payload(opcode, vin, user_id, rand=None):
    """opcode: hex string like '741001'. Returns the 'data' field for the POST."""
    frame = bytes.fromhex(opcode) + str(vin).encode() + str(user_id).encode()
    pad = (-len(frame)) % 16
    frame += b"\x00" * pad
    rb = rand if rand is not None else os.urandom(8)
    rh = rb.hex()
    key = bytes.fromhex(_FIXED_KEY_HEX + rh)
    ct = encrypt_ecb(key, frame)
    return "66" + rh + ct.hex()

# self-test of the AES core against the FIPS-197 vector at import
_tv = encrypt_ecb(bytes.fromhex("000102030405060708090a0b0c0d0e0f"),
                  bytes.fromhex("00112233445566778899aabbccddeeff"))
assert _tv.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a", _tv.hex()

if __name__ == "__main__":
    VIN = "MF7HD27B8TJ014064"; UID = "88504"
    caps = {
      "741001": "665b860f36237770bc9e20d41399792a5cfd304f234dbd081a007dc9cef3b81634465e4e5d2e470785",
      "741000": "66d605e8d5dfef0987565af8d5caf3d921d37a1d6be606fcb6400a930baa03acbf56180cf760cf2f26",
      "741001b":"6626f9f0c671271a8c956a30579874df39eb415e5cd42730010bb982060d174e1d89b690206231224e",
    }
    ok = True
    for name, cap in caps.items():
        op = name[:6]; rb = bytes.fromhex(cap)[1:9]
        got = build_control_payload(op, VIN, UID, rand=rb)
        m = got == cap
        ok &= m
        print(name, "MATCH" if m else "DIFF")
        if not m:
            print(" got", got); print(" exp", cap)
    print("ALL OK" if ok else "FAIL")
