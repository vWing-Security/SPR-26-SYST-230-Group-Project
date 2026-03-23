"""
archery_system.py
Core business logic for the Smart Archery training tracker.

Author: Smart Archery Team
Classes:
    SmartArcherySystem: Manages session lifecycle — initialization, scoring,
                        statistics calculation, and session persistence.
Dependencies:
    - session_database.SessionDatabase
    - math (for standard deviation)
"""

import math

from session_database import SessionDatabase


class SmartArcherySystem:
    """Core system logic for archery training session management.

    Handles session initialization, arrow score entry, running totals,
    statistics computation, and coordination with the SessionDatabase
    for persistence and retrieval.

    Attributes:
        db (SessionDatabase): Database instance for session persistence.
        current_session (dict or None): The active session being recorded.

    Methods:
        initializeSession(date, distance, target_face, weather, equipment_notes):
            Creates a new blank training session with metadata.
        submitScore(scores):
            Records an end of arrow scores into the current session.
        calculateTotalAndAccuracy():
            Computes running total and accuracy for the current session.
        saveSession():
            Persists the current session to the database.
        requestSessionList():
            Retrieves summary list of all stored sessions.
        requestSessionData(session_id):
            Retrieves full data for a specific session.
        generateReport(filepath):
            Exports all sessions to CSV via the database.
        computeStatistics(session):
            Calculates detailed statistics for a given session dict.
        computeGlobalStats():
            Calculates aggregate statistics across all stored sessions.
    """

    VALID_SCORES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, "X"]

    def __init__(self):
        self.db = SessionDatabase()
        self.current_session = None

    def initializeSession(self, date, distance, target_face, weather, equipment_notes):
        """Creates and stores a new blank training session with metadata.

        Corresponds to step 2 in the Start_Training_Session sequence diagram.

        :param date: Session date string (e.g., '2026-02-25').
        :param distance: Shooting distance string (e.g., '18m', '70m').
        :param target_face: Target type (e.g., '40cm', '80cm', '122cm').
        :param weather: Weather conditions note (e.g., 'Indoor', 'Sunny 72F').
        :param equipment_notes: Equipment config notes (e.g., 'Hoyt Helix 50#').
        :returns: dict — the newly created session dictionary.
        """
        self.current_session = {
            "date": date,
            "distance": distance,
            "target_face": target_face,
            "weather": weather,
            "equipment_notes": equipment_notes,
            "ends": [],
            "stats": {},
        }
        return self.current_session

    def submitScore(self, scores):
        """Records one end of arrow scores into the current session.

        Corresponds to step 5 in the Start_Training_Session sequence diagram.

        :param scores: list of arrow values — integers 0-10 or 'X' for inner 10.
        :returns: dict with 'end_total' and 'running_total'.
        :raises ValueError: If no active session or invalid score values.
        """
        if self.current_session is None:
            raise ValueError("No active session. Call initializeSession() first.")

        for s in scores:
            if s not in self.VALID_SCORES:
                raise ValueError(f"Invalid score '{s}'. Valid: 0-10 or 'X'.")

        self.current_session["ends"].append(scores)
        self.calculateTotalAndAccuracy()

        end_total = sum(10 if a == "X" else a for a in scores)
        running = self.current_session["stats"]["total_score"]
        return {"end_total": end_total, "running_total": running}

    def calculateTotalAndAccuracy(self):
        """Computes running total score and accuracy for the current session.

        Corresponds to step 6 (self-call) in the Start_Training_Session
        sequence diagram. Updates self.current_session['stats'] in place.

        :side effects: Modifies current_session['stats'] with computed values.
        """
        if self.current_session is None:
            return

        stats = self.computeStatistics(self.current_session)
        self.current_session["stats"] = stats

    def saveSession(self):
        """Persists the current session to the database.

        Corresponds to steps 9-11 in the Start_Training_Session sequence diagram.

        :returns: str — status message with the assigned session ID.
        :raises ValueError: If no active session exists.
        """
        if self.current_session is None:
            raise ValueError("No active session to save.")

        self.calculateTotalAndAccuracy()
        sid = self.db.storeSessionData(self.current_session)
        saved = self.current_session
        self.current_session = None
        return f"Session saved with ID {sid}."

    def requestSessionList(self):
        """Retrieves a summary list of all stored sessions from the database.

        Corresponds to steps 2-4 in the Retrieve_Past_Session sequence diagram.

        :returns: list[dict] — summary dicts with 'id', 'date', 'distance',
                  'total_score', 'num_ends'.
        """
        return self.db.ObtainSessionList()

    def requestSessionData(self, session_id):
        """Retrieves full data for a specific past session.

        Corresponds to steps 7-8 in the Retrieve_Past_Session sequence diagram.

        :param session_id: Integer index of the session.
        :returns: dict — full session data, or None if not found.
        """
        return self.db.retrieveSessionData(session_id)

    def generateReport(self, filepath="archery_export.csv"):
        """Triggers CSV export of all sessions via the database.

        Corresponds to steps 11-13 in the Retrieve_Past_Session sequence diagram.

        :param filepath: Output file path for the CSV.
        :returns: str — status message from the database export.
        """
        return self.db.exportReport(filepath)

    @staticmethod
    def computeStatistics(session):
        """Calculates detailed statistics for a single session.

        :param session: dict with an 'ends' key containing list of arrow-score lists.
        :returns: dict with keys:
            - total_score: sum of all arrows
            - max_possible: maximum achievable score
            - accuracy_pct: percentage of max possible
            - arrow_count: total arrows shot
            - average_arrow: mean score per arrow
            - std_dev: standard deviation of arrow scores
            - x_count: number of X (inner 10) hits
            - x_pct: X-count as percentage of total arrows
            - ten_count: number of 10s (including X)
            - personal_best_end: highest single-end total
            - end_scores: list of per-end totals
        """
        ends = session.get("ends", [])
        if not ends:
            return {
                "total_score": 0,
                "max_possible": 0,
                "accuracy_pct": 0.0,
                "arrow_count": 0,
                "average_arrow": 0.0,
                "std_dev": 0.0,
                "x_count": 0,
                "x_pct": 0.0,
                "ten_count": 0,
                "personal_best_end": 0,
                "end_scores": [],
            }

        all_arrows = []
        end_scores = []
        x_count = 0

        for end in ends:
            end_total = 0
            for arrow in end:
                if arrow == "X":
                    all_arrows.append(10)
                    x_count += 1
                    end_total += 10
                else:
                    all_arrows.append(int(arrow))
                    end_total += int(arrow)
            end_scores.append(end_total)

        total = sum(all_arrows)
        count = len(all_arrows)
        max_possible = count * 10
        avg = total / count if count > 0 else 0.0

        # Standard deviation
        if count > 1:
            variance = sum((a - avg) ** 2 for a in all_arrows) / (count - 1)
            std_dev = math.sqrt(variance)
        else:
            std_dev = 0.0

        ten_count = sum(1 for a in all_arrows if a == 10)

        return {
            "total_score": total,
            "max_possible": max_possible,
            "accuracy_pct": round((total / max_possible) * 100, 1)
            if max_possible > 0
            else 0.0,
            "arrow_count": count,
            "average_arrow": round(avg, 2),
            "std_dev": round(std_dev, 2),
            "x_count": x_count,
            "x_pct": round((x_count / count) * 100, 1) if count > 0 else 0.0,
            "ten_count": ten_count,
            "personal_best_end": max(end_scores) if end_scores else 0,
            "end_scores": end_scores,
        }

    def computeGlobalStats(self):
        """Calculates aggregate statistics across all stored sessions.

        Useful for tracking long-term trends and personal bests.

        :returns: dict with keys:
            - total_sessions, total_arrows, overall_average,
              overall_std_dev, global_best_end, global_best_session,
              session_averages (list for trend plotting).
        """
        sessions = self.db.sessions
        if not sessions:
            return {
                "total_sessions": 0,
                "total_arrows": 0,
                "overall_average": 0.0,
                "overall_std_dev": 0.0,
                "global_best_end": 0,
                "global_best_session": 0,
                "session_averages": [],
            }

        all_arrows = []
        session_averages = []
        best_end = 0
        best_session = 0

        for s in sessions:
            stats = s.get("stats", {})
            total = stats.get("total_score", 0)
            best_session = max(best_session, total)
            pb_end = stats.get("personal_best_end", 0)
            best_end = max(best_end, pb_end)

            for end in s.get("ends", []):
                for arrow in end:
                    all_arrows.append(10 if arrow == "X" else int(arrow))

            avg = stats.get("average_arrow", 0.0)
            session_averages.append(
                {"date": s.get("date", "?"), "average": avg, "total": total}
            )

        count = len(all_arrows)
        overall_avg = sum(all_arrows) / count if count else 0.0
        if count > 1:
            var = sum((a - overall_avg) ** 2 for a in all_arrows) / (count - 1)
            overall_std = math.sqrt(var)
        else:
            overall_std = 0.0

        return {
            "total_sessions": len(sessions),
            "total_arrows": count,
            "overall_average": round(overall_avg, 2),
            "overall_std_dev": round(overall_std, 2),
            "global_best_end": best_end,
            "global_best_session": best_session,
            "session_averages": session_averages,
        }


if __name__ == "__main__":
    sys = SmartArcherySystem()
    sys.initializeSession("2026-02-25", "18m", "40cm", "Indoor", "Hoyt Helix 50#")
    sys.submitScore([10, 9, 10, "X", 8, 9])
    sys.submitScore([10, 10, 9, 9, 8, 10])
    print("Stats:", sys.current_session["stats"])
    print(sys.saveSession())
