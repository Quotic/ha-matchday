# Matchday – Home Assistant Integration

A HACS custom integration that tracks your favourite football (soccer) team's
fixtures, results, live score and league standing using the free tier of
[API-Football](https://www.api-football.com/).

## Features

| Sensor | State | Key attributes |
|--------|-------|----------------|
| **Next Match** | Date/time of next fixture | Home/away team, venue, round, referee, logos |
| **Last Match** | Score string e.g. `HSV 2 – 1 Heidenheim` | Full-time & half-time score, match date, status |
| **League Standing** | League position (integer) | Points, W/D/L, GF, GA, GD, form string |
| **Live Score** | Live score string or `No live match` | Minute, status, home/away score, `is_live` flag |

The poll interval is adjusted automatically:

- **30 minutes** – idle days
- **5 minutes** – on a match day (pre/post match)
- **1 minute** – during an active match

---

## Prerequisites

1. A free API key from [api-football.com](https://dashboard.api-football.com/)
   (100 requests / day on the free plan – sufficient for this integration)
2. [HACS](https://hacs.xyz/) installed in your Home Assistant instance

---

## Installation via HACS

1. Open **HACS → Integrations → ⋮ → Custom repositories**
2. Add this repository URL, category **Integration**
3. Search for **Matchday** and click **Download**
4. Restart Home Assistant

## Manual installation

Copy the `custom_components/matchday/` folder into your HA
`config/custom_components/` directory and restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Matchday**
3. Enter your API key, select the league (default: 2. Bundesliga) and season
4. Pick your team from the dropdown

All four sensors are created automatically under a single device entry.

---

## Leagues included

| League | ID |
|--------|-----|
| 1. Bundesliga | 78 |
| 2. Bundesliga | 79 |
| DFB Pokal | 81 |

You can follow multiple teams by adding the integration more than once.

---

## Example Lovelace card

```yaml
type: entities
title: Hamburger SV
entities:
  - entity: sensor.next_match
  - entity: sensor.last_match
  - entity: sensor.league_standing
  - entity: sensor.live_score
```

---

## Data source

Data is provided by [API-Football](https://www.api-football.com/) –
v3.football.api-sports.io.
