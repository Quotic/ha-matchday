"""Sensor platform for the Matchday integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_TEAM_NAME,
    DOMAIN,
    LEAGUE_NAMES,
    SENSOR_LAST_MATCH,
    SENSOR_LIVE_SCORE,
    SENSOR_NEXT_MATCH,
    SENSOR_STANDING,
)
from .coordinator import MatchdayCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MatchdayCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [
            NextMatchSensor(coordinator, config_entry),
            LastMatchSensor(coordinator, config_entry),
            StandingSensor(coordinator, config_entry),
            LiveScoreSensor(coordinator, config_entry),
        ]
    )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class MatchdaySensorBase(CoordinatorEntity[MatchdayCoordinator], SensorEntity):
    """Base class for all Matchday sensors."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._team_name: str = config_entry.data.get(CONF_TEAM_NAME, "Team")
        league_id = coordinator.league_id
        self._league_name = LEAGUE_NAMES.get(league_id, f"League {league_id}")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=f"{self._team_name} – {self._league_name}",
            manufacturer="API-Football",
            model="Football Data",
            configuration_url="https://dashboard.api-football.com/",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Next Match
# ---------------------------------------------------------------------------

class NextMatchSensor(MatchdaySensorBase):
    """Shows the date/time of the next scheduled match."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_match"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_NEXT_MATCH}"

    @property
    def native_value(self) -> datetime | None:
        fixture = self.coordinator.data.get("next_match") if self.coordinator.data else None
        if not fixture:
            return None
        return _parse_dt(fixture["fixture"]["date"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("next_match") if self.coordinator.data else None
        if not fixture:
            return {}
        return _fixture_attributes(fixture)


# ---------------------------------------------------------------------------
# Last Match
# ---------------------------------------------------------------------------

class LastMatchSensor(MatchdaySensorBase):
    """Shows the result of the most recent finished match."""

    _attr_translation_key = "last_match"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_LAST_MATCH}"

    @property
    def native_value(self) -> str | None:
        fixture = self.coordinator.data.get("last_match") if self.coordinator.data else None
        if not fixture:
            return None
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        gh = fixture["goals"]["home"] if fixture["goals"]["home"] is not None else "-"
        ga = fixture["goals"]["away"] if fixture["goals"]["away"] is not None else "-"
        return f"{home} {gh} – {ga} {away}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("last_match") if self.coordinator.data else None
        if not fixture:
            return {}
        attrs = _fixture_attributes(fixture)
        goals = fixture.get("goals", {})
        score = fixture.get("score", {})
        attrs.update(
            {
                "home_score": goals.get("home"),
                "away_score": goals.get("away"),
                "halftime_home": score.get("halftime", {}).get("home"),
                "halftime_away": score.get("halftime", {}).get("away"),
                "status": fixture["fixture"]["status"]["long"],
                "match_date": fixture["fixture"]["date"],
            }
        )
        return attrs


# ---------------------------------------------------------------------------
# Standing
# ---------------------------------------------------------------------------

class StandingSensor(MatchdaySensorBase):
    """Shows the team's current league position."""

    _attr_native_unit_of_measurement = "position"
    _attr_translation_key = "standing"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_STANDING}"

    @property
    def native_value(self) -> int | None:
        standing = self.coordinator.data.get("standing") if self.coordinator.data else None
        return standing.get("rank") if standing else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        standing = self.coordinator.data.get("standing") if self.coordinator.data else None
        if not standing:
            return {}
        all_stats = standing.get("all", {})
        goals = all_stats.get("goals", {})
        return {
            "team": standing.get("team", {}).get("name"),
            "points": standing.get("points"),
            "played": all_stats.get("played"),
            "wins": all_stats.get("win"),
            "draws": all_stats.get("draw"),
            "losses": all_stats.get("lose"),
            "goals_for": goals.get("for"),
            "goals_against": goals.get("against"),
            "goal_difference": standing.get("goalsDiff"),
            "form": standing.get("form"),
            "description": standing.get("description"),
        }


# ---------------------------------------------------------------------------
# Live Score
# ---------------------------------------------------------------------------

class LiveScoreSensor(MatchdaySensorBase):
    """Shows the live score during a match, idle otherwise."""

    _attr_translation_key = "live_score"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_LIVE_SCORE}"

    @property
    def native_value(self) -> str:
        fixture = self.coordinator.data.get("live") if self.coordinator.data else None
        if not fixture:
            return "No live match"
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        gh = fixture["goals"]["home"] if fixture["goals"]["home"] is not None else 0
        ga = fixture["goals"]["away"] if fixture["goals"]["away"] is not None else 0
        return f"{home} {gh} – {ga} {away}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("live") if self.coordinator.data else None
        if not fixture:
            return {"is_live": False}
        attrs = _fixture_attributes(fixture)
        goals = fixture.get("goals", {})
        attrs.update(
            {
                "is_live": True,
                "minute": fixture["fixture"].get("status", {}).get("elapsed"),
                "status": fixture["fixture"]["status"]["long"],
                "home_score": goals.get("home", 0),
                "away_score": goals.get("away", 0),
            }
        )
        return attrs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(raw: str) -> datetime | None:
    """Parse an ISO-8601 date string and return a timezone-aware datetime."""
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _fixture_attributes(fixture: dict) -> dict[str, Any]:
    """Return a common dict of fixture attributes shared by multiple sensors."""
    fix = fixture.get("fixture", {})
    league = fixture.get("league", {})
    teams = fixture.get("teams", {})
    venue = fix.get("venue", {})

    return {
        "match_id": fix.get("id"),
        "home_team": teams.get("home", {}).get("name"),
        "home_team_id": teams.get("home", {}).get("id"),
        "home_logo": teams.get("home", {}).get("logo"),
        "away_team": teams.get("away", {}).get("name"),
        "away_team_id": teams.get("away", {}).get("id"),
        "away_logo": teams.get("away", {}).get("logo"),
        "venue": venue.get("name"),
        "venue_city": venue.get("city"),
        "referee": fix.get("referee"),
        "round": league.get("round"),
        "competition": league.get("name"),
        "season": league.get("season"),
    }
