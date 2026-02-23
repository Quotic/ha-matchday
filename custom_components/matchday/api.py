"""API client for API-Football (v3.football.api-sports.io)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_HOST

_LOGGER = logging.getLogger(__name__)


class MatchdayApiError(Exception):
    """General API error."""


class MatchdayAuthError(MatchdayApiError):
    """Invalid or missing API key."""


class MatchdayRateLimitError(MatchdayApiError):
    """Daily request quota exceeded."""


class MatchdayApiClient:
    """Async HTTP client for API-Football v3."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        self._api_key = api_key
        self._session = session
        self._headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": API_HOST,
        }

    async def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{API_BASE_URL}/{endpoint}"
        try:
            async with self._session.get(
                url, headers=self._headers, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 401:
                    raise MatchdayAuthError("Invalid API key")
                if response.status == 499:
                    raise MatchdayRateLimitError("Daily request quota exceeded")
                response.raise_for_status()

                data: dict = await response.json()

                # API-Football returns errors inside the JSON body even on HTTP 200
                errors = data.get("errors")
                if errors:
                    if isinstance(errors, dict):
                        err_msg = " | ".join(errors.values())
                    else:
                        err_msg = str(errors)
                    if "token" in err_msg.lower() or "key" in err_msg.lower():
                        raise MatchdayAuthError(err_msg)
                    if "limit" in err_msg.lower() or "requests" in err_msg.lower():
                        raise MatchdayRateLimitError(err_msg)
                    raise MatchdayApiError(err_msg)

                return data

        except (aiohttp.ClientError, TimeoutError) as err:
            raise MatchdayApiError(f"Connection error: {err}") from err

    async def validate_api_key(self) -> bool:
        """Return True if the API key is valid."""
        try:
            data = await self._request("status")
            account = data.get("response", {}).get("account")
            return account is not None
        except MatchdayAuthError:
            return False
        except MatchdayApiError:
            return False

    async def get_quota_remaining(self) -> int | None:
        """Return remaining daily requests, or None on error."""
        try:
            data = await self._request("status")
            requests_info = data.get("response", {}).get("requests", {})
            limit = requests_info.get("limit_day", 0)
            used = requests_info.get("current", 0)
            return max(0, limit - used)
        except MatchdayApiError:
            return None

    async def get_teams(self, league_id: int, season: int) -> list[dict]:
        """Return all teams for a league/season, sorted by name."""
        data = await self._request("teams", {"league": league_id, "season": season})
        teams = data.get("response", [])
        return sorted(teams, key=lambda t: t.get("team", {}).get("name", ""))

    async def get_fixtures(self, league_id: int, season: int, team_id: int) -> list[dict]:
        """Return all fixtures for the given team in this league/season."""
        data = await self._request(
            "fixtures",
            {"league": league_id, "season": season, "team": team_id},
        )
        return data.get("response", [])

    async def get_standings(self, league_id: int, season: int) -> list[dict]:
        """Return standings for the league/season."""
        data = await self._request("standings", {"league": league_id, "season": season})
        return data.get("response", [])

    async def get_fixture_events(self, fixture_id: int) -> list[dict]:
        """Return events (goals, cards, subs) for a live or finished fixture."""
        data = await self._request("fixtures/events", {"fixture": fixture_id})
        return data.get("response", [])
