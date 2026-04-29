# Smart Archery Tracker

Single-file Python app for tracking archery training sessions — click-to-score
target canvas, per-session and global statistics, JSON persistence, and CSV
export. A text-mode CLI is bundled for non-graphical use.

## Run

```
python archery_tracker.py          # tkinter GUI (default)
python archery_tracker.py --cli    # interactive command-line interface
```

Sessions persist to `sessions.json`; CSV exports go to `archery_export.csv`.
