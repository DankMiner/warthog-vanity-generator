# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] — 2026-05-08
First release.

### Added
- Multi-process CPU search engine (`warthog_engine.py`) using
  `coincurve` (or `ecdsa` fallback) + `hashlib.ripemd160` (or
  `pycryptodome` / pure-Python fallbacks).
- Tkinter GUI (`warthog_gui.py`) with the brand "coal & gold" palette,
  multi-resolution `.ico`, `SetCurrentProcessExplicitAppUserModelID` so
  the taskbar binds to the app instead of `pythonw.exe`, real-time
  prefix validation that disables the START button on bad input, live
  status panel for CPU/GPU rate and ETA.
- CLI (`warthog_cli.py`) with the same engine, JSONL output.
- GPU runner (`warthog_gpu_runner.py`) that drives
  `VanitySearch-Warthog.exe`, reading raw bytes so the carriage-return
  rate updates from VanitySearch are captured live.
- Patched VanitySearch source under `VanitySearch-Warthog/`:
  - `Secp256K1::GetAddress` and `GetPrivAddress` rewritten to emit
    Warthog's `hex(hash160 || sha256(hash160)[0:4])` and raw 64-char
    hex (no version byte, no Base58, no WIF).
  - `Vanity::initPrefix` rewritten to parse hex prefixes (4-40 chars).
  - `output()` drops the WIF line.
  - `main.cpp` `RELEASE` bumped to `Warthog-1.0.0 (DankMiner)`,
    `-ca` / `-cp` flags simplified to one address scheme.
  - `fflush(stdout)` after the rate `printf` (carried over from the
    CapStash patch — without it, piped readers see no live updates).
  - `.vcxproj` targets CUDA 12.8, `v143` toolset, multi-arch
    `sm_75/80/86/89/90`.
- Launchers `Warthog-Vanity.bat` (GUI, no console), `warthog_cli.bat`
  (CLI), `install.bat` (Python deps), `install-gpu.bat` (optional
  pyopencl).

### Notes
- Reference upstream Warthog source confirms: secp256k1 + HASH160 +
  hex+SHA256-checksum encoding. See
  `src/shared/src/crypto/{address,crypto}.{hpp,cpp}` in the upstream
  repo. No HRP collision, no parser fallback paths, no version byte.
