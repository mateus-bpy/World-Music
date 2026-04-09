"""
Run this script ONCE to find the best local music radio station per country.
It searches Radio Browser API filtering for music stations, avoiding news/talk.
Results are saved to countries.json as radio_stream_url and radio_station_name.

Run: python fetch_radio_stations.py
"""

import json
import time
import requests

HEADERS = {"User-Agent": "SoundmapApp/1.0 - student project"}

# Country codes mapped to Radio Browser country names
COUNTRY_NAMES = {
    "PT": "Portugal",
    "BR": "Brazil",
    "US": "United States of America",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "MX": "Mexico",
    "AR": "Argentina",
    "AU": "Australia",
    "NO": "Norway",
    "SE": "Sweden",
    "FI": "Finland",
    "NL": "Netherlands"
}

# Tags to skip — stations with these tags are likely news or talk heavy
SKIP_TAGS = {
    "news", "talk", "sports", "information", "politics", "religion",
    "christian", "gospel", "bible", "spoken word", "comedy", "podcast",
    "weather", "traffic", "public radio", "talk radio"
}

# Tags that strongly suggest local/national music content
PREFER_TAGS = {
    "folk", "national", "local", "traditional", "fado", "samba",
    "country music", "regional", "world music", "schlager", "chanson",
    "latin", "tango", "flamenco", "celtic", "nordic", "scandinavian",
    "hits", "pop", "music"
}


def get_stations(country_name, limit=50):
    """Fetch top stations for a country ordered by click count."""
    try:
        response = requests.get(
            f"https://de1.api.radio-browser.info/json/stations/bycountry/{country_name}",
            headers=HEADERS,
            params={
                "limit": limit,
                "order": "clickcount",
                "reverse": "true",
                "hidebroken": "true"
            },
            timeout=10
        )
        return response.json()
    except Exception as e:
        print(f"  Error fetching stations for {country_name}: {e}")
        return []


def score_station(station):
    """
    Score a station based on how suitable it is.
    Higher score = more likely to play local music without too much talking.
    Returns -1 if the station should be skipped entirely.
    """
    tags = set(station.get("tags", "").lower().split(","))
    tags = {t.strip() for t in tags}
    name_lower = station.get("name", "").lower()

    # hard skip — news or talk heavy
    if tags & SKIP_TAGS:
        return -1

    # hard skip by name keywords
    skip_name_keywords = ["news", "talk", "sport", "fm news", "information", "radio nacional"]
    if any(kw in name_lower for kw in skip_name_keywords):
        return -1

    # hard skip if no stream URL
    if not station.get("url_resolved"):
        return -1

    score = 0

    # prefer stations with local/folk/national tags
    score += len(tags & PREFER_TAGS) * 3

    # prefer higher click count (popularity)
    score += min(station.get("clickcount", 0) // 100, 20)

    # prefer stations with votes
    score += min(station.get("votes", 0) // 10, 10)

    # prefer mp3 or aac streams (more compatible than HLS)
    url = station.get("url_resolved", "").lower()
    if ".mp3" in url or ".aac" in url or "mp3" in station.get("codec", "").lower():
        score += 5

    # slight preference for stations with a country language tag
    if station.get("language", ""):
        score += 2

    return score


def find_best_station(country_code, country_name):
    """Find the best local music station for a country."""
    print(f"  Searching stations for {country_name}...")
    stations = get_stations(country_name)

    if not stations:
        print(f"  No stations found.")
        return None, None

    # score and sort
    scored = []
    for station in stations:
        score = score_station(station)
        if score >= 0:
            scored.append((score, station))

    if not scored:
        print(f"  No suitable stations found after filtering.")
        return None, None

    scored.sort(key=lambda x: x[0], reverse=True)

    # print top 5 for manual review
    print(f"  Top candidates:")
    for score, station in scored[:5]:
        print(f"    [{score:3d}] {station['name'][:45]:<45} | tags: {station.get('tags','')[:50]}")

    best = scored[0][1]
    name = best["name"]
    stream_url = best["url_resolved"]
    print(f"  → Selected: {name}")
    return name, stream_url


def update_countries_json(path="countries.json"):
    with open(path) as f:
        countries = json.load(f)

    for code, info in countries.items():
        country_name = COUNTRY_NAMES.get(code, info["name"])
        print(f"\n{info['name']} ({code}):")
        name, stream_url = find_best_station(code, country_name)

        if name and stream_url:
            countries[code]["radio_station_name"] = name
            countries[code]["radio_stream_url"] = stream_url
        else:
            print(f"  Keeping existing radio data if any.")

        time.sleep(1)  # be polite to the API

    with open(path, "w") as f:
        json.dump(countries, f, indent=2, ensure_ascii=False)

    print("\nDone. countries.json updated with radio station data.")
    print("\nReview the selections above and manually adjust any that don't fit.")
    print("To override a station, edit countries.json directly:")
    print('  "radio_station_name": "Your Station Name"')
    print('  "radio_stream_url": "https://stream.url/station.mp3"')


if __name__ == "__main__":
    update_countries_json()