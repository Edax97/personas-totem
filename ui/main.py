"""
Kiosk
Host that embeds X11 window apps

Requirements:
  apt install xdotool
  pip install pillow
"""

import tkinter as tk
import subprocess
import threading
import time
import os
import signal
from PIL import Image, ImageTk

# ---------------------------------------------------------------------------
# App definitions — add any graphical app here
# ---------------------------------------------------------------------------
APPS = [
    # {
    #     "id": "people_counter",
    #     "label": "People Counter",
    #     "icon": "👥",
    #     "desc": "Live people counting via OpenCV",
    #     "cmd": ["bash", "start_people_counting.sh"],
    #     # xdotool will search for a window whose name contains this string
    #     "window_title_hint": "People Counter",
    # },
    {
        "id": "text-editor",
        "label": "Text Editor",
        "icon": "",
        "desc": "System text editor",
        "cmd": ["thonny"],          # swap for mousepad, kate, etc.
        "window_title_hint": "Thonny",
    },
    {
        "id": "calculator",
        "label": "Calculator",
        "icon": "",
        "desc": "System calculator",
        "cmd": ["galculator"],
        "window_title_hint": "galculator",
    },
]

# ---------------------------------------------------------------------------
# X11 embed
# ---------------------------------------------------------------------------

def find_window_id(title_hint: str, timeout: float = 8.0) -> int | None:
    """Poll xdotool until a window matching title_hint appears, return its XID."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["xdotool", "search", "--name", title_hint],
            capture_output=True, text=True
        )
        ids = result.stdout.strip().splitlines()
        if ids:
            return int(ids[-1])   # take the most-recently-opened one
        time.sleep(0.25)
    return None

def reparent_window(xid: int, target_xid: int):
    """Re-parent xid into target_xid using xdotool."""
    subprocess.run(["xdotool", "windowreparent", str(xid), str(target_xid)],
                   check=True)

def resize_window(xid: int, w: int, h: int):
    subprocess.run(["xdotool", "windowsize", str(xid), str(w), str(h)])

def move_window(xid: int, x: int, y: int):
    subprocess.run(["xdotool", "windowmove", str(xid), str(x), str(y)])

def remove_decorations(xid: int):
    """Strip title-bar / decorations with xprop (Motif hints)."""
    subprocess.run([
        "xprop", "-id", str(xid),
        "-f", "_MOTIF_WM_HINTS", "32c",
        "-set", "_MOTIF_WM_HINTS", "2, 0, 0, 0, 0"
    ])

# ---------------------------------------------------------------------------
# Main kiosk
# ---------------------------------------------------------------------------
class KioskApp(tk.Tk):
   
    SIDEBAR_W = 280
    BG        = "#0d0f14"
    SIDEBAR   = "#131720"
    TOPBAR_H = 48
    TOPBAR = "#131620"
    ACCENT    = "#00d4ff"
    BTN_NORM  = "#1c2030"
    BTN_ACT   = "#1e3a4a"
    TXT       = "#e8eaf0"
    TXT_DIM   = "#6b7280"
    FONT = "Helvetica"

    def __init__(self):
        super().__init__()
        self.title("Labotec - Visión artificial")
        self.configure(bg=self.BG)
        self.resizable(False, False)
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        self.geometry(f"{w}x{h}")

        self._proc: subprocess.Popen | None = None
        self._embedded_xid: int | None = None
        self._active_btn: tk.Widget | None = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ── Topbar ────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=self.TOPBAR, height=self.TOPBAR_H)
        topbar.pack(side=tk.TOP, fill=tk.X)
        topbar.pack_propagate(False)
        self.toggle_btn = tk.Button(
            topbar,
            text="☰",
            bg=self.TOPBAR,
            fg="white",
            activebackground=self.TOPBAR,
            activeforeground="white",
            font=("Monospace", 28),
            highlightthickness=0,
            bd=0,
            command=self._toggle_sidebar,
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=8, pady=2)
        img = ImageTk.PhotoImage(Image.open("labotec.png").resize((48, 48)))
        img_label = tk.Label(topbar, image=img, bg=self.TOPBAR)
        img_label.image = img
        img_label.pack(side=tk.RIGHT, padx=5, pady=0)
        tk.Label(
            topbar, text="Labotec | Visión artificial", bg=self.TOPBAR,
            fg="white", font=(self.FONT, 12, "bold"),
        ).pack(side=tk.TOP, fill=tk.X, pady=(16, 4))

        self.sidebar_expanded=False
        self.toggle_clicked_time=time.time()
        
        mainframe = tk.Frame(self, bg=self.BG)
        mainframe.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.sidebar = tk.Frame(mainframe, bg=self.SIDEBAR, width=self.SIDEBAR_W)
        self.sidebar.place(x=0, y=0, relheight=1.0, width=0)
        #sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # ── Content area ───────────────────────────────────────────────
        self.content = tk.Frame(mainframe, bg=self.BG)
        self.content.place(x=0, y=0, relwidth=1, relheight=1, width=self.winfo_width())

        # Logo / title
        tk.Label(
            self.sidebar, text="Selecciona app", bg=self.SIDEBAR,
            fg=self.ACCENT, font=(self.FONT, 14, "bold"),
            pady=24
        ).pack(fill=tk.X)

        tk.Frame(self.sidebar, bg="#2a2f3e", height=1).pack(fill=tk.X, padx=16)

        # App buttons
        self._btns = {}
        for app in APPS:
            btn = tk.Button(
                self.sidebar,
                text=f"  {app['icon']+' ' if app['icon'] else ''}{app['label']}",
                anchor="w",
                bg=self.BTN_NORM, fg=self.TXT,
                activebackground=self.BTN_ACT, activeforeground=self.ACCENT,
                relief=tk.FLAT, bd=0,
                font=(self.FONT, 13),
                padx=16, pady=18,
                cursor="hand2",
                command=lambda a=app: self._launch(a),
            )
            btn.pack(fill=tk.X, pady=2, padx=8)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.BTN_ACT))
            btn.bind("<Leave>", lambda e, b=btn: self._restore_btn_color(b))
            self._btns[app["id"]] = btn

        # Stop button at bottom
        tk.Frame(self.sidebar, bg="#2a2f3e", height=1).pack(fill=tk.X, padx=16, pady=8)
        self._stop_btn = tk.Button(
            self.sidebar,
            text="  ✕  Terminar app",
            anchor="w",
            bg=self.BTN_NORM, fg="#ff4d6d",
            activebackground="#2a0a12", activeforeground="#ff4d6d",
            relief=tk.FLAT, bd=0,
            font=(self.FONT, 13),
            padx=16, pady=18,
            cursor="hand2",
            command=self._stop_current,
            state=tk.DISABLED,
        )
        self._stop_btn.pack(fill=tk.X, pady=2, padx=8)

        # Embed frame — this is where X11 windows will live
        self._embed_frame = tk.Frame(self.content, bg=self.BG)
        self._embed_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Placeholder shown when no app is running
        self._placeholder = tk.Frame(self._embed_frame, bg=self.BG)
        tk.Label(
            self._placeholder,
            text="Seleccione app desde el menú",
            bg=self.BG, fg=self.TXT_DIM,
            font=(self.FONT, 14),
        ).place(relx=0.5, rely=0.5, anchor="center")
        if len(APPS) > 0:
            self._launch(app=APPS[0])
        else:
            self._placeholder.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _toggle_sidebar(self, time_off=0.5):
        if time.time() < self.toggle_clicked_time + time_off:
            return
        self.toggle_clicked_time = time.time()        
        target = 0 if self.sidebar_expanded else self.SIDEBAR_W
        self._animate_sidebar(target)
        self.sidebar_expanded = not self.sidebar_expanded
        
    def _animate_sidebar(self, target: int, step=15):
        current = self.sidebar.winfo_width()
        delta = step if target > current else -step
        if abs(target - current) <= step:
            self.sidebar.place_configure(width=target)
            self.content.place_configure(x=target, width=-target)
            return
        new_w = current + delta
        self.sidebar.place_configure(width=new_w)
        w=self.winfo_width()
        self.content.place_configure(x=new_w, width=w-new_w)
        self.sidebar_anim_id = self.after(10, lambda: self._animate_sidebar(target, step)) 

    def _launch(self, app: dict):
        self._stop_current()           # kill whatever is running first
        self._set_active_btn(app["id"])
        self._stop_btn.configure(state=tk.NORMAL)
        self._placeholder.place_forget()

        # Launch in a thread so the GUI stays responsive
        threading.Thread(
            target=self._embed_worker,
            args=(app,),
            daemon=True
        ).start()

    def _embed_worker(self, app: dict):
        try:
            # 1. Start the subprocess
            proc = subprocess.Popen(
                app["cmd"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._proc = proc

            # 2. Wait for its window to appear on screen
            xid = find_window_id(app["window_title_hint"], timeout=10.0)

            if xid is None:
                return

            self._embedded_xid = xid

            # 3. Remove title bar / decorations
            remove_decorations(xid)

            # 4. Re-parent the window into our embed frame
            embed_xid = self._embed_frame.winfo_id()
            reparent_window(xid, embed_xid)

            # 5. Resize to fill the embed frame
            self.after(100, self._fit_embedded_window)

        except Exception as exc:
            print(f"Error: {exc}")

    def _fit_embedded_window(self):
        """Resize the embedded window to fill the embed frame."""
        if self._embedded_xid is None:
            return
        self._embed_frame.update_idletasks()
        w = self._embed_frame.winfo_width()
        h = self._embed_frame.winfo_height()
        resize_window(self._embedded_xid, w, h)
        move_window(self._embedded_xid, 0, 0)
        # Re-bind on frame resize so the embedded window tracks it
        self._embed_frame.bind("<Configure>", self._on_frame_resize)

    def _on_frame_resize(self, event):
        if self._embedded_xid:
            resize_window(self._embedded_xid, event.width, event.height)

    def _stop_current(self):
        self._embed_frame.unbind("<Configure>")
        if self._proc is not None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception:
                pass
            self._proc = None
        self._embedded_xid = None
        self._placeholder.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._stop_btn.configure(state=tk.DISABLED)
        self._set_active_btn(None)

    def _set_active_btn(self, app_id: str | None):
        for aid, btn in self._btns.items():
            if aid == app_id:
                btn.configure(bg=self.BTN_ACT, fg=self.ACCENT)
            else:
                btn.configure(bg=self.BTN_NORM, fg=self.TXT)

    def _restore_btn_color(self, btn: tk.Button):
        # Only restore if it's not the active one
        for aid, b in self._btns.items():
            if b is btn:
                active_color = self.BTN_ACT if b.cget("fg") == self.ACCENT else self.BTN_NORM
                btn.configure(bg=active_color)
                return

    def _on_close(self):
        self._stop_current()
        self.destroy()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = KioskApp()
    app.mainloop()