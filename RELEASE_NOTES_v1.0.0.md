# Warthog Vanity Generator — v1.0.0

**Released:** 2026-05-08
**Creator:** DankMiner

---

## Highlights

- First release of a desktop vanity-address generator for Warthog (WART).
- CPU search through `coincurve` / `ecdsa` (auto-detected) plus optional
  CUDA GPU search via the bundled `VanitySearch-Warthog.exe`.
- Tkinter GUI with Warthog "coal & gold" theming, real-time prefix
  validation, and a one-line "import to wallet" recipe shown next to
  every hit.

## Verifying the prebuilt binary

The prebuilt `VanitySearch-Warthog.exe` ships at the top level of the
zip and is GPL-3.0 (forked from VanitySearch). Compute its SHA-256 and
compare:

```text
> certutil -hashfile VanitySearch-Warthog.exe SHA256
SHA256 hash of VanitySearch-Warthog.exe:
c0aa4ccc407c0af9e30ce72ecc19f75e2b34a6b9b30ec6398021f0b3c8ee681d
```

**Expected SHA-256 (v1.0.0):**
`c0aa4ccc407c0af9e30ce72ecc19f75e2b34a6b9b30ec6398021f0b3c8ee681d`

If yours doesn't match, prefer to rebuild from source: `cd
VanitySearch-Warthog && build.bat`. The build is deterministic given
the same MSVC + CUDA toolchain.

If you'd rather build it yourself, follow `README.md` →
"Build VanitySearch-Warthog.exe". The full source is included under
`VanitySearch-Warthog/`.

## What's in the zip

```
warthog-vanity-generator/
├── README.md, CHANGELOG.md, LICENSE
├── docs/screenshots/gui.png
├── Warthog-Vanity.bat, warthog_cli.bat
├── install.bat, install-gpu.bat
├── warthog_engine.py, warthog_gui.py, warthog_cli.py, warthog_gpu_runner.py
├── warthog_logo.png, warthog_logo.ico
├── VanitySearch-Warthog.exe        (prebuilt — RTX 4070 SUPER tested, sm_75-90 fat binary)
└── VanitySearch-Warthog/           (full GPL-3.0 source + build.bat)
```

## Tested on

- Windows 11 Home 26200, RTX 4070 SUPER (sm_89), CUDA 12.8, Visual
  Studio 2022 Community (`v143`), Python 3.14.2 (with coincurve fallback
  to ecdsa) and Python 3.12.

## Known limitations

- The GPU binary requires a hex prefix of length 4-40. Shorter
  prefixes auto-route to the CPU path (which finds a match in
  milliseconds anyway).
- `pyopencl` is only used by the GUI to display the GPU device name. It
  has no effect on actual search throughput — that comes from
  `VanitySearch-Warthog.exe`. If `pyopencl` has no wheel for your
  Python version, the GUI just shows "(none detected)" and works
  otherwise.
- Pure-Python `ripemd160` fallback is *very* slow (only used if both
  OpenSSL and pycryptodome are missing). Stick to OpenSSL or
  pycryptodome.

## Credits

- Upstream Warthog implementation: Pumbaa, Timon & Rafiki.
- VanitySearch: Jean-Luc Pons (GPL-3.0).
- Patches & packaging: **DankMiner**.

> *The past can hurt. But the way I see it, you can either run from it or learn from it.* — Rafiki
