import os
import json
from datetime import datetime
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def find_page_by_country_code(code):
    """Find an existing Notion page by country code."""
    response = notion.databases.query(
        database_id=DATABASE_ID,
        filter={
            "property": "Country Code",
            "rich_text": {"equals": code}
        }
    )
    results = response.get("results", [])
    return results[0]["id"] if results else None


def safe_text(value):
    """Return a Notion rich_text property, handling None values."""
    return {"rich_text": [{"text": {"content": value or "N/A"}}]}


def build_properties(data, code):
    """Build the Notion properties dict from country data."""
    props = {
        "Name": {
            "title": [{"text": {"content": data["name"]}}]
        },
        "Country Code": safe_text(code),
        "Top Song": safe_text(data.get("top_song")),
        "Top Artist": safe_text(data.get("top_artist")),
        "Top Genre": safe_text(data.get("top_genre")),
        "Upcoming Concert": safe_text(data.get("upcoming_concert")),
        "Last Updated": {
            "date": {"start": datetime.now().strftime("%Y-%m-%d")}
        }
    }

    if data.get("spotify_link"):
        props["Spotify Link"] = {"url": data["spotify_link"]}

    if data.get("radio_garden_url"):
        props["Radio Garden"] = {"url": data["radio_garden_url"]}

    return props


def build_page_body(data):
    """Build the Notion page body blocks from country data."""
    blocks = []

    # --- Top Tracks ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "🎵 Top 10 Tracks This Week"}}]
        }
    })
    for track in data.get("top_tracks", []):
        blocks.append({
            "object": "block",
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": [{"type": "text", "text": {"content": track}}]
            }
        })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Spotify Link ---
    if data.get("spotify_link"):
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "▶️ Listen to the Top Song on Spotify"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "bookmark",
            "bookmark": {"url": data["spotify_link"]}
        })
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Radio Garden ---
    if data.get("radio_garden_url"):
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📻 Listen to Local Radio"}}]
            }
        })
        # embedded Radio Garden iframe
        blocks.append({
            "object": "block",
            "type": "embed",
            "embed": {"url": data["radio_garden_url"]}
        })
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Upcoming Concert ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "🎤 Upcoming Concert"}}]
        }
    })
    concert_text = data.get("upcoming_concert") or "No upcoming concerts found"
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": concert_text}}]
        }
    })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Music Culture (manual placeholder) ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "🌍 Music Culture"}}]
        }
    })
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Add a description of this country's music culture here."
            }, "annotations": {"italic": True, "color": "gray"}}]
        }
    })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Comparison with Portugal (manual placeholder) ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "🇵🇹 Comparison with Portugal"}}]
        }
    })
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Add comparison with Portugal here."
            }, "annotations": {"italic": True, "color": "gray"}}]
        }
    })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Music History (manual placeholder) ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "📖 Music History"}}]
        }
    })
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Add a brief history of music in this country here."
            }, "annotations": {"italic": True, "color": "gray"}}]
        }
    })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # --- Fun Fact (manual placeholder) ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "💡 Fun Fact"}}]
        }
    })
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Add a fun music fact about this country here."
            }, "annotations": {"italic": True, "color": "gray"}}]
        }
    })

    return blocks


# ---------------------------------------------------------------------------
# CREATE OR UPDATE
# ---------------------------------------------------------------------------

def create_page(data, code):
    """Create a new Notion page for a country."""
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=build_properties(data, code),
        children=build_page_body(data)
    )
    print(f"  Created page for {data['name']}")


def update_page(page_id, data, code):
    """Update an existing Notion page."""
    notion.pages.update(
        page_id=page_id,
        properties=build_properties(data, code)
    )

    # delete existing blocks and rewrite
    existing_blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
    for block in existing_blocks:
        try:
            notion.blocks.delete(block_id=block["id"])
        except Exception:
            pass

    notion.blocks.children.append(
        block_id=page_id,
        children=build_page_body(data)
    )
    print(f"  Updated page for {data['name']}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def update_notion(music_data_path="music_data.json"):
    with open(music_data_path) as f:
        music_data = json.load(f)

    for code, data in music_data.items():
        print(f"\nProcessing {data['name']}...")
        try:
            page_id = find_page_by_country_code(code)
            if page_id:
                update_page(page_id, data, code)
            else:
                create_page(data, code)
        except Exception as e:
            print(f"  Error processing {data['name']}: {e}")


if __name__ == "__main__":
    update_notion()
    print("\nDone. Notion database updated.")