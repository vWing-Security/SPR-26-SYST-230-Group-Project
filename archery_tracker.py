import tkinter as tk
from tkinter import ttk, messagebox
import math
import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archery_data.json")

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


# ─── Data Model ──────────────────────────────────────────────────────────────

class Session:
    def __init__(self, name, distance="", bow_type=""):
        self.name = name
        self.date = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.distance = distance
        self.bow_type = bow_type
        self.shots = []          # {"x": float, "y": float, "score": int, "end": int}
        self.current_end = 1

    def add_shot(self, x_norm, y_norm, score):
        self.shots.append({"x": x_norm, "y": y_norm, "score": score, "end": self.current_end})

    def total_score(self):
        return sum(s["score"] for s in self.shots)

    def shot_count(self):
        return len(self.shots)

    def average_score(self):
        return self.total_score() / len(self.shots) if self.shots else 0.0

    def end_scores(self):
        ends = {}
        for shot in self.shots:
            ends.setdefault(shot["end"], []).append(shot["score"])
        return ends

    def to_dict(self):
        return {
            "name": self.name, "date": self.date,
            "distance": self.distance, "bow_type": self.bow_type,
            "shots": self.shots, "current_end": self.current_end,
        }

    @classmethod
    def from_dict(cls, d):
        s = cls(d["name"], d.get("distance", ""), d.get("bow_type", ""))
        s.date = d["date"]
        s.shots = d["shots"]
        s.current_end = d.get("current_end", 1)
        return s


# ─── App ─────────────────────────────────────────────────────────────────────

class ArcheryTracker:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Archery Tracker")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(800, 600)

        self.sessions = self._load_sessions()
        self.current_session = None

        self.show_main_menu()
        self.root.mainloop()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_sessions(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    return [Session.from_dict(d) for d in json.load(f)]
            except Exception:
                return []
        return []

    def _save(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump([s.to_dict() for s in self.sessions], f, indent=2)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ── Navigation helpers ────────────────────────────────────────────────────

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

    # ── Main Menu ─────────────────────────────────────────────────────────────

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
        ]):
            self._btn(btns, label, cmd, width=22).grid(row=i, column=0, pady=7)

        self._btn(btns, "Quit", self.root.quit,
                  bg="#5a0000", fg=COLORS["text"], width=22).grid(row=3, column=0, pady=7)

        # Recent sessions
        if self.sessions:
            tk.Label(body, text="Recent Sessions", font=("Helvetica", 12, "bold"),
                     bg=COLORS["bg"], fg=COLORS["subtext"]).pack(pady=(28, 6))

            for session in list(reversed(self.sessions))[:5]:
                row = tk.Frame(body, bg=COLORS["panel"], cursor="hand2")
                row.pack(fill="x", pady=3)
                meta = f"{session.distance}  {session.bow_type}".strip()
                label = f"  {session.name}    {session.date}    {session.shot_count()} shots    {session.total_score()} pts"
                if meta:
                    label += f"    [{meta}]"
                lbl = tk.Label(row, text=label, font=("Helvetica", 10),
                               bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
                lbl.pack(fill="x", padx=8, pady=7)
                for widget in (row, lbl):
                    widget.bind("<Button-1>", lambda e, s=session: self._open_session(s))
                    widget.bind("<Enter>", lambda e, r=row, l=lbl: [r.configure(bg=COLORS["accent"]), l.configure(bg=COLORS["accent"])])
                    widget.bind("<Leave>", lambda e, r=row, l=lbl: [r.configure(bg=COLORS["panel"]), l.configure(bg=COLORS["panel"])])

    # ── New Session Dialog ────────────────────────────────────────────────────

    def _new_session_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Session")
        dlg.geometry("380x280")
        dlg.configure(bg=COLORS["bg"])
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text="New Session", font=("Helvetica", 15, "bold"),
                 bg=COLORS["bg"], fg=COLORS["highlight"]).pack(pady=14)

        entries = {}
        defaults = [
            ("Session Name", f"Session {len(self.sessions) + 1}"),
            ("Distance (e.g. 20m)", ""),
            ("Bow Type", ""),
        ]
        for label, default in defaults:
            f = tk.Frame(dlg, bg=COLORS["bg"])
            f.pack(fill="x", padx=30, pady=4)
            tk.Label(f, text=label, font=("Helvetica", 10), bg=COLORS["bg"],
                     fg=COLORS["subtext"], anchor="w").pack(fill="x")
            e = tk.Entry(f, font=("Helvetica", 11), bg=COLORS["panel"],
                         fg=COLORS["text"], insertbackground=COLORS["text"],
                         relief="flat", bd=4)
            e.insert(0, default)
            e.pack(fill="x")
            entries[label] = e

        def start():
            name = entries["Session Name"].get().strip() or defaults[0][1]
            dist = entries["Distance (e.g. 20m)"].get().strip()
            bow  = entries["Bow Type"].get().strip()
            s = Session(name, dist, bow)
            self.sessions.append(s)
            self._save()
            dlg.destroy()
            self._open_session(s)

        self._btn(dlg, "Start Session", start,
                  bg=COLORS["highlight"], fg="white").pack(pady=18)
        entries["Session Name"].focus_set()
        dlg.bind("<Return>", lambda e: start())

    # ── Session List ─────────────────────────────────────────────────────────

    def _open_session_list(self):
        if not self.sessions:
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

        for s in reversed(self.sessions):
            lb.insert(tk.END, f"  {s.name}   {s.date}   {s.shot_count()} shots   {s.total_score()} pts")

        def open_sel(event=None):
            sel = lb.curselection()
            if sel:
                idx = len(self.sessions) - 1 - sel[0]
                dlg.destroy()
                self._open_session(self.sessions[idx])

        lb.bind("<Double-Button-1>", open_sel)
        self._btn(dlg, "Open", open_sel).pack(pady=10)

    def _open_session(self, session):
        self.current_session = session
        self.show_target_screen()

    # ── Target Screen ─────────────────────────────────────────────────────────

    def show_target_screen(self):
        self._clear()
        self.root.geometry("1080x720")
        session = self.current_session

        # Top bar
        topbar = tk.Frame(self.root, bg=COLORS["panel"], height=48)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        self._btn(topbar, "← Menu", self._back_to_menu,
                  bg=COLORS["panel"], fg=COLORS["subtext"]).pack(side="left", padx=8, pady=6)

        title = session.name
        if session.distance or session.bow_type:
            title += f"   [{session.distance}  {session.bow_type}".strip() + "]"
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

        self._draw_target()
        self._redraw_shots()

        # Right: sidebar
        sidebar = tk.Frame(body, bg=COLORS["panel"], width=270)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

    def _back_to_menu(self):
        self._save()
        self.current_session = None
        self.show_main_menu()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        # Score card
        card = tk.Frame(parent, bg=COLORS["accent"])
        card.pack(fill="x", padx=10, pady=(14, 6))

        tk.Label(card, text="TOTAL SCORE", font=("Helvetica", 9),
                 bg=COLORS["accent"], fg=COLORS["subtext"]).pack(pady=(10, 0))
        self._score_var = tk.StringVar(value=str(self.current_session.total_score()))
        tk.Label(card, textvariable=self._score_var, font=("Helvetica", 40, "bold"),
                 bg=COLORS["accent"], fg=COLORS["highlight"]).pack()

        row = tk.Frame(card, bg=COLORS["accent"])
        row.pack(pady=(0, 12))
        self._shots_var = tk.StringVar()
        self._avg_var   = tk.StringVar()
        self._end_var   = tk.StringVar()
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
        s = self.current_session
        self._shots_var.set(str(s.shot_count()))
        self._avg_var.set(f"{s.average_score():.1f}")
        self._end_var.set(str(s.current_end))

    def _update_display(self):
        s = self.current_session
        self._score_var.set(str(s.total_score()))
        self._refresh_vars()
        self._refresh_shot_list()

    def _refresh_shot_list(self):
        self._shot_lb.delete(0, tk.END)
        ends = self.current_session.end_scores()
        for end_num in sorted(ends):
            scores = ends[end_num]
            parts  = "  ".join(str(v) for v in scores)
            total  = sum(scores)
            self._shot_lb.insert(tk.END, f"End {end_num}: {parts:<20} = {total}")
        self._shot_lb.see(tk.END)

    # ── Target Drawing ────────────────────────────────────────────────────────

    def _draw_target(self):
        cs = self._canvas_size
        cx = cy = cs // 2
        self._cx = cx
        self._cy = cy
        self._radius = cs // 2 - 12

        self.canvas.delete("target")

        # Rings: draw 10 → 1 (outside in, so inner rings paint over outer)
        for ring in range(10, 0, -1):
            r = self._radius * ring / 10
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     fill=RING_COLORS[ring - 1],
                                     outline="#00000044", width=1,
                                     tags="target")

        # Ring score labels — right side of each ring
        for ring in range(1, 11):
            r_outer = self._radius * ring / 10
            r_inner = self._radius * (ring - 1) / 10
            mid_r   = (r_outer + r_inner) / 2 if ring > 1 else r_outer * 0.5
            self.canvas.create_text(cx + mid_r, cy, text=str(ring),
                                     font=("Helvetica", 7, "bold"),
                                     fill=RING_TEXT_COLORS[ring - 1],
                                     tags="target")

        # Center crosshair
        self.canvas.create_line(cx - 5, cy, cx + 5, cy, fill="#00000066", width=1, tags="target")
        self.canvas.create_line(cx, cy - 5, cx, cy + 5, fill="#00000066", width=1, tags="target")

    def _score_for(self, x, y):
        dist  = math.hypot(x - self._cx, y - self._cy)
        ratio = dist / self._radius
        if ratio >= 1.0:
            return 0
        score = 10 - int(ratio * 10)
        return max(1, min(10, score))

    # ── Canvas Events ─────────────────────────────────────────────────────────

    def _on_click(self, event):
        x, y  = event.x, event.y
        score = self._score_for(x, y)
        if score == 0:
            return  # click outside target

        x_norm = (x - self._cx) / self._radius
        y_norm = (y - self._cy) / self._radius
        self.current_session.add_shot(x_norm, y_norm, score)
        self._save()

        self._draw_arrow(x, y, score)
        self._update_display()

    def _on_hover(self, event):
        self.canvas.delete("hover")
        score = self._score_for(event.x, event.y)
        if score > 0:
            self.canvas.create_text(event.x + 16, event.y - 14,
                                     text=str(score), font=("Helvetica", 14, "bold"),
                                     fill="white", tags="hover",
                                     anchor="w")

    def _on_leave(self, event):
        self.canvas.delete("hover")

    def _draw_arrow(self, x, y, score):
        # Dot color by score tier
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
        for shot in self.current_session.shots:
            x = self._cx + shot["x"] * self._radius
            y = self._cy + shot["y"] * self._radius
            self._draw_arrow(x, y, shot["score"])

    # ── End Controls ──────────────────────────────────────────────────────────

    def _new_end(self):
        self.current_session.current_end += 1
        self._save()
        self._update_display()

    def _undo_last(self):
        if self.current_session.shots:
            self.current_session.shots.pop()
            self._save()
            self._draw_target()
            self._redraw_shots()
            self._update_display()

    def _clear_end(self):
        e = self.current_session.current_end
        self.current_session.shots = [s for s in self.current_session.shots if s["end"] != e]
        self._save()
        self._draw_target()
        self._redraw_shots()
        self._update_display()

    # ── Statistics Screen ─────────────────────────────────────────────────────

    def show_stats(self):
        if not self.sessions:
            messagebox.showinfo("No Data", "No sessions recorded yet.")
            return

        self._clear()
        self.root.geometry("940x680")

        hdr = tk.Frame(self.root, bg=COLORS["panel"], height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self._btn(hdr, "← Back", self.show_main_menu,
                  bg=COLORS["panel"], fg=COLORS["subtext"]).pack(side="left", padx=10, pady=8)
        tk.Label(hdr, text="Statistics", font=("Helvetica", 17, "bold"),
                 bg=COLORS["panel"], fg=COLORS["highlight"]).pack(side="left", padx=6)

        content = tk.Frame(self.root, bg=COLORS["bg"])
        content.pack(fill="both", expand=True, padx=28, pady=18)

        all_shots   = [s for sess in self.sessions for s in sess.shots]
        total_shots = len(all_shots)
        total_score = sum(s["score"] for s in all_shots)
        avg         = total_score / total_shots if total_shots else 0

        # Summary tiles
        tiles = tk.Frame(content, bg=COLORS["bg"])
        tiles.pack(fill="x", pady=(0, 18))
        for val, label in [
            (len(self.sessions), "Sessions"),
            (total_shots,        "Total Arrows"),
            (total_score,        "Total Score"),
            (f"{avg:.2f}",       "Avg / Arrow"),
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

        dist = {i: 0 for i in range(1, 11)}
        for s in all_shots:
            dist[s["score"]] += 1
        max_count = max(dist.values()) if dist else 1

        for ring in range(10, 0, -1):
            count = dist[ring]
            row   = tk.Frame(dist_frame, bg=COLORS["panel"])
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

        cols = ("Name", "Date", "Distance", "Bow", "Arrows", "Score", "Avg")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=6)
        widths = (160, 130, 80, 100, 70, 70, 70)
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")

        for sess in reversed(self.sessions):
            tree.insert("", "end", values=(
                sess.name, sess.date, sess.distance, sess.bow_type,
                sess.shot_count(), sess.total_score(), f"{sess.average_score():.2f}",
            ))

        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)


if __name__ == "__main__":
    ArcheryTracker()
