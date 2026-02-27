# Matchday – Home Assistant Integration

A HACS custom integration that tracks your favourite German football team's
fixtures, results, live score and league standing.
Data is provided for free by [OpenLigaDB](https://openligadb.de) – no API key required.

## Features

| Sensor | State | Key attributes |
|--------|-------|----------------|
| **Next Match** | Date/time of next fixture | Home/away team, venue, round, logos |
| **Last Match** | Score string e.g. `HSV 2 – 1 Heidenheim` | Full-time & half-time score, match date |
| **League Standing** | League position (integer) | Points, W/D/L, GF, GA, GD |
| **Live Score** | Live score string or `No live match` | Status, home/away score, `is_live` flag |
| **Next Opponent** | Name of the next opponent | Opponent ID, logo, match date |
| **Last Opponent** | Name of the last opponent | Opponent ID, logo, match date |
| **Goals Scored** | Season total goals scored | – |
| **Goals Conceded** | Season total goals conceded | – |
| **Last Result** | `Win`, `Draw`, or `Loss` | Goals scored/conceded, home/away, match date |
| **Next Game Home/Away** | `Home` or `Away` | Venue name, city, match date |

The poll interval adjusts automatically:

- **30 minutes** – idle days
- **5 minutes** – on a match day (pre/post match)
- **1 minute** – during an active match

---

## Prerequisites

[HACS](https://hacs.xyz/) installed in your Home Assistant instance.
No external account or API key is needed.

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
3. Select the league (default: 2. Bundesliga) and season
4. Pick your team from the dropdown

All ten sensors are created automatically under a single device entry.
You can follow multiple teams by adding the integration more than once.

---

## Supported leagues

| League | OpenLigaDB shortcut |
|--------|---------------------|
| 1. Bundesliga | `bl1` |
| 2. Bundesliga | `bl2` |
| DFB Pokal | `dfb` |

---

## Example Lovelace card

```yaml
type: entities
title: Hamburger SV
entities:
  - entity: sensor.next_match
  - entity: sensor.next_opponent
  - entity: sensor.next_game_home_away
  - entity: sensor.last_match
  - entity: sensor.last_result
  - entity: sensor.last_opponent
  - entity: sensor.goals_scored
  - entity: sensor.goals_conceded
  - entity: sensor.league_standing
  - entity: sensor.live_score
```

---

## Data source

Data is provided by [OpenLigaDB](https://openligadb.de) – free, open, no registration required.
