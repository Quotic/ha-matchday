"""API client for OpenLigaDB (api.openligadb.de) – no API key required."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import OPENLIGADB_BASE_URL, OPENLIGADB_LEAGUE_SHORTCUTS

_LOGGER = logging.getLogger(__name__)


class OpenLigaDbError(Exception):
    """General OpenLigaDB error."""


class OpenLigaDbClient:
    """Async HTTP client for OpenLigaDB v1 (no authentication required)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _request(self, path: str) -> Any:
        url = f"{OPENLIGADB_BASE_URL}/{path}"
        try:
            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                body = await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as err:
            raise OpenLigaDbError(f"Connection error for {path}: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise OpenLigaDbError(f"Unexpected error for {path}: {err}") from err

        try:
            import json as _json  # noqa: PLC0415
            return _json.loads(body)
        except ValueError as err:
            _LOGGER.error("Non-JSON response from %s (first 200 chars): %s", path, body[:200])
            raise OpenLigaDbError(f"Non-JSON response from {path}") from err

    # ------------------------------------------------------------------
    # Public API – same interface as MatchdayApiClient
    # ------------------------------------------------------------------

    async def get_teams(self, league_id: int, season: int) -> list[dict]:
        """Return teams for a league/season in API-Football format, sorted by name."""
        shortcut = OPENLIGADB_LEAGUE_SHORTCUTS.get(league_id)
        if not shortcut:
            raise OpenLigaDbError(f"No OpenLigaDB shortcut for league ID {league_id}")

        raw = await self._request(f"getavailableteams/{shortcut}/{season}")
        if not isinstance(raw, list):
            return []

        teams = [_normalize_team(t) for t in raw]
        return sorted(teams, key=lambda t: t.get("team", {}).get("name", ""))

    async def get_fixtures(self, league_id: int, season: int, team_id: int) -> list[dict]:
        """Return all fixtures for the given team in API-Football-compatible format."""
        shortcut = OPENLIGADB_LEAGUE_SHORTCUTS.get(league_id)
        if not shortcut:
            raise OpenLigaDbError(f"No OpenLigaDB shortcut for league ID {league_id}")

        raw = await self._request(f"getmatchdata/{shortcut}/{season}")
        if not isinstance(raw, list):
            return []

        now = datetime.now(tz=timezone.utc)
        fixtures = []
        for match in raw:
            home_id = match.get("team1", {}).get("teamId")
            away_id = match.get("team2", {}).get("teamId")
            if team_id not in (home_id, away_id):
                continue
            fixtures.append(_normalize_fixture(match, league_id, now))

        return fixtures

    async def get_standings(self, league_id: int, season: int) -> list[dict]:
        """Return standings in API-Football-compatible format."""
        shortcut = OPENLIGADB_LEAGUE_SHORTCUTS.get(league_id)
        if not shortcut:
            raise OpenLigaDbError(f"No OpenLigaDB shortcut for league ID {league_id}")

        raw = await self._request(f"getbltable/{shortcut}/{season}")
        if not isinstance(raw, list):
            return []

        from .const import LEAGUE_NAMES  # noqa: PLC0415
        league_name = LEAGUE_NAMES.get(league_id, f"League {league_id}")

        return _normalize_standings(raw, league_id, league_name)


# ---------------------------------------------------------------------------
# Normalisation helpers – map OpenLigaDB format → API-Football format
# ---------------------------------------------------------------------------

def _normalize_team(team: dict) -> dict:
    """Wrap an OpenLigaDB team entry in API-Football's team/venue envelope."""
    return {
        "team": {
            "id": team.get("teamId"),
            "name": team.get("teamName", ""),
            "logo": team.get("teamIconUrl"),
        },
        "venue": {},
    }


def _normalize_fixture(match: dict, league_id: int, now: datetime) -> dict:
    """Convert a single OpenLigaDB match dict to API-Football fixture format."""
    results = match.get("matchResults") or []
    final = next((r for r in results if r.get("resultTypeID") == 2), None)
    halftime = next((r for r in results if r.get("resultTypeID") == 1), None)

    is_finished: bool = match.get("matchIsFinished", False)

    # Prefer UTC timestamp; fall back to local datetime
    date_str: str = match.get("matchDateTimeUTC") or match.get("matchDateTime") or ""

    # Determine match status
    if is_finished:
        status_short = "FT"
        status_long = "Match Finished"
    else:
        # Check if the match has likely already kicked off (within 2.5-hour window)
        match_dt = _parse_utc(date_str)
        if match_dt is not None:
            minutes_since_ko = (now - match_dt).total_seconds() / 60
            if 0 <= minutes_since_ko <= 150:
                status_short = "LIVE"
                status_long = "In Progress"
            else:
                status_short = "NS"
                status_long = "Not Started"
        else:
            status_short = "NS"
            status_long = "Not Started"

    location = match.get("location") or {}

    return {
        "fixture": {
            "id": match.get("matchID"),
            "date": date_str,
            "status": {
                "short": status_short,
                "long": status_long,
                "elapsed": None,
            },
            "venue": {
                "name": location.get("locationStadium"),
                "city": location.get("locationCity"),
            },
            "referee": None,
        },
        "league": {
            "id": league_id,
            "name": match.get("leagueName", ""),
            "season": _safe_int(match.get("leagueSeason")),
            "round": (match.get("group") or {}).get("groupName"),
        },
        "teams": {
            "home": {
                "id": match.get("team1", {}).get("teamId"),
                "name": match.get("team1", {}).get("teamName", ""),
                "logo": match.get("team1", {}).get("teamIconUrl"),
            },
            "away": {
                "id": match.get("team2", {}).get("teamId"),
                "name": match.get("team2", {}).get("teamName", ""),
                "logo": match.get("team2", {}).get("teamIconUrl"),
            },
        },
        "goals": {
            "home": final["pointsTeam1"] if final else None,
            "away": final["pointsTeam2"] if final else None,
        },
        "score": {
            "halftime": {
                "home": halftime["pointsTeam1"] if halftime else None,
                "away": halftime["pointsTeam2"] if halftime else None,
            },
        },
    }


def _normalize_standings(
    table: list[dict], league_id: int, league_name: str
) -> list[dict]:
    """Convert an OpenLigaDB table to the API-Football standings envelope."""
    group: list[dict] = []
    for rank, entry in enumerate(table, start=1):
        group.append(
            {
                "team": {
                    "id": entry.get("teamInfoId"),
                    "name": entry.get("teamName", ""),
                    "logo": entry.get("teamIconUrl"),
                },
                "rank": rank,
                "points": entry.get("points", 0),
                "goalsDiff": entry.get("goalDiff", 0),
                "form": None,
                "description": None,
                "all": {
                    "played": entry.get("matches", 0),
                    "win": entry.get("won", 0),
                    "draw": entry.get("draw", 0),
                    "lose": entry.get("lost", 0),
                    "goals": {
                        "for": entry.get("goals", 0),
                        "against": entry.get("opponentGoals", 0),
                    },
                },
            }
        )

    return [{"league": {"id": league_id, "name": league_name, "standings": [group]}}]


def _parse_utc(date_str: str) -> datetime | None:
    """Parse an ISO-8601 string and return a UTC-aware datetime, or None."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _safe_int(value: Any) -> int | None:
    """Convert a value to int, returning None on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
