"""End-to-end verification for the v1.0.0 release.

Runs the GPU binary against a few prefixes, parses each hit, and checks
that the Python engine derives the SAME address from the SAME private
key and that the address checksum decodes successfully.

Used during release packaging. Removed from the shipped zip.
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "VanitySearch-Warthog.exe")

sys.path.insert(0, HERE)
import warthog_engine as eng  # noqa: E402

RE_ADDR = re.compile(r"^PubAddress:\s+([0-9a-fA-F]{48})\s*$")
RE_PRIV = re.compile(r"^Priv \(HEX\):\s+0x([0-9a-fA-F]+)\s*$")


def run_search(prefix: str, n_hits: int = 3, timeout_s: int = 15):
    proc = subprocess.Popen(
        [EXE, "-gpu", prefix],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=HERE,
        bufsize=1,
        universal_newlines=True,
    )
    hits = []
    pending_addr = None
    deadline = time.time() + timeout_s
    try:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.rstrip()
            m = RE_ADDR.match(line)
            if m:
                pending_addr = m.group(1).lower()
                continue
            m = RE_PRIV.match(line)
            if m and pending_addr:
                hits.append((pending_addr, m.group(1).lower()))
                pending_addr = None
                if len(hits) >= n_hits:
                    break
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    return hits


def main():
    print(f"Verifying {EXE}")
    if not os.path.isfile(EXE):
        print("  MISSING. Build first.")
        return 1
    failures = 0
    for prefix in ("dead", "beef", "dead0"):
        print(f"\n  prefix '{prefix}':")
        hits = run_search(prefix, n_hits=3, timeout_s=15)
        if not hits:
            print(f"    NO HITS (timeout) — investigate")
            failures += 1
            continue
        for addr, priv_hex in hits:
            # 1) prefix must match (lowercase)
            if not addr.startswith(prefix.lower()):
                print(f"    [FAIL] address {addr} does not start with {prefix}")
                failures += 1
                continue
            # 2) privkey must be exactly 64 hex chars (Warthog wallet requirement)
            if len(priv_hex) != 64:
                print(f"    [FAIL] privkey is {len(priv_hex)} chars, want 64: {priv_hex}")
                failures += 1
                continue
            # 3) Python derivation from privkey must match the address
            try:
                priv_bytes = bytes.fromhex(priv_hex)
                py_addr, _ = eng.derive_address(priv_bytes)
            except Exception as e:
                print(f"    [FAIL] Python derive raised: {e}")
                failures += 1
                continue
            if py_addr != addr:
                print(f"    [FAIL] python={py_addr}  cpp={addr}")
                failures += 1
                continue
            # 4) Address checksum must decode
            try:
                eng.decode_address(addr)
            except Exception as e:
                print(f"    [FAIL] address checksum: {e}")
                failures += 1
                continue
            print(f"    [OK] {addr}  (priv {priv_hex[:8]}...{priv_hex[-8:]})")
    print()
    if failures:
        print(f"  {failures} failure(s).")
        return 2
    print("  ALL OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
