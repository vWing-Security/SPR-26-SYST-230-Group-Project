"""
smart_archery_ui.py
Command-line interface for the Smart Archery training tracker.

Classes:
    SmartArcheryUI: Interactive CLI that maps to the use cases and sequence
                    diagrams — Start Training Session, Store Scores,
                    Save Session, Retrieve Past Session, Print Scoresheet.
Dependencies:
    - archery_system.SmartArcherySystem
Usage:
    Run as a script:  python smart_archery_ui.py
"""

from archery_system import SmartArcherySystem

BANNER = r"""
 ____                       _        _             _
/ ___| _ __ ___   __ _ _ __| |_     / \   _ __ ___| |__   ___ _ __ _   _
\___ \| '_ ` _ \ / _` | '__| __|   / _ \ | '__/ __| '_ \ / _ \ '__| | | |
 ___) | | | | | | (_| | |  | |_   / ___ \| | | (__| | | |  __/ |  | |_| |
|____/|_| |_| |_|\__,_|_|   \__| /_/   \_\_|  \___|_| |_|\___|_|   \__, |
                                                                     |___/
"""

MAIN_MENU = """
=== Main Menu ===
  [S] Start Training Session
  [R] Retrieve Past Session
  [T] View Score Trends & Stats
  [E] Export to CSV
  [Q] Quit
"""


class SmartArcheryUI:
    """Command-line interface for the Smart Archery training tracker.

    Provides an interactive menu system that implements the use cases
    shown in the UML diagrams:
      - Start Training Session (score entry, running totals)
      - Store Scores / Save Session (persist to database)
      - Retrieve Past Session (view history, details)
      - Print Scoresheet (display formatted scores & stats)

    Attributes:
        sys (SmartArcherySystem): The core system handling business logic.

    Methods:
        run(): Main event loop for the CLI.
        clickStartSession(): Handles new session creation and scoring.
        displayScoringInterface(): Prompts user for end-by-end score entry.
        clickSaveSession(): Saves the current session.
        selectViewPastSessions(): Lists and displays past sessions.
        displaySessionDetails(session): Formats and prints full session data.
        displayTrends(): Shows global statistics and score trends.
        clickExport(): Triggers CSV export.
    """

    def __init__(self):
        self.sys = SmartArcherySystem()

    def run(self):
        """Main event loop. Displays menu and dispatches to handlers."""
        print(BANNER)
        print("Welcome to Smart Archery — your training session tracker.\n")

        while True:
            print(MAIN_MENU)
            choice = input(">> ").strip().upper()

            if choice == "S":
                self.clickStartSession()
            elif choice == "R":
                self.selectViewPastSessions()
            elif choice == "T":
                self.displayTrends()
            elif choice == "E":
                self.clickExport()
            elif choice == "Q":
                print("\nSession ended. Train hard!\n")
                break
            else:
                print("Unknown command. Valid options: S, R, T, E, Q")

    # ── Start Training Session (Sequence Diagram: Start_Training_Session) ──

    def clickStartSession(self):
        """Step 1: User clicks Start Session. Collects metadata and enters scoring flow.

        Maps to the Start_Training_Session sequence diagram:
        1 → clickStartSession, 2 → initializeSession, 3 → displayScoringInterface
        """
        print("\n--- New Training Session ---")
        date = input("  Date (YYYY-MM-DD): ").strip() or "unknown"
        distance = input("  Distance (e.g. 18m, 70m): ").strip() or "unknown"
        target_face = (
            input("  Target face (e.g. 40cm, 80cm, 122cm): ").strip() or "unknown"
        )
        weather = input("  Weather / conditions: ").strip() or "N/A"
        equipment = input("  Equipment notes: ").strip() or "N/A"

        # Step 2: initializeSession
        self.sys.initializeSession(date, distance, target_face, weather, equipment)
        print(f"\n  Session started: {date} @ {distance}")

        # Step 3: displayScoringInterface
        self.displayScoringInterface()

    def displayScoringInterface(self):
        """Steps 3-7: Scoring loop — user enters arrow scores end by end.

        Arrow input format: space-separated values (0-10 or X).
        Type 'done' to finish scoring, 'undo' to remove last end.

        After each end:
          - Step 5: submitScore → Step 6: calculateTotal&Accuracy
          - Step 7: updateRunningTotal (displayed to user)
        """
        print("\n  Enter arrow scores per end (space-separated, 0-10 or X).")
        print("  Type 'done' when finished, 'undo' to remove last end.\n")

        end_num = 1
        while True:
            raw = input(f"  End {end_num}: ").strip()

            if raw.lower() == "done":
                break
            if raw.lower() == "undo":
                ends = self.sys.current_session["ends"]
                if ends:
                    ends.pop()
                    self.sys.calculateTotalAndAccuracy()
                    end_num -= 1
                    print("    Last end removed.")
                else:
                    print("    Nothing to undo.")
                continue

            # Parse scores
            scores = self._parse_scores(raw)
            if scores is None:
                continue

            # Step 5: submitScore → Step 6: calculateTotal&Accuracy
            try:
                result = self.sys.submitScore(scores)
            except ValueError as e:
                print(f"    Error: {e}")
                continue

            # Step 7: updateRunningTotal
            stats = self.sys.current_session["stats"]
            print(
                f"    End total: {result['end_total']}  |  "
                f"Running: {result['running_total']}  |  "
                f"Avg arrow: {stats['average_arrow']}  |  "
                f"X-count: {stats['x_count']}"
            )
            end_num += 1

        # After scoring, offer to save
        if self.sys.current_session and self.sys.current_session["ends"]:
            self._printScoresheet(self.sys.current_session)
            save = input("\n  Save this session? (Y/n): ").strip().upper()
            if save != "N":
                self.clickSaveSession()
        else:
            print("  No scores recorded. Session discarded.")
            self.sys.current_session = None

    def clickSaveSession(self):
        """Steps 8-12: Saves the current session to the database.

        Maps to Start_Training_Session steps:
        8 → clickSaveSession, 9 → saveSession,
        10 → storeSessionData, 11 → status, 12 → displayConfirmation
        """
        try:
            # Steps 9-11
            status = self.sys.saveSession()
            # Step 12: displayConfirmation
            print(f"  {status}")
        except ValueError as e:
            print(f"  Error: {e}")

    # ── Retrieve Past Session (Sequence Diagram: Retrieve_Past_Session) ──

    def selectViewPastSessions(self):
        """Steps 1-9: Browse and view past training sessions.

        Maps to Retrieve_Past_Session sequence diagram:
        1 → selectViewPastSessions, 2-4 → requestSessionList/ObtainSessionList,
        5 → displaySessionList, 6 → selectSession, 7-9 → requestSessionData
        """
        # Steps 2-4: Get session list
        session_list = self.sys.requestSessionList()

        if not session_list:
            print("\n  No past sessions found.")
            return

        # Step 5: displaySessionList
        print(f"\n--- Past Sessions ({len(session_list)} total) ---")
        print(f"  {'ID':>4}  {'Date':<12}  {'Distance':<10}  {'Ends':>5}  {'Score':>6}")
        print(f"  {'─' * 4}  {'─' * 12}  {'─' * 10}  {'─' * 5}  {'─' * 6}")
        for s in session_list:
            print(
                f"  {s['id']:>4}  {s['date']:<12}  {s['distance']:<10}  "
                f"{s['num_ends']:>5}  {s['total_score']:>6}"
            )

        # Step 6: selectSession
        raw = input("\n  Enter session ID to view (or Enter to go back): ").strip()
        if not raw:
            return

        try:
            session_id = int(raw)
        except ValueError:
            print("  Invalid ID.")
            return

        # Steps 7-8: requestSessionData / retrieveSessionData
        session = self.sys.requestSessionData(session_id)
        if session is None:
            print(f"  Session {session_id} not found.")
            return

        # Step 9: displaySessionDetails
        self.displaySessionDetails(session)

        # Optional export (steps 10-14)
        exp = input("\n  Export all sessions to CSV? (y/N): ").strip().upper()
        if exp == "Y":
            self.clickExport()

    def displaySessionDetails(self, session):
        """Formats and prints full session details including scoresheet and stats.

        :param session: Full session dictionary from the database.
        """
        print(f"\n{'=' * 55}")
        print(f"  Date: {session.get('date', 'N/A')}")
        print(
            f"  Distance: {session.get('distance', 'N/A')}  |  "
            f"Target: {session.get('target_face', 'N/A')}"
        )
        print(f"  Weather: {session.get('weather', 'N/A')}")
        print(f"  Equipment: {session.get('equipment_notes', 'N/A')}")
        print(f"{'=' * 55}")
        self._printScoresheet(session)

    # ── Trends & Global Stats ──

    def displayTrends(self):
        """Displays aggregate statistics and score trend across all sessions."""
        gstats = self.sys.computeGlobalStats()

        if gstats["total_sessions"] == 0:
            print("\n  No sessions recorded yet.")
            return

        print(f"\n{'=' * 55}")
        print("  GLOBAL STATISTICS")
        print(f"{'=' * 55}")
        print(f"  Sessions recorded:    {gstats['total_sessions']}")
        print(f"  Total arrows shot:    {gstats['total_arrows']}")
        print(f"  Overall avg arrow:    {gstats['overall_average']}")
        print(f"  Overall std dev:      {gstats['overall_std_dev']}")
        print(f"  Best single end:      {gstats['global_best_end']}")
        print(f"  Best session total:   {gstats['global_best_session']}")

        # Simple text-based trend chart
        avgs = gstats["session_averages"]
        if len(avgs) > 1:
            print(f"\n  --- Score Trend (session avg arrow) ---")
            max_avg = max(a["average"] for a in avgs) or 1
            chart_width = 30
            for entry in avgs:
                bar_len = int((entry["average"] / max_avg) * chart_width)
                bar = "█" * bar_len
                print(f"  {entry['date']:>12}  {bar} {entry['average']:.1f}")
        print()

    # ── Export ──

    def clickExport(self):
        """Steps 10-14 of Retrieve_Past_Session: Triggers CSV export.

        Maps to: 10 → clickExport, 11 → generateReport,
        12 → exportReport, 13 → status, 14 → displayConfirmation
        """
        filepath = input("  Filename (default: archery_export.csv): ").strip()
        if not filepath:
            filepath = "archery_export.csv"
        # Steps 11-13
        status = self.sys.generateReport(filepath)
        # Step 14: displayConfirmation
        print(f"  {status}")

    # ── Internal Helpers ──

    def _parse_scores(self, raw):
        """Parses a space-separated string of arrow scores.

        :param raw: User input string (e.g., '10 9 X 8 10 9').
        :returns: list of validated scores, or None if parsing fails.
        """
        tokens = raw.split()
        scores = []
        for t in tokens:
            t = t.strip().upper()
            if t == "X":
                scores.append("X")
            else:
                try:
                    val = int(t)
                    if 0 <= val <= 10:
                        scores.append(val)
                    else:
                        print(f"    Score '{val}' out of range (0-10). Try again.")
                        return None
                except ValueError:
                    print(f"    Invalid score '{t}'. Use 0-10 or X.")
                    return None
        if not scores:
            print("    No scores entered. Try again.")
            return None
        return scores

    def _printScoresheet(self, session):
        """Prints a formatted scoresheet for a session.

        :param session: Session dict with 'ends' and 'stats' keys.
        """
        ends = session.get("ends", [])
        stats = session.get("stats", {})

        if not ends:
            print("  (No ends recorded)")
            return

        # Determine arrows per end for column formatting
        max_arrows = max(len(e) for e in ends)

        # Header
        arrow_hdr = "  ".join(f"A{i + 1:>1}" for i in range(max_arrows))
        print(f"\n  {'End':>4}  {arrow_hdr}   Total")
        print(f"  {'─' * 4}  {'─' * (max_arrows * 4)}  {'─' * 5}")

        running = 0
        for i, end in enumerate(ends):
            arrow_str = ""
            end_total = 0
            for a in end:
                if a == "X":
                    arrow_str += f"{'X':>4}"
                    end_total += 10
                else:
                    arrow_str += f"{a:>4}"
                    end_total += int(a)
            # Pad if fewer arrows than max
            arrow_str += "    " * (max_arrows - len(end))
            running += end_total
            print(f"  {i + 1:>4} {arrow_str}  {end_total:>5}")

        print(f"  {'─' * 4}  {'─' * (max_arrows * 4)}  {'─' * 5}")
        print(
            f"  {'Total':>4}  {' ' * (max_arrows * 4)}  {stats.get('total_score', running):>5}"
        )

        print(f"\n  Accuracy:  {stats.get('accuracy_pct', 0.0)}% of max")
        print(f"  Avg arrow: {stats.get('average_arrow', 0.0)}")
        print(f"  Std dev:   {stats.get('std_dev', 0.0)}")
        print(f"  X-count:   {stats.get('x_count', 0)} ({stats.get('x_pct', 0.0)}%)")
        print(f"  10s total: {stats.get('ten_count', 0)}")
        print(f"  Best end:  {stats.get('personal_best_end', 0)}")


if __name__ == "__main__":
    ui = SmartArcheryUI()
    ui.run()
