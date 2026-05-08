"""Render warthog_gui in-process and screenshot it to docs/screenshots/gui.png.

Imports `warthog_gui` directly so the capture always reflects the
current source (no subprocess, no .pyc caching, no risk of grabbing an
unrelated GUI window the user happens to have open).

Used during release packaging. Removed from the shipped zip.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "screenshots", "gui.png")

sys.path.insert(0, HERE)
# Force position so we can find it deterministically and so it doesn't
# overlap a user-launched session.
import warthog_gui  # noqa: E402

GEOM = "+60+30"  # near top-left so the full window fits any screen


def main():
    app = warthog_gui.VanityApp()
    app.geometry(GEOM)
    app.update_idletasks()

    def grab_and_quit():
        app.update_idletasks()
        time.sleep(0.4)  # let WM finalize the geometry
        x = app.winfo_rootx()
        y = app.winfo_rooty()
        w = app.winfo_width()
        h = app.winfo_height()
        # Grab the bbox of *this* Tk window (winfo_rootx/y is the
        # top-left of the client area in screen coords; we expand
        # upward by ~30 px to include the titlebar).
        bbox = (x, max(0, y - 32), x + w, y + h)
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        img.save(OUT, optimize=True)
        print(f"saved {OUT}  ({img.size[0]}x{img.size[1]})")
        app.after(50, app.destroy)

    app.after(700, grab_and_quit)
    app.mainloop()


if __name__ == "__main__":
    main()
