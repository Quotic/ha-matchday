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
    SENSOR_GOALS_AGAINST,
    SENSOR_GOALS_FOR,
    SENSOR_LAST_MATCH,
    SENSOR_LAST_OPPONENT,
    SENSOR_LAST_RESULT,
    SENSOR_LIVE_SCORE,
    SENSOR_NEXT_GAME_VENUE,
    SENSOR_NEXT_MATCH,
    SENSOR_NEXT_OPPONENT,
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
            NextOpponentSensor(coordinator, config_entry),
            LastOpponentSensor(coordinator, config_entry),
            GoalsForSensor(coordinator, config_entry),
            GoalsAgainstSensor(coordinator, config_entry),
            LastResultSensor(coordinator, config_entry),
            NextGameVenueSensor(coordinator, config_entry),
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
            manufacturer="OpenLigaDB",
            model="Football Data",
            configuration_url="https://openligadb.de",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    def _opponent(self, fixture: dict) -> dict:
        """Return the opposing team dict for a given fixture."""
        team_id = self.coordinator.team_id
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]
        return away if home["id"] == team_id else home


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
# Next Opponent
# ---------------------------------------------------------------------------

class NextOpponentSensor(MatchdaySensorBase):
    """Shows the name of the next opponent."""

    _attr_translation_key = "next_opponent"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_NEXT_OPPONENT}"

    @property
    def native_value(self) -> str | None:
        fixture = self.coordinator.data.get("next_match") if self.coordinator.data else None
        if not fixture:
            return None
        return self._opponent(fixture).get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("next_match") if self.coordinator.data else None
        if not fixture:
            return {}
        opp = self._opponent(fixture)
        return {
            "opponent_id": opp.get("id"),
            "opponent_logo": opp.get("logo"),
            "match_date": fixture["fixture"]["date"],
        }


# ---------------------------------------------------------------------------
# Last Opponent
# ---------------------------------------------------------------------------

class LastOpponentSensor(MatchdaySensorBase):
    """Shows the name of the last opponent."""

    _attr_translation_key = "last_opponent"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_LAST_OPPONENT}"

    @property
    def native_value(self) -> str | None:
        fixture = self.coordinator.data.get("last_match") if self.coordinator.data else None
        if not fixture:
            return None
        return self._opponent(fixture).get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("last_match") if self.coordinator.data else None
        if not fixture:
            return {}
        opp = self._opponent(fixture)
        return {
            "opponent_id": opp.get("id"),
            "opponent_logo": opp.get("logo"),
            "match_date": fixture["fixture"]["date"],
        }


# ---------------------------------------------------------------------------
# Goals For (season total)
# ---------------------------------------------------------------------------

class GoalsForSensor(MatchdaySensorBase):
    """Shows total goals scored by the team this season."""

    _attr_native_unit_of_measurement = "goals"
    _attr_translation_key = "goals_for"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_GOALS_FOR}"

    @property
    def native_value(self) -> int | None:
        standing = self.coordinator.data.get("standing") if self.coordinator.data else None
        if not standing:
            return None
        return standing.get("all", {}).get("goals", {}).get("for")


# ---------------------------------------------------------------------------
# Goals Against (season total)
# ---------------------------------------------------------------------------

class GoalsAgainstSensor(MatchdaySensorBase):
    """Shows total goals conceded by the team this season."""

    _attr_native_unit_of_measurement = "goals"
    _attr_translation_key = "goals_against"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_GOALS_AGAINST}"

    @property
    def native_value(self) -> int | None:
        standing = self.coordinator.data.get("standing") if self.coordinator.data else None
        if not standing:
            return None
        return standing.get("all", {}).get("goals", {}).get("against")


# ---------------------------------------------------------------------------
# Last Result (Win / Draw / Loss)
# ---------------------------------------------------------------------------

class LastResultSensor(MatchdaySensorBase):
    """Shows whether the team won, drew, or lost their last match."""

    _attr_translation_key = "last_result"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_LAST_RESULT}"

    @property
    def native_value(self) -> str | None:
        fixture = self.coordinator.data.get("last_match") if self.coordinator.data else None
        if not fixture:
            return None
        goals = fixture.get("goals", {})
        home_goals = goals.get("home")
        away_goals = goals.get("away")
        if home_goals is None or away_goals is None:
            return None

        team_id = self.coordinator.team_id
        is_home = fixture["teams"]["home"]["id"] == team_id
        our_goals = home_goals if is_home else away_goals
        their_goals = away_goals if is_home else home_goals

        if our_goals > their_goals:
            return "Win"
        if our_goals == their_goals:
            return "Draw"
        return "Loss"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("last_match") if self.coordinator.data else None
        if not fixture:
            return {}
        goals = fixture.get("goals", {})
        team_id = self.coordinator.team_id
        is_home = fixture["teams"]["home"]["id"] == team_id
        return {
            "home_or_away": "Home" if is_home else "Away",
            "goals_scored": goals.get("home") if is_home else goals.get("away"),
            "goals_conceded": goals.get("away") if is_home else goals.get("home"),
            "match_date": fixture["fixture"]["date"],
        }


# ---------------------------------------------------------------------------
# Next Game Venue (Home / Away)
# ---------------------------------------------------------------------------

class NextGameVenueSensor(MatchdaySensorBase):
    """Shows whether the next match is a home or away game."""

    _attr_translation_key = "next_game_venue"

    def __init__(self, coordinator: MatchdayCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_{SENSOR_NEXT_GAME_VENUE}"

    @property
    def native_value(self) -> str | None:
        fixture = self.coordinator.data.get("next_match") if self.coordinator.data else None
        if not fixture:
            return None
        team_id = self.coordinator.team_id
        is_home = fixture["teams"]["home"]["id"] == team_id
        return "Home" if is_home else "Away"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fixture = self.coordinator.data.get("next_match") if self.coordinator.data else None
        if not fixture:
            return {}
        return {
            "venue": fixture["fixture"].get("venue", {}).get("name"),
            "venue_city": fixture["fixture"].get("venue", {}).get("city"),
            "match_date": fixture["fixture"]["date"],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(raw: str) -> datetime | None:
    """Parse an ISO-8601 date string and return a timezone-aware datetime."""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
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
