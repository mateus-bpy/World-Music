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


# ---------------------------------------------------------------------------
# LAST.FM COUNTRY NAME OVERRIDES
# Some countries need a different name for Last.fm's API
# ---------------------------------------------------------------------------

LASTFM_COUNTRY_NAMES = {
    "GB": "United Kingdom",
    "US": "United States",
}


# ---------------------------------------------------------------------------
# GENRE NORMALIZATION
# ---------------------------------------------------------------------------

GENRE_MAP = {
    # Pop
    "pop": "Pop", "dance pop": "Pop", "electropop": "Pop", "synth-pop": "Pop",
    "teen pop": "Pop", "baroque pop": "Pop", "art pop": "Pop", "pop punk": "Pop",
    "candy pop": "Pop", "bubblegum pop": "Pop", "chamber pop": "Pop",
    # Rock
    "rock": "Rock", "alternative rock": "Rock", "indie rock": "Rock",
    "classic rock": "Rock", "hard rock": "Rock", "soft rock": "Rock",
    "punk": "Rock", "punk rock": "Rock", "post-punk": "Rock", "grunge": "Rock",
    # Metal — own genre
    "metal": "Metal", "heavy metal": "Metal", "death metal": "Metal",
    "black metal": "Metal", "power metal": "Metal", "thrash metal": "Metal",
    "doom metal": "Metal", "progressive metal": "Metal", "metalcore": "Metal",
    "nu metal": "Metal", "alternative metal": "Metal",
    "symphonic metal": "Metal", "finnish metal": "Metal", "melodic death metal": "Metal",
    # Hip-Hop
    "hip-hop": "Hip-Hop", "hip hop": "Hip-Hop", "rap": "Hip-Hop",
    "trap": "Hip-Hop", "gangsta rap": "Hip-Hop", "conscious hip hop": "Hip-Hop",
    "drill": "Hip-Hop", "uk hip hop": "Hip-Hop", "east coast hip hop": "Hip-Hop",
    "west coast hip hop": "Hip-Hop", "alternative hip hop": "Hip-Hop",
    "french hip hop": "Hip-Hop", "italian hip hop": "Hip-Hop",
    "dirty south": "Hip-Hop", "latin trap": "Hip-Hop",
    # Electronic
    "electronic": "Electronic", "edm": "Electronic", "house": "Electronic",
    "techno": "Electronic", "trance": "Electronic", "ambient": "Electronic",
    "dubstep": "Electronic", "electronica": "Electronic", "drum and bass": "Electronic",
    "downtempo": "Electronic", "trip hop": "Electronic", "synthwave": "Electronic",
    # Latin
    "latin": "Latin", "reggaeton": "Latin", "latin pop": "Latin",
    "salsa": "Latin", "bachata": "Latin", "cumbia": "Latin",
    "latin alternative": "Latin", "urban latin": "Latin",
    # Classical
    "classical": "Classical", "orchestra": "Classical", "opera": "Classical",
    "classical music": "Classical", "piano": "Classical",
    # Indie
    "indie": "Indie", "indie pop": "Indie", "lo-fi": "Indie",
    "chillwave": "Indie", "shoegaze": "Indie", "dream pop": "Indie",
    "bedroom pop": "Indie", "lo fi": "Indie",
    # Folk
    "folk": "Folk", "folk pop": "Folk", "country": "Folk",
    "acoustic": "Folk", "singer-songwriter": "Folk", "americana": "Folk",
    "nordic folk": "Folk", "scandinavian folk": "Folk",
    # R&B
    "r&b": "R&B", "contemporary r&b": "R&B", "soul": "R&B",
    "neo soul": "R&B", "rnb": "R&B", "rhythm and blues": "R&B",
    # Fado
    "fado": "Fado", "portuguese music": "Fado",
}

def normalize_genre(raw_genre):
    if not raw_genre:
        return "Pop"
    lower = raw_genre.lower().strip()
    if lower in GENRE_MAP:
        return GENRE_MAP[lower]
    for key, value in GENRE_MAP.items():
        if key in lower:
            return value
    return "Pop"


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
# LAST.FM
# ---------------------------------------------------------------------------

def get_top_tracks_lastfm(country_name, limit=10):
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
    if not response.content:
        return []
    tracks = response.json().get("tracks", {}).get("track", [])
    return [{"name": t["name"], "artist": t["artist"]["name"]} for t in tracks]


def get_top_artist_info_lastfm(country_name):
    """Returns (artist_name, listener_count)."""
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
    if not response.content:
        return "Unknown", 0
    artists = response.json().get("topartists", {}).get("artist", [])
    if artists:
        name = artists[0]["name"]
        raw_listeners = artists[0].get("listeners", 0)
        try:
            listeners = int(str(raw_listeners).replace(",", ""))
        except (ValueError, TypeError):
            listeners = 0
        return name, listeners
    return "Unknown", 0


def get_artist_genre_lastfm(artist_name):
    response = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "artist.getTopTags",
            "artist": artist_name,
            "api_key": LASTFM_API_KEY,
            "format": "json"
        }
    )
    if not response.content:
        return "pop"
    skip = {
        "seen live", "favourites", "favorite", "love", "awesome", "cool",
        "great", "beautiful", "amazing", "epic", "favorite bands",
        "all time favorite", "under 2000 listeners"
    }
    tags = response.json().get("toptags", {}).get("tag", [])
    for tag in tags:
        name = tag["name"].lower().strip()
        if name not in skip and len(name) > 1:
            return tag["name"]
    return "pop"


# ---------------------------------------------------------------------------
# SPOTIFY
# ---------------------------------------------------------------------------

def search_track_spotify(token, track_name, artist_name):
    """Returns (spotify_url, embed_url)."""
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"track:{track_name} artist:{artist_name}",
            "type": "track",
            "limit": 1
        }
    )
    if not response.content or response.status_code != 200:
        print(f"  ⚠️  Spotify track search failed: {response.status_code}")
        return None, None
    items = response.json().get("tracks", {}).get("items", [])
    if items:
        track_id = items[0]["id"]
        url = items[0]["external_urls"]["spotify"]
        embed_url = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"
        return url, embed_url
    return None, None


def get_artist_spotify_info(token, artist_name, exclude_track_name=None):
    """Returns (image_url, most_popular_track_embed_url) using search sorted by popularity."""
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": artist_name, "type": "artist", "limit": 1}
    )
    if not response.content or response.status_code != 200:
        print(f"  ⚠️  Spotify artist search failed: {response.status_code}")
        return None, None

    artists = response.json().get("artists", {}).get("items", [])
    if not artists:
        return None, None

    artist = artists[0]
    image = artist["images"][0]["url"] if artist.get("images") else None

    track_response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": f"artist:{artist_name}", "type": "track", "limit": 10}
    )
    if not track_response.content or track_response.status_code != 200:
        print(f"  ⚠️  Spotify track search failed: {track_response.status_code}")
        return image, None

    tracks = track_response.json().get("tracks", {}).get("items", [])
    tracks.sort(key=lambda t: t.get("popularity", 0), reverse=True)

    for track in tracks:
        track_name = track["name"].lower().strip()
        if exclude_track_name and track_name == exclude_track_name.lower().strip():
            continue
        track_id = track["id"]
        embed_url = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"
        return image, embed_url

    return image, None


# ---------------------------------------------------------------------------
# REST COUNTRIES API
# ---------------------------------------------------------------------------

def get_population(country_code):
    try:
        response = requests.get(
            f"https://restcountries.com/v3.1/alpha/{country_code}",
            timeout=5
        )
        return response.json()[0].get("population", 1)
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# GLOBAL STATS
# ---------------------------------------------------------------------------

def calculate_global_stats(results, spotify_token):
    # most listened artist — appears as top artist in most countries
    artist_counts = {}
    for country in results.values():
        a = country.get("top_artist")
        if a:
            artist_counts[a] = artist_counts.get(a, 0) + 1
    top_global_artist = max(artist_counts, key=artist_counts.get) if artist_counts else "Unknown"

    # find top song for global artist first so we can exclude it from signature track
    global_artist_top_song = None
    global_artist_top_song_embed = None
    for country in results.values():
        if country.get("top_artist") == top_global_artist:
            song = country.get("top_song")
            artist = country.get("top_song_artist", top_global_artist)
            if song:
                _, embed = search_track_spotify(spotify_token, song, artist)
                global_artist_top_song = song
                global_artist_top_song_embed = embed
                break
    time.sleep(0.3)

    # artist image and signature track excluding the top song
    top_global_artist_image, top_global_artist_embed_artist = get_artist_spotify_info(
        spotify_token, top_global_artist, exclude_track_name=global_artist_top_song
    )
    time.sleep(0.3)

    # top 10 songs weighted by position across all countries
    song_weights = {}
    for country in results.values():
        for i, track in enumerate(country.get("top_tracks", [])[:5]):
            clean = track.split(". ", 1)[-1] if ". " in track else track
            weight = 5 - i
            song_weights[clean] = song_weights.get(clean, 0) + weight
    top_songs_raw = sorted(song_weights.items(), key=lambda x: x[1], reverse=True)[:10]
    top_songs = [f"{i+1}. {song}" for i, (song, _) in enumerate(top_songs_raw)]

    return {
        "top_global_artist": top_global_artist,
        "top_global_artist_image": top_global_artist_image,
        "top_global_artist_embed_artist": top_global_artist_embed_artist,
        "top_global_artist_embed": global_artist_top_song_embed,
        "top_3_songs": top_songs,
    }


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

def fetch_all_countries(countries_path="countries.json"):
    with open(countries_path) as f:
        countries = json.load(f)

    spotify_token = get_spotify_token()
    results = {}

    priority_order = ["PT"] + [c for c in countries if c != "PT"]

    for code in priority_order:
        info = countries[code]
        country_name = info["name"]
        lastfm_name = LASTFM_COUNTRY_NAMES.get(code, country_name)
        print(f"\nFetching {country_name}...")

        try:
            tracks = get_top_tracks_lastfm(lastfm_name)
            if not tracks:
                print(f"  No tracks found, skipping.")
                continue

            top_song = tracks[0]["name"]
            top_song_artist = tracks[0]["artist"]

            top_artist, listeners = get_top_artist_info_lastfm(lastfm_name)
            population = get_population(code)
            listeners_per_capita = round((listeners / population) * 100000, 2) if population > 0 else 0
            if listeners_per_capita > 500:
                print(f"  ⚠️  Suspicious listeners value ({listeners}), capping per capita at 0")
                listeners_per_capita = 0

            raw_genre = get_artist_genre_lastfm(top_artist)
            top_genre = normalize_genre(raw_genre)

            spotify_link, spotify_embed_url = search_track_spotify(spotify_token, top_song, top_song_artist)
            artist_image, artist_embed_url = get_artist_spotify_info(spotify_token, top_artist, exclude_track_name=top_song)

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
                "spotify_embed_url": spotify_embed_url,
                "top_tracks": top_tracks_list,
                "artist_image": artist_image,
                "artist_embed_url": artist_embed_url,
                "listeners_per_capita": listeners_per_capita,
            }

            print(f"  Song: {top_song} by {top_song_artist}")
            print(f"  Artist: {top_artist} | Genre: {top_genre} (raw: {raw_genre})")
            print(f"  Listeners/100k: {listeners_per_capita}")

        except Exception as e:
            print(f"  Error: {e}")

        time.sleep(0.5)

    print("\nCalculating global stats...")
    global_stats = calculate_global_stats(results, spotify_token)
    print(f"  Top global artist: {global_stats['top_global_artist']}")
    print(f"  Top songs calculated: {len(global_stats['top_3_songs'])}")

    return results, global_stats


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results, global_stats = fetch_all_countries()
    output = {"countries": results, "global": global_stats}
    with open("music_data.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print("\nDone. Data saved to music_data.json")