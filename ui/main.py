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

try:
    from Xlib import display as Xdisplay, X
    from Xlib.error import XError
    XLIB_OK = True
except ImportError:
    XLIB_OK = False
    print("Warning: python3-xlib not found. Run: sudo apt install python3-xlib")

APPS = [
    {
            "id": "mpv",
            "label": "Labotec",
            "icon": "",
            "desc": "mpv show video",
            "cmd": ["./mpv_loop.sh"],
            "window_title_hint": "mpv",
            "size_args": False,
        },
    {
        "id": "contador",
        "label": "Conteo de visitantes",
        "icon": "",
        "desc": "Contador de personas",
        "cmd": ["/usr/local/bin/conteo-personas.sh"],
        "window_title_hint": "Contador personas",
        "size_args": True,
    },
    # {
    #     "id": "fatiga",
    #     "label": "Sensor de fatiga",
    #     "icon": "",
    #     "desc": "Sensor de fatiga",
    #     "cmd": ["/usr/local/bin/fatiga.sh"],
    #     "window_title_hint": "fatiga",
    #     "size_args": True,
    # },
    # {
    #         "id": "pose",
    #         "label": "Pose humana",
    #         "icon": "",
    #         "desc": "Pose tracking",
    #         "cmd": ["/usr/local/bin/pose.sh"],
    #         "window_title_hint": "Pose",
    #         "size_args": True,
    #     },
]

RESIZE_DEBOUNCE_MS = 120


def find_window_id(title_hint: str, timeout: float = 30.0) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["xdotool", "search", "--name", title_hint],
            capture_output=True, text=True,
        )
        ids = result.stdout.strip().splitlines()
        if ids:
            return int(ids[-1])
        time.sleep(0.25)
    return None


def _get_window_geometry(xid: int) -> tuple[int, int]:
    if not XLIB_OK:
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", str(xid)],
            capture_output=True, text=True,
        )
        ww = wh = 0
        for line in result.stdout.splitlines():
            if line.startswith("WIDTH="):
                ww = int(line.split("=")[1])
            elif line.startswith("HEIGHT="):
                wh = int(line.split("=")[1])
        return ww, wh

    d = Xdisplay.Display()
    try:
        win = d.create_resource_object("window", xid)
        geom = win.get_geometry()
        return geom.width, geom.height
    except Exception:
        return 0, 0
    finally:
        d.close()


def hide_window_offscreen(xid: int) -> None:
    if not XLIB_OK:
        subprocess.run(["xdotool", "windowmove", str(xid), "-10000", "-10000"],
                       capture_output=True)
        return

    d = Xdisplay.Display()
    try:
        win = d.create_resource_object("window", xid)
        d.grab_server()
        win.configure(x=-10000, y=-10000)
        d.ungrab_server()
        d.sync()
    except Exception:
        try:
            d.ungrab_server()
        except Exception:
            pass
    finally:
        d.close()


def embed_window(xid: int, parent_xid: int, frame_w: int, frame_h: int) -> None:
    if not XLIB_OK:
        subprocess.run(["xdotool", "windowreparent", str(xid), str(parent_xid)], capture_output=True)
        win_w, win_h = _get_window_geometry(xid)
        ox = max(0, (frame_w - win_w) // 2)
        oy = max(0, (frame_h - win_h) // 2)
        subprocess.run(["xdotool", "windowmove", str(xid), str(ox), str(oy)], capture_output=True)
        return

    d = Xdisplay.Display()
    try:
        win    = d.create_resource_object("window", xid)
        parent = d.create_resource_object("window", parent_xid)

        d.grab_server()
        win.unmap()

        motif_atom = d.intern_atom("_MOTIF_WM_HINTS")
        win.change_property(motif_atom, motif_atom, 32, [2, 0, 0, 0, 0])

        try:
            win.delete_property(d.intern_atom("WM_NORMAL_HINTS"))
        except Exception:
            pass

        geom  = win.get_geometry()
        win_w = geom.width
        win_h = geom.height

        FILL_THRESHOLD = 0.9
        if win_w >= frame_w * FILL_THRESHOLD and win_h >= frame_h * FILL_THRESHOLD:
            target_w, target_h = frame_w, frame_h
            ox, oy = 0, 0
        else:
            target_w, target_h = win_w, win_h
            ox = max(0, (frame_w - win_w) // 2)
            oy = max(0, (frame_h - win_h) // 2)

        win.reparent(parent, ox, oy)
        win.configure(width=max(1, target_w), height=max(1, target_h), x=ox, y=oy)
        win.map()

        d.ungrab_server()
        d.sync()
    except XError as e:
        print(f"embed_window XError: {e}")
        try:
            d.ungrab_server()
        except Exception:
            pass
    finally:
        d.close()


def resize_embedded(xid: int, frame_w: int, frame_h: int) -> None:
    if not XLIB_OK:
        win_w, win_h = _get_window_geometry(xid)
        FILL_THRESHOLD = 0.9
        if win_w >= frame_w * FILL_THRESHOLD and win_h >= frame_h * FILL_THRESHOLD:
            subprocess.run(["xdotool", "windowsize", str(xid), str(frame_w), str(frame_h)], capture_output=True)
            subprocess.run(["xdotool", "windowmove", str(xid), "0", "0"], capture_output=True)
        else:
            ox = max(0, (frame_w - win_w) // 2)
            oy = max(0, (frame_h - win_h) // 2)
            subprocess.run(["xdotool", "windowmove", str(xid), str(ox), str(oy)], capture_output=True)
        return

    d = Xdisplay.Display()
    try:
        win = d.create_resource_object("window", xid)
        d.grab_server()

        geom  = win.get_geometry()
        win_w = geom.width
        win_h = geom.height

        FILL_THRESHOLD = 0.9
        if win_w >= frame_w * FILL_THRESHOLD and win_h >= frame_h * FILL_THRESHOLD:
            win.configure(width=max(1, frame_w), height=max(1, frame_h), x=0, y=0)
        else:
            ox = max(0, (frame_w - win_w) // 2)
            oy = max(0, (frame_h - win_h) // 2)
            win.configure(x=ox, y=oy)

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


class KioskApp(tk.Tk):

    SIDEBAR_W = 480
    BG       = "#0d0f14"
    SIDEBAR  = "#131720"
    TOPBAR_H = 88
    TOPBAR   = "#131620"
    ACCENT   = "#00d4ff"
    BTN_NORM = "#1c2030"
    BTN_ACT  = "#1e3a4a"
    TXT      = "#e8eaf0"
    TXT_DIM  = "#6b7280"
    FONT     = "Helvetica"

    def __init__(self):
        super().__init__()
        self.title("Labotec - Visión artificial")
        self.configure(bg=self.BG)
        self.resizable(False, False)
        self.w = self.winfo_screenwidth()
        self.h = self.winfo_screenheight()
        self.geometry(f"{self.w}x{self.h}+0+0")
        #self.overrideredirect(True)

        self._proc: subprocess.Popen | None = None
        self._embedded_xid: int | None = None
        self._active_btn: tk.Widget | None = None
        self._resize_job: str | None = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        topbar = tk.Frame(self, bg=self.TOPBAR, height=self.TOPBAR_H)
        topbar.pack(side=tk.TOP, fill=tk.X)
        topbar.pack_propagate(False)

        tk.Button(
            topbar,
            text="☰",
            bg=self.TOPBAR, fg="white",
            activebackground=self.TOPBAR, activeforeground="white",
            font=("Monospace", 48),
            highlightthickness=0, bd=0,
            command=self._toggle_sidebar,
        ).pack(side=tk.LEFT, padx=8, pady=2)

        tk.Label(
            topbar, text="Labotec | Visión artificial   ",
            bg=self.TOPBAR, fg="white",
            font=(self.FONT, 22, "bold"),
        ).pack(side=tk.TOP, fill=tk.X, pady=(36, 4), padx=(0,0))

        self.sidebar_expanded = False
        self.toggle_clicked_time = time.time()

        mainframe = tk.Frame(self, bg=self.BG)
        mainframe.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(mainframe, bg=self.SIDEBAR, width=self.SIDEBAR_W)
        self.sidebar.place(x=0, y=0, relheight=1.0, width=0)
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(mainframe, bg=self.BG)
        self.content.place(x=0, y=0, relwidth=1, relheight=1)

        tk.Label(
            self.sidebar, text="Selecciona app",
            bg=self.SIDEBAR, fg=self.ACCENT,
            font=(self.FONT, 24, "bold"), pady=24,
        ).pack(fill=tk.X)
        tk.Frame(self.sidebar, bg="#2a2f3e", height=1).pack(fill=tk.X, padx=16)

        self._btns: dict[str, tk.Button] = {}
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

        self._embed_frame = tk.Frame(self.content, bg=self.BG)
        self._embed_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._placeholder = tk.Frame(self._embed_frame, bg=self.BG)
        tk.Label(
            self._placeholder,
            text="Seleccione app desde el menú",
            bg=self.BG, fg=self.TXT_DIM,
            font=(self.FONT, 24),
        ).place(relx=0.5, rely=0.5, anchor="center")

        if APPS:
            self.after(1000, lambda: self._launch(APPS[0], True))
        else:
            self._placeholder.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _toggle_sidebar(self, time_off: float = 0.5):
        if time.time() < self.toggle_clicked_time + time_off:
            return
        if self.sidebar_expanded:
            self.sidebar.place_configure(width=0)
            self.content.place_configure(x=0, relwidth=1)
        else:
            self.sidebar.place_configure(width=self.SIDEBAR_W)
            self.content.place_configure(x=self.SIDEBAR_W)
        self.toggle_clicked_time = time.time()
        self.sidebar_expanded = not self.sidebar_expanded
        self._resize_embedded_to_frame()

    def _get_embed_frame_size(self) -> tuple[int, int]:
        self.update_idletasks()
        w = self._embed_frame.winfo_width()
        h = self._embed_frame.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        print(f"[kiosk] frame: {w}x{h}  screen: {sw}x{sh}  window: {self.w}x{self.h}")
        return max(1, w), max(1, h)

    def _launch(self, app: dict, first_launch=False):
        self._stop_current()
        self._set_active_btn(app["id"])
        self._stop_btn.configure(state=tk.NORMAL)
        self._placeholder.lower()
        if not first_launch:
            self._toggle_sidebar()
        embed_w, embed_h = self._get_embed_frame_size()
        embed_w, embed_h = 2156, 3748
        threading.Thread(
            target=self._embed_worker,
            args=(app, embed_w, embed_h),
            daemon=True,
        ).start()

    def _embed_worker(self, app: dict, embed_w: int, embed_h: int):
        try:
            cmd = list(app["cmd"])
            if app.get("size_args") and embed_w > 1 and embed_h > 1:
                cmd += ["--width", str(embed_w), "--height", str(embed_h)]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._proc = proc

            xid = find_window_id(app["window_title_hint"], timeout=35.0)
            if xid is None:
                print(f"[kiosk] window '{app['window_title_hint']}' not found")
                return

            print(f"[kiosk] found window xid={xid} for '{app['window_title_hint']}'")

            self._embedded_xid = xid
            hide_window_offscreen(xid)
            self.after(0, lambda: self._do_embed(embed_w, embed_h))

        except Exception as exc:
            print(f"[kiosk] embed_worker error: {exc}")

    def __do_embed(self, w: int, h: int):
        if self._embedded_xid is None:
            print("[kiosk] _do_embed called but _embedded_xid is None")
            return
        actual_w, actual_h = self._get_embed_frame_size()
        parent_xid = self._embed_frame.winfo_id()
        embed_window(self._embedded_xid, parent_xid, actual_w, actual_h)
        self._embed_frame.bind("<Configure>", self._on_frame_resize)
    def _do_embed(self, w: int, h: int):
        if self._embedded_xid is None:
            print("[kiosk] _do_embed called but _embedded_xid is None")
            return
        
        parent_xid = self._embed_frame.winfo_id()
        mapped = self._embed_frame.winfo_ismapped()
        print(f"[kiosk] _do_embed: embedded_xid={self._embedded_xid} parent_xid={parent_xid} mapped={mapped} w={w} h={h}")
        
        actual_w, actual_h = self._get_embed_frame_size()
        embed_window(self._embedded_xid, parent_xid, actual_w, actual_h)
        self._embed_frame.bind("<Configure>", self._on_frame_resize)
    def _resize_embedded_to_frame(self):
        if not self._embedded_xid:
            return
        w, h = self._get_embed_frame_size()
        if w > 1 and h > 1:
            resize_embedded(self._embedded_xid, w, h)

    def _on_frame_resize(self, event):
        if not self._embedded_xid:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        w, h = event.width, event.height
        self._resize_job = self.after(
            RESIZE_DEBOUNCE_MS,
            lambda: self._apply_resize(w, h),
        )

    def _apply_resize(self, w: int, h: int):
        self._resize_job = None
        if self._embedded_xid and w > 1 and h > 1:
            resize_embedded(self._embedded_xid, w, h)

    def _stop_current(self):
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
        for b in self._btns.values():
            if b is btn:
                color = self.BTN_ACT if b.cget("fg") == self.ACCENT else self.BTN_NORM
                btn.configure(bg=color)
                return

    def _on_close(self):
        self._stop_current()
        self.destroy()


if __name__ == "__main__":
    app = KioskApp()
    app.mainloop()
