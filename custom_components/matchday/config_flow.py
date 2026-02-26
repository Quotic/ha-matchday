"""Config flow for the Matchday integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import MatchdayApiClient, MatchdayApiError, MatchdayAuthError
from .api_openligadb import OpenLigaDbClient, OpenLigaDbError
from .const import (
    CONF_API_KEY,
    CONF_DATA_SOURCE,
    CONF_LEAGUE_ID,
    CONF_SEASON,
    CONF_TEAM_ID,
    CONF_TEAM_NAME,
    DATA_SOURCE_APIFOOTBALL,
    DATA_SOURCE_OPENLIGADB,
    DOMAIN,
    LEAGUE_2_BUNDESLIGA,
    LEAGUE_NAMES,
    OPENLIGADB_LEAGUE_SHORTCUTS,
)

_LOGGER = logging.getLogger(__name__)

# Leagues available in the config flow dropdown
AVAILABLE_LEAGUES = [
    SelectOptionDict(value=str(lid), label=name)
    for lid, name in LEAGUE_NAMES.items()
]

DATA_SOURCE_OPTIONS = [
    SelectOptionDict(value=DATA_SOURCE_OPENLIGADB, label="OpenLigaDB (free, no key needed)"),
    SelectOptionDict(value=DATA_SOURCE_APIFOOTBALL, label="API-Football (api-sports.io)"),
]


class MatchdayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Multi-step config flow: data source → league/API key → team selection."""

    VERSION = 1

    def __init__(self) -> None:
        self._data_source: str = DATA_SOURCE_OPENLIGADB
        self._api_key: str = ""
        self._league_id: int = LEAGUE_2_BUNDESLIGA
        self._season: int = 2025
        self._teams: list[dict] = []

    # ------------------------------------------------------------------
    # Step 1: data source + API key (optional) + league + season
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            data_source = user_input[CONF_DATA_SOURCE]
            league_id = int(user_input[CONF_LEAGUE_ID])
            season = int(user_input[CONF_SEASON])
            api_key = user_input.get(CONF_API_KEY, "").strip()

            session = async_get_clientsession(self.hass)

            try:
                if data_source == DATA_SOURCE_APIFOOTBALL:
                    if not api_key:
                        errors[CONF_API_KEY] = "invalid_auth"
                    else:
                        client = MatchdayApiClient(api_key, session)
                        valid = await client.validate_api_key()
                        if not valid:
                            errors[CONF_API_KEY] = "invalid_auth"
                        else:
                            self._teams = await client.get_teams(league_id, season)
                            if not self._teams:
                                errors["base"] = "no_teams"

                else:  # OpenLigaDB
                    if league_id not in OPENLIGADB_LEAGUE_SHORTCUTS:
                        errors["base"] = "no_teams"
                    else:
                        client_oldb = OpenLigaDbClient(session)
                        self._teams = await client_oldb.get_teams(league_id, season)
                        if not self._teams:
                            errors["base"] = "no_teams"

            except (MatchdayAuthError,):
                errors[CONF_API_KEY] = "invalid_auth"
            except (MatchdayApiError, OpenLigaDbError) as err:
                _LOGGER.error("Cannot connect to data source: %s", err, exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Matchday setup: %s", err)
                errors["base"] = "cannot_connect"

            if not errors:
                self._data_source = data_source
                self._api_key = api_key
                self._league_id = league_id
                self._season = season
                return await self.async_step_team()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DATA_SOURCE, default=DATA_SOURCE_OPENLIGADB): SelectSelector(
                        SelectSelectorConfig(
                            options=DATA_SOURCE_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_API_KEY, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Required(CONF_LEAGUE_ID, default=str(LEAGUE_2_BUNDESLIGA)): SelectSelector(
                        SelectSelectorConfig(
                            options=AVAILABLE_LEAGUES,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_SEASON, default=2025): NumberSelector(
                        NumberSelectorConfig(
                            min=2010,
                            max=2030,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2: team selection
    # ------------------------------------------------------------------

    async def async_step_team(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            team_id = int(user_input[CONF_TEAM_ID])
            team_name = next(
                (
                    t["team"]["name"]
                    for t in self._teams
                    if t["team"]["id"] == team_id
                ),
                str(team_id),
            )

            await self.async_set_unique_id(
                f"{self._data_source}_{self._league_id}_{team_id}_{self._season}"
            )
            self._abort_if_unique_id_configured()

            league_label = LEAGUE_NAMES.get(self._league_id, f"League {self._league_id}")

            entry_data: dict[str, Any] = {
                CONF_DATA_SOURCE: self._data_source,
                CONF_LEAGUE_ID: self._league_id,
                CONF_SEASON: self._season,
                CONF_TEAM_ID: team_id,
                CONF_TEAM_NAME: team_name,
            }
            if self._data_source == DATA_SOURCE_APIFOOTBALL:
                entry_data[CONF_API_KEY] = self._api_key

            return self.async_create_entry(
                title=f"{team_name} – {league_label} {self._season}/{self._season + 1}",
                data=entry_data,
            )

        team_options = [
            SelectOptionDict(
                value=str(t["team"]["id"]),
                label=t["team"]["name"],
            )
            for t in self._teams
        ]

        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TEAM_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=team_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )
