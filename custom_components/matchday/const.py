"""Constants for the Matchday integration."""

DOMAIN = "matchday"
PLATFORMS = ["sensor"]

# Config entry keys
CONF_API_KEY = "api_key"
CONF_LEAGUE_ID = "league_id"
CONF_TEAM_ID = "team_id"
CONF_TEAM_NAME = "team_name"
CONF_SEASON = "season"
CONF_DATA_SOURCE = "data_source"

# Data source identifiers
DATA_SOURCE_APIFOOTBALL = "apifootball"
DATA_SOURCE_OPENLIGADB = "openligadb"

# API
API_BASE_URL = "https://v3.football.api-sports.io"

# OpenLigaDB
OPENLIGADB_BASE_URL = "https://api.openligadb.de"
# Maps well-known league IDs to OpenLigaDB shortcut strings
OPENLIGADB_LEAGUE_SHORTCUTS = {
    78: "bl1",   # 1. Bundesliga
    79: "bl2",   # 2. Bundesliga
    81: "dfb",   # DFB Pokal
}

# Well-known league IDs
LEAGUE_1_BUNDESLIGA = 78
LEAGUE_2_BUNDESLIGA = 79
LEAGUE_DFB_POKAL = 81

LEAGUE_NAMES = {
    78: "1. Bundesliga",
    79: "2. Bundesliga",
    81: "DFB Pokal",
}

# Update intervals (in minutes)
SCAN_INTERVAL_DEFAULT = 30   # Idle days
SCAN_INTERVAL_MATCHDAY = 5   # Match day, pre/post match
SCAN_INTERVAL_LIVE = 1       # During an active match

# Live match status codes from API-Football
LIVE_STATUS_CODES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}
FINISHED_STATUS_CODES = {"FT", "AET", "PEN"}

# Sensor entity IDs
SENSOR_NEXT_MATCH = "next_match"
SENSOR_LAST_MATCH = "last_match"
SENSOR_STANDING = "standing"
SENSOR_LIVE_SCORE = "live_score"

# Attribution
ATTRIBUTION = "Data provided by API-Football (api-football.com)"
