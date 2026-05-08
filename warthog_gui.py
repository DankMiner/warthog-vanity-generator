#!/usr/bin/env python3
# =====================================================================
#  Warthog Vanity GUI  v1.0.0
#  Creator: DankMiner
#
#  Tusked-boar / dark-coal-and-gold theme. Tkinter front-end for
#  warthog_engine (CPU) and warthog_gpu_runner (GPU).
#
#  Drop "warthog_logo.png" next to this file for the header logo, and
#  "warthog_logo.ico" for the titlebar / taskbar icon.
# =====================================================================

import json
import multiprocessing as mp
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import warthog_engine as eng
import warthog_gpu_runner as gpu_runner


APP_TITLE = "Warthog Vanity Generator  v1.0.0  -  Creator: DankMiner"
LOGO_FILENAME = "warthog_logo.png"
ICON_FILENAME = "warthog_logo.ico"


# ---------------- Warthog "coal & gold" palette -----------------------
# Sampled from warthog_logo.png — dominant tones:
#   coal shadow     : #181820 .. #282018 (near-black with warm/violet tint)
#   tusked gold     : #f8b810 .. #ffce40 (pure brand gold)
#   warm bronze     : #886018 .. #c89010 (mid-luminance accents)
#   sage / patina   : #587030 .. #88a040 (cool counter-accent for 'OK' state)
THEME = {
    "bg":          "#0e0a04",   # darkest coal
    "bg_panel":    "#1c1408",   # mid-coal panel
    "bg_field":    "#080500",   # near-black input fields
    "bg_text":     "#0a0600",   # results panel
    "fg":          "#d4a868",   # warm cream-brown text
    "fg_dim":      "#806040",   # dim text
    "fg_disabled": "#503820",
    "gold":        "#f8b810",   # brand gold (tusks)
    "gold_hi":     "#ffce40",   # brightened gold
    "gold_dark":   "#7a5808",
    "bronze":      "#c89010",
    "sage":        "#88a040",   # patina accent for 'OK' state
    "sage_hi":     "#b8d860",
    "sage_dark":   "#384818",
    "amber":       "#e8c878",   # warm cream-gold for stat readouts
    "border":      "#806038",   # weathered metal frame
    "border_dark": "#382818",
    "danger":      "#c04020",
    "ok":          "#b8d860",
}

FONT_TITLE_FAMILY = "Consolas"
FONT_BODY_FAMILY  = "Consolas"


def _font(size, bold=False):
    return (FONT_BODY_FAMILY, size, "bold" if bold else "normal")


# ---------------- Custom widgets --------------------------------------
class GoldButton(tk.Canvas):
    """A flat brushed-gold button with hover/press feedback. Matches the
       Warthog brand: deep coal frame, brand-gold face, bronze underline."""
    def __init__(self, master, text="", command=None,
                 width=110, height=32, color="gold",
                 enabled=True, font=None, **kw):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0,
                         bg=master.cget("bg") if "bg" not in kw else kw["bg"])
        self._text = text
        self._command = command
        self._cw, self._ch = width, height
        self._color = color
        self._enabled = enabled
        self._hover = False
        self._press = False
        self._font = font or _font(10, bold=True)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def configure_text(self, text):
        self._text = text; self._draw()

    def set_enabled(self, on: bool):
        self._enabled = on; self._draw()

    def _palette(self):
        if not self._enabled:
            return (THEME["border_dark"], THEME["fg_disabled"], THEME["border"])
        if self._color == "gold":
            base = THEME["gold"]; hi = THEME["gold_hi"]
        elif self._color == "sage":
            base = THEME["sage"]; hi = THEME["sage_hi"]
        elif self._color == "bronze":
            base = THEME["bronze"]; hi = THEME["gold_hi"]
        else:
            base = THEME["amber"]; hi = THEME["gold_hi"]
        bg = hi if (self._hover or self._press) else base
        fg = "#1a0f04"
        border = THEME["border"]
        return bg, fg, border

    def _draw(self):
        self.delete("all")
        bg, fg, border = self._palette()
        # outer dark frame
        self.create_rectangle(0, 0, self._cw-1, self._ch-1,
                              fill=THEME["border_dark"], outline="")
        pad = 2 if not self._press else 3
        self.create_rectangle(pad, pad, self._cw-pad-1, self._ch-pad-1,
                              fill=bg, outline=border, width=1)
        # bronze underline (brushed-metal streak)
        self.create_line(pad+4, self._ch-pad-3, self._cw-pad-4, self._ch-pad-3,
                         fill=THEME["gold_dark"], width=1)
        # text
        self.create_text(self._cw//2, self._ch//2,
                         text=self._text, fill=fg, font=self._font)

    def _on_enter(self, _): self._hover = True; self._draw()
    def _on_leave(self, _): self._hover = False; self._press = False; self._draw()
    def _on_press(self, _):
        if not self._enabled: return
        self._press = True; self._draw()
    def _on_release(self, _):
        was_press = self._press
        self._press = False; self._draw()
        if was_press and self._enabled and self._command:
            self._command()


# ---------------- Main app --------------------------------------------
class VanityApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x840")
        self.minsize(900, 800)
        self.configure(bg=THEME["bg"])
        self._apply_window_icon()

        self._procs = []
        self._results_q = None
        self._stats_q = None
        self._stop_ev = None
        self._poll_job = None
        self._gpu = None
        self._gpu_pending = []
        self._gpu_status = {"rate_str": "—", "gpu_rate_str": "—",
                            "tried_str": "—", "found": 0,
                            "rate_keys_per_sec": 0,
                            "gpu_rate_keys_per_sec": 0,
                            "tried_keys": 0}

        self._t_start = None
        self._tried = 0
        self._found = 0
        self._target_count = 1
        self._difficulty = 0.0
        self._output_path = None
        self._output_fp = None
        self._mode = "cpu"

        self._logo_image = None  # keep reference so it doesn't get GC'd
        self._setup_styles()
        self._build_ui()
        self._refresh_env()

    # ------------- window icon (titlebar / taskbar / alt-tab) --------
    def _apply_window_icon(self):
        here = os.path.dirname(os.path.abspath(__file__))

        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "DankMiner.WarthogVanity.1.0.0"
                )
            except Exception:
                pass

        ico = os.path.join(here, ICON_FILENAME)
        if os.path.isfile(ico):
            try:
                self.iconbitmap(default=ico)
            except Exception:
                try:
                    self.iconbitmap(ico)
                except Exception:
                    pass

        png = os.path.join(here, LOGO_FILENAME)
        if os.path.isfile(png):
            try:
                from PIL import Image, ImageTk
                im = Image.open(png).convert("RGBA")
                im = im.resize((64, 64), Image.LANCZOS)
                self._icon_photo = ImageTk.PhotoImage(im)
                self.iconphoto(True, self._icon_photo)
            except Exception:
                try:
                    self._icon_photo = tk.PhotoImage(file=png)
                    self.iconphoto(True, self._icon_photo)
                except Exception:
                    pass

    # ------------- canvas-fallback warthog tusk emblem ---------------
    def _draw_warthog_emblem(self, parent, size=84):
        """A stylized golden tusks-on-coal emblem, used if warthog_logo.png
           is missing. Two crossed tusks + a coal disc, brand-gold accents."""
        import math
        c = tk.Canvas(parent, width=size, height=size,
                      highlightthickness=0, bd=0,
                      bg=THEME["bg_panel"])
        cx = cy = size / 2
        outer_r = size / 2 - 2

        # Coal disc background
        c.create_oval(cx-outer_r, cy-outer_r, cx+outer_r, cy+outer_r,
                      fill="#0a0600", outline=THEME["border"], width=1)
        # Inner brushed disc
        ir = outer_r * 0.84
        c.create_oval(cx-ir, cy-ir, cx+ir, cy+ir,
                      fill="#1c1408", outline=THEME["gold_dark"], width=1)

        # Two crossed tusks (curved arcs in gold)
        for sign in (-1, 1):
            pts = []
            for t in range(0, 41):
                u = t / 40.0
                # Arc parameter
                ang = math.pi * (0.10 + 0.80 * u)
                rr = outer_r * (0.45 + 0.30 * (1 - u))
                x = cx + sign * math.cos(ang) * rr - sign * outer_r * 0.10
                y = cy - math.sin(ang) * rr + outer_r * 0.05
                pts.extend([x, y])
            # Tusk shadow
            shadow = [pts[i] + 1 if i % 2 == 0 else pts[i] + 1 for i in range(len(pts))]
            c.create_line(*shadow, fill="#3a2810", width=4, smooth=True)
            # Tusk gold
            c.create_line(*pts, fill=THEME["gold"], width=3, smooth=True,
                          capstyle="round")
            # Tusk highlight
            c.create_line(*pts[:24], fill=THEME["gold_hi"], width=1, smooth=True)

        # Center glyph: stylized "W" in gold
        c.create_text(cx+1, cy+1, text="W", fill="#1a0f04",
                      font=("Georgia", int(size*0.42), "bold italic"))
        c.create_text(cx,   cy,   text="W", fill=THEME["gold_hi"],
                      font=("Georgia", int(size*0.42), "bold italic"))
        return c

    # ------------- ttk theming ---------------------------------------
    def _setup_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")  # most customizable base
        except tk.TclError:
            pass

        s.configure(".",
                    background=THEME["bg"],
                    foreground=THEME["fg"],
                    fieldbackground=THEME["bg_field"],
                    bordercolor=THEME["border"],
                    lightcolor=THEME["border"],
                    darkcolor=THEME["border_dark"],
                    troughcolor=THEME["bg_field"],
                    font=_font(10))
        s.configure("TFrame", background=THEME["bg"])
        s.configure("Panel.TFrame", background=THEME["bg_panel"])
        s.configure("TLabel", background=THEME["bg"], foreground=THEME["fg"])
        s.configure("Panel.TLabel", background=THEME["bg_panel"], foreground=THEME["fg"])
        s.configure("Dim.TLabel", background=THEME["bg_panel"], foreground=THEME["fg_dim"])
        s.configure("Gold.TLabel", background=THEME["bg_panel"], foreground=THEME["gold_hi"], font=_font(10, bold=True))
        s.configure("Sage.TLabel", background=THEME["bg_panel"], foreground=THEME["sage_hi"], font=_font(10, bold=True))
        s.configure("Amber.TLabel", background=THEME["bg_panel"], foreground=THEME["amber"], font=_font(10, bold=True))
        s.configure("Danger.TLabel", background=THEME["bg_panel"], foreground=THEME["danger"], font=_font(10, bold=True))

        # LabelFrame (panels)
        s.configure("TLabelframe",
                    background=THEME["bg_panel"],
                    foreground=THEME["gold_hi"],
                    bordercolor=THEME["border"])
        s.configure("TLabelframe.Label",
                    background=THEME["bg"],
                    foreground=THEME["gold_hi"],
                    font=_font(10, bold=True))

        # Entry / Spinbox
        s.configure("TEntry",
                    fieldbackground=THEME["bg_field"],
                    foreground=THEME["amber"],
                    insertcolor=THEME["amber"],
                    bordercolor=THEME["border"],
                    lightcolor=THEME["border"],
                    darkcolor=THEME["border_dark"])
        s.configure("TSpinbox",
                    fieldbackground=THEME["bg_field"],
                    foreground=THEME["amber"],
                    background=THEME["bg_panel"],
                    arrowcolor=THEME["gold_hi"],
                    bordercolor=THEME["border"])
        s.map("TSpinbox",
              fieldbackground=[("readonly", THEME["bg_field"])])

        # Checkbutton
        s.configure("TCheckbutton",
                    background=THEME["bg_panel"],
                    foreground=THEME["fg"],
                    indicatorbackground=THEME["bg_field"],
                    indicatorforeground=THEME["sage_hi"],
                    focuscolor=THEME["bg_panel"])
        s.map("TCheckbutton",
              background=[("active", THEME["bg_panel"])],
              foreground=[("disabled", THEME["fg_disabled"])])

        # Button
        s.configure("TButton",
                    background=THEME["gold_dark"],
                    foreground=THEME["fg"],
                    bordercolor=THEME["border"])
        s.map("TButton",
              background=[("active", THEME["gold"]),
                          ("pressed", THEME["gold_dark"])])

    # ------------- UI layout -----------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # ----------- Header (logo + title bar) ----------------------
        header = tk.Frame(self, bg=THEME["bg_panel"], height=92,
                          highlightthickness=1, highlightbackground=THEME["border"])
        header.pack(side="top", fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        logo_path = os.path.join(os.path.dirname(__file__), LOGO_FILENAME)
        logo_loaded = False
        if os.path.isfile(logo_path):
            try:
                from PIL import Image, ImageTk
                im = Image.open(logo_path).convert("RGBA")
                target_h = 84
                ratio = target_h / im.height
                im = im.resize((int(im.width * ratio), target_h),
                               Image.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(im)
                tk.Label(header, image=self._logo_image,
                         bg=THEME["bg_panel"], bd=0).pack(side="left", padx=8, pady=2)
                logo_loaded = True
            except Exception:
                try:
                    self._logo_image = tk.PhotoImage(file=logo_path)
                    w = self._logo_image.width()
                    if w > 90:
                        factor = max(1, w // 80)
                        self._logo_image = self._logo_image.subsample(factor, factor)
                    tk.Label(header, image=self._logo_image,
                             bg=THEME["bg_panel"], bd=0).pack(side="left", padx=8, pady=4)
                    logo_loaded = True
                except Exception:
                    self._logo_image = None
        if not logo_loaded:
            self._draw_warthog_emblem(header).pack(side="left", padx=8, pady=4)

        title_box = tk.Frame(header, bg=THEME["bg_panel"])
        title_box.pack(side="left", fill="y", padx=(8 if self._logo_image else 16, 0), pady=0)

        tk.Label(title_box, text="WARTHOG VANITY",
                 bg=THEME["bg_panel"], fg=THEME["gold_hi"],
                 font=(FONT_TITLE_FAMILY, 22, "bold")).pack(anchor="w")
        tk.Label(title_box, text="GENERATOR",
                 bg=THEME["bg_panel"], fg=THEME["sage_hi"],
                 font=(FONT_TITLE_FAMILY, 18, "bold")).pack(anchor="w")

        right = tk.Frame(header, bg=THEME["bg_panel"])
        right.pack(side="right", fill="y", padx=12)
        tk.Label(right, text="v1.0.0", bg=THEME["bg_panel"],
                 fg=THEME["amber"], font=_font(11, bold=True)).pack(anchor="e", pady=(14,0))
        tk.Label(right, text="Creator: DankMiner", bg=THEME["bg_panel"],
                 fg=THEME["fg_dim"], font=_font(9)).pack(anchor="e")
        tk.Label(right,
                 text="The past can hurt. But the way I see it,\n"
                      "you can either run from it or learn from it.",
                 bg=THEME["bg_panel"], fg=THEME["gold"],
                 font=(FONT_TITLE_FAMILY, 9, "italic"),
                 justify="right").pack(anchor="e")

        # divider strip ("brushed seam")
        seam = tk.Frame(self, bg=THEME["gold_dark"], height=2)
        seam.pack(side="top", fill="x")
        seam2 = tk.Frame(self, bg=THEME["border_dark"], height=1)
        seam2.pack(side="top", fill="x")

        # ----------- Search panel -----------------------------------
        body = tk.Frame(self, bg=THEME["bg"])
        body.pack(side="top", fill="both", expand=True, padx=10, pady=8)

        frm = ttk.LabelFrame(body, text="  TARGET PREFIX  ", padding=8)
        frm.pack(side="top", fill="x", pady=4)

        ttk.Label(frm, text="Vanity prefix:", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", **pad)
        self.var_prefix = tk.StringVar(value="dead")
        self.ent_prefix = tk.Entry(frm, textvariable=self.var_prefix,
                              width=28, font=(FONT_BODY_FAMILY, 13, "bold"),
                              bg=THEME["bg_field"], fg=THEME["amber"],
                              insertbackground=THEME["amber"],
                              bd=0, highlightthickness=2,
                              highlightbackground=THEME["border"],
                              highlightcolor=THEME["gold_hi"],
                              relief="flat")
        self.ent_prefix.grid(row=0, column=1, sticky="we", **pad)
        self.ent_prefix.bind("<KeyRelease>", lambda e: self._update_estimate())

        ttk.Label(frm, text="(hex chars 0-9 a-f, max 40 chars)",
                  style="Dim.TLabel").grid(row=0, column=2, sticky="w", **pad)

        # Case-insensitive is a functional no-op for Warthog hex addresses
        # (canonical form is always lowercase, uppercase input is silently
        # lowercased before search), so the checkbox is hidden. The
        # BooleanVar stays for engine-API parity.
        self.var_insensitive = tk.BooleanVar(value=False)

        ttk.Label(frm, text="Find this many:", style="Panel.TLabel").grid(
            row=2, column=0, sticky="w", **pad)
        self.var_count = tk.IntVar(value=1)
        ttk.Spinbox(frm, from_=1, to=999, textvariable=self.var_count,
                    width=6).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="CPU workers:", style="Panel.TLabel").grid(
            row=3, column=0, sticky="w", **pad)
        cpu_max = max(1, mp.cpu_count())
        self.var_workers = tk.IntVar(value=max(1, cpu_max - 1))
        ttk.Spinbox(frm, from_=1, to=cpu_max, textvariable=self.var_workers,
                    width=6, command=self._update_estimate).grid(
            row=3, column=1, sticky="w", **pad)
        ttk.Label(frm, text=f"(of {cpu_max} cores)", style="Dim.TLabel").grid(
            row=3, column=2, sticky="w", **pad)

        self.var_use_gpu = tk.BooleanVar(value=gpu_runner.is_available())
        gpu_label = ("Use GPU  (VanitySearch-Warthog.exe — 100x+ faster)"
                     if gpu_runner.is_available()
                     else "Use GPU  (build VanitySearch-Warthog first)")
        cb_gpu = ttk.Checkbutton(frm, text=gpu_label,
                                 variable=self.var_use_gpu,
                                 command=self._update_estimate)
        cb_gpu.grid(row=4, column=0, columnspan=3, sticky="w", **pad)
        if not gpu_runner.is_available():
            cb_gpu.state(["disabled"])

        ttk.Label(frm, text="Save hits to file:", style="Panel.TLabel").grid(
            row=5, column=0, sticky="w", **pad)
        out_row = tk.Frame(frm, bg=THEME["bg_panel"])
        out_row.grid(row=5, column=1, columnspan=2, sticky="we", **pad)
        self.var_output = tk.StringVar(value="")
        out_ent = tk.Entry(out_row, textvariable=self.var_output,
                           bg=THEME["bg_field"], fg=THEME["fg"],
                           insertbackground=THEME["fg"], bd=0,
                           highlightthickness=1,
                           highlightbackground=THEME["border"],
                           relief="flat")
        out_ent.pack(side="left", fill="x", expand=True, ipady=2)
        GoldButton(out_row, text="BROWSE", command=self._pick_output,
                   width=92, height=24, color="amber").pack(side="left", padx=4)

        frm.columnconfigure(1, weight=0)
        frm.columnconfigure(2, weight=1)

        # ----------- Estimate strip ---------------------------------
        est = ttk.LabelFrame(body, text="  ESTIMATE  ", padding=8)
        est.pack(side="top", fill="x", pady=4)
        self.lbl_difficulty = ttk.Label(est, text="Difficulty: —",
                                         style="Amber.TLabel", font=_font(11, bold=True))
        self.lbl_difficulty.pack(side="left", padx=10, pady=2)
        self.lbl_eta_est = ttk.Label(est, text="Estimated time: —",
                                      style="Sage.TLabel", font=_font(11, bold=True))
        self.lbl_eta_est.pack(side="left", padx=20, pady=2)

        # ----------- Validation warning (hidden until needed) -------
        self.warn_frame = tk.Frame(body, bg=THEME["bg_panel"],
                                   highlightthickness=1,
                                   highlightbackground=THEME["danger"])
        self.lbl_warn = tk.Label(self.warn_frame, text="",
                                 bg=THEME["bg_panel"], fg=THEME["danger"],
                                 font=_font(10, bold=True), justify="left",
                                 anchor="w", wraplength=820)
        self.lbl_warn.pack(side="left", fill="x", expand=True, padx=10, pady=6)

        # ----------- Buttons ----------------------------------------
        btns = tk.Frame(body, bg=THEME["bg"])
        btns.pack(side="top", fill="x", pady=6)
        self.btn_start = GoldButton(btns, text="START SEARCH",
                                    command=self._start, width=140, height=36,
                                    color="sage",
                                    font=_font(11, bold=True))
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = GoldButton(btns, text="STOP",
                                   command=self._stop_user, width=90, height=36,
                                   color="gold", enabled=False,
                                   font=_font(11, bold=True))
        self.btn_stop.pack(side="left", padx=4)
        GoldButton(btns, text="EDIT SCRIPT",
                   command=self._open_in_notepad, width=110, height=36,
                   color="amber",
                   font=_font(10, bold=True)).pack(side="right", padx=4)

        # ----------- Live status ------------------------------------
        live = ttk.LabelFrame(body, text="  LIVE STATUS  ", padding=8)
        live.pack(side="top", fill="x", pady=4)
        self.lbl_state = ttk.Label(live, text="Idle.",
                                    style="Gold.TLabel", font=_font(11, bold=True))
        self.lbl_state.grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=2)

        def _stat(parent, label):
            holder = tk.Frame(parent, bg=THEME["bg_panel"])
            ttk.Label(holder, text=label, style="Dim.TLabel",
                      font=_font(9)).pack(anchor="w")
            v = ttk.Label(holder, text="—",
                          style="Amber.TLabel", font=_font(12, bold=True))
            v.pack(anchor="w")
            return holder, v

        h1, self.lbl_tried   = _stat(live, "KEYS TRIED")
        h2, self.lbl_rate    = _stat(live, "RATE")
        h3, self.lbl_elapsed = _stat(live, "ELAPSED")
        h4, self.lbl_eta     = _stat(live, "ETA")
        h1.grid(row=1, column=0, padx=12, pady=4, sticky="w")
        h2.grid(row=1, column=1, padx=12, pady=4, sticky="w")
        h3.grid(row=1, column=2, padx=12, pady=4, sticky="w")
        h4.grid(row=1, column=3, padx=12, pady=4, sticky="w")
        live.columnconfigure((0,1,2,3), weight=1)

        # ----------- Footer / env (packed FIRST at bottom so it always shows)
        envf = ttk.LabelFrame(body, text="  ENVIRONMENT  ", padding=6)
        envf.pack(side="bottom", fill="x", pady=4)
        self.lbl_env = ttk.Label(envf, text="", style="Panel.TLabel",
                                  font=(FONT_BODY_FAMILY, 9), justify="left")
        self.lbl_env.pack(anchor="w", padx=6, pady=2)

        # ----------- Results (expands into remaining space) ---------
        res = ttk.LabelFrame(body, text="  MATCHES  ", padding=4)
        res.pack(side="top", fill="both", expand=True, pady=4)
        self.txt = tk.Text(res, height=8,
                           bg=THEME["bg_text"], fg=THEME["amber"],
                           insertbackground=THEME["amber"],
                           bd=0, highlightthickness=1,
                           highlightbackground=THEME["border"],
                           font=(FONT_BODY_FAMILY, 10), wrap="word",
                           selectbackground=THEME["gold_dark"])
        self.txt.pack(fill="both", expand=True, padx=2, pady=2)
        self.txt.tag_config("hit_addr", foreground=THEME["sage_hi"], font=_font(10, bold=True))
        self.txt.tag_config("hit_priv", foreground=THEME["gold_hi"])
        self.txt.tag_config("hit_hex",  foreground=THEME["fg"])
        self.txt.tag_config("dim",      foreground=THEME["fg_dim"])
        self.txt.tag_config("hdr",      foreground=THEME["amber"], font=_font(10, bold=True))
        self.txt.insert("end", "  Warthog vanity hits will appear here.\n", "dim")
        self.txt.insert("end", "  Treat your private keys like your left tusk. Don't lose them.\n\n", "dim")
        self.txt.config(state="disabled")

        self._update_estimate()

    # ------------- helpers -------------------------------------------
    def _refresh_env(self):
        info = eng.env_summary()
        gpu_exe = gpu_runner.find_exe()
        gpu_status = (
            "READY (VanitySearch-Warthog.exe found)"
            if gpu_exe else
            "NOT BUILT — see VanitySearch-Warthog/build.bat"
        )
        gpu_dev = info["gpu"] or "(none detected)"
        text = (
            f"CPU backend  :  EC = {info['ec_backend']}    "
            f"hash = {info['hash_backend']}    cores = {info['cpu_count']}\n"
            f"GPU device   :  {gpu_dev}\n"
            f"GPU binary   :  {gpu_status}"
        )
        self.lbl_env.config(text=text)

    def _open_in_notepad(self):
        target = os.path.join(os.path.dirname(__file__), "warthog_engine.py")
        try:
            os.startfile(target, "edit")
        except Exception:
            try:
                os.system(f'notepad "{target}"')
            except Exception as e:
                messagebox.showerror("Notepad", str(e))

    def _pick_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".jsonl",
            filetypes=[("JSON Lines", "*.jsonl"), ("All files", "*.*")],
            initialfile="warthog_vanity_hits.jsonl",
        )
        if path:
            self.var_output.set(path)

    def _est_rate_per_worker(self) -> float:
        # Same hash chain as Bitcoin (compressed pubkey -> SHA256 -> RIPEMD160)
        # so per-worker rates match the CapStash measurements.
        if eng.EC_BACKEND == "coincurve" and eng.HASH_BACKEND == "openssl":
            return 35000
        if eng.EC_BACKEND == "coincurve":
            return 18000
        if eng.HASH_BACKEND in ("openssl", "pycryptodome"):
            return 2500
        return 600

    def _est_total_rate(self) -> float:
        if self.var_use_gpu.get() and gpu_runner.is_available():
            # Conservative estimate; observed ~3 Gkey/s on RTX 4070 SUPER
            # for the same HASH160 search VanitySearch performs.
            return 3_000_000_000
        workers = max(1, self.var_workers.get())
        return workers * self._est_rate_per_worker()

    def _update_estimate(self):
        prefix = self.var_prefix.get().strip()
        ins = self.var_insensitive.get()
        try:
            eng.validate_pattern(prefix, ins)
        except eng.PatternError as e:
            self._set_pattern_valid(False, str(e))
            self.lbl_difficulty.config(text="Difficulty: —")
            self.lbl_eta_est.config(text="(fix the prefix to see ETA)")
            self._difficulty = 0.0
            return

        self._set_pattern_valid(True)
        d = eng.difficulty(prefix, ins)
        self.lbl_difficulty.config(text=f"Difficulty: ~1 in {eng.fmt_n(d)} keys")
        rate = self._est_total_rate()
        est_seconds = d / rate if rate > 0 else float("inf")
        backend = "GPU" if (self.var_use_gpu.get() and gpu_runner.is_available()) else "CPU"
        self.lbl_eta_est.config(
            text=f"Estimated: {eng.fmt_eta(est_seconds)}  @  ~{eng.fmt_n(rate)}/s  [{backend}]")
        self._difficulty = d

    def _set_pattern_valid(self, ok: bool, message: str = ""):
        if ok:
            try:
                self.ent_prefix.configure(highlightbackground=THEME["border"],
                                          highlightcolor=THEME["sage_hi"])
            except Exception:
                pass
            try: self.warn_frame.pack_forget()
            except Exception: pass
            try: self.btn_start.set_enabled(True)
            except Exception: pass
        else:
            try:
                self.ent_prefix.configure(highlightbackground=THEME["danger"],
                                          highlightcolor=THEME["danger"])
            except Exception:
                pass
            self.lbl_warn.config(text="⚠  " + message)
            try:
                self.warn_frame.pack(side="top", fill="x", pady=(2, 4),
                                     before=self.btn_start.master)
            except Exception:
                self.warn_frame.pack(side="top", fill="x", pady=(2, 4))
            try: self.btn_start.set_enabled(False)
            except Exception: pass

    # ------------- search lifecycle ----------------------------------
    def _start(self):
        if eng.EC_BACKEND is None:
            messagebox.showerror("Missing dependency",
                                 "Install ecdsa first:\n  pip install ecdsa")
            return
        prefix = self.var_prefix.get().strip().lower()
        ins = self.var_insensitive.get()
        try:
            eng.validate_pattern(prefix, ins)
        except eng.PatternError as e:
            messagebox.showerror("Invalid prefix", str(e))
            return

        out_path = self.var_output.get().strip() or None
        if out_path:
            try:
                self._output_fp = open(out_path, "a", encoding="utf-8")
                self._output_path = out_path
            except OSError as e:
                messagebox.showerror("Output file", str(e))
                return
        else:
            self._output_fp = None
            self._output_path = None

        self._target_count = max(1, self.var_count.get())
        self._tried = 0
        self._found = 0
        self._t_start = time.time()
        self._gpu_pending = []
        self._gpu_status = {"rate_str": "—", "gpu_rate_str": "—",
                            "tried_str": "—", "found": 0,
                            "rate_keys_per_sec": 0,
                            "gpu_rate_keys_per_sec": 0,
                            "tried_keys": 0}

        use_gpu = self.var_use_gpu.get() and gpu_runner.is_available()
        self._mode = "gpu" if use_gpu else "cpu"

        if use_gpu:
            try:
                self._gpu = gpu_runner.GPURunner(stop_after=self._target_count)
                self._gpu.start(
                    prefix, case_insensitive=ins,
                    on_hit=lambda h: self._gpu_pending.append(h),
                    on_status=lambda s: self._gpu_status.update(s),
                    on_done=lambda rc: self._gpu_pending.append({"__done__": rc}),
                )
                self.lbl_state.config(text=f"GPU search running… target = '{prefix}'")
            except Exception as e:
                messagebox.showerror("GPU launch failed", str(e))
                return
        else:
            self._procs, self._results_q, self._stats_q, self._stop_ev, _ = \
                eng.spawn_workers(prefix, ins, self.var_workers.get())
            self.lbl_state.config(text=f"CPU search running… target = '{prefix}'")

        self.btn_start.set_enabled(False)
        self.btn_stop.set_enabled(True)
        self._append_text("\n")
        self._append_text(f"  ── START ── prefix='{prefix}'  mode={self._mode}",
                          "hdr")
        self._append_text(
            f"  workers/path: "
            f"{('gpu='+gpu_runner.find_exe()) if use_gpu else 'cpu_workers='+str(self.var_workers.get())}\n",
            "dim")
        self._poll()

    def _stop_user(self):
        self._stop("stopped")

    def _stop(self, reason: str = "stopped"):
        if self._stop_ev:
            eng.stop_workers(self._procs, self._stop_ev)
            self._stop_ev = None
        if self._gpu:
            try: self._gpu.stop()
            except Exception: pass
            self._gpu = None
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self._output_fp:
            try: self._output_fp.close()
            except Exception: pass
            self._output_fp = None

        elapsed = (time.time() - self._t_start) if self._t_start else 0
        self.btn_start.set_enabled(True)
        self.btn_stop.set_enabled(False)
        if self._mode == "cpu":
            tried_text = eng.fmt_n(self._tried)
        else:
            tried_text = self._gpu_status.get("tried_str", "—")
        self.lbl_state.config(
            text=f"{reason.upper()}.   found={self._found}   "
                 f"tried={tried_text}   elapsed={eng.fmt_eta(elapsed)}"
        )

    def _poll(self):
        if self._mode == "cpu":
            try:
                while True:
                    _, n, _ = self._stats_q.get_nowait()
                    self._tried += n
            except Exception:
                pass
            try:
                while True:
                    hit = self._results_q.get_nowait()
                    self._found += 1
                    self._render_hit(hit)
                    if self._output_fp:
                        self._output_fp.write(json.dumps(hit) + "\n")
                        self._output_fp.flush()
                    if self._found >= self._target_count:
                        self._stop("done")
                        return
            except Exception:
                pass
        else:
            while self._gpu_pending:
                ev = self._gpu_pending.pop(0)
                if "__done__" in ev:
                    self._stop("done" if self._found >= self._target_count else "exited")
                    return
                self._found += 1
                self._render_hit(ev)
                if self._output_fp:
                    self._output_fp.write(json.dumps(ev) + "\n")
                    self._output_fp.flush()
                if self._found >= self._target_count:
                    self._stop("done")
                    return

        elapsed = time.time() - self._t_start
        if self._mode == "cpu":
            rate = self._tried / elapsed if elapsed > 0 else 0.0
            remaining = max(0, self._difficulty - self._tried) if self._difficulty else 0
            eta = remaining / rate if rate > 0 else float("inf")
            self.lbl_tried.config(text=eng.fmt_n(self._tried))
            self.lbl_rate.config(text=f"{eng.fmt_n(rate)}/s")
        else:
            self.lbl_tried.config(text=self._gpu_status.get("tried_str", "—"))
            gpu_str = self._gpu_status.get("gpu_rate_str", "—")
            self.lbl_rate.config(text=gpu_str + "  [GPU]")
            rate = self._gpu_status.get("gpu_rate_keys_per_sec", 0) or \
                   self._gpu_status.get("rate_keys_per_sec", 0)
            tried = self._gpu_status.get("tried_keys", 0)
            remaining = max(0, self._difficulty - tried) if self._difficulty else 0
            eta = remaining / rate if rate > 0 else float("inf")

        self.lbl_elapsed.config(text=eng.fmt_eta(elapsed))
        self.lbl_eta.config(text=eng.fmt_eta(eta))
        self._poll_job = self.after(250, self._poll)

    def _render_hit(self, hit):
        self._append_text(
            f"\n  [HIT {self._found}/{self._target_count}]\n", "hdr")
        self._append_text(f"    Address     : ", "dim")
        self._append_text(f"{hit['address']}\n", "hit_addr")
        self._append_text(f"    Private hex : ", "dim")
        self._append_text(f"{hit['privkey_hex']}\n", "hit_priv")
        if hit.get("pubkey_hex"):
            self._append_text(f"    Pubkey      : ", "dim")
            self._append_text(f"{hit['pubkey_hex']}\n", "hit_hex")
        self._append_text(
            f"    Import with : wart-wallet --restore {hit['privkey_hex']} "
            f"-f my-wallet.json\n", "dim")

    def _append_text(self, s: str, tag: str = None):
        self.txt.config(state="normal")
        if tag:
            self.txt.insert("end", s, tag)
        else:
            self.txt.insert("end", s)
        self.txt.see("end")
        self.txt.config(state="disabled")


def main():
    if eng.EC_BACKEND is None:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(
            "Missing dependency",
            "Neither coincurve nor ecdsa is installed.\n\n"
            "Run install.bat first."
        )
        return 2
    app = VanityApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
