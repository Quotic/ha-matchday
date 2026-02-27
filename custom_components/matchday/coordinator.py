"""DataUpdateCoordinator for the Matchday integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_openligadb import OpenLigaDbClient, OpenLigaDbError
from .const import (
    CONF_LEAGUE_ID,
    CONF_SEASON,
    CONF_TEAM_ID,
    FINISHED_STATUS_CODES,
    LIVE_STATUS_CODES,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_LIVE,
    SCAN_INTERVAL_MATCHDAY,
)

_LOGGER = logging.getLogger(__name__)


class MatchdayCoordinator(DataUpdateCoordinator):
    """Fetch and cache Matchday data; adjusts poll interval automatically."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: OpenLigaDbClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Matchday",
            config_entry=config_entry,
            update_interval=timedelta(minutes=SCAN_INTERVAL_DEFAULT),
        )
        self._api = api_client
        self._league_id: int = config_entry.data[CONF_LEAGUE_ID]
        self._season: int = config_entry.data[CONF_SEASON]
        self._team_id: int = config_entry.data[CONF_TEAM_ID]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def league_id(self) -> int:
        return self._league_id

    @property
    def team_id(self) -> int:
        return self._team_id

    # ------------------------------------------------------------------
    # Core fetch
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Fetch all data from OpenLigaDB and return a processed dict."""
        try:
            fixtures = await self._api.get_fixtures(self._league_id, self._season, self._team_id)
            standings = await self._api.get_standings(self._league_id, self._season)
        except OpenLigaDbError as err:
            raise UpdateFailed(f"OpenLigaDB error: {err}") from err

        processed = self._process_fixtures(fixtures)
        processed["standing"] = self._extract_standing(standings)
        self._adjust_poll_interval(processed)

        return processed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_fixtures(self, fixtures: list[dict]) -> dict:
        now = datetime.now(tz=timezone.utc)
        upcoming: list[dict] = []
        past: list[dict] = []
        live: dict | None = None

        for fixture in fixtures:
            status_short = fixture["fixture"]["status"]["short"]

            if status_short in LIVE_STATUS_CODES:
                live = fixture
                continue

            raw_date = fixture["fixture"].get("date")
            if not raw_date:
                continue

            try:
                match_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                if match_dt.tzinfo is None:
                    match_dt = match_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if status_short in FINISHED_STATUS_CODES or match_dt <= now:
                past.append(fixture)
            else:
                upcoming.append(fixture)

        upcoming.sort(key=lambda f: f["fixture"]["date"])
        past.sort(key=lambda f: f["fixture"]["date"], reverse=True)

        return {
            "live": live,
            "next_match": upcoming[0] if upcoming else None,
            "last_match": past[0] if past else None,
        }

    def _extract_standing(self, standings: list[dict]) -> dict | None:
        for league_entry in standings:
            for group in league_entry.get("league", {}).get("standings", []):
                for entry in group:
                    if entry.get("team", {}).get("id") == self._team_id:
                        return entry
        return None

    def _adjust_poll_interval(self, data: dict) -> None:
        if data.get("live"):
            new_interval = timedelta(minutes=SCAN_INTERVAL_LIVE)
        elif data.get("next_match") and self._is_today(data["next_match"]):
            new_interval = timedelta(minutes=SCAN_INTERVAL_MATCHDAY)
        else:
            new_interval = timedelta(minutes=SCAN_INTERVAL_DEFAULT)

        if self.update_interval != new_interval:
            _LOGGER.debug(
                "Adjusting poll interval to %s minutes",
                int(new_interval.total_seconds() / 60),
            )
            self.update_interval = new_interval

    @staticmethod
    def _is_today(fixture: dict) -> bool:
        raw_date = fixture["fixture"].get("date")
        if not raw_date:
            return False
        try:
            match_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if match_dt.tzinfo is None:
                match_dt = match_dt.replace(tzinfo=timezone.utc)
            return match_dt.date() == datetime.now(tz=timezone.utc).date()
        except ValueError:
            return False
