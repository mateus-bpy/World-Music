import os
import json
import time
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
LASTFM_API_KEY = os.environ["LASTFM_API_KEY"]
TICKETMASTER_API_KEY = os.environ["TICKETMASTER_API_KEY"]

# ---------------------------------------------------------------------------
# SPOTIFY AUTH
# ---------------------------------------------------------------------------

def get_spotify_token():
    credentials = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {credentials}"},
        data={"grant_type": "client_credentials"}
    )
    return response.json()["access_token"]


# ---------------------------------------------------------------------------
# LAST.FM CALLS
# ---------------------------------------------------------------------------

def get_top_tracks_lastfm(country_name, limit=10):
    """Get top tracks for a country from Last.fm."""
    response = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "geo.getTopTracks",
            "country": country_name,
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "limit": limit
        }
    )
    data = response.json()
    tracks = data.get("tracks", {}).get("track", [])
    return [{"name": t["name"], "artist": t["artist"]["name"]} for t in tracks]


def get_top_artist_lastfm(country_name):
    """Get the top artist for a country from Last.fm."""
    response = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "geo.getTopArtists",
            "country": country_name,
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "limit": 1
        }
    )
    data = response.json()
    artists = data.get("topartists", {}).get("artist", [])
    return artists[0]["name"] if artists else "Unknown"


def get_artist_tags_lastfm(artist_name):
    """Get the top genre tag for an artist from Last.fm."""
    response = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "artist.getTopTags",
            "artist": artist_name,
            "api_key": LASTFM_API_KEY,
            "format": "json"
        }
    )
    tags = response.json().get("toptags", {}).get("tag", [])
    skip_tags = {"seen live", "favourites", "favorite", "love", "awesome", "cool", "great"}
    for tag in tags:
        if tag["name"].lower() not in skip_tags:
            return tag["name"]
    return "unknown"


# ---------------------------------------------------------------------------
# SPOTIFY CALLS
# ---------------------------------------------------------------------------

def search_track_spotify(token, track_name, artist_name):
    """Search for a track on Spotify and return its URL."""
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"track:{track_name} artist:{artist_name}",
            "type": "track",
            "limit": 1
        }
    )
    items = response.json().get("tracks", {}).get("items", [])
    if items:
        return items[0]["external_urls"]["spotify"]
    return None


# ---------------------------------------------------------------------------
# TICKETMASTER API
# ---------------------------------------------------------------------------

def get_upcoming_concert(country_code):
    """Get the most relevant upcoming music event in a country."""
    try:
        response = requests.get(
            "https://app.ticketmaster.com/discovery/v2/events.json",
            params={
                "apikey": TICKETMASTER_API_KEY,
                "countryCode": country_code,
                "classificationName": "music",
                "size": 1,
                "sort": "relevance,desc"
            }
        )
        data = response.json()
        events = data.get("_embedded", {}).get("events", [])
        if events:
            event = events[0]
            name = event["name"]
            date = event["dates"]["start"].get("localDate", "TBA")
            venue = event.get("_embedded", {}).get("venues", [{}])[0].get("name", "Unknown venue")
            return f"{name} — {venue} ({date})"
    except Exception as e:
        print(f"  Concert error: {e}")
    return None


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

def fetch_all_countries(countries_path="countries.json"):
    with open(countries_path) as f:
        countries = json.load(f)

    spotify_token = get_spotify_token()
    results = {}

    # Process Portugal first
    priority_order = ["PT"] + [c for c in countries if c != "PT"]

    for code in priority_order:
        info = countries[code]
        country_name = info["name"]
        print(f"\nFetching {country_name}...")

        try:
            # Step 1: top tracks and artist from Last.fm
            tracks = get_top_tracks_lastfm(country_name)
            top_artist = get_top_artist_lastfm(country_name)

            if not tracks:
                print(f"  No tracks found, skipping.")
                continue

            top_song = tracks[0]["name"]
            top_song_artist = tracks[0]["artist"]
            print(f"  Top song: {top_song} by {top_song_artist}")
            print(f"  Top artist: {top_artist}")

            # Step 2: genre from Last.fm
            top_genre = get_artist_tags_lastfm(top_artist)
            print(f"  Top genre: {top_genre}")

            # Step 3: Spotify link for top song
            spotify_link = search_track_spotify(spotify_token, top_song, top_song_artist)
            print(f"  Spotify link: {spotify_link}")

            # Step 4: Radio Garden URL from countries.json
            radio_garden_url = info.get("radio_garden_url")
            print(f"  Radio Garden: {radio_garden_url}")

            # Step 5: upcoming concert
            concert = get_upcoming_concert(code)
            print(f"  Concert: {concert}")

            # Step 6: build top tracks list
            top_tracks_list = [
                f"{i+1}. {t['name']} — {t['artist']}"
                for i, t in enumerate(tracks)
            ]

            results[code] = {
                "name": country_name,
                "top_song": top_song,
                "top_song_artist": top_song_artist,
                "top_artist": top_artist,
                "top_genre": top_genre,
                "spotify_link": spotify_link,
                "radio_garden_url": radio_garden_url,
                "upcoming_concert": concert,
                "top_tracks": top_tracks_list
            }

        except Exception as e:
            print(f"  Error fetching {country_name}: {e}")

        time.sleep(0.5)

    return results


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data = fetch_all_countries()
    with open("music_data.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nDone. Data saved to music_data.json")