#!/usr/bin/env python3
"""
Trek Geeks Podcast Network - RSS Feed Merger

Fetches multiple podcast RSS/Atom feeds, merges their episodes,
removes duplicates, sorts them by publication date, and writes
one combined podcast RSS feed to docs/feed.xml.
"""

import datetime
import html
import os
import re
from email.utils import parsedate_to_datetime

import feedparser
import pytz
from feedgen.feed import FeedGenerator


# =============================================================================
# CONFIGURATION
# =============================================================================

# Add new podcast RSS/Atom feed URLs here.
FEEDS = [
    "https://feeds.libsyn.com/324119/rss",           # Trek Geeks
    "https://feeds.libsyn.com/62071/rss",            # The BIG Sci-Fi Podcast
    "https://anchor.fm/s/fd59f580/podcast/rss",      # SyFy Sistas
    "https://anchor.fm/s/e3caae34/podcast/rss",      # Planet Zero
    "https://anchor.fm/s/109773ecc/podcast/rss",     # Space Crime Continuum
    "https://anchor.fm/s/113d7f58c/podcast/rss",     # We Are Starfleet
    "https://anchor.fm/s/10dd8986c/podcast/rss",     # The Brian Donahue Podcast
    "https://secretfriendsunite.com/code-47-star-trek-talk?format=rss",  # Code 47
    "https://rss.buzzsprout.com/2302178.rss",        # Crusher Convo
]

NETWORK_TITLE = "Trek Geeks Podcast Network"

NETWORK_LINK = "https://www.trekgeeks.com"

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

NETWORK_IMAGE = (
    "https://wesmith1017-lab.github.io/network-feed/artwork.jpg"
)

NETWORK_FEED_URL = (
    "https://wesmith1017-lab.github.io/network-feed/feed.xml"
)

NETWORK_EMAIL = "podcast@trekgeeks.com"

NETWORK_AUTHOR = "Trek Geeks Podcast Network"

NETWORK_LANGUAGE = "en-us"

NETWORK_EXPLICIT = "no"

MAX_EPISODES = 100

OUTPUT_PATH = "docs/feed.xml"


# =============================================================================
# HELPERS
# =============================================================================

def parse_date(entry):
    """
    Return a timezone-aware UTC datetime for an RSS entry.

    Uses feedparser's parsed date first and falls back to
    the raw published/updated date when necessary.
    """

    published_parsed = entry.get("published_parsed")

    if published_parsed:
        try:
            return datetime.datetime(
                *published_parsed[:6],
                tzinfo=pytz.utc,
            )
        except (TypeError, ValueError):
            pass

    updated_parsed = entry.get("updated_parsed")

    if updated_parsed:
        try:
            return datetime.datetime(
                *updated_parsed[:6],
                tzinfo=pytz.utc,
            )
        except (TypeError, ValueError):
            pass

    raw_date = (
        entry.get("published")
        or entry.get("updated")
        or entry.get("pubDate")
        or ""
    )

    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=pytz.utc)

            return parsed.astimezone(pytz.utc)

        except (TypeError, ValueError, OverflowError):
            pass

    return datetime.datetime(
        1970,
        1,
        1,
        tzinfo=pytz.utc,
    )


def clean_text(value):
    """
    Convert HTML entities and remove unnecessary HTML tags.
    """

    if not value:
        return ""

    value = html.unescape(str(value))

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    return value.strip()


def get_description(entry):
    """
    Get the best available episode description.
    """

    content = entry.get("content", [])

    if content:
        for item in content:
            value = item.get("value")

            if value:
                return clean_text(value)

    for field in (
        "summary",
        "description",
        "subtitle",
    ):
        value = entry.get(field)

        if value:
            return clean_text(value)

    return ""


def get_episode_image(entry):
    """
    Try to find episode artwork from common RSS/iTunes locations.
    """

    image = entry.get("itunes_image")

    if image:
        if isinstance(image, dict):
            href = image.get("href")

            if href:
                return href

        elif isinstance(image, str):
            return image

    image = entry.get("image")

    if image:
        if isinstance(image, dict):
            href = image.get("href")

            if href:
                return href

        elif isinstance(image, str):
            return image

    for tag in entry.get("tags", []):
        term = str(tag.get("term", "")).lower()

        if "image" in term:
            scheme = tag.get("scheme")

            if scheme:
                return scheme

            label = tag.get("label")

            if label:
                return label

    return NETWORK_IMAGE


def get_enclosure(entry):
    """
    Return the first valid audio enclosure, if available.
    """

    enclosures = entry.get("enclosures", [])

    for enclosure in enclosures:
        url = (
            enclosure.get("href")
            or enclosure.get("url")
            or ""
        )

        if not url:
            continue

        return {
            "url": url,
            "length": str(enclosure.get("length") or "0"),
            "type": enclosure.get("type") or "audio/mpeg",
        }

    return None


def get_guid(entry):
    """
    Return a stable GUID for an episode.
    """

    guid = (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
    )

    if guid:
        return str(guid).strip()

    title = str(entry.get("title") or "").strip()

    if title:
        return title

    return ""


def get_episode_author(entry, show_title):
    """
    Prefer the source show's title as the episode author.
    """

    return (
        show_title
        or entry.get("itunes_author")
        or entry.get("author")
        or NETWORK_AUTHOR
    )


def get_explicit_value(entry):
    """
    Normalize iTunes explicit values to yes/no/clean.
    """

    raw_value = str(
        entry.get("itunes_explicit")
        or NETWORK_EXPLICIT
    ).lower().strip()

    if raw_value in (
        "yes",
        "true",
        "explicit",
    ):
        return "yes"

    if raw_value == "clean":
        return "clean"

    return "no"


# =============================================================================
# FETCH FEEDS
# =============================================================================

def fetch_feeds():
    """
    Fetch all configured podcast feeds.

    Returns:
        list: All collected episode entries.
        int: Number of successfully processed feeds.
        list: Failed feed URLs.
    """

    all_entries = []

    successful_feeds = 0
    failed_feeds = []

    print("=" * 70)
    print("Fetching podcast feeds")
    print("=" * 70)

    for url in FEEDS:
        print(f"\nFetching: {url}")

        try:
            parsed = feedparser.parse(
                url,
                request_headers={
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "User-Agent": (
                        "TrekGeeksPodcastNetwork/1.0 "
                        "(RSS Feed Merger)"
                    ),
                },
            )

        except Exception as exc:
            print(f"  ERROR: {exc}")
            failed_feeds.append(url)
            continue

        if parsed.bozo and not parsed.entries:
            print("  WARNING: Feed could not be parsed.")
            failed_feeds.append(url)
            continue

        show_title = (
            parsed.feed.get("title")
            or "Unknown Show"
        )

        print(
            f"  Show: {show_title}"
        )

        print(
            f"  Episodes found: {len(parsed.entries)}"
        )

        successful_feeds += 1

        for entry in parsed.entries:
            title = str(
                entry.get("title") or ""
            ).strip()

            guid = get_guid(entry)

            if not title and not guid:
                print("  Skipping episode without title/GUID.")
                continue

            entry["_show_title"] = show_title

            all_entries.append(entry)

    return (
        all_entries,
        successful_feeds,
        failed_feeds,
    )


# =============================================================================
# REMOVE DUPLICATES
# =============================================================================

def remove_duplicates(entries):
    """
    Remove duplicate episodes using GUID/link/title fallback.
    """

    unique_entries = []
    seen = set()
    duplicate_count = 0

    for entry in entries:
        guid = get_guid(entry)

        if not guid:
            continue

        if guid in seen:
            duplicate_count += 1
            continue

        seen.add(guid)
        unique_entries.append(entry)

    return unique_entries, duplicate_count


# =============================================================================
# BUILD RSS FEED
# =============================================================================

def build_feed():
    """
    Fetch, merge, clean, sort, and write the network RSS feed.
    """

    (
        all_entries,
        successful_feeds,
        failed_feeds,
    ) = fetch_feeds()

    print("\n" + "=" * 70)
    print("Processing episodes")
    print("=" * 70)

    print(
        f"Total collected episodes: {len(all_entries)}"
    )

    all_entries, duplicate_count = remove_duplicates(
        all_entries
    )

    print(
        f"Duplicate episodes removed: {duplicate_count}"
    )

    # Newest episodes first.
    all_entries.sort(
        key=parse_date,
        reverse=True,
    )

    # Limit total number of episodes.
    all_entries = all_entries[:MAX_EPISODES]

    print(
        f"Episodes included in final feed: {len(all_entries)}"
    )

    print("\nNewest episodes:")

    for entry in all_entries[:5]:
        print(
            f"  {parse_date(entry)} — "
            f"{entry.get('title', 'Untitled')}"
        )

    # -------------------------------------------------------------------------
    # Create FeedGenerator
    # -------------------------------------------------------------------------

    fg = FeedGenerator()

    fg.load_extension("podcast")

    fg.id(NETWORK_LINK)

    fg.title(NETWORK_TITLE)

    fg.link(
        href=NETWORK_LINK
    )

    fg.description(
        NETWORK_DESCRIPTION
    )

    fg.language(
        NETWORK_LANGUAGE
    )

    fg.image(
        url=NETWORK_IMAGE,
        title=NETWORK_TITLE,
        link=NETWORK_LINK,
    )

    fg.author(
        {
            "name": NETWORK_AUTHOR,
            "email": NETWORK_EMAIL,
        }
    )

    # iTunes / Podcast metadata.
    fg.podcast.itunes_author(
        NETWORK_AUTHOR
    )

    fg.podcast.itunes_category(
        "TV & Film",
        cat2="Film Reviews",
    )

    fg.podcast.itunes_explicit(
        NETWORK_EXPLICIT
    )

    fg.podcast.itunes_image(
        NETWORK_IMAGE
    )

    fg.podcast.itunes_owner(
        name=NETWORK_AUTHOR,
        email=NETWORK_EMAIL,
    )

    # -------------------------------------------------------------------------
    # Add episodes
    # -------------------------------------------------------------------------

    # feedgen writes entries in reverse order, so feed oldest-first here.
    for entry in reversed(all_entries):

        title = (
            str(entry.get("title") or "Untitled")
            .strip()
        )

        guid = get_guid(entry)

        if not guid:
            continue

        fe = fg.add_entry()

        fe.id(guid)

        fe.title(title)

        link = (
            entry.get("link")
            or NETWORK_LINK
        )

        fe.link(
            href=link
        )

        fe.pubDate(
            parse_date(entry)
        )

        description = get_description(entry)

        if description:
            fe.description(
                description
            )

        # ---------------------------------------------------------------------
        # Audio enclosure
        # ---------------------------------------------------------------------

        enclosure = get_enclosure(entry)

        if enclosure:
            fe.enclosure(
                url=enclosure["url"],
                length=enclosure["length"],
                type=enclosure["type"],
            )

        # ---------------------------------------------------------------------
        # iTunes duration
        # ---------------------------------------------------------------------

        duration = (
            entry.get("itunes_duration")
            or ""
        )

        if duration:
            fe.podcast.itunes_duration(
                str(duration)
            )

        # ---------------------------------------------------------------------
        # Explicit flag
        # ---------------------------------------------------------------------

        fe.podcast.itunes_explicit(
            get_explicit_value(entry)
        )

        # ---------------------------------------------------------------------
        # Episode artwork
        # ---------------------------------------------------------------------

        episode_image = get_episode_image(
            entry
        )

        try:
            fe.podcast.itunes_image(
                episode_image
                or NETWORK_IMAGE
            )

        except ValueError:
            fe.podcast.itunes_image(
                NETWORK_IMAGE
            )

        # ---------------------------------------------------------------------
        # Episode type
        # ---------------------------------------------------------------------

        episode_type = (
            entry.get("itunes_episodetype")
            or "full"
        )

        fe.podcast.itunes_episode_type(
            str(episode_type)
        )

        # ---------------------------------------------------------------------
        # Author / show name
        # ---------------------------------------------------------------------

        show_title = entry.get(
            "_show_title"
        )

        author = get_episode_author(
            entry,
            show_title,
        )

        fe.podcast.itunes_author(
            author
        )

        # ---------------------------------------------------------------------
        # Episode number
        # ---------------------------------------------------------------------

        episode_number = (
            entry.get("itunes_episode")
        )

        if episode_number:
            fe.podcast.itunes_episode(
                str(episode_number)
            )

        # ---------------------------------------------------------------------
        # Season number
        # ---------------------------------------------------------------------

        season_number = (
            entry.get("itunes_season")
        )

        if season_number:
            fe.podcast.itunes_season(
                str(season_number)
            )

    # -------------------------------------------------------------------------
    # Write feed
    # -------------------------------------------------------------------------

    output_directory = os.path.dirname(
        OUTPUT_PATH
    )

    if output_directory:
        os.makedirs(
            output_directory,
            exist_ok=True,
        )

    fg.rss_file(
        OUTPUT_PATH,
        pretty=True,
    )

    # -------------------------------------------------------------------------
    # Final report
    # -------------------------------------------------------------------------

    print("\n" + "=" * 70)
    print("BUILD COMPLETE")
    print("=" * 70)

    print(
        f"Feeds configured: {len(FEEDS)}"
    )

    print(
        f"Feeds processed successfully: "
        f"{successful_feeds}"
    )

    print(
        f"Feed failures: {len(failed_feeds)}"
    )

    print(
        f"Final episodes: {len(all_entries)}"
    )

    print(
        f"Duplicates removed: {duplicate_count}"
    )

    print(
        f"Output file: {OUTPUT_PATH}"
    )

    print(
        f"Live feed: {NETWORK_FEED_URL}"
    )

    if failed_feeds:
        print("\nFailed feeds:")

        for url in failed_feeds:
            print(f"  - {url}")

    print("=" * 70)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    build_feed()