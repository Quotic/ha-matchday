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
from .const import (
    CONF_API_KEY,
    CONF_LEAGUE_ID,
    CONF_SEASON,
    CONF_TEAM_ID,
    CONF_TEAM_NAME,
    DOMAIN,
    LEAGUE_2_BUNDESLIGA,
    LEAGUE_NAMES,
)

_LOGGER = logging.getLogger(__name__)

# Leagues available in the config flow dropdown
AVAILABLE_LEAGUES = [
    SelectOptionDict(value=str(lid), label=name)
    for lid, name in LEAGUE_NAMES.items()
]


class MatchdayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Multi-step config flow: API key → team selection."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str = ""
        self._league_id: int = LEAGUE_2_BUNDESLIGA
        self._season: int = 2025
        self._teams: list[dict] = []

    # ------------------------------------------------------------------
    # Step 1: API key + league + season
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            league_id = int(user_input[CONF_LEAGUE_ID])
            season = int(user_input[CONF_SEASON])

            session = async_get_clientsession(self.hass)
            client = MatchdayApiClient(api_key, session)

            try:
                valid = await client.validate_api_key()
                if not valid:
                    errors["base"] = "invalid_auth"
                else:
                    # Fetch team list for step 2
                    self._teams = await client.get_teams(league_id, season)
                    if not self._teams:
                        errors["base"] = "no_teams"
                    else:
                        self._api_key = api_key
                        self._league_id = league_id
                        self._season = season
                        return await self.async_step_team()
            except MatchdayAuthError:
                errors["base"] = "invalid_auth"
            except MatchdayApiError as err:
                _LOGGER.error("API error during setup: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
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

            await self.async_set_unique_id(f"{self._league_id}_{team_id}_{self._season}")
            self._abort_if_unique_id_configured()

            league_label = LEAGUE_NAMES.get(self._league_id, f"League {self._league_id}")

            return self.async_create_entry(
                title=f"{team_name} – {league_label} {self._season}/{self._season + 1}",
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_LEAGUE_ID: self._league_id,
                    CONF_SEASON: self._season,
                    CONF_TEAM_ID: team_id,
                    CONF_TEAM_NAME: team_name,
                },
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
