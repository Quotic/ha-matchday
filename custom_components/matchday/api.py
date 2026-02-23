"""API client for API-Football (v3.football.api-sports.io)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL

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
            "x-apisports-key": api_key,
        }

    async def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{API_BASE_URL}/{endpoint}"
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 401:
                    raise MatchdayAuthError("Invalid API key (HTTP 401)")
                if response.status == 499:
                    raise MatchdayRateLimitError("Daily request quota exceeded (HTTP 499)")
                response.raise_for_status()

                # Read body as text first so we always have it for error messages
                body = await response.text()

        except (MatchdayAuthError, MatchdayRateLimitError):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as err:
            raise MatchdayApiError(f"Connection error talking to {endpoint}: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise MatchdayApiError(f"Unexpected error for {endpoint}: {err}") from err

        # Parse JSON outside the HTTP context manager so network errors are separate
        try:
            import json as _json  # noqa: PLC0415
            data: dict = _json.loads(body)
        except ValueError as err:
            _LOGGER.error(
                "Non-JSON response from %s (first 200 chars): %s", endpoint, body[:200]
            )
            raise MatchdayApiError(f"Non-JSON response from {endpoint}") from err

        # API-Football returns errors inside the JSON body even on HTTP 200
        errors = data.get("errors")
        if errors:
            if isinstance(errors, dict):
                err_msg = " | ".join(str(v) for v in errors.values())
            elif isinstance(errors, list) and errors:
                err_msg = " | ".join(str(v) for v in errors)
            else:
                err_msg = str(errors)

            _LOGGER.debug("API-Football error for %s: %s", endpoint, err_msg)

            if "token" in err_msg.lower() or "key" in err_msg.lower():
                raise MatchdayAuthError(err_msg)
            if "limit" in err_msg.lower() or "requests" in err_msg.lower():
                raise MatchdayRateLimitError(err_msg)
            raise MatchdayApiError(err_msg)

        return data

    async def validate_api_key(self) -> bool:
        """Return True if the API key is valid."""
        try:
            data = await self._request("status")
            response_val = data.get("response")
            # response is a dict on success, [] on failure
            if not isinstance(response_val, dict):
                return False
            return response_val.get("account") is not None
        except MatchdayAuthError:
            return False
        except MatchdayApiError as err:
            _LOGGER.debug("validate_api_key failed: %s", err)
            return False

    async def get_quota_remaining(self) -> int | None:
        """Return remaining daily requests, or None on error."""
        try:
            data = await self._request("status")
            response_val = data.get("response", {})
            if not isinstance(response_val, dict):
                return None
            requests_info = response_val.get("requests", {})
            limit = requests_info.get("limit_day", 0)
            used = requests_info.get("current", 0)
            return max(0, limit - used)
        except MatchdayApiError:
            return None

    async def get_teams(self, league_id: int, season: int) -> list[dict]:
        """Return all teams for a league/season, sorted by name."""
        data = await self._request("teams", {"league": league_id, "season": season})
        teams = data.get("response", [])
        if not isinstance(teams, list):
            return []
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
