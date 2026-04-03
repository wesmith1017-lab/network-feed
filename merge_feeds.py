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
import re
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

NETWORK_IMAGE    = "https://wesmith1017-lab.github.io/network-feed/artwork.jpg"
NETWORK_FEED_URL = "https://wesmith1017-lab.github.io/network-feed/feed.xml"
NETWORK_EMAIL    = "podcast@trekgeeks.com"
NETWORK_AUTHOR   = "Trek Geeks Podcast Network"
NETWORK_LANGUAGE = "en-us"
NETWORK_EXPLICIT = "no"
MAX_EPISODES     = 100

OUTPUT_PATH = "docs/feed.xml"
# ─────────────────────────────────────────────────────────────────────────────


def parse_date(entry):
    """Return a timezone-aware datetime for sorting. Falls back to epoch."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime.datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
        except Exception:
            pass
    raw = entry.get("published") or entry.get("updated") or ""
    if raw:
        try:
            return parsedate_to_datetime(raw).astimezone(pytz.utc)
        except Exception:
            pass
    return datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)


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
            entry["_show_title"] = show_title
            all_entries.append(entry)

    # Sort newest first, cap at MAX_EPISODES
    all_entries.sort(key=parse_date, reverse=True)
    all_entries = all_entries[:MAX_EPISODES]

    print(f"\nTotal episodes in merged feed: {len(all_entries)}")
    for e in all_entries[:5]:
        print(f"  {parse_date(e)} — {e.get('title')}")

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

    # feedgen reverses entry order on write, so feed oldest-first here
    for entry in reversed(all_entries):
        fe = fg.add_entry()

        guid = entry.get("id") or entry.get("link") or entry.get("title", "")
        fe.id(guid)
        fe.title(entry.get("title", "Untitled"))
        fe.link(href=entry.get("link", NETWORK_LINK))
        fe.pubDate(parse_date(entry))

        content = entry.get("content", [])
        if content:
            description = content[0].get("value", "")
        else:
            description = entry.get("summary") or entry.get("description") or ""
        fe.description(description)

        enclosures = entry.get("enclosures", [])
        if enclosures:
            enc = enclosures[0]
            fe.enclosure(
                url=enc.get("href", ""),
                length=str(enc.get("length", "0")),
                type=enc.get("type", "audio/mpeg"),
            )

        duration = entry.get("itunes_duration") or ""
        if duration:
            fe.podcast.itunes_duration(str(duration))

        raw_explicit = str(entry.get("itunes_explicit") or NETWORK_EXPLICIT).lower().strip()
        if raw_explicit in ("yes", "true", "explicit"):
            explicit = "yes"
        elif raw_explicit == "clean":
            explicit = "clean"
        else:
            explicit = "no"
        fe.podcast.itunes_explicit(explicit)

        ep_image = ""
        # Try multiple locations feedparser uses depending on host
        if entry.get("itunes_image"):
            img = entry.get("itunes_image")
            ep_image = img.get("href", "") if isinstance(img, dict) else str(img)
        if not ep_image and entry.get("image"):
            img = entry.get("image")
            ep_image = img.get("href", "") if isinstance(img, dict) else str(img)
        if not ep_image:
            for tag in entry.get("tags", []):
                if "image" in tag.get("term", "").lower():
                    ep_image = tag.get("scheme", "") or tag.get("label", "")
                    break
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

        ep_num = entry.get("itunes_episode")
        if ep_num:
            fe.podcast.itunes_episode(str(ep_num))

        season = entry.get("itunes_season")
        if season:
            fe.podcast.itunes_season(str(season))

    # ── Write output ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fg.rss_file(OUTPUT_PATH, pretty=True)

    # Verify written order
    print(f"\nFeed written to: {OUTPUT_PATH}")
    print(f"Live at: {NETWORK_FEED_URL}")


if __name__ == "__main__":
    build_feed()
