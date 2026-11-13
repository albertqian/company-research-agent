"""Free company news from the Google News RSS feed (no API key).

Claude only ranks these headlines, so news costs a fraction of a cent.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

import config

TIMEOUT = 10


def fetch_news(company: str) -> list[dict]:
    """Return headlines from the last NEWS_WINDOW_DAYS, newest first. Empty list on failure."""
    query = quote(f'"{company}" when:{config.NEWS_WINDOW_DAYS}d')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError):
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=config.NEWS_WINDOW_DAYS)
    items = []
    for it in root.iter("item"):
        try:
            published = parsedate_to_datetime(it.findtext("pubDate", ""))
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published < cutoff:
            continue
        items.append({
            "headline": it.findtext("title", ""),
            "url": it.findtext("link", ""),
            "source": it.findtext("source", ""),
            "date": published.date().isoformat(),
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[: config.NEWS_HEADLINES_TO_RANK]
