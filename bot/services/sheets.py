import datetime
from typing import Any, Optional

import gspread
from google.oauth2.service_account import Credentials

import bot.config

_instance = None


def get_sheets() -> "SheetsService":
    global _instance
    if _instance is None:
        _instance = SheetsService()
    return _instance


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsService:

    SHEETS = {
        "members": ["tg_id", "username", "rating", "joined", "invited_by"],
        "games": ["id", "p1_id", "p2_id", "winner_id", "result", "delta", "date"],
        "pending_members": ["id", "tg_id", "username", "invited_by", "date", "status"],
        "pending_games": ["id", "p1_id", "p2_id", "winner_id", "result", "submitted_by", "date", "status"],
        "admins": ["tg_id", "username"],
    }

    def __init__(self, spreadsheet_id: str | None = None, credentials_path: str | None = None):
        self.spreadsheet_id = spreadsheet_id or bot.config.SPREADSHEET_ID
        creds_path = credentials_path or bot.config.GOOGLE_CREDENTIALS
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(self.spreadsheet_id)
        self.init_sheets()

    def _ws(self, name: str):
        return self.sh.worksheet(name)

    def init_sheets(self) -> None:
        existing = {ws.title for ws in self.sh.worksheets()}
        for name, headers in self.SHEETS.items():
            if name not in existing:
                self.sh.add_worksheet(title=name, rows=100, cols=len(headers))
                self._ws(name).update(range_name="A1", values=[headers], value_input_option="RAW")

    def _get_values(self, range_name: str) -> list[list[Any]]:
        sheet_name, range_part = range_name.split("!", 1)
        return self._ws(sheet_name).get_values(range_part)

    def _append_values(self, range_name: str, values: list[list[Any]]) -> None:
        sheet_name, _ = range_name.split("!", 1)
        self._ws(sheet_name).append_rows(values, value_input_option="USER_ENTERED")

    def _update_range(self, range_name: str, values: list[list[Any]]) -> None:
        self._ws(range_name.split("!")[0]).update(range_name.split("!")[1], values, value_input_option="RAW")

    @staticmethod
    def _row_to_dict(headers: list[str], row: list[Any]) -> dict[str, Any]:
        return {h: (row[i] if i < len(row) else "") for i, h in enumerate(headers)}

    # ── Members ──────────────────────────────────────────────────────

    def get_members(self) -> list[dict[str, Any]]:
        rows = self._get_values("members!A2:E")
        headers = self.SHEETS["members"]
        return [self._row_to_dict(headers, row) for row in rows if row]

    def get_member(self, tg_id: int) -> Optional[dict[str, Any]]:
        str_tg = str(tg_id)
        rows = self._get_values("members!A2:E")
        headers = self.SHEETS["members"]
        for row in rows:
            if row and row[0] == str_tg:
                return self._row_to_dict(headers, row)
        return None

    def add_member(self, tg_id: int, username: str, invited_by: str = "") -> None:
        today = datetime.date.today().isoformat()
        self._append_values("members!A:E", [[str(tg_id), username, "1500", today, str(invited_by)]])

    def update_member_rating(self, tg_id: int, delta: int) -> None:
        rows = self._get_values("members!A2:E")
        for i, row in enumerate(rows):
            if row and row[0] == str(tg_id):
                current = int(row[2]) if row[2] else 1500
                self._update_range(f"members!C{i + 2}", [[str(current + delta)]])
                return

    def remove_member(self, tg_id: int) -> None:
        rows = self._get_values("members!A2:E")
        for i, row in enumerate(rows):
            if row and row[0] == str(tg_id):
                row_num = i + 2
                self._ws("members").update(f"A{row_num}:E{row_num}", [["" for _ in range(5)]], value_input_option="RAW")
                return

    def update_member_tg_id(self, username: str, new_tg_id: int) -> bool:
        rows = self._get_values("members!A2:E")
        for i, row in enumerate(rows):
            if row and len(row) > 1 and row[1].lstrip("@") == username.lstrip("@") and (not row[0] or row[0] in ("", "0")):
                self._update_range(f"members!A{i + 2}", [[str(new_tg_id)]])
                return True
        return None

    # ── Games ────────────────────────────────────────────────────────

    def get_games(self) -> list[dict[str, Any]]:
        rows = self._get_values("games!A2:G")
        headers = self.SHEETS["games"]
        return [self._row_to_dict(headers, row) for row in rows if row]

    def add_game(self, p1_id: int, p2_id: int, winner_id: int, result: str, delta: int) -> None:
        rows = self._get_values("games!A2:A")
        next_id = len([r for r in rows if r and r[0]]) + 1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._append_values("games!A:G", [[str(next_id), str(p1_id), str(p2_id), str(winner_id), result, str(delta), now]])

    # ── Pending Members ──────────────────────────────────────────────

    def get_pending_members(self, status: str = "pending") -> list[dict[str, Any]]:
        rows = self._get_values("pending_members!A2:F")
        headers = self.SHEETS["pending_members"]
        return [
            self._row_to_dict(headers, row)
            for row in rows
            if row and len(row) > 5 and row[5] == status
        ]

    def add_pending_member(self, tg_id: str, username: str, invited_by: str) -> int:
        rows = self._get_values("pending_members!A2:A")
        next_id = len([r for r in rows if r and r[0]]) + 1
        today = datetime.date.today().isoformat()
        self._append_values("pending_members!A:F", [[str(next_id), str(tg_id), username, str(invited_by), today, "pending"]])
        return next_id

    def update_pending_member(self, id: int, status: str) -> None:
        self._update_range(f"pending_members!F{id + 1}", [[status]])

    # ── Pending Games ────────────────────────────────────────────────

    def get_pending_games(self, status: str = "pending") -> list[dict[str, Any]]:
        rows = self._get_values("pending_games!A2:H")
        headers = self.SHEETS["pending_games"]
        return [
            self._row_to_dict(headers, row)
            for row in rows
            if row and len(row) > 7 and row[7] == status
        ]

    def add_pending_game(self, p1_id: int, p2_id: int, winner_id: int, result: str, submitted_by: int) -> int:
        rows = self._get_values("pending_games!A2:A")
        next_id = len([r for r in rows if r and r[0]]) + 1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._append_values("pending_games!A:H", [[str(next_id), str(p1_id), str(p2_id), str(winner_id), result, str(submitted_by), now, "pending"]])
        return next_id

    def update_pending_game(self, id: int, status: str) -> None:
        self._update_range(f"pending_games!H{id + 1}", [[status]])

    # ── Admins ───────────────────────────────────────────────────────

    def get_admins(self) -> list[dict[str, Any]]:
        rows = self._get_values("admins!A2:B")
        headers = self.SHEETS["admins"]
        return [self._row_to_dict(headers, row) for row in rows if row]

    def is_admin(self, tg_id: int) -> bool:
        str_tg = str(tg_id)
        rows = self._get_values("admins!A2:A")
        return any(row and row[0] == str_tg for row in rows)

    # ── Utility ──────────────────────────────────────────────────────

    def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        username = username.lstrip("@")
        rows = self._get_values("members!A2:E")
        headers = self.SHEETS["members"]
        for row in rows:
            if row and len(row) > 1 and row[1].lstrip("@") == username:
                return self._row_to_dict(headers, row)
        return None

    def get_all_tg_ids(self) -> list[int]:
        rows = self._get_values("members!A2:A")
        return [int(row[0]) for row in rows if row and row[0]]
