"""
session_database.py
Manages persistent storage and retrieval of archery training sessions.

Author: Smart Archery Team
Classes:
    SessionDatabase: Handles storing, retrieving, listing, and exporting
                     session data to/from a JSON file.
Constants:
    DB_FILE (str): Path to the JSON file where sessions are stored.
Dependencies:
    - json, os, csv
"""

import json
import os
import csv

DB_FILE = "sessions.json"


class SessionDatabase:
    """Manages persistent storage and retrieval of archery training sessions.

    Sessions are stored as a list of dictionaries in a JSON file. Each session
    contains scoring data, metadata (distance, target face, weather, equipment),
    and computed statistics.

    Attributes:
        db_file (str): Path to the JSON storage file.
        sessions (list): In-memory list of all stored session dictionaries.

    Methods:
        storeSessionData(session_dict):
            Appends a session to storage and writes to disk.
        ObtainSessionList():
            Returns a summary list of all stored sessions.
        retrieveSessionData(session_id):
            Retrieves full session data by its index ID.
        exportReport(filepath):
            Exports all session data to a CSV file.
        load():
            Loads sessions from the JSON file into memory.
        save():
            Writes all in-memory sessions to the JSON file.
    """

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.sessions = []
        self.load()

    def storeSessionData(self, session_dict):
        """Appends a new session dictionary to storage and persists to disk.

        :param session_dict: Dictionary containing session data with keys:
            'date', 'distance', 'target_face', 'weather', 'equipment_notes',
            'ends', and 'stats'.
        :returns: int — the session ID (index) of the newly stored session.
        :side effects: Updates self.sessions and writes to the JSON file.
        """
        self.sessions.append(session_dict)
        self.save()
        return len(self.sessions) - 1

    def ObtainSessionList(self):
        """Returns a lightweight summary list of all stored sessions.

        Each summary includes the session index, date, distance, and total score
        so the user can identify which session to retrieve in full.

        :returns: list[dict] — list of summary dicts with keys
            'id', 'date', 'distance', 'total_score', 'num_ends'.
        """
        summary = []
        for i, s in enumerate(self.sessions):
            summary.append({
                "id": i,
                "date": s.get("date", "N/A"),
                "distance": s.get("distance", "N/A"),
                "total_score": s.get("stats", {}).get("total_score", 0),
                "num_ends": len(s.get("ends", []))
            })
        return summary

    def retrieveSessionData(self, session_id):
        """Retrieves the full session dictionary for a given session ID.

        :param session_id: Integer index of the session to retrieve.
        :returns: dict — the full session data, or None if not found.
        :raises IndexError: If session_id is out of range.
        """
        if 0 <= session_id < len(self.sessions):
            return self.sessions[session_id]
        return None

    def exportReport(self, filepath="archery_export.csv"):
        """Exports all session data to a CSV file for external backup/analysis.

        Each row represents one end within a session. Columns include session
        metadata, end number, individual arrow scores, and end total.

        :param filepath: Output CSV file path (default: 'archery_export.csv').
        :returns: str — status message indicating success or failure.
        """
        if not self.sessions:
            return "No sessions to export."

        try:
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                # Determine max arrows per end for column headers
                max_arrows = 0
                for s in self.sessions:
                    for end in s.get("ends", []):
                        max_arrows = max(max_arrows, len(end))
                if max_arrows == 0:
                    max_arrows = 6

                header = ["Session_ID", "Date", "Distance", "Target_Face",
                          "Weather", "Equipment_Notes", "End_Number"]
                header += [f"Arrow_{i+1}" for i in range(max_arrows)]
                header += ["End_Total"]
                writer.writerow(header)

                for sid, s in enumerate(self.sessions):
                    for eidx, end in enumerate(s.get("ends", [])):
                        row = [
                            sid,
                            s.get("date", ""),
                            s.get("distance", ""),
                            s.get("target_face", ""),
                            s.get("weather", ""),
                            s.get("equipment_notes", ""),
                            eidx + 1
                        ]
                        # Pad arrows to max_arrows columns
                        arrow_scores = []
                        for a in end:
                            arrow_scores.append("X" if a == "X" else str(a))
                        arrow_scores += [""] * (max_arrows - len(end))
                        row += arrow_scores

                        end_total = sum(10 if a == "X" else int(a) for a in end)
                        row.append(end_total)
                        writer.writerow(row)

            return f"Exported {len(self.sessions)} session(s) to {filepath}"
        except Exception as e:
            return f"Export failed: {e}"

    def load(self):
        """Loads sessions from the JSON file into memory.

        If the file does not exist, initializes an empty session list
        and creates the file.
        """
        try:
            with open(self.db_file, "r") as f:
                self.sessions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.sessions = []
            self.save()

    def save(self):
        """Writes the current in-memory session list to the JSON file.

        :side effects: Overwrites the existing JSON file with current data.
        """
        with open(self.db_file, "w") as f:
            json.dump(self.sessions, f, indent=2)


if __name__ == "__main__":
    db = SessionDatabase("test_sessions.json")
    print(f"Loaded {len(db.sessions)} session(s).")
