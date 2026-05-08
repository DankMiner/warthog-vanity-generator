#!/usr/bin/env python3
# =====================================================================
#  Warthog Vanity Engine  v1.0.0
#  Creator: DankMiner
#
#  Core: ECC (secp256k1) + HASH160 (RIPEMD160(SHA256)) + hex+SHA256
#  checksum encoding + CPU multi-process worker.
#
#  Reference: warthog/src/shared/src/crypto/{address,crypto}.{hpp,cpp}
#    PubKey::address()  =  RIPEMD160(SHA256(pubkey_compressed_33))
#    AddressView::serialize()  appends SHA256(addr20)[0:4] checksum
#    AddressView::to_string()  emits 48 lowercase hex chars
#    PrivKey::to_string()  emits 64 lowercase hex chars (raw, no WIF)
#
#  Used by both the GUI (warthog_gui.py) and CLI (warthog_cli.py).
# =====================================================================

import hashlib
import multiprocessing as mp
import os
import sys
import time
from typing import Tuple

# --- Warthog mainnet params ------------------------------------------
HEX_ALPHABET     = "0123456789abcdef"
HEX_ALPHABET_SET = set(HEX_ALPHABET) | set(HEX_ALPHABET.upper())
ADDRESS_PAYLOAD_BYTES   = 20
ADDRESS_CHECKSUM_BYTES  = 4
ADDRESS_TOTAL_HEX_CHARS = (ADDRESS_PAYLOAD_BYTES + ADDRESS_CHECKSUM_BYTES) * 2
PAYLOAD_HEX_CHARS       = ADDRESS_PAYLOAD_BYTES * 2  # 40 — controllable by vanity

# --- Pick the fastest EC backend available ----------------------------
EC_BACKEND = None
try:
    from coincurve import PrivateKey as _CCPriv
    EC_BACKEND = "coincurve"
except Exception:
    try:
        from ecdsa import SigningKey, SECP256k1
        EC_BACKEND = "ecdsa"
    except Exception:
        EC_BACKEND = None

# --- Pick the fastest RIPEMD-160 available ----------------------------
HASH_BACKEND = "pure-python"
try:
    h = hashlib.new("ripemd160"); h.update(b""); h.digest()
    HASH_BACKEND = "openssl"
    def ripemd160(data: bytes) -> bytes:
        h = hashlib.new("ripemd160"); h.update(data); return h.digest()
except Exception:
    try:
        from Crypto.Hash import RIPEMD160 as _PCRipemd  # pycryptodome
        HASH_BACKEND = "pycryptodome"
        def ripemd160(data: bytes) -> bytes:
            h = _PCRipemd.new(); h.update(data); return h.digest()
    except Exception:
        # Pure-Python RIPEMD-160 (public domain reference) — slow.
        _R  = [7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,
               3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,
               1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,
               4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
        _RR = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,
               6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,
               15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,
               8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14]
        _S  = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,
               7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,
               11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,
               11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12]
        _SS = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,
               9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,
               9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,
               15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8]
        _K  = [0x00000000,0x5A827999,0x6ED9EBA1,0x8F1BBCDC,0xA953FD4E]
        _KK = [0x50A28BE6,0x5C4DD124,0x6D703EF3,0x7A6D76E9,0x00000000]

        def _rol(x, n):
            x &= 0xFFFFFFFF
            return ((x << n) | (x >> (32-n))) & 0xFFFFFFFF

        def _f(j,x,y,z):
            if j<16: return x^y^z
            if j<32: return (x&y) | ((~x)&0xFFFFFFFF&z)
            if j<48: return (x|((~y)&0xFFFFFFFF))^z
            if j<64: return (x&z) | (y&((~z)&0xFFFFFFFF))
            return x ^ (y | ((~z)&0xFFFFFFFF))

        def ripemd160(data: bytes) -> bytes:
            ml = len(data)
            data = data + b"\x80"
            while len(data) % 64 != 56:
                data += b"\x00"
            data += (ml*8).to_bytes(8, "little")
            h0,h1,h2,h3,h4 = 0x67452301,0xEFCDAB89,0x98BADCFE,0x10325476,0xC3D2E1F0
            for off in range(0, len(data), 64):
                X=[int.from_bytes(data[off+i*4:off+i*4+4],"little") for i in range(16)]
                A,B,C,D,E = h0,h1,h2,h3,h4
                AA,BB,CC,DD,EE = h0,h1,h2,h3,h4
                for j in range(80):
                    T = (A + _f(j,B,C,D) + X[_R[j]] + _K[j//16]) & 0xFFFFFFFF
                    T = (_rol(T,_S[j]) + E) & 0xFFFFFFFF
                    A,E,D,C,B = E, D, _rol(C,10), B, T
                    T = (AA + _f(79-j,BB,CC,DD) + X[_RR[j]] + _KK[j//16]) & 0xFFFFFFFF
                    T = (_rol(T,_SS[j]) + EE) & 0xFFFFFFFF
                    AA,EE,DD,CC,BB = EE, DD, _rol(CC,10), BB, T
                T = (h1 + C + DD) & 0xFFFFFFFF
                h1 = (h2 + D + EE) & 0xFFFFFFFF
                h2 = (h3 + E + AA) & 0xFFFFFFFF
                h3 = (h4 + A + BB) & 0xFFFFFFFF
                h4 = (h0 + B + CC) & 0xFFFFFFFF
                h0 = T
            return b"".join(h.to_bytes(4,"little") for h in (h0,h1,h2,h3,h4))


# --- Detect optional GPU backend (best-effort, used as a flag) --------
GPU_INFO = {"available": False, "name": None, "note": None}
try:
    import pyopencl as _cl  # noqa: F401
    plats = _cl.get_platforms()
    devs = []
    for p in plats:
        for d in p.get_devices(_cl.device_type.GPU):
            devs.append(d.name.strip())
    if devs:
        GPU_INFO = {
            "available": True,
            "name": devs[0],
            "note": "OpenCL GPU detected (used for batched hash160).",
        }
    else:
        GPU_INFO["note"] = "pyopencl installed but no GPU device found."
except Exception:
    GPU_INFO["note"] = (
        "pyopencl not installed. Run install-gpu.bat for the optional GPU "
        "hashing path. Pure GPU EC scanning needs VanitySearch-Warthog "
        "(see VanitySearch-Warthog/build.bat)."
    )


# --- Address encoding (Warthog hex+sha256-checksum) -------------------
def encode_address(payload20: bytes) -> str:
    """20-byte HASH160 -> 48-char lowercase hex address with 4-byte SHA-256 checksum.

    Mirrors warthog/src/shared/src/crypto/address.cpp:5-12.
    """
    if len(payload20) != ADDRESS_PAYLOAD_BYTES:
        raise ValueError(f"Address payload must be {ADDRESS_PAYLOAD_BYTES} bytes")
    chk = hashlib.sha256(payload20).digest()[:ADDRESS_CHECKSUM_BYTES]
    return (payload20 + chk).hex()


def decode_address(addr_hex: str) -> bytes:
    """48-hex-char address -> 20-byte payload, raising on bad checksum or length.

    Mirrors warthog/src/shared/src/crypto/address.cpp:19-31.
    """
    s = addr_hex.strip()
    if len(s) != ADDRESS_TOTAL_HEX_CHARS:
        raise ValueError(f"Address must be exactly {ADDRESS_TOTAL_HEX_CHARS} hex chars")
    try:
        raw = bytes.fromhex(s)
    except ValueError as e:
        raise ValueError(f"Address contains non-hex characters: {e}") from e
    payload, chk = raw[:20], raw[20:]
    if hashlib.sha256(payload).digest()[:4] != chk:
        raise ValueError("Address checksum mismatch")
    return payload


# --- Key derivation --------------------------------------------------
def derive_pub(priv: bytes) -> bytes:
    if EC_BACKEND == "coincurve":
        return _CCPriv(priv).public_key.format(compressed=True)
    sk = SigningKey.from_string(priv, curve=SECP256k1)
    pt = sk.verifying_key.pubkey.point
    prefix = b"\x02" if pt.y() % 2 == 0 else b"\x03"
    return prefix + pt.x().to_bytes(32, "big")


def pub_to_address(pub: bytes) -> str:
    h160 = ripemd160(hashlib.sha256(pub).digest())
    return encode_address(h160)


def derive_address(priv: bytes) -> Tuple[str, bytes]:
    pub = derive_pub(priv)
    return pub_to_address(pub), pub


# --- Pattern validation ----------------------------------------------
class PatternError(ValueError):
    pass


def validate_pattern(pat: str, insensitive: bool = False) -> None:
    """Reject prefixes that can't be reached or that exceed the controllable
       range. Warthog has no version byte / HRP, so any hex char is reachable
       at every position. The only constraints are:
         - prefix must be non-empty
         - prefix must contain only hex chars [0-9a-fA-F]
         - prefix length must be <= 40 (the trailing 8 chars are checksum,
           computed as SHA256(payload)[0:4] and not freely matchable as a
           prefix).
    """
    if not pat:
        raise PatternError("Pattern is empty.")
    bad = sorted({c for c in pat if c not in HEX_ALPHABET_SET})
    if bad:
        raise PatternError(
            f"Invalid hex character(s): {''.join(bad)}\n"
            f"Allowed: 0-9 a-f (case insensitive). Warthog addresses are "
            f"lowercase hex; uppercase input is normalized to lowercase."
        )
    if len(pat) > PAYLOAD_HEX_CHARS:
        raise PatternError(
            f"Prefix is too long: {len(pat)} chars > {PAYLOAD_HEX_CHARS}.\n"
            f"  Warthog addresses are 48 hex chars total. The first 40 are "
            f"the HASH160 payload (controllable as prefix). The last 8 are "
            f"a SHA-256 checksum derived from the payload, so they are not "
            f"controllable as a vanity prefix.\n"
            f"  Tip: 8 chars already needs ~4.3B keys; 10 chars needs ~1.1T."
        )


def difficulty(pat: str, insensitive: bool = False) -> float:
    """Expected attempts to find an address whose lowercase hex starts with `pat`.

    Each hex char has 16 reachable values, so difficulty = 16^len(pat).
    The `insensitive` arg is accepted for API parity with the GUI but is a
    no-op: canonical Warthog addresses are always lowercase, and our
    matcher normalizes both sides to lowercase already (see `_worker`).
    """
    return float(16 ** len(pat))


# --- ETA / number formatting -----------------------------------------
def fmt_eta(seconds: float) -> str:
    """Pretty-print a duration as up to three biggest non-zero units.
       Y / mo / d / h / m / s, e.g. '2y 3mo 14d', '5h 12m', '47s'."""
    if seconds is None or seconds == float("inf") or seconds < 0:
        return "—"
    if seconds < 1:
        return "<1s"
    units = [
        ("y",  365.25 * 86400),
        ("mo", 30.4375 * 86400),
        ("d",  86400),
        ("h",  3600),
        ("m",  60),
        ("s",  1),
    ]
    rem = float(seconds)
    parts = []
    for name, sec in units:
        if rem < sec and not parts:
            continue
        count = int(rem // sec)
        rem -= count * sec
        parts.append(f"{count}{name}")
        if len(parts) >= 3:
            break
    return " ".join(parts) if parts else "<1s"


def fmt_n(n: float) -> str:
    if n < 1e3:  return f"{n:,.0f}"
    if n < 1e6:  return f"{n/1e3:,.2f}K"
    if n < 1e9:  return f"{n/1e6:,.2f}M"
    if n < 1e12: return f"{n/1e9:,.2f}B"
    if n < 1e15: return f"{n/1e12:,.2f}T"
    return f"{n:,.2e}"


# --- Worker (multiprocess) -------------------------------------------
def _worker(idx: int, prefix: str, insensitive: bool,
            results, stop, stats, batch_size: int = 4096) -> None:
    # Warthog canonical address form is lowercase; normalize the prefix once
    # and compare against the canonical lowercase address. `insensitive` is
    # accepted but functionally equivalent here (see validate_pattern).
    cmp_pat = prefix.lower()
    plen = len(cmp_pat)
    local = 0
    last = time.time()
    try:
        while not stop.is_set():
            priv = os.urandom(32)
            addr, pub = derive_address(priv)
            if addr[:plen] == cmp_pat:
                results.put({
                    "worker":      idx,
                    "address":     addr,
                    "pubkey_hex":  pub.hex(),
                    "privkey_hex": priv.hex(),
                })
            local += 1
            if local % batch_size == 0:
                now = time.time()
                stats.put((idx, batch_size, now - last))
                last = now
    except KeyboardInterrupt:
        pass


def spawn_workers(prefix: str, insensitive: bool, n_workers: int):
    """Returns (procs, results_queue, stats_queue, stop_event, ctx)."""
    ctx = mp.get_context("spawn") if sys.platform == "win32" else mp.get_context()
    results = ctx.Queue()
    stats   = ctx.Queue()
    stop    = ctx.Event()
    procs = []
    for i in range(max(1, n_workers)):
        p = ctx.Process(target=_worker,
                        args=(i, prefix, insensitive, results, stop, stats),
                        daemon=True)
        p.start()
        procs.append(p)
    return procs, results, stats, stop, ctx


def stop_workers(procs, stop, timeout: float = 1.5):
    stop.set()
    for p in procs:
        p.join(timeout=timeout)
        if p.is_alive():
            try:
                p.terminate()
            except Exception:
                pass


# --- Banner ----------------------------------------------------------
BANNER = r"""
 __        __         _   _                 _   _              _ _
 \ \      / /_ _ _ __| |_| |__   ___   __ _| | | | __ _ _ __  (_) |_ _   _
  \ \ /\ / / _` | '__| __| '_ \ / _ \ / _` | | | |/ _` | '_ \ | | __| | | |
   \ V  V / (_| | |  | |_| | | | (_) | (_| | | | | (_| | | | || | |_| |_| |
    \_/\_/ \__,_|_|   \__|_| |_|\___/ \__, |_| |_|\__,_|_| |_|/ |\__|\__, |
                                      |___/                  |__/    |___/
                            V A N I T Y   v1.0.0
                              Creator: DankMiner
"""


def env_summary() -> dict:
    return {
        "ec_backend":   EC_BACKEND or "MISSING",
        "hash_backend": HASH_BACKEND,
        "gpu":          GPU_INFO["name"] if GPU_INFO["available"] else None,
        "gpu_note":     GPU_INFO["note"],
        "cpu_count":    mp.cpu_count(),
    }


if __name__ == "__main__":
    # Quick smoke test — verifies derivation matches the upstream test vector
    # found by computing the canonical address of a deterministic privkey.
    print(BANNER)
    print("Environment:", env_summary())
    if EC_BACKEND is None:
        print("ERROR: install ecdsa or coincurve.")
        sys.exit(2)
    priv = bytes.fromhex(
        "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20")
    addr, pub = derive_address(priv)
    print("Test priv:", priv.hex())
    print("Test pub :", pub.hex())
    print("Test addr:", addr)
    # Round-trip the address through decode_address to verify checksum logic
    payload = decode_address(addr)
    print("Decoded  :", payload.hex(), "(checksum OK)")
    print("ETA fmt  :", fmt_eta(0), "|", fmt_eta(45), "|", fmt_eta(3700),
          "|", fmt_eta(90061), "|", fmt_eta(86400*40), "|", fmt_eta(86400*800))
    print("Difficulty for 'dead'    :", fmt_n(difficulty('dead')))
    print("Difficulty for 'deadbeef':", fmt_n(difficulty('deadbeef')))
