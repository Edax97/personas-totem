"""
Kiosk
Host that embeds X11 window apps

Requirements:
  pip install pillow
  sudo apt install xdotool x11-utils python3-xlib
"""

import tkinter as tk
import subprocess
import threading
import time
import os
import signal
#from PIL import Image, ImageTk

try:
    from Xlib import display as Xdisplay, X
    from Xlib.error import XError
    XLIB_OK = True
except ImportError:
    XLIB_OK = False
    print("Warning: python3-xlib not found. Run: sudo apt install python3-xlib")

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
    # {
    #     "id": "text-editor",
    #     "label": "Text Editor",
    #     "icon": "",
    #     "desc": "System text editor",
    #     "cmd": ["thonny"],          # swap for mousepad, kate, etc.
    #     "window_title_hint": "Thonny",
    # },
    {
        "id": "calculator",
        "label": "Calculator",
        "icon": "",
        "desc": "System calculator",
        "cmd": ["galculator"],
        "window_title_hint": "galculator",
    }, 
    {
          "id": "contador",
          "label": "Contador de personas",
          "icon": "",
          "desc": "Contador de personas",
          "cmd": ["/usr/local/bin/conteo-personas.sh"],
          "window_title_hint": "Tracking",
      },
]

# How many ms to wait before acting on a resize event (debounce).
RESIZE_DEBOUNCE_MS = 120

# ---------------------------------------------------------------------------
# X11 embed  (only this section changed)
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


def embed_window(xid: int, parent_xid: int, w: int, h: int):
    """
    Atomically strip decorations, reparent, and size the window in one
    server-grabbed transaction so the compositor never sees an intermediate
    state — eliminates the reparent blink.
    """
    if not XLIB_OK:
        # xdotool fallback (more blink-prone but functional)
        subprocess.run(["xdotool", "windowreparent", str(xid), str(parent_xid)], capture_output=True)
        subprocess.run(["xdotool", "windowsize",     str(xid), str(w), str(h)],  capture_output=True)
        subprocess.run(["xdotool", "windowmove",     str(xid), "0", "0"],         capture_output=True)
        return

    d = Xdisplay.Display()
    try:
        win    = d.create_resource_object("window", xid)
        parent = d.create_resource_object("window", parent_xid)

        d.grab_server()                                    # freeze compositor

        win.unmap()                                        # hide during transition

        atom = d.intern_atom("_MOTIF_WM_HINTS")           # strip decorations
        win.change_property(atom, atom, 32, [2, 0, 0, 0, 0])

        win.reparent(parent, 0, 0)                         # move into our frame
        win.configure(width=max(1, w), height=max(1, h), x=0, y=0)

        win.map()                                          # show at final size/pos

        d.ungrab_server()                                  # one single repaint
        d.sync()
    except XError as e:
        print(f"embed_window XError: {e}")
        try:
            d.ungrab_server()
        except Exception:
            pass
    finally:
        d.close()


def resize_embedded(xid: int, w: int, h: int):
    """
    Resize an already-embedded window without a visible blank frame.
    GrabServer prevents the compositor from showing intermediate states.
    """
    if not XLIB_OK:
        subprocess.run(["xdotool", "windowsize", str(xid), str(w), str(h)], capture_output=True)
        subprocess.run(["xdotool", "windowmove", str(xid), "0", "0"],        capture_output=True)
        return

    d = Xdisplay.Display()
    try:
        win = d.create_resource_object("window", xid)
        d.grab_server()
        win.configure(width=max(1, w), height=max(1, h), x=0, y=0)
        d.ungrab_server()
        d.sync()
    except XError as e:
        print(f"resize_embedded XError: {e}")
        try:
            d.ungrab_server()
        except Exception:
            pass
    finally:
        d.close()


# ---------------------------------------------------------------------------
# Main kiosk
# ---------------------------------------------------------------------------
class KioskApp(tk.Tk):
   
    SIDEBAR_W = 480
    BG        = "#0d0f14"
    SIDEBAR   = "#131720"
    TOPBAR_H = 88
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
        self.w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        self.geometry(f"{self.w}x{h}")

        self._proc: subprocess.Popen | None = None
        self._embedded_xid: int | None = None
        self._active_btn: tk.Widget | None = None
        self._resize_job: str | None = None   # debounce handle

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
            font=("Monospace", 48),
            highlightthickness=0,
            bd=0,
            command=self._toggle_sidebar,
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=8, pady=2)
        # img = ImageTk.PhotoImage(Image.open("labotec.png").resize((48, 48)))
        # img_label = tk.Label(topbar, image=img, bg=self.TOPBAR)
        # img_label.image = img
        # img_label.pack(side=tk.RIGHT, padx=5, pady=0)
        tk.Label(
            topbar, text="Labotec | Visión artificial", bg=self.TOPBAR,
            fg="white", font=(self.FONT, 22, "bold"),
        ).pack(side=tk.TOP, fill=tk.X, pady=(16, 4))

        self.sidebar_expanded=False
        self.toggle_clicked_time=time.time()
        
        mainframe = tk.Frame(self, bg=self.BG)
        mainframe.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.sidebar = tk.Frame(mainframe, bg=self.SIDEBAR, width=self.SIDEBAR_W)
        self.sidebar.place(x=0, y=0, relheight=1.0, width=0)
        self.sidebar.pack_propagate(False)
        
        # ── Content area ───────────────────────────────────────────────
        self.content = tk.Frame(mainframe, bg=self.BG)
        self.content.place(x=0, y=0, relwidth=1, relheight=1, width=self.winfo_width())

        # Logo / title
        tk.Label(
            self.sidebar, text="Selecciona app", bg=self.SIDEBAR,
            fg=self.ACCENT, font=(self.FONT, 24, "bold"),
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
                font=(self.FONT, 23),
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
            font=(self.FONT, 23),
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
            font=(self.FONT, 24),
        ).place(relx=0.5, rely=0.5, anchor="center")
        if len(APPS) > 0:
            self._launch(app=APPS[0])
        else:
            self._placeholder.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _toggle_sidebar(self, time_off=0.5):
        if time.time() < self.toggle_clicked_time + time_off:
            return

        if self.sidebar_expanded:
            self.sidebar.place_configure(width=0)
            self.content.place_configure(x=0, width=self.w)
        else:
            self.sidebar.place_configure(width=self.SIDEBAR_W)
            self.content.place_configure(x=self.SIDEBAR_W, width=self.w-self.SIDEBAR_W)

        self.toggle_clicked_time = time.time()        
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
        # lower placeholder instead of place_forget to avoid triggering
        # a redraw on _embed_frame (which causes a flash)
        self._placeholder.lower()

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

            # 3. Schedule the actual embedding on the main thread
            #    (Tkinter is not thread-safe; winfo_id/winfo_width must
            #    be called from the main thread)
            self.after(0, self._do_embed)

        except Exception as exc:
            print(f"Error: {exc}")

    def _do_embed(self):
        """Main-thread: atomically embed and size the foreign window."""
        if self._embedded_xid is None:
            return
        self._embed_frame.update_idletasks()
        w          = max(1, self._embed_frame.winfo_width())
        h          = max(1, self._embed_frame.winfo_height())
        parent_xid = self._embed_frame.winfo_id()

        embed_window(self._embedded_xid, parent_xid, w, h)

        # Start tracking resizes only after embedding is done
        self._embed_frame.bind("<Configure>", self._on_frame_resize)

    def _on_frame_resize(self, event):
        """Debounced resize — fires once the user stops dragging."""
        if not self._embedded_xid:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        w, h = event.width, event.height
        self._resize_job = self.after(
            RESIZE_DEBOUNCE_MS,
            lambda: self._apply_resize(w, h)
        )

    def _apply_resize(self, w: int, h: int):
        self._resize_job = None
        if self._embedded_xid and w > 1 and h > 1:
            resize_embedded(self._embedded_xid, w, h)

    def _stop_current(self):
        # Cancel any pending debounced resize
        if self._resize_job:
            self.after_cancel(self._resize_job)
            self._resize_job = None

        self._embed_frame.unbind("<Configure>")

        if self._proc is not None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception:
                pass
            self._proc = None

        self._embedded_xid = None
        # lift placeholder back on top (no layout recalc, no flash)
        self._placeholder.lift()
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