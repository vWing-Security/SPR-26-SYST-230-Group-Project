"""
archery_tracker.py
Graphical (tkinter) interface for the Smart Archery training tracker.

Integrates with the shared backend:
    - archery_system.SmartArcherySystem  (business logic & statistics)
    - session_database.SessionDatabase   (persistent JSON storage)

The GUI provides an interactive target canvas for click-to-score entry,
session management, and a statistics dashboard — all backed by the same
data store used by the CLI (smart_archery_ui.py).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
from datetime import datetime

from archery_system import SmartArcherySystem

COLORS = {
    "bg":        "#1a1a2e",
    "panel":     "#16213e",
    "accent":    "#0f3460",
    "highlight": "#e94560",
    "text":      "#eaeaea",
    "subtext":   "#a0a0b0",
}

# Index 0 = ring 1 (outermost), index 9 = ring 10 (bullseye)
RING_COLORS = [
    "#CCCCCC",  # 1
    "#FFFFFF",  # 2
    "#555555",  # 3
    "#333333",  # 4
    "#3355CC",  # 5
    "#2244BB",  # 6
    "#CC3333",  # 7
    "#BB2222",  # 8
    "#FFD700",  # 9
    "#FFA500",  # 10
]

RING_TEXT_COLORS = [
    "#000000", "#000000",
    "#FFFFFF", "#FFFFFF",
    "#FFFFFF", "#FFFFFF",
    "#FFFFFF", "#FFFFFF",
    "#000000", "#000000",
]

# Target face types
TARGET_FACES = {
    "Recurve (Full)": {
        "min_ring": 1,       # outermost ring score
        "rings": 10,         # number of ring bands drawn
        "x_ring_ratio": 0.5, # X-ring is inner half of the 10-ring
    },
    "Compound (Inner 10)": {
        "min_ring": 5,       # outermost ring score
        "rings": 5,          # 5 ring bands for scores 5-9
        "x_ring_ratio": 0.5, # X-ring in center of 9-ring
    },
}


class ArcheryTracker:
    """Tkinter GUI for archery training, backed by SmartArcherySystem."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Archery Tracker")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(800, 600)

        self.system = SmartArcherySystem()
        self.current_session = None       # Active session dict
        self._session_idx = None          # Index in db.sessions
        self.current_end_buffer = []      # Arrows for the current (incomplete) end

        # Sidebar display variables (created here so they exist before _build_sidebar)
        self._score_var = tk.StringVar(value="0")
        self._shots_var = tk.StringVar(value="0")
        self._avg_var   = tk.StringVar(value="0.0")
        self._end_var   = tk.StringVar(value="1")
        self._shot_lb   = None

        # Zoom and pan state
        self._zoom = 1.0
        self._pan_x = 0.0  # current canvas pan offset
        self._pan_y = 0.0

        self.show_main_menu()
        self.root.mainloop()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _save_progress(self):
        """Persist current session state to the shared database."""
        if self.current_session is None:
            return
        # Store the buffer so the session can be resumed
        self.current_session["current_end_buffer"] = list(self.current_end_buffer)
        # Recompute stats for completed ends
        self.current_session["stats"] = SmartArcherySystem.computeStatistics(
            self.current_session
        )

        if self._session_idx is not None:
            self.system.db.sessions[self._session_idx] = self.current_session
        else:
            self.system.db.sessions.append(self.current_session)
            self._session_idx = len(self.system.db.sessions) - 1
        self.system.db.save()

    # ── Navigation helpers ───────────────────────────────────────────────────

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _btn(self, parent, text, cmd, bg=None, fg=None, **kw):
        bg = bg or COLORS["accent"]
        fg = fg or COLORS["text"]
        b = tk.Button(parent, text=text, command=cmd, font=("Helvetica", 12),
                      bg=bg, fg=fg, activebackground=COLORS["highlight"],
                      activeforeground="white", relief="flat", cursor="hand2",
                      padx=16, pady=8, **kw)
        b.bind("<Enter>", lambda e: b.configure(bg=COLORS["highlight"]))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    # ── Helpers for display values (includes buffered arrows) ────────────────

    def _total_score(self):
        base = self.current_session.get("stats", {}).get("total_score", 0)
        return base + sum(self.current_end_buffer)

    def _shot_count(self):
        base = self.current_session.get("stats", {}).get("arrow_count", 0)
        return base + len(self.current_end_buffer)

    def _average_score(self):
        count = self._shot_count()
        if count == 0:
            return 0.0
        total = (self.current_session.get("stats", {}).get("total_score", 0)
                 + sum(self.current_end_buffer))
        return total / count

    # ── Main Menu ────────────────────────────────────────────────────────────

    def show_main_menu(self):
        self._clear()
        self.root.geometry("860x640")

        # Header
        hdr = tk.Frame(self.root, bg=COLORS["panel"], height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Archery Tracker", font=("Helvetica", 26, "bold"),
                 bg=COLORS["panel"], fg=COLORS["highlight"]).pack(pady=22)

        body = tk.Frame(self.root, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=50, pady=30)

        # Menu buttons
        btns = tk.Frame(body, bg=COLORS["bg"])
        btns.pack()
        for i, (label, cmd) in enumerate([
            ("New Session",      self._new_session_dialog),
            ("Resume Session",   self._open_session_list),
            ("Statistics",       self.show_stats),
            ("Export CSV",       self._export_csv),
        ]):
            self._btn(btns, label, cmd, width=22).grid(row=i, column=0, pady=7)

        self._btn(btns, "Quit", self.root.quit,
                  bg="#5a0000", fg=COLORS["text"], width=22).grid(
                      row=len(btns.winfo_children()), column=0, pady=7)

        # Recent sessions
        sessions = self.system.db.sessions
        if sessions:
            tk.Label(body, text="Recent Sessions", font=("Helvetica", 12, "bold"),
                     bg=COLORS["bg"], fg=COLORS["subtext"]).pack(pady=(28, 6))

            for idx in range(len(sessions) - 1, max(len(sessions) - 6, -1), -1):
                session = sessions[idx]
                row = tk.Frame(body, bg=COLORS["panel"], cursor="hand2")
                row.pack(fill="x", pady=3)

                name = session.get("name", f"Session {idx}")
                date = session.get("date", "")
                stats = session.get("stats", {})
                shots = stats.get("arrow_count", 0)
                total = stats.get("total_score", 0)
                dist = session.get("distance", "")
                bow = session.get("equipment_notes", "")

                meta = f"{dist}  {bow}".strip()
                label = f"  {name}    {date}    {shots} shots    {total} pts"
                if meta:
                    label += f"    [{meta}]"

                lbl = tk.Label(row, text=label, font=("Helvetica", 10),
                               bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
                lbl.pack(fill="x", padx=8, pady=7)

                for widget in (row, lbl):
                    widget.bind("<Button-1>",
                                lambda e, i=idx: self._open_session(i))
                    widget.bind("<Enter>",
                                lambda e, r=row, l=lbl: [
                                    r.configure(bg=COLORS["accent"]),
                                    l.configure(bg=COLORS["accent"])])
                    widget.bind("<Leave>",
                                lambda e, r=row, l=lbl: [
                                    r.configure(bg=COLORS["panel"]),
                                    l.configure(bg=COLORS["panel"])])

    # ── New Session Dialog ───────────────────────────────────────────────────

    def _new_session_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Session")
        dlg.geometry("400x480")
        dlg.configure(bg=COLORS["bg"])
        dlg.grab_set()

        tk.Label(dlg, text="New Session", font=("Helvetica", 15, "bold"),
                 bg=COLORS["bg"], fg=COLORS["highlight"]).pack(pady=14)

        entries = {}
        session_count = len(self.system.db.sessions)
        text_fields = [
            ("Session Name", f"Session {session_count + 1}"),
            ("Distance (e.g. 20m)", ""),
            ("Weather / Conditions", ""),
            ("Equipment Notes", ""),
        ]
        for label, default in text_fields:
            f = tk.Frame(dlg, bg=COLORS["bg"])
            f.pack(fill="x", padx=30, pady=3)
            tk.Label(f, text=label, font=("Helvetica", 10), bg=COLORS["bg"],
                     fg=COLORS["subtext"], anchor="w").pack(fill="x")
            e = tk.Entry(f, font=("Helvetica", 11), bg=COLORS["panel"],
                         fg=COLORS["text"], insertbackground=COLORS["text"],
                         relief="flat", bd=4)
            e.insert(0, default)
            e.pack(fill="x")
            entries[label] = e

        # Target face dropdown
        f = tk.Frame(dlg, bg=COLORS["bg"])
        f.pack(fill="x", padx=30, pady=3)
        tk.Label(f, text="Target Face", font=("Helvetica", 10), bg=COLORS["bg"],
                 fg=COLORS["subtext"], anchor="w").pack(fill="x")
        face_var = tk.StringVar(value=list(TARGET_FACES.keys())[0])
        face_menu = ttk.Combobox(f, textvariable=face_var,
                                 values=list(TARGET_FACES.keys()),
                                 font=("Helvetica", 11), state="readonly")
        face_menu.pack(fill="x")

        def start():
            name = entries["Session Name"].get().strip() or text_fields[0][1]
            dist = entries["Distance (e.g. 20m)"].get().strip() or "N/A"
            target = face_var.get()
            weather = entries["Weather / Conditions"].get().strip() or "N/A"
            equip = entries["Equipment Notes"].get().strip() or "N/A"

            self.current_session = {
                "name": name,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "distance": dist,
                "target_face": target,
                "weather": weather,
                "equipment_notes": equip,
                "ends": [],
                "shot_positions": [],
                "current_end": 1,
                "current_end_buffer": [],
                "stats": {},
            }
            self._session_idx = None
            self.current_end_buffer = []
            self._save_progress()
            dlg.destroy()
            self.show_target_screen()

        self._btn(dlg, "Start Session", start,
                  bg=COLORS["highlight"], fg="white").pack(pady=14)
        entries["Session Name"].focus_set()
        dlg.bind("<Return>", lambda e: start())

    # ── Session List ─────────────────────────────────────────────────────────

    def _open_session_list(self):
        sessions = self.system.db.sessions
        if not sessions:
            messagebox.showinfo("No Sessions", "No sessions yet — start a new one!")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Resume Session")
        dlg.geometry("520x380")
        dlg.configure(bg=COLORS["bg"])
        dlg.grab_set()

        tk.Label(dlg, text="Select a Session", font=("Helvetica", 13, "bold"),
                 bg=COLORS["bg"], fg=COLORS["highlight"]).pack(pady=10)

        frm = tk.Frame(dlg, bg=COLORS["bg"])
        frm.pack(fill="both", expand=True, padx=16, pady=6)

        sb = tk.Scrollbar(frm)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(frm, yscrollcommand=sb.set, font=("Helvetica", 10),
                        bg=COLORS["panel"], fg=COLORS["text"],
                        selectbackground=COLORS["highlight"], relief="flat",
                        bd=0, activestyle="none")
        lb.pack(fill="both", expand=True)
        sb.config(command=lb.yview)

        # Build index map (reversed display order → actual index)
        index_map = []
        for idx in range(len(sessions) - 1, -1, -1):
            s = sessions[idx]
            name = s.get("name", f"Session {idx}")
            date = s.get("date", "")
            stats = s.get("stats", {})
            shots = stats.get("arrow_count", 0)
            total = stats.get("total_score", 0)
            lb.insert(tk.END, f"  {name}   {date}   {shots} shots   {total} pts")
            index_map.append(idx)

        def open_sel(event=None):
            sel = lb.curselection()
            if sel:
                real_idx = index_map[sel[0]]
                dlg.destroy()
                self._open_session(real_idx)

        lb.bind("<Double-Button-1>", open_sel)
        self._btn(dlg, "Open", open_sel).pack(pady=10)

    def _open_session(self, idx):
        """Open a session by its index in the database."""
        self._session_idx = idx
        self.current_session = self.system.db.sessions[idx]
        self.current_end_buffer = list(
            self.current_session.get("current_end_buffer", [])
        )
        self.show_target_screen()

    # ── Target Screen ────────────────────────────────────────────────────────

    def show_target_screen(self):
        self._clear()
        self.root.geometry("1080x720")
        session = self.current_session

        # Top bar
        topbar = tk.Frame(self.root, bg=COLORS["panel"], height=48)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        self._btn(topbar, "\u2190 Menu", self._back_to_menu,
                  bg=COLORS["panel"], fg=COLORS["subtext"]).pack(side="left", padx=8, pady=6)

        name = session.get("name", "Session")
        dist = session.get("distance", "")
        equip = session.get("equipment_notes", "")
        title = name
        meta = f"{dist}  {equip}".strip()
        if meta and meta != "N/A  N/A":
            title += f"   [{meta}]"
        tk.Label(topbar, text=title, font=("Helvetica", 12, "bold"),
                 bg=COLORS["panel"], fg=COLORS["text"]).pack(side="left", padx=6)

        # Main body
        body = tk.Frame(self.root, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)

        # Left: canvas
        left = tk.Frame(body, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=20, pady=16)

        self._canvas_size = 520
        self.canvas = tk.Canvas(left, width=self._canvas_size, height=self._canvas_size,
                                bg=COLORS["bg"], highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>",   self._on_hover)
        self.canvas.bind("<Leave>",    self._on_leave)

        # Zoom controls
        zoom_bar = tk.Frame(left, bg=COLORS["bg"])
        zoom_bar.pack(pady=(6, 0))
        self._zoom_label = tk.StringVar(value=f"{self._zoom:.1f}x")
        tk.Button(zoom_bar, text="\u2212", command=self._zoom_out, font=("Helvetica", 12, "bold"),
                  bg=COLORS["accent"], fg=COLORS["text"], relief="flat", cursor="hand2",
                  width=3, padx=4, pady=2).pack(side="left", padx=4)
        tk.Label(zoom_bar, textvariable=self._zoom_label, font=("Helvetica", 11),
                 bg=COLORS["bg"], fg=COLORS["subtext"], width=5).pack(side="left")
        tk.Button(zoom_bar, text="+", command=self._zoom_in, font=("Helvetica", 12, "bold"),
                  bg=COLORS["accent"], fg=COLORS["text"], relief="flat", cursor="hand2",
                  width=3, padx=4, pady=2).pack(side="left", padx=4)
        tk.Button(zoom_bar, text="Reset", command=self._zoom_reset, font=("Helvetica", 9),
                  bg=COLORS["accent"], fg=COLORS["text"], relief="flat", cursor="hand2",
                  padx=8, pady=4).pack(side="left", padx=8)

        self._draw_target()
        self._redraw_shots()

        # Right: sidebar
        sidebar = tk.Frame(body, bg=COLORS["panel"], width=270)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

    def _back_to_menu(self):
        # Submit any buffered arrows as an end before leaving
        if self.current_end_buffer:
            self.current_session["ends"].append(list(self.current_end_buffer))
            self.current_end_buffer = []
        self._save_progress()
        self.current_session = None
        self._session_idx = None
        self.show_main_menu()

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        # Score card
        card = tk.Frame(parent, bg=COLORS["accent"])
        card.pack(fill="x", padx=10, pady=(14, 6))

        tk.Label(card, text="TOTAL SCORE", font=("Helvetica", 9),
                 bg=COLORS["accent"], fg=COLORS["subtext"]).pack(pady=(10, 0))
        self._score_var.set(str(self._total_score()))
        tk.Label(card, textvariable=self._score_var, font=("Helvetica", 40, "bold"),
                 bg=COLORS["accent"], fg=COLORS["highlight"]).pack()

        row = tk.Frame(card, bg=COLORS["accent"])
        row.pack(pady=(0, 12))
        self._refresh_vars()

        for var, lbl in [(self._shots_var, "Shots"), (self._avg_var, "Avg"), (self._end_var, "End #")]:
            col = tk.Frame(row, bg=COLORS["accent"])
            col.pack(side="left", padx=12)
            tk.Label(col, textvariable=var, font=("Helvetica", 17, "bold"),
                     bg=COLORS["accent"], fg=COLORS["text"]).pack()
            tk.Label(col, text=lbl, font=("Helvetica", 8),
                     bg=COLORS["accent"], fg=COLORS["subtext"]).pack()

        # Controls
        ctrl = tk.Frame(parent, bg=COLORS["panel"])
        ctrl.pack(fill="x", padx=10, pady=4)
        tk.Label(ctrl, text="Controls", font=("Helvetica", 9, "bold"),
                 bg=COLORS["panel"], fg=COLORS["subtext"]).pack(anchor="w", padx=4, pady=(8, 3))

        row2 = tk.Frame(ctrl, bg=COLORS["panel"])
        row2.pack(fill="x", padx=4, pady=(0, 8))
        for label, cmd, bg in [
            ("New End",   self._new_end,   COLORS["accent"]),
            ("Undo",      self._undo_last, "#553300"),
            ("Clear End", self._clear_end, "#5a0000"),
        ]:
            b = tk.Button(row2, text=label, command=cmd, font=("Helvetica", 9),
                          bg=bg, fg=COLORS["text"], relief="flat", cursor="hand2",
                          padx=8, pady=5)
            b.pack(side="left", padx=2)

        # Shot list
        tk.Label(parent, text="Shot History", font=("Helvetica", 10, "bold"),
                 bg=COLORS["panel"], fg=COLORS["subtext"]).pack(anchor="w", padx=14, pady=(10, 3))

        lf = tk.Frame(parent, bg=COLORS["panel"])
        lf.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        sb = tk.Scrollbar(lf)
        sb.pack(side="right", fill="y")
        self._shot_lb = tk.Listbox(lf, yscrollcommand=sb.set, font=("Courier", 10),
                                    bg=COLORS["bg"], fg=COLORS["text"],
                                    selectbackground=COLORS["accent"],
                                    relief="flat", bd=0, activestyle="none")
        self._shot_lb.pack(fill="both", expand=True)
        sb.config(command=self._shot_lb.yview)

        self._refresh_shot_list()

    def _refresh_vars(self):
        self._shots_var.set(str(self._shot_count()))
        self._avg_var.set(f"{self._average_score():.1f}")
        self._end_var.set(str(self.current_session.get("current_end", 1)))

    def _update_display(self):
        self._score_var.set(str(self._total_score()))
        self._refresh_vars()
        self._refresh_shot_list()

    def _refresh_shot_list(self):
        if self._shot_lb is None:
            return
        self._shot_lb.delete(0, tk.END)
        # Completed ends
        for i, end in enumerate(self.current_session.get("ends", [])):
            scores = end
            parts = "  ".join("X" if s == "X" else str(s) for s in scores)
            total = sum(10 if s == "X" else s for s in scores)
            self._shot_lb.insert(tk.END, f"End {i + 1}: {parts:<20} = {total}")
        # Current end buffer (in progress)
        if self.current_end_buffer:
            end_num = self.current_session.get("current_end", 1)
            parts = "  ".join(str(s) for s in self.current_end_buffer)
            total = sum(self.current_end_buffer)
            self._shot_lb.insert(tk.END, f"End {end_num}: {parts:<20} = {total}  *")
        self._shot_lb.see(tk.END)

    # ── Target Drawing ───────────────────────────────────────────────────────

    def _get_face_config(self):
        """Return the TARGET_FACES config for the current session."""
        face_name = self.current_session.get("target_face", "Recurve (Full)")
        return TARGET_FACES.get(face_name, TARGET_FACES["Recurve (Full)"])

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.5, 5.0)
        self._zoom_label.set(f"{self._zoom:.1f}x")
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._draw_target()
        self._redraw_shots()

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.5, 1.0)
        self._zoom_label.set(f"{self._zoom:.1f}x")
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._draw_target()
        self._redraw_shots()

    def _zoom_reset(self):
        self._zoom = 1.0
        self._zoom_label.set(f"{self._zoom:.1f}x")
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._draw_target()
        self._redraw_shots()

    def _draw_target(self):
        cs = self._canvas_size
        self._base_radius = cs // 2 - 12
        self._radius = self._base_radius * self._zoom
        # Target center on canvas, shifted by pan offset
        cx = cs // 2 + self._pan_x
        cy = cs // 2 + self._pan_y
        self._cx = cx
        self._cy = cy

        self.canvas.delete("target")

        face = self._get_face_config()
        min_ring = face["min_ring"]
        num_rings = face["rings"]
        x_ratio = face["x_ring_ratio"]

        # Draw ring bands from outermost to innermost
        # Each band i (1=innermost, num_rings=outermost) scores min_ring + num_rings - i
        for i in range(num_rings, 0, -1):
            score = min_ring + num_rings - i
            r = self._radius * i / num_rings
            color_idx = min(score - 1, 9)
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill=RING_COLORS[color_idx],
                                    outline="#444444", width=1,
                                    tags="target")

        # Ring score labels
        for i in range(1, num_rings + 1):
            score = min_ring + num_rings - i
            r_outer = self._radius * i / num_rings
            r_inner = self._radius * (i - 1) / num_rings
            mid_r = (r_outer + r_inner) / 2 if i > 1 else r_outer * 0.5
            color_idx = min(score - 1, 9)
            self.canvas.create_text(cx + mid_r, cy, text=str(score),
                                    font=("Helvetica", 7, "bold"),
                                    fill=RING_TEXT_COLORS[color_idx],
                                    tags="target")

        # X-ring: small circle in center of the innermost ring band
        inner_ring_r = self._radius / num_rings
        xr = inner_ring_r * x_ratio
        self.canvas.create_oval(cx - xr, cy - xr, cx + xr, cy + xr,
                                fill=RING_COLORS[9], outline="#111111", width=1,
                                tags="target")
        self.canvas.create_text(cx, cy, text="X",
                                font=("Helvetica", 7, "bold"),
                                fill="#000000", tags="target")

        # Center crosshair
        self.canvas.create_line(cx - 5, cy, cx + 5, cy, fill="#666666", width=1, tags="target")
        self.canvas.create_line(cx, cy - 5, cx, cy + 5, fill="#666666", width=1, tags="target")

    def _score_for(self, x, y):
        dist = math.hypot(x - self._cx, y - self._cy)
        ratio = dist / self._radius
        if ratio >= 1.0:
            return 0

        face = self._get_face_config()
        min_ring = face["min_ring"]
        num_rings = face["rings"]
        x_ratio = face["x_ring_ratio"]

        # Check X-ring first (small circle in the center)
        inner_ring_ratio = 1.0 / num_rings
        x_ring_ratio = inner_ring_ratio * x_ratio
        if ratio <= x_ring_ratio:
            return 10

        # Which ring band did we hit? (1 = innermost, num_rings = outermost)
        band = int(ratio * num_rings) + 1
        band = min(band, num_rings)
        score = min_ring + num_rings - band
        return max(min_ring, min(10, score))

    # ── Pan / View Follow ──────────────────────────────────────────────────

    def _pan_view(self, mx, my):
        """Pan the zoomed view so the area under the cursor stays visible."""
        if self._zoom <= 1.0:
            return

        cc = self._canvas_size / 2
        # How far the target extends beyond the canvas at this zoom
        max_pan = self._base_radius * (self._zoom - 1)

        # Cursor position as fraction of canvas (-1 to 1)
        frac_x = max(-1.0, min(1.0, (mx - cc) / cc)) if cc else 0
        frac_y = max(-1.0, min(1.0, (my - cc) / cc)) if cc else 0

        # Desired pan: shift target opposite to cursor direction
        new_pan_x = -frac_x * max_pan
        new_pan_y = -frac_y * max_pan

        # Only redraw if pan changed meaningfully
        if abs(new_pan_x - self._pan_x) < 1 and abs(new_pan_y - self._pan_y) < 1:
            return

        self._pan_x = new_pan_x
        self._pan_y = new_pan_y
        self._draw_target()
        self._redraw_shots()

    # ── Canvas Events ────────────────────────────────────────────────────────

    def _on_click(self, event):
        x, y = event.x, event.y
        score = self._score_for(x, y)
        if score == 0:
            return

        # Store positions normalized to zoomed radius (true target coordinates)
        x_norm = (x - self._cx) / self._radius
        y_norm = (y - self._cy) / self._radius

        self.current_end_buffer.append(score)
        self.current_session.setdefault("shot_positions", []).append({
            "x": x_norm, "y": y_norm, "score": score,
            "end": self.current_session.get("current_end", 1),
        })

        self._draw_arrow(x, y, score)
        self._update_display()
        self._save_progress()

    def _on_hover(self, event):
        self._pan_view(event.x, event.y)
        self.canvas.delete("hover")
        score = self._score_for(event.x, event.y)
        if score > 0:
            self.canvas.create_text(event.x + 16, event.y - 14,
                                    text=str(score), font=("Helvetica", 14, "bold"),
                                    fill="white", tags="hover", anchor="w")

    def _on_leave(self, event):
        self.canvas.delete("hover")

    def _draw_arrow(self, x, y, score):
        if score >= 9:
            dot_color = "#FFD700"
        elif score >= 7:
            dot_color = "#FF6666"
        elif score >= 5:
            dot_color = "#88AAFF"
        else:
            dot_color = "#CCCCCC"

        r = 6
        self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                fill=dot_color, outline="#111111", width=2, tags="shot")
        self.canvas.create_line(x, y - r, x, y + r, fill="#111111", width=1, tags="shot")
        self.canvas.create_line(x - r, y, x + r, y, fill="#111111", width=1, tags="shot")

    def _redraw_shots(self):
        self.canvas.delete("shot")
        for shot in self.current_session.get("shot_positions", []):
            x = self._cx + shot["x"] * self._radius
            y = self._cy + shot["y"] * self._radius
            self._draw_arrow(x, y, shot["score"])

    # ── End Controls ─────────────────────────────────────────────────────────

    def _new_end(self):
        if self.current_end_buffer:
            self.current_session["ends"].append(list(self.current_end_buffer))
            self.current_end_buffer = []
        self.current_session["current_end"] = (
            self.current_session.get("current_end", 1) + 1
        )
        self.current_session["stats"] = SmartArcherySystem.computeStatistics(
            self.current_session
        )
        self._save_progress()
        self._update_display()

    def _undo_last(self):
        positions = self.current_session.get("shot_positions", [])
        if self.current_end_buffer:
            self.current_end_buffer.pop()
            if positions:
                positions.pop()
        elif self.current_session.get("ends"):
            last_end = self.current_session["ends"].pop()
            for _ in last_end:
                if positions:
                    positions.pop()
            self.current_session["current_end"] = max(
                1, self.current_session.get("current_end", 1) - 1
            )
            self.current_session["stats"] = SmartArcherySystem.computeStatistics(
                self.current_session
            )
        else:
            return
        self._save_progress()
        self._draw_target()
        self._redraw_shots()
        self._update_display()

    def _clear_end(self):
        current_end_num = self.current_session.get("current_end", 1)
        self.current_end_buffer = []
        positions = self.current_session.get("shot_positions", [])
        self.current_session["shot_positions"] = [
            p for p in positions if p.get("end") != current_end_num
        ]
        self._save_progress()
        self._draw_target()
        self._redraw_shots()
        self._update_display()

    # ── Export ───────────────────────────────────────────────────────────────

    def _export_csv(self):
        msg = self.system.generateReport()
        messagebox.showinfo("Export", msg)

    # ── Statistics Screen ────────────────────────────────────────────────────

    def show_stats(self):
        sessions = self.system.db.sessions
        if not sessions:
            messagebox.showinfo("No Data", "No sessions recorded yet.")
            return

        self._clear()
        self.root.geometry("940x680")

        hdr = tk.Frame(self.root, bg=COLORS["panel"], height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self._btn(hdr, "\u2190 Back", self.show_main_menu,
                  bg=COLORS["panel"], fg=COLORS["subtext"]).pack(side="left", padx=10, pady=8)
        tk.Label(hdr, text="Statistics", font=("Helvetica", 17, "bold"),
                 bg=COLORS["panel"], fg=COLORS["highlight"]).pack(side="left", padx=6)

        content = tk.Frame(self.root, bg=COLORS["bg"])
        content.pack(fill="both", expand=True, padx=28, pady=18)

        # Use SmartArcherySystem for global stats
        gstats = self.system.computeGlobalStats()

        # Summary tiles
        tiles = tk.Frame(content, bg=COLORS["bg"])
        tiles.pack(fill="x", pady=(0, 18))
        for val, label in [
            (gstats["total_sessions"],                     "Sessions"),
            (gstats["total_arrows"],                       "Total Arrows"),
            (gstats.get("global_best_session", 0),         "Best Session"),
            (f"{gstats['overall_average']:.2f}",           "Avg / Arrow"),
        ]:
            t = tk.Frame(tiles, bg=COLORS["accent"])
            t.pack(side="left", expand=True, fill="both", padx=5, pady=4)
            tk.Label(t, text=str(val), font=("Helvetica", 26, "bold"),
                     bg=COLORS["accent"], fg=COLORS["highlight"]).pack(pady=(10, 2))
            tk.Label(t, text=label, font=("Helvetica", 9),
                     bg=COLORS["accent"], fg=COLORS["subtext"]).pack(pady=(0, 10))

        # Score distribution bar chart
        tk.Label(content, text="Score Distribution", font=("Helvetica", 11, "bold"),
                 bg=COLORS["bg"], fg=COLORS["subtext"]).pack(anchor="w", pady=(4, 4))

        dist_frame = tk.Frame(content, bg=COLORS["panel"])
        dist_frame.pack(fill="x", pady=(0, 18))

        # Collect all arrow scores from ends
        dist = {i: 0 for i in range(1, 11)}
        for sess in sessions:
            for end in sess.get("ends", []):
                for arrow in end:
                    val = 10 if arrow == "X" else int(arrow)
                    if 1 <= val <= 10:
                        dist[val] += 1
        max_count = max(dist.values()) if any(dist.values()) else 1

        for ring in range(10, 0, -1):
            count = dist[ring]
            row = tk.Frame(dist_frame, bg=COLORS["panel"])
            row.pack(fill="x", padx=10, pady=2)

            tk.Label(row, text=f"{ring:2d}", font=("Courier", 10, "bold"),
                     bg=COLORS["panel"], fg=RING_COLORS[ring - 1],
                     width=3, anchor="e").pack(side="left")

            bar_host = tk.Frame(row, bg=COLORS["bg"], height=16)
            bar_host.pack(side="left", fill="x", expand=True, padx=6)
            bar_host.pack_propagate(False)
            if count:
                w_ratio = count / max_count
                bar = tk.Frame(bar_host, bg=RING_COLORS[ring - 1], height=16)
                bar.place(relx=0, rely=0, relwidth=w_ratio, relheight=1)

            tk.Label(row, text=f"{count:4d}", font=("Courier", 10),
                     bg=COLORS["panel"], fg=COLORS["subtext"]).pack(side="left")

        # Session table
        tk.Label(content, text="All Sessions", font=("Helvetica", 11, "bold"),
                 bg=COLORS["bg"], fg=COLORS["subtext"]).pack(anchor="w", pady=(4, 4))

        tbl_frame = tk.Frame(content, bg=COLORS["panel"])
        tbl_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=COLORS["panel"], foreground=COLORS["text"],
                        fieldbackground=COLORS["panel"], rowheight=24)
        style.configure("Treeview.Heading",
                        background=COLORS["accent"], foreground=COLORS["text"],
                        font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", COLORS["highlight"])])

        cols = ("Name", "Date", "Distance", "Equipment", "Arrows", "Score", "Avg")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=6)
        widths = (160, 130, 80, 100, 70, 70, 70)
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")

        for sess in reversed(sessions):
            stats = sess.get("stats", {})
            arrow_count = stats.get("arrow_count", 0)
            total_score = stats.get("total_score", 0)
            avg = stats.get("average_arrow", 0.0)
            tree.insert("", "end", values=(
                sess.get("name", "?"),
                sess.get("date", "?"),
                sess.get("distance", ""),
                sess.get("equipment_notes", ""),
                arrow_count,
                total_score,
                f"{avg:.2f}",
            ))

        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)


if __name__ == "__main__":
    ArcheryTracker()
