"""Read-only card catalogue from Flamingo's public destination pages."""
import json
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

BASE = "https://www.flamingotravels.co.in/"
IMAGE_BASE = "https://imgcdn.flamingotravels.co.in/"
CATALOG_PATH = Path(__file__).with_name("data") / "flamingo_cards.json"


class NextDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def parse_cards(html):
    parser = NextDataParser()
    parser.feed(html)
    props = json.loads("".join(parser.parts))["props"]["pageProps"]
    rows = props.get("packageCount")
    if not isinstance(rows, list):
        rows = [row for group in props.get("Details", {}).values()
                if isinstance(group, list) for row in group]
    cards = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = urljoin(BASE, str(row.get("pageSlug") or ""))
        parsed = urlparse(url)
        title = str(row.get("name") or "").strip()
        if (not title or parsed.scheme != "https" or parsed.netloc != "www.flamingotravels.co.in"
                or not re.fullmatch(r"/international-tour-packages/[^/]+/[^/]+/[a-z]\d+/?", parsed.path, re.I)):
            continue
        if url in cards:
            continue
        image = urljoin(IMAGE_BASE, quote(str(row.get("imageNamePath") or ""), safe="/:%"))
        if urlparse(image).netloc != "imgcdn.flamingotravels.co.in" or image == IMAGE_BASE:
            image = ""
        duration = str(row.get("totalDays") or "")
        match = re.search(r"(\d+)\s*Days?", duration, re.I)
        try:
            price = int(Decimal(str(row.get("sellingPrice") or 0)))
        except (InvalidOperation, ValueError, OverflowError):
            price = 0
        if str(row.get("isSellingPricePublish")) != "1" or unescape(str(row.get("currencySymbol") or "")) != "₹":
            price = 0
        cards[url] = {
            "title": title, "url": url, "image": image, "duration": duration,
            "days": int(match.group(1)) if match else 0, "price": max(price, 0),
            "code": str(row.get("bI_Code") or ""),
            "style": "group" if "group" in str(row.get("typeOfTour") or "").lower() else "individual",
            "style_label": str(row.get("typeOfTour") or ""),
            "cities": str(row.get("cities") or "").strip(),
            "flight": str(row.get("flightIncluded") or ""),
        }
    return list(cards.values())


@lru_cache(maxsize=1)
def load_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
