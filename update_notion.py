import os
import json
from datetime import datetime
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
LANDING_PAGE_ID = os.environ["NOTION_LANDING_PAGE_ID"]

CONTINENT_MAP = {
    "PT": "Europe", "GB": "Europe", "DE": "Europe", "FR": "Europe",
    "ES": "Europe", "IT": "Europe", "NL": "Europe", "SE": "Europe",
    "NO": "Europe", "FI": "Europe",
    "US": "Americas", "BR": "Americas", "MX": "Americas", "AR": "Americas",
    "AU": "Oceania"
}



# ---------------------------------------------------------------------------
# SHARED HELPERS
# ---------------------------------------------------------------------------

def safe_text(value):
    return {"rich_text": [{"text": {"content": str(value) if value else "N/A"}}]}

def paragraph(text, bold=False, italic=False, color="default"):
    annotations = {}
    if bold: annotations["bold"] = True
    if italic: annotations["italic"] = True
    if color != "default": annotations["color"] = color
    rt = {"type": "text", "text": {"content": str(text) if text else ""}}
    if annotations: rt["annotations"] = annotations
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [rt]}}

def divider():
    return {"object": "block", "type": "divider", "divider": {}}

def callout(text, emoji="💡", color="gray_background"):
    return {
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": emoji},
            "color": color
        }
    }

def numbered_item(text):
    return {
        "object": "block", "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}
    }

def image_block(url):
    return {
        "object": "block", "type": "image",
        "image": {"type": "external", "external": {"url": url}}
    }

def embed_block(url):
    return {"object": "block", "type": "embed", "embed": {"url": url}}


# ---------------------------------------------------------------------------
# DATABASE PROPERTIES
# ---------------------------------------------------------------------------

def build_properties(data, code, include_name=True):
    props = {
        "Country Code": safe_text(code),
        "Top Song": safe_text(data.get("top_song")),
        "Top Artist": {"select": {"name": data.get("top_artist", "Unknown")}},
        "Top Genre": {"select": {"name": data.get("top_genre", "Pop")}},
        "Continent": {"select": {"name": CONTINENT_MAP.get(code, "Other")}},
        "Listeners Per Capita": {"number": data.get("listeners_per_capita", 0)},
        "Last Updated": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}
    }
    # only set Name on creation — teammates may have added flag emojis
    if include_name:
        props["Name"] = {"title": [{"text": {"content": data["name"]}}]}
    if data.get("spotify_link"):
        props["Spotify Link"] = {"url": data["spotify_link"]}
    if data.get("spotify_embed_url"):
        props["Spotify Embed URL"] = {"url": data["spotify_embed_url"]}
    if data.get("artist_image"):
        props["Artist Image"] = {"url": data["artist_image"]}
    if data.get("artist_embed_url"):
        props["Artist Embed URL"] = {"url": data["artist_embed_url"]}
    return props


# ---------------------------------------------------------------------------
# COUNTRY PAGE LIVE DATA SECTION
# ---------------------------------------------------------------------------

COUNTRY_ANCHOR_HEADING = "H I G H L I G H T S"
COUNTRY_BLOCK_IDS_FILE = "country_block_ids.json"


def load_country_block_ids():
    try:
        with open(COUNTRY_BLOCK_IDS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_country_block_ids(ids):
    with open(COUNTRY_BLOCK_IDS_FILE, "w") as f:
        json.dump(ids, f, indent=2)


def build_country_live_blocks(data):
    """
    Three column layout mirroring the global highlights section:
    Col 1 — Top Artist label + artist name + image
    Col 2 — top song embed + artist signature track embed
    Col 3 — top 10 songs + last updated
    """
    # column 1 — top artist label + name in one line, then image
    col1 = []
    col1.append(paragraph(
        f"Top Artist — {data.get('top_artist', '—')}",
        bold=True
    ))
    if data.get("artist_image"):
        col1.append(image_block(data["artist_image"]))

    # column 2 — signature track first, then top song
    col2 = []
    col2.append(paragraph(
        f"{data.get('top_artist', 'Artist')}'s Signature Track",
        bold=True
    ))
    if data.get("artist_embed_url"):
        col2.append(embed_block(data["artist_embed_url"]))
    else:
        col2.append(paragraph("Unavailable.", italic=True, color="gray"))
    col2.append(paragraph("Top Song This Week", bold=True))
    if data.get("spotify_embed_url"):
        col2.append(embed_block(data["spotify_embed_url"]))
    else:
        col2.append(paragraph("Unavailable.", italic=True, color="gray"))

    # column 3 — top 10 tracks, then genre, then last updated
    col3 = []
    col3.append(paragraph("Top 10 This Week", bold=True))
    for track in data.get("top_tracks", []):
        clean = track.split(". ", 1)[-1] if ". " in track else track
        col3.append(numbered_item(clean))
    col3.append(callout(
        data.get("top_genre", "—"),
        emoji="🎸",
        color="purple_background"
    ))
    col3.append(divider())
    col3.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {
                "content": f"Last Updated - {datetime.now().strftime('%B %d, %Y')}"
            }}],
            "icon": {"type": "emoji", "emoji": "🔄"},
            "color": "default"
        }
    })

    def to_column(blocks):
        return {
            "object": "block",
            "type": "column",
            "column": {"children": blocks}
        }

    return [
        {
            "object": "block",
            "type": "column_list",
            "column_list": {
                "children": [
                    to_column(col1),
                    to_column(col2),
                    to_column(col3),
                ]
            }
        }
    ]


def update_country_live_section(page_id, code, data):
    """Find anchor heading, append new block after it, delete old one."""
    all_blocks = notion.blocks.children.list(
        block_id=page_id
    ).get("results", [])

    # find the anchor heading
    heading_id = None
    for block in all_blocks:
        if block["type"] in ("heading_1", "heading_2", "heading_3"):
            text = "".join(
                t["text"]["content"]
                for t in block.get(block["type"], {}).get("rich_text", [])
            )
            if COUNTRY_ANCHOR_HEADING in text:
                heading_id = block["id"]
                break

    if heading_id is None:
        print(f"  ⚠️  No '{COUNTRY_ANCHOR_HEADING}' heading found on {data['name']} page. Skipping live section.")
        return

    country_block_ids = load_country_block_ids()
    old_block_id = country_block_ids.get(code)

    # append new block after heading
    response = notion.blocks.children.append(
        block_id=page_id,
        children=build_country_live_blocks(data),
        after=heading_id
    )

    # save new block ID
    new_blocks = response.get("results", [])
    new_block_id = new_blocks[0]["id"] if new_blocks else None
    if new_block_id:
        country_block_ids[code] = new_block_id
        save_country_block_ids(country_block_ids)

    # delete old block
    if old_block_id and old_block_id != new_block_id:
        try:
            notion.blocks.delete(block_id=old_block_id)
        except Exception as e:
            print(f"  Could not delete old block: {e}")


# ---------------------------------------------------------------------------
# COUNTRY PAGES
# ---------------------------------------------------------------------------

def find_page_by_country_code(code):
    response = notion.databases.query(
        database_id=DATABASE_ID,
        filter={"property": "Country Code", "rich_text": {"equals": code}}
    )
    results = response.get("results", [])
    return results[0]["id"] if results else None


def create_country_page(data, code):
    """Create a new country page — teammates add their own heading as anchor."""
    page = notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=build_properties(data, code),
        children=[]
    )
    page_id = page["id"]
    update_country_live_section(page_id, code, data)
    print(f"  Created: {data['name']}")


def update_country_page(page_id, data, code):
    """Update properties and live section only. Name excluded to preserve emoji titles."""
    notion.pages.update(
        page_id=page_id,
        properties=build_properties(data, code, include_name=False)
    )
    update_country_live_section(page_id, code, data)
    print(f"  Updated: {data['name']}")


# ---------------------------------------------------------------------------
# LANDING PAGE
# ---------------------------------------------------------------------------

def build_landing_section_blocks(global_stats):
    # column 1 — artist info
    col1 = []
    col1.append(paragraph(
        f"Top Artist — {global_stats.get('top_global_artist', '—')}",
        bold=True
    ))
    if global_stats.get("top_global_artist_image"):
        col1.append(image_block(global_stats["top_global_artist_image"]))

    # column 2 — two spotify embeds, minimal labels
    col2 = []
    col2.append(paragraph("Signature Track", bold=True))
    if global_stats.get("top_global_artist_embed_artist"):
        col2.append(embed_block(global_stats["top_global_artist_embed_artist"]))
    else:
        col2.append(paragraph("Unavailable.", italic=True, color="gray"))
    col2.append(paragraph("Top Song This Week", bold=True))
    if global_stats.get("top_global_artist_embed"):
        col2.append(embed_block(global_stats["top_global_artist_embed"]))
    else:
        col2.append(paragraph("Unavailable.", italic=True, color="gray"))

    # column 3 — top 10 songs + last updated at bottom
    col3 = []
    col3.append(paragraph("Top 10 Songs Globally", bold=True))
    for song in global_stats.get("top_3_songs", [])[:10]:
        clean = song.split(". ", 1)[-1] if ". " in song else song
        col3.append(numbered_item(clean))
    col3.append(divider())
    col3.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {
                "content": f"Last Updated - {datetime.now().strftime('%B %d, %Y')}"
            }}],
            "icon": {"type": "emoji", "emoji": "🔄"},
            "color": "default"
        }
    })

    def to_column(blocks):
        return {
            "object": "block",
            "type": "column",
            "column": {"children": blocks}
        }

    return [
        {
            "object": "block",
            "type": "column_list",
            "column_list": {
                "children": [
                    to_column(col1),
                    to_column(col2),
                    to_column(col3),
                ]
            }
        }
    ]


# ---------------------------------------------------------------------------
# LANDING PAGE — finds heading anchor, appends new block after it,
# then deletes the previous block using stored ID
# ---------------------------------------------------------------------------

LANDING_SECTION_HEADING = "G L O B A L  H I G H L I G H T S"
HIGHLIGHTS_ID_FILE = "highlights_block_id.json"


def load_highlights_block_id():
    try:
        with open(HIGHLIGHTS_ID_FILE) as f:
            return json.load(f).get("block_id")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_highlights_block_id(block_id):
    with open(HIGHLIGHTS_ID_FILE, "w") as f:
        json.dump({"block_id": block_id}, f)


def update_landing_page(global_stats):
    all_blocks = notion.blocks.children.list(
        block_id=LANDING_PAGE_ID
    ).get("results", [])

    # find the heading anchor
    heading_id = None
    for block in all_blocks:
        if block["type"] in ("heading_1", "heading_2", "heading_3"):
            text = "".join(
                t["text"]["content"]
                for t in block.get(block["type"], {}).get("rich_text", [])
            ).strip()
            if LANDING_SECTION_HEADING.strip() in text or text in LANDING_SECTION_HEADING.strip():
                heading_id = block["id"]
                break

    if heading_id is None:
        print(f"  ⚠️  Could not find heading '{LANDING_SECTION_HEADING}' on landing page.")
        print("  Add this heading as a top-level block on the landing page and rerun.")
        return

    old_block_id = load_highlights_block_id()

    # step 1 — append new block after the heading
    response = notion.blocks.children.append(
        block_id=LANDING_PAGE_ID,
        children=build_landing_section_blocks(global_stats),
        after=heading_id
    )

    # step 2 — save new block ID
    new_blocks = response.get("results", [])
    new_block_id = new_blocks[0]["id"] if new_blocks else None
    if new_block_id:
        save_highlights_block_id(new_block_id)

    # step 3 — delete old block now that new one is in place
    if old_block_id and old_block_id != new_block_id:
        try:
            notion.blocks.delete(block_id=old_block_id)
            print("  Old highlights block deleted.")
        except Exception as e:
            print(f"  Could not delete old block: {e}")

    print("  Landing page highlights updated.")

def update_notion(music_data_path="music_data.json"):
    with open(music_data_path) as f:
        raw = json.load(f)

    countries_data = raw["countries"]
    global_stats = raw["global"]

    print("\n--- Updating country pages ---")
    for code, data in countries_data.items():
        print(f"\nProcessing {data['name']}...")
        try:
            page_id = find_page_by_country_code(code)
            if page_id:
                update_country_page(page_id, data, code)
            else:
                create_country_page(data, code)
        except Exception as e:
            print(f"  Error: {e}")

    print("\n--- Updating landing page section ---")
    try:
        update_landing_page(global_stats)
    except Exception as e:
        print(f"  Error updating landing page: {e}")


if __name__ == "__main__":
    update_notion()
    print("\nDone. Notion fully updated.")