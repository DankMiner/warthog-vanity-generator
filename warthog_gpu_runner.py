#!/usr/bin/env python3
# =====================================================================
#  GPU runner — spawns VanitySearch-Warthog.exe and parses its output.
#  Creator: DankMiner   v1.0.0
#
#  VanitySearch (Jean-Luc Pons), patched for Warthog's address scheme:
#     - 20-byte HASH160 payload, no version byte
#     - hex(payload || SHA256(payload)[0:4]) = 48 lowercase hex chars
#     - private key emitted as raw 64-char hex (no WIF, no checksum)
#
#  Reads bytes (not lines) so the carriage-return rate updates from
#  VanitySearch's Search() loop are captured in real time.
# =====================================================================

import math
import os
import re
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

EXE_NAME = "VanitySearch-Warthog.exe"


def find_exe() -> Optional[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, EXE_NAME)
    return p if os.path.isfile(p) else None


def is_available() -> bool:
    return find_exe() is not None


# Hit format emitted by patched Vanity.cpp:
#   PubAddress: <48-char hex address>
#   Priv (HEX): 0x<64-char hex privkey>
# (No WIF line — Warthog has no WIF format.)
_RE_ADDR = re.compile(r"^PubAddress:\s+([0-9a-fA-F]+)")
_RE_HEX  = re.compile(r"^Priv \(HEX\):\s+0x([0-9A-Fa-f]+)")

# Status line VanitySearch prints (carriage-return updated):
#   [123.45 Mkey/s][GPU 678.90 Mkey/s][Total 2^28.34][...][Found 0]
_RE_RATE_TOTAL = re.compile(
    r"\[\s*([\d.]+)\s*Mkey/s\s*\]"
    r"\s*\[\s*GPU\s*([\d.]+)\s*Mkey/s\s*\]"
    r"\s*\[\s*Total\s*2\^\s*([\d.]+)\s*\]"
)
_RE_FOUND = re.compile(r"\[\s*Found\s+(\d+)\s*\]")


class GPURunner:
    """Drives VanitySearch-Warthog.exe and reports hits via callbacks.

       on_hit(dict)       - {address, privkey_hex, pubkey_hex}
       on_status(dict)    - {rate_str, gpu_rate_str, tried_str,
                             rate_keys_per_sec, tried_keys}
       on_done(int rc)
       on_log(str line)
    """

    def __init__(self, exe_path: str = None, stop_after: int = 0):
        self.exe = exe_path or find_exe()
        if not self.exe:
            raise FileNotFoundError(
                f"{EXE_NAME} not found. Build it first: "
                "VanitySearch-Warthog/build.bat")
        self.stop_after = stop_after
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stop = False
        self._on_hit = self._on_status = self._on_done = self._on_log = None

    def start(self, prefix: str,
              case_insensitive: bool = False,
              gpu_id: int = 0,
              extra_args=None,
              on_hit: Callable = None,
              on_status: Callable = None,
              on_done: Callable = None,
              on_log: Callable = None):
        self._on_hit, self._on_status = on_hit, on_status
        self._on_done, self._on_log = on_done, on_log

        args = [self.exe, "-gpu"]
        if gpu_id != 0:
            args += ["-gpuId", str(gpu_id)]
        # Warthog hex addresses are case-insensitive at the parser level
        # (parse_hex accepts both cases) but the canonical form is lowercase.
        # Always normalize the prefix to lowercase before passing to the GPU
        # binary; the case_insensitive flag is accepted for API parity but
        # functionally a no-op.
        if extra_args:
            args += list(extra_args)
        args += [prefix.lower()]

        self._stop = False
        # NOTE: we deliberately do NOT pass VanitySearch's "-stop" flag.
        # "-stop" makes it exit after the FIRST hit, which breaks the
        # "Find this many = N" feature. Instead, callers count hits and
        # call .stop() to terminate the subprocess once N is reached.
        self._proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            cwd=os.path.dirname(os.path.abspath(self.exe)),
            creationflags=(0x08000000  # CREATE_NO_WINDOW
                           if sys.platform == "win32" else 0),
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def stop(self):
        self._stop = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # -- internal ----------------------------------------------------
    def _read_loop(self):
        buf = bytearray()
        addr = hexkey = None
        try:
            stream = self._proc.stdout
            while not self._stop:
                chunk = stream.read(256)
                if not chunk:
                    break
                buf.extend(chunk)
                while True:
                    idx_n = buf.find(b"\n")
                    idx_r = buf.find(b"\r")
                    if idx_n == -1 and idx_r == -1:
                        break
                    if idx_n == -1:
                        idx = idx_r
                    elif idx_r == -1:
                        idx = idx_n
                    else:
                        idx = min(idx_n, idx_r)
                    raw = bytes(buf[:idx])
                    del buf[:idx + 1]
                    try:
                        line = raw.decode("utf-8", errors="replace").rstrip()
                    except Exception:
                        continue
                    if not line:
                        continue
                    if self._on_log:
                        try: self._on_log(line)
                        except Exception: pass
                    addr, hexkey = self._handle_line(line, addr, hexkey)
        finally:
            rc = self._proc.wait() if self._proc else -1
            if self._on_done:
                try: self._on_done(rc)
                except Exception: pass

    def _handle_line(self, line, addr, hexkey):
        m = _RE_ADDR.match(line)
        if m:
            return m.group(1).lower(), hexkey
        m = _RE_HEX.match(line)
        if m:
            hexkey = m.group(1).lower()
            if addr and self._on_hit:
                try:
                    self._on_hit({
                        "address":     addr,
                        "privkey_hex": hexkey,
                        "pubkey_hex":  "",
                    })
                except Exception:
                    pass
            return None, None

        rm = _RE_RATE_TOTAL.search(line)
        if rm:
            cpu_rate = float(rm.group(1)) * 1e6
            gpu_rate = float(rm.group(2)) * 1e6
            log2_total = float(rm.group(3))
            tried = 2 ** log2_total
            fm = _RE_FOUND.search(line)
            found = int(fm.group(1)) if fm else 0
            if self._on_status:
                try:
                    self._on_status({
                        "rate_str":          f"{cpu_rate/1e6:.2f} Mkey/s",
                        "gpu_rate_str":      f"{gpu_rate/1e6:.2f} Mkey/s",
                        "tried_str":         self._fmt_keys(tried),
                        "rate_keys_per_sec": cpu_rate,
                        "gpu_rate_keys_per_sec": gpu_rate,
                        "tried_keys":        tried,
                        "found":             found,
                    })
                except Exception:
                    pass
        return addr, hexkey

    @staticmethod
    def _fmt_keys(n: float) -> str:
        if n < 1e3:  return f"{n:,.0f}"
        if n < 1e6:  return f"{n/1e3:,.2f}K"
        if n < 1e9:  return f"{n/1e6:,.2f}M"
        if n < 1e12: return f"{n/1e9:,.2f}B"
        return f"{n/1e12:,.2f}T"


if __name__ == "__main__":
    if not is_available():
        print(f"{EXE_NAME} not found.")
        sys.exit(1)
    def on_hit(h): print(f"\n[HIT] {h['address']} | priv {h['privkey_hex']}")
    def on_status(s):
        sys.stdout.write(
            f"\rrate={s['rate_str']:>15}  gpu={s['gpu_rate_str']:>15}  "
            f"tried={s['tried_str']:>10}  found={s['found']}   ")
        sys.stdout.flush()
    def on_done(rc): print(f"\n[exit rc={rc}]")
    r = GPURunner(stop_after=1)
    r.start(sys.argv[1] if len(sys.argv) > 1 else "dead",
            on_hit=on_hit, on_status=on_status, on_done=on_done)
    try:
        while r.is_running():
            time.sleep(0.3)
    except KeyboardInterrupt:
        r.stop()
