#!/usr/bin/env python3
"""
Trek Geeks Podcast Network - RSS Feed Merger
Fetches all show feeds, merges episodes sorted by date,
and outputs a single valid podcast RSS feed to docs/feed.xml.
"""

import feedparser
from feedgen.feed import FeedGenerator
import datetime
import pytz
import os
from email.utils import parsedate_to_datetime

# ── CONFIG — edit these ───────────────────────────────────────────────────────
FEEDS = [
    "https://feeds.libsyn.com/324119/rss",
    "https://feeds.libsyn.com/62071/rss",
    "https://anchor.fm/s/fd59f580/podcast/rss",
    "https://anchor.fm/s/e3caae34/podcast/rss",
    "https://anchor.fm/s/109773ecc/podcast/rss",
]

NETWORK_TITLE = "Trek Geeks Podcast Network"
NETWORK_LINK  = "https://www.trekgeeks.com"
NETWORK_DESCRIPTION = (
    "Trek Geeks Podcast Network is home to a collection of fan-driven podcasts "
    "celebrating Star Trek, science fiction, and the fandoms that bring us together. "
    "From deep dives into Star Trek episodes and characters to conversations about sci-fi "
    "across film, television, and books, the network offers a variety of shows with unique "
    "voices and perspectives. Our lineup includes Trek Geeks, SyFy Sistas, The BIG Sci-Fi "
    "Podcast, Space Crime Continuum, and Planet Zero — each bringing its own style, insight, "
    "and passion for storytelling, fandom, and community. Whether you're a lifelong Star Trek "
    "fan, a sci-fi enthusiast, or someone who just loves great conversations about the stories "
    "that inspire us, the Trek Geeks Podcast Network has something for you."
)

# Replace YOURUSERNAME with your actual GitHub username
NETWORK_IMAGE    = "https://wesmith1017-lab.github.io/network-feed/artwork.jpg"
NETWORK_FEED_URL = "https://wesmith1017-lab.github.io/network-feed/feed.xml"
NETWORK_EMAIL    = "podcast@trekgeeks.com"
NETWORK_AUTHOR   = "Trek Geeks Podcast Network"
NETWORK_LANGUAGE = "en-us"
NETWORK_CATEGORY = "TV & Film"
NETWORK_EXPLICIT = "no"

OUTPUT_PATH = "docs/feed.xml"
# ─────────────────────────────────────────────────────────────────────────────


def parse_date(entry):
    # Try structured parsed date first
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime.datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
        except Exception:
            pass
    # Fall back to raw date string
    raw = entry.get("published") or entry.get("updated") or ""
    if raw:
        try:
            return parsedate_to_datetime(raw).astimezone(pytz.utc)
        except Exception:
            pass
    return datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)


def safe_get(entry, *keys, default=""):
    """Try multiple attribute names, return first hit."""
    for key in keys:
        val = getattr(entry, key, None)
        if val:
            return val
        if isinstance(entry, dict) and key in entry:
            return entry[key]
    return default


def build_feed():
    all_entries = []

    for url in FEEDS:
        print(f"Fetching: {url}")
    parsed = feedparser.parse(url, request_headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })

        if parsed.bozo and not parsed.entries:
            print(f"  WARNING: Could not parse {url} — skipping")
            continue

        show_title = parsed.feed.get("title", "Unknown Show")
        print(f"  Found {len(parsed.entries)} episodes from: {show_title}")

        for entry in parsed.entries:
            # Stash show metadata on the entry for later use
            entry["_show_title"] = show_title
            all_entries.append(entry)

    # Sort newest first, cap at 100
    all_entries.sort(key=parse_date, reverse=True)
   # all_entries = all_entries[:100] # temporarily disabled for testing
    print(f"\nTotal episodes across all shows: {len(all_entries)}")

    # ── Build the output feed ─────────────────────────────────────────────────
    fg = FeedGenerator()
    fg.load_extension("podcast")

    fg.id(NETWORK_LINK)
    fg.title(NETWORK_TITLE)
    fg.link(href=NETWORK_LINK)
    fg.description(NETWORK_DESCRIPTION)
    fg.language(NETWORK_LANGUAGE)
    fg.image(url=NETWORK_IMAGE, title=NETWORK_TITLE, link=NETWORK_LINK)
    fg.author({"name": NETWORK_AUTHOR, "email": NETWORK_EMAIL})

    fg.podcast.itunes_author(NETWORK_AUTHOR)
    fg.podcast.itunes_category("TV & Film", cat2="Film Reviews")
    fg.podcast.itunes_explicit(NETWORK_EXPLICIT)
    fg.podcast.itunes_image(NETWORK_IMAGE)
    fg.podcast.itunes_owner(name=NETWORK_AUTHOR, email=NETWORK_EMAIL)

    for entry in all_entries:
        fe = fg.add_entry()

        # Core fields
        guid = entry.get("id") or entry.get("link") or entry.get("title", "")
        fe.id(guid)
        fe.title(entry.get("title", "Untitled"))
        fe.link(href=entry.get("link", NETWORK_LINK))
        fe.pubDate(parse_date(entry))

        # Description — prefer content, fall back to summary
        content = entry.get("content", [])
        if content:
            description = content[0].get("value", "")
        else:
            description = entry.get("summary") or entry.get("description") or ""
        fe.description(description)

        # Enclosure (the audio file)
        enclosures = entry.get("enclosures", [])
        if enclosures:
            enc = enclosures[0]
            fe.enclosure(
                url=enc.get("href", ""),
                length=str(enc.get("length", "0")),
                type=enc.get("type", "audio/mpeg"),
            )

        # iTunes-specific tags
        duration = (
            entry.get("itunes_duration")
            or entry.get("itunes_duration")
            or ""
        )
        if duration:
            fe.podcast.itunes_duration(str(duration))

        raw_explicit = str(entry.get("itunes_explicit") or NETWORK_EXPLICIT).lower().strip()
        if raw_explicit in ("yes", "true", "explicit"):
            explicit = "yes"
        elif raw_explicit in ("clean",):
            explicit = "clean"
        else:
            explicit = "no"
        fe.podcast.itunes_explicit(explicit)

        # Per-episode artwork (falls back to network image)
        ep_image = entry.get("itunes_image", {})
        if isinstance(ep_image, dict):
            ep_image = ep_image.get("href", "")
        fe.podcast.itunes_image(ep_image or NETWORK_IMAGE)

        episode_type = entry.get("itunes_episodetype", "full")
        fe.podcast.itunes_episode_type(episode_type)

        author = (
            entry.get("itunes_author")
            or entry.get("author")
            or entry.get("_show_title")
            or NETWORK_AUTHOR
        )
        fe.podcast.itunes_author(author)

        # Episode/season numbers if present
        ep_num = entry.get("itunes_episode")
        if ep_num:
            fe.podcast.itunes_episode(str(ep_num))

        season = entry.get("itunes_season")
        if season:
            fe.podcast.itunes_season(str(season))

    # ── Write output ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fg.rss_file(OUTPUT_PATH, pretty=True)
    print(f"\nFeed written to: {OUTPUT_PATH}")
    print(f"Will be live at: {NETWORK_FEED_URL}")


if __name__ == "__main__":
    build_feed()
