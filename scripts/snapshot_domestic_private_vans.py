#!/usr/bin/env python3
"""Collect factual domestic private-vehicle itinerary data from public supplier pages.

Only stores package facts (name, source URL, dates, pricing, city-night sequence,
attraction names, meal counts, hotel-name options and short DAY HEADINGS).
Do NOT archive or reproduce supplier marketing prose or full itinerary paragraphs.
Run this snapshot builder in CI, not on the live website's startup path.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

BASE = "https://www.flamingotravels.co.in"
ROOT = BASE + "/india-tour-packages"
SITEMAP = BASE + "/sitemap_in/sitemap.xml"
OUTPUT = Path(__file__).resolve().parents[1] / "travel/data/flamingo_domestic_private_vans.json"
RE_DETAIL = re.compile(r"^/india-tour-packages/(?P<area>[^/]+)/(?P<slug>[^/]+)/(?P<id>f\d+)/?$", re.I)
RE_CATEGORY = re.compile(r"^/india-tour-packages/[^/]+-holiday-tour-packages/?$", re.I)
RE_DURATION = re.compile(r"(\d{1,2})\s*Nights?\s*/\s*(\d{1,2})\s*Days?", re.I)
RE_PRICE = re.compile(r"₹\s*([\d,]+)")
RE_VALID = re.compile(r"Valid\s+up\s*to\s+(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", re.I)
RE_CITY = re.compile(r"([^,]{2,65}?)\s*\(\s*(\d{1,2})\s*N\s*\)")
RE_DAY = re.compile(r"^Day\s*(\d{1,2})\s*[:\-–]\s*(.{2,105})$", re.I)
SKIP_AREAS = {"bhutan", "nepal", "maldives", "sri-lanka", "dubai", "thailand", "singapore"}
# Deliberately only these India destination categories: no international countries
INDIA_TERMS = (
    "goa", "rajasthan", "gujarat", "leh", "ladakh", "himachal", "uttranchal",
    "uttarakhand", "sikkim", "kashmir", "andaman", "maharashtra", "karnataka",
    "golden-triangle", "odisha", "northeast", "north-east", "madhya-pradesh",
    "hyderabad", "north-kerala", "uttar-pradesh", "kerala", "lakshadweep",
    "tamil-nadu", "south-india", "punjab", "assam", "west-bengal",
    "telangana", "bihar", "chhattisgarh",
)
FALLBACK_CATEGORIES = [
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages",
    "/india-tour-packages/uttranchal-holiday-tour-packages",
    "/india-tour-packages/rajasthan-holiday-tour-packages",
    "/india-tour-packages/gujarat-holiday-tour-packages",
    "/india-tour-packages/odisha-holiday-tour-packages",
    "/india-tour-packages/kerala-holiday-tour-packages",
    "/india-tour-packages/karnataka-holiday-tour-packages",
    "/india-tour-packages/maharashtra-holiday-tour-packages",
    "/india-tour-packages/kashmir-holiday-tour-packages",
    "/india-tour-packages/northeast-holiday-tour-packages",
    "/india-tour-packages/uttar-pradesh-holiday-tour-packages",
    "/india-tour-packages/andaman-holiday-tour-packages",
    "/india-tour-packages/goa-holiday-tour-packages",
]
FALLBACK_DETAILS = [
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/scenic-himachal-7nights/f1360",
    "/india-tour-packages/rajasthan-holiday-tour-packages/the-golden-rajasthan-5nights/f1402",
    "/india-tour-packages/odisha-holiday-tour-packages/glorious-odisha-tour-5nights/f4075",
    "/india-tour-packages/uttranchal-holiday-tour-packages/uniquely-uttaranchal-7nights/f1363",
    "/india-tour-packages/gujarat-holiday-tour-packages/discover-gujarat-7nights/f1644",
    "/india-tour-packages/gujarat-holiday-tour-packages/sacred-saurashtra-6nights/f1374",
    "/india-tour-packages/gujarat-holiday-tour-packages/complete-kutch-6nights/f1370",
    "/india-tour-packages/kerala-holiday-tour-packages/experience-the-natures-magic-vagamon-2nights/f2153",
]
AREA_MAP = {
    "himachal-pradesh": "Himachal Pradesh", "uttranchal": "Uttarakhand",
    "uttarakhand": "Uttarakhand", "odisha": "Odisha", "kashmir": "Jammu & Kashmir",
    "northeast": "North East India", "north-east": "North East India",
    "andaman": "Andaman & Nicobar", "golden-triangle": "Delhi / Agra / Rajasthan",
    "north-kerala": "Kerala", "karnataka": "Karnataka", "leh": "Ladakh",
    "ladakh": "Ladakh", "south-india": "South India", "hyderabad": "Telangana",
    "maharashtra": "Maharashtra",
}

def tidy(value):
    return re.sub(r"\s+", " ", value or "").strip()

def canonical(raw):
    absolute = urljoin(BASE, raw or "").split("?")[0].rstrip("/")
    parsed = urlparse(absolute)
    if parsed.hostname not in ("www.flamingotravels.co.in", "flamingotravels.co.in"):
        return ""
    return BASE + parsed.path.rstrip("/")

def is_india_area(area):
    key = area.replace("-holiday-tour-packages", "").lower()
    return key not in SKIP_AREAS and any(term in key for term in INDIA_TERMS)

def get(session, url, timeout=18):
    res = session.get(url, timeout=timeout)
    res.raise_for_status()
    return res.text

def sitemap_urls(session, url, depth=0, max_depth=2):
    if depth > max_depth:
        return []
    try:
        root = ElementTree.fromstring(get(session, url, timeout=23))
    except Exception as exc:
        print("sitemap not readable:", url, type(exc).__name__)
        return []
    entries = [tidy(node.text) for node in root.iter()
               if node.tag.rsplit("}", 1)[-1] == "loc" and tidy(node.text)]
    if root.tag.rsplit("}", 1)[-1] != "sitemapindex":
        return entries
    result = []
    for item in entries:
        if "sitemap" in item:
            result.extend(sitemap_urls(session, item, depth + 1, max_depth))
    return result

def listing_facts(soup):
    """Optional starting price from *listing*, which may not appear on detail."""
    found = {}
    for a in soup.find_all("a", href=True):
        link = canonical(a.get("href", ""))
        if not RE_DETAIL.match(urlparse(link).path):
            continue
        node = a
        card_text = ""
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            text = tidy(node.get_text(" ", strip=True))
            # Smallest card with a recognized style, duration and price.
            if "Private Van Tour" in text and RE_DURATION.search(text) and len(text) < 1800:
                card_text = text
                break
        if not card_text:
            continue
        value = RE_PRICE.search(card_text)
        if not value:
            continue
        valid = RE_VALID.search(card_text)
        found[link] = {
            "starting_price_inr": int(value.group(1).replace(",", "")),
            "valid_until": (f"{valid.group(3)}-{datetime.strptime(valid.group(2)[:3].title(), '%b').month:02d}-{int(valid.group(1)):02d}" if valid else ""),
            "price_source": "supplier catalogue listing",
        }
    return found

def text_lines(soup):
    return [tidy(x) for x in soup.get_text("\n", strip=True).split("\n") if tidy(x)]

def get_route(text, nights):
    marker = re.search(r"\bCities\s*:\s*", text, re.I)
    if not marker:
        return []
    segment = text[marker.end():marker.end() + 650]
    result, total = [], 0
    for m in RE_CITY.finditer(segment):
        city = tidy(m.group(1)).split("  ")[-1]
        # On scripts/menus, only a tightly-bounded city/name can be accepted.
        if len(city) > 50 or len(city) < 2:
            continue
        city = city.lstrip(" ,:")
        night_count = int(m.group(2))
        result.append({"city": city, "nights": night_count})
        total += night_count
        if nights and total >= nights:
            break
    return result if result and (not nights or total == nights) else []

def parse_factual_sections(soup, nights):
    lines = text_lines(soup)
    joined = tidy(soup.get_text(" ", strip=True))
    route = get_route(joined, nights)
    stops = []
    hotels = []
    if route:
        begin = next((i for i, line in enumerate(lines) if re.search(r"\bCities\s*:", line)), 0)
        zone = lines[begin + 1:begin + 130]
        # Scope to the initial overview, not duplicate gallery caption lists.
        for j, value in enumerate(zone):
            if j > 3 and value in ("Gallery", "Videos", "Videos and Guides", "Optionals", "Tour Information", "Day wise travel itinerary"):
                zone = zone[:j]
                break
        found_sightseeing = False
        current_city = ""
        for line in zone:
            if line in ("Sightseeing", "Sight Seeing"):
                found_sightseeing = True
                current_city = ""
                continue
            if line in ("Flight and transport", "Meals", "Gallery", "Hotels", "Hotel Included", "Tour Information"):
                found_sightseeing = False
            hotel = re.search(r"(\d+)\s*Night\(s\)\s*in\s+(.+?)\s+at\s+(.+?)\s+or similar", line, re.I)
            if hotel and len(hotels) < 15:
                hotels.append({"city": tidy(hotel.group(2))[:80], "nights": int(hotel.group(1)),
                               "example": tidy(hotel.group(3))[:160]})
            if not found_sightseeing:
                continue
            if re.fullmatch(r"[A-Za-z0-9 /&,\-().]{2,60},\s*India", line):
                current_city = line.rsplit(",", 1)[0].strip()
                continue
            if current_city and 3 <= len(line) <= 95 and not line.startswith(("Image:", "Tour Code", "Click", "View")):
                if not re.search(r"\d+\s*(Breakfast|Dinner|Lunch)|nights?\s*/|price", line, re.I):
                    item = {"city": current_city, "name": line}
                    if item not in stops and len(stops) < 80:
                        stops.append(item)
    meals = {}
    for meal in ("Breakfast", "Lunch", "Dinner"):
        match = re.search(r"\b(\d{1,2})\s+" + meal + r"\b", joined[:15000], re.I)
        if match:
            meals[meal.lower()] = int(match.group(1))
    itinerary_titles = {}
    start = next((i for i, ln in enumerate(lines) if ln.lower() == "day wise travel itinerary"), -1)
    if start >= 0:
        for line in lines[start + 1:start + 200]:
            if line in ("Tour Information", "Important Notes", "Cancellation Policy"):
                break
            m = RE_DAY.match(line)
            if m and int(m.group(1)) not in itinerary_titles:
                itinerary_titles[int(m.group(1))] = tidy(m.group(2))[:95]
    return route, stops, hotels, meals, itinerary_titles

def parse_detail(url, html, listed):
    soup = BeautifulSoup(html, "html.parser")
    headline = soup.find("h1")
    if not headline:
        return None
    name = tidy(headline.get_text(" ", strip=True))[:160]
    full = tidy(soup.get_text(" ", strip=True))
    near_title = full.find(name)
    if near_title < 0:
        return None
    header = full[near_title:near_title + 700]
    # Prevent accidentally importing group or fixed-departure entries.
    if not re.search(r"\bPrivate Van Tour\b", header, re.I):
        return None
    duration = RE_DURATION.search(header)
    if not duration:
        return None
    nights, days = int(duration.group(1)), int(duration.group(2))
    if not (1 <= nights <= 24 and days == nights + 1):
        return None
    code = re.search(r"FIT\s*/\s*(\d+)", header, re.I)
    category = RE_DETAIL.match(urlparse(url).path)
    if not category or not is_india_area(category.group("area")):
        return None
    route, sightseeing, hotels, meals, day_headings = parse_factual_sections(soup, nights)
    # Only publish source-grounded routes; skip misleading guessed itineraries.
    if not route:
        return None
    nearby = full[near_title:near_title+12000].lower()
    transfers = bool(re.search(r"transfers.{0,80}(?:vehicle|car)|(?:vehicle|car).{0,80}transfers", nearby))
    return {
        "source_url": url, "supplier": "Flamingo Travels",
        "title": name, "tour_code_supplier": f"FIT/{code.group(1)}" if code else "FIT/" + category.group("id")[1:],
        "category": category.group("area").replace("-holiday-tour-packages", ""),
        "region_label": AREA_MAP.get(category.group("area").replace("-holiday-tour-packages", ""), category.group("area").replace("-holiday-tour-packages", "").replace("-", " ").title()),
        "type": "private_van", "days": days, "nights": nights,
        "route": route, "sightseeing": sightseeing, "hotel_examples": hotels,
        "meals": meals, "day_headings": day_headings,
        "private_vehicle_mentioned": transfers,
        "flight_not_included": bool(listed.get("flight_not_included", True)),
        "starting_price_inr": int(listed.get("starting_price_inr") or 0),
        "valid_until": listed.get("valid_until", ""),
        "price_source": listed.get("price_source", ""),
        "tags": [tag for tag in ("Family Tour", "Honeymoon", "Couple", "Romantic")
                 if tag.lower() in header.lower()],
    }

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--out", default=str(OUTPUT))
    cli.add_argument("--max-detail", type=int, default=0, help="0 = all discovered")
    cli.add_argument("--workers", type=int, default=6)
    cli.add_argument("--min-records", type=int, default=12)
    args = cli.parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SaiSamarthCatalogue/1.0)"})
    sources = sitemap_urls(session, SITEMAP)
    print("Official sitemap entries:", len(sources))
    categories = {canonical(BASE+p) for p in FALLBACK_CATEGORIES}
    detail_urls = {canonical(BASE+p) for p in FALLBACK_DETAILS}
    for url in sources:
        url = canonical(url)
        m = RE_DETAIL.match(urlparse(url).path)
        if m and is_india_area(m.group("area")):
            detail_urls.add(url)
        elif RE_CATEGORY.match(urlparse(url).path):
            cat = urlparse(url).path.rsplit("/", 1)[-1].replace("-holiday-tour-packages", "")
            if is_india_area(cat):
                categories.add(url)
    prices = {}
    for category in sorted(categories | {ROOT}):
        try:
            soup = BeautifulSoup(get(session, category), "html.parser")
            prices.update(listing_facts(soup))
            for a in soup.find_all("a", href=True):
                url = canonical(a["href"])
                m = RE_DETAIL.match(urlparse(url).path)
                if m and is_india_area(m.group("area")):
                    detail_urls.add(url)
        except Exception as exc:
            print("Listing unavailable:", category, type(exc).__name__)
    urls = sorted(filter(None, detail_urls))
    if args.max_detail:
        urls = urls[:args.max_detail]
    print("Domestic detail candidates:", len(urls), "priced listings:", len(prices))
    records = []
    failed = 0
    def fetch_one(url):
        # One isolated Session per worker to avoid cross-thread connection state.
        with requests.Session() as client:
            client.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SaiSamarthCatalogue/1.0)"})
            return parse_detail(url, get(client, url), prices.get(url, {}))
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        futures = {pool.submit(fetch_one, url): url for url in urls}
        for f in as_completed(futures):
            try:
                record = f.result()
                if record:
                    records.append(record)
            except Exception as exc:
                failed += 1
    records = sorted({p["tour_code_supplier"]: p for p in records}.values(),
                     key=lambda r: (r["region_label"], r["title"], r["tour_code_supplier"]))
    if len(records) < args.min_records:
        raise SystemExit(f"Refusing incomplete snapshot: {len(records)} records, {failed} errors; need {args.min_records}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {"source": ROOT, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "kind": "indian_domestic_private_van_facts", "total": len(records),
                "failed_details": failed, "packages": records}
    tmp = output.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output)
    print(f"Collected {len(records)} verified Indian private-van tours into {output}")

if __name__ == "__main__":
    main()
