"""Build Warthog-Vanity-v1.0.0.zip from this folder.

Excludes:
  - VanitySearch-Warthog/x64/        (build artifacts, ~hundreds of MB)
  - VanitySearch-Warthog/Release*/   (build artifacts)
  - __pycache__, *.pyc
  - this script + _capture_gui.py + any .log files
  - .git, .vscode, .idea
  - existing zip files

Used once during release packaging. Removed from the shipped zip.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
ZIP_NAME = "Warthog-Vanity-v1.0.0.zip"
ZIP_PATH = os.path.join(PARENT, ZIP_NAME)
TOP = "warthog-vanity-generator"  # archive top-level folder name

EXCLUDE_DIRS = {
    "x64", "Release", "ReleaseSM30", "Debug",
    "__pycache__", ".git", ".vscode", ".idea",
}
EXCLUDE_NAMES = {
    "_pack_release.py",
    "_capture_gui.py",
    "_verify_release.py",
    "gpu_test.log",
    "gpu_test2.log",
    "cpu_test.log",
}
EXCLUDE_EXTS = {".pyc", ".pyo", ".jsonl", ".log",
                ".obj", ".pdb", ".ilk", ".exp", ".lib", ".tlog",
                ".idb", ".ipdb", ".iobj"}


def included(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    name = parts[-1]
    if name in EXCLUDE_NAMES:
        return False
    if any(p in EXCLUDE_DIRS for p in parts[:-1]):
        return False
    ext = os.path.splitext(name)[1].lower()
    if ext in EXCLUDE_EXTS:
        return False
    return True


def main():
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    files_added = 0
    total_bytes = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(HERE):
            # Prune excluded dirs in-place so os.walk doesn't descend
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, HERE)
                if not included(rel):
                    continue
                arcname = TOP + "/" + rel.replace("\\", "/")
                zf.write(full, arcname)
                files_added += 1
                total_bytes += os.path.getsize(full)
    size = os.path.getsize(ZIP_PATH)
    print(f"wrote {ZIP_PATH}")
    print(f"  files: {files_added}")
    print(f"  uncompressed: {total_bytes/1e6:.1f} MB")
    print(f"  zip size    : {size/1e6:.1f} MB")
    # Compute SHA-256 of the prebuilt VanitySearch-Warthog.exe
    import hashlib
    exe = os.path.join(HERE, "VanitySearch-Warthog.exe")
    if os.path.isfile(exe):
        h = hashlib.sha256()
        with open(exe, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        print(f"  exe sha256  : {h.hexdigest()}")


if __name__ == "__main__":
    main()
