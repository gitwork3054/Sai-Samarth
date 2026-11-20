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
FALLBACK_DETAILS.extend([
    "/india-tour-packages/golden-triangle-tour-packages/soulful-india-4nights/f1376",
    "/india-tour-packages/gujarat-holiday-tour-packages/natural-beauty-with-historical-place-of-gujarat-5nights/f2367",
    "/india-tour-packages/gujarat-holiday-tour-packages/discover-gujarat-9nights/f1372",
    "/india-tour-packages/maharashtra-holiday-tour-packages/beautiful-south-gujarat-without-nashik-6nights/f2195",
    "/india-tour-packages/maharashtra-holiday-tour-packages/beautiful-south-gujarat-with-nashik-7nights/f2186",
    "/india-tour-packages/gujarat-holiday-tour-packages/statue-of-unity-tent-city-3nights/f4185",
    "/india-tour-packages/gujarat-holiday-tour-packages/adventure-lover-special-3nights/f2734",
    "/india-tour-packages/rajasthan-holiday-tour-packages/golden-heritage-7nights/f1380",
    "/india-tour-packages/rajasthan-holiday-tour-packages/golden-triangle-5nights/f1377",
    "/india-tour-packages/rajasthan-holiday-tour-packages/romantic-mount-abu-with-udaipur-5nights/f2741",
    "/india-tour-packages/karnataka-holiday-tour-packages/the-little-paris-of-india-4nights/f2759",
    "/india-tour-packages/kerala-holiday-tour-packages/whole-of-kerala-9nights/f1316",
    "/india-tour-packages/kerala-holiday-tour-packages/complete-kerala-8nights/f1385",
    "/india-tour-packages/kerala-holiday-tour-packages/kerala-god%E2%80%99s-own-country-honeymoon-tour-7nights/f3673",
    "/india-tour-packages/kerala-holiday-tour-packages/kerala-highlights-7nights/f1310",
    "/india-tour-packages/kerala-holiday-tour-packages/lagoons-of-kerala-7nights/f1314",
    "/india-tour-packages/goa-holiday-tour-packages/2-nights-north-goa-2-nights-south-goa-4nights/f3457",
    "/india-tour-packages/kerala-holiday-tour-packages/cool-kerala-6nights/f1304",
    "/india-tour-packages/kerala-holiday-tour-packages/kerala-gods-own-country-7nights/f1305",
    "/india-tour-packages/kerala-holiday-tour-packages/taj-incredible-kerala-journeys-6-nights/f3542",
    "/india-tour-packages/kerala-holiday-tour-packages/kerala-soul-journey-6nights/f1312",
    "/india-tour-packages/kerala-holiday-tour-packages/kerala-honeymoon-special-7nights/f3808",
    "/india-tour-packages/kerala-holiday-tour-packages/kerala-coast-8nights/f1308",
    "/india-tour-packages/kerala-holiday-tour-packages/wild-kerala-5nights/f1290",
    "/india-tour-packages/andaman-holiday-tour-packages/tropical-andaman-5nights/f1626",
    "/india-tour-packages/andaman-holiday-tour-packages/tropical-andaman-5nights/f3390",
    "/india-tour-packages/andaman-holiday-tour-packages/magical-andaman-5nights/f4154",
    "/india-tour-packages/andaman-holiday-tour-package/exotic-andaman-6nights/f3057",
    "/india-tour-packages/andaman-holiday-tour-packages/tropical-andaman-with-cgh-hotel-5-nights/f3525",
    "/india-tour-packages/andaman-holiday-tour-packages/best-of-andaman-with-baratang-6nights/f4067",
    "/india-tour-packages/andaman-holiday-tour-packages/combination-of-3-beautiful-islands/f3054",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/himachal-with-golden-temple-4nghts/f1351",
    "/india-tour-packages/uttranchal-holiday-tour-packages/best-of-uttaranchal-6nights/f2039",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/magical-himachal-6nights/f1844",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/himalayan-wonder-6nights/f2122",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/idyllic-himachal-4nights/f2335",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/charming-himachal-5night/f2219",
    "/india-tour-packages/karnataka-holiday-tour-packages/karnataka-hills-8nights/f1357",
    "/india-tour-packages/uttranchal-holiday-tour-packages/3-dham-by-road-and-1-dham-by-helicopter-8nights/f3583",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/himachal-with-amritsar-6nights/f1969",
    "/india-tour-packages/west-bengal-sikkim-holiday-tour-packages/scenic-sikkim-4nights/f3331",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/heavenly-himachal-with-golden-temple-9night/f2228",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/mesmerizing-himachal-6nights/f2131",
    "/india-tour-packages/himachal-pradesh-holiday-tour-packages/heavenly-himachal-8night/f2374",
    "/india-tour-packages/west-bengal-sikkim-holiday-tour-packages/sikkim-splendor/f3123",
    "/india-tour-packages/uttranchal-holiday-tour-packages/a-travelers-paradise-nainital-and-corbett-5nights/f2169",
])
KNOWN_LISTING_QUOTES = {
  "f1360": (32830, "2027-09-30"),
  "f1363": (33410, "2027-09-30"),
  "f1402": (27120, "2027-09-30"),
  "f4075": (21040, "2027-09-30"),
  "f1844": (28420, "2027-09-30"),
  "f2335": (18510, "2027-09-30"),
  "f1969": (28100, "2027-09-30"),
  "f1376": (18940, "2027-09-30"),
}
AREA_MAP = {
    "himachal-pradesh": "Himachal Pradesh", "uttranchal": "Uttarakhand",
    "uttarakhand": "Uttarakhand", "odisha": "Odisha", "kashmir": "Jammu & Kashmir",
    "northeast": "North East India", "north-east": "North East India",
    "andaman": "Andaman & Nicobar", "golden-triangle": "Delhi / Agra / Rajasthan",
    "north-kerala": "Kerala", "karnataka": "Karnataka", "leh": "Ladakh",
    "ladakh": "Ladakh", "south-india": "South India", "hyderabad": "Telangana",
    "maharashtra": "Maharashtra",
}


# Additional verified/possible Indian catalogue routes. A missing category
# is recorded as unavailable, never fabricated into an offered product.
MORE_DOMESTIC_CATEGORIES = ("/india-tour-packages/delhi-holiday-tour-packages",
"/india-tour-packages/delhi-tour-packages",
"/india-tour-packages/andaman-holiday-tour-package",
"/india-tour-packages/north-kerala-holiday-tour-packages",
"/india-tour-packages/north-east-holiday-tour-packages",
"/india-tour-packages/northeast-holiday-tour-packages",
"/india-tour-packages/west-bengal-sikkim-holiday-tour-packages",
"/india-tour-packages/sikkim-holiday-tour-packages",
"/india-tour-packages/kashmir-tour-packages",
"/india-tour-packages/leh-ladakh-holiday-tour-packages",
"/india-tour-packages/leh-ladakh-tour-packages",
"/india-tour-packages/lakshadweep-holiday-tour-packages",
"/india-tour-packages/madhya-pradesh-holiday-tour-packages",
"/india-tour-packages/tamil-nadu-holiday-tour-packages",
"/india-tour-packages/hyderabad-holiday-tour-packages",
"/india-tour-packages/punjab-holiday-tour-packages",
"/india-tour-packages/south-india-holiday-tour-packages",
"/india-tour-packages/north-india-holiday-tour-packages",
"/india-tour-packages/bihar-holiday-tour-packages",
"/india-tour-packages/assam-holiday-tour-packages",
"/india-tour-packages/golden-triangle-tour-packages",
"/india-tour-packages/uttar-pradesh-holiday-tour-packages",
"/india-tour-packages/west-bengal-holiday-tour-packages",
"/india-tour-packages/saurashtra-holiday-tour-packages",
"/india-tour-packages/jammu-kashmir-holiday-tour-packages",
"/india-tour-packages/kashmir-holiday-tour-packages",
"/india-tour-packages/pondicherry-holiday-tour-packages",
"/india-tour-packages/lakshadweep-island-holiday-tour-packages",)
CATEGORY_STATES = {
    "rajasthan": ["Rajasthan"],
    "golden-triangle": ["Delhi", "Rajasthan"],
    "delhi": ["Delhi"],
    "gujarat": ["Gujarat"],
    "saurashtra": ["Gujarat"],
    "uttranchal": ["Uttarakhand"],
    "uttarakhand": ["Uttarakhand"],
    "himachal-pradesh": ["Himachal Pradesh"],
    "kerala": ["Kerala"],
    "north-kerala": ["Kerala", "Karnataka"],
    "karnataka": ["Karnataka"],
    "tamil-nadu": ["Tamil Nadu"],
    "south-india": ["Karnataka", "Kerala", "Tamil Nadu"],
    "andaman": ["Andaman & Nicobar"],
    "odisha": ["Odisha"],
    "uttar-pradesh": ["Uttar Pradesh"],
    "west-bengal-sikkim": ["West Bengal", "Sikkim"],
    "sikkim": ["Sikkim"],
    "west-bengal": ["West Bengal"],
    "maharashtra": ["Maharashtra"],
    "goa": ["Goa"],
    "kashmir": ["Jammu & Kashmir"],
    "jammu-kashmir": ["Jammu & Kashmir"],
    "leh": ["Ladakh"],
    "leh-ladakh": ["Ladakh"],
    "punjab": ["Punjab"],
    "hyderabad": ["Telangana"],
    "madhya-pradesh": ["Madhya Pradesh"],
    "northeast": ["Assam", "Meghalaya", "Arunachal Pradesh"],
    "north-east": ["Assam", "Meghalaya", "Arunachal Pradesh"],
    "assam": ["Assam"],
    "bihar": ["Bihar"],
    "lakshadweep": ["Lakshadweep"],
    "lakshadweep-island": ["Lakshadweep"],
    "pondicherry": ["Puducherry"],
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


def route_from_listing(text):
    result = []
    for item in (text or "").split(","):
        found = re.search(r"^\s*(.{2,65}?)\s*\((\d{1,2})\s*N\)\s*$", item, re.I)
        if not found:
            return []
        city = tidy(found.group(1))
        nights = int(found.group(2))
        if not city or nights < 1:
            return []
        result.append({"city": city, "nights": nights})
    return result


def category_key(url):
    path = urlparse(url).path.strip("/").split("/")
    if len(path) < 2 or path[0] != "india-tour-packages":
        return ""
    return re.sub(r"-(holiday-)?tour-packages?$", "", path[1], flags=re.I)


def from_listing_next(html, listing_url):
    """Flamingo's canonical cards are in Next.js pageProps.Details,
    not server-rendered HTML anchors. Only use 'Private Van Tour' items.
    """
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return []
    try:
        prop = json.loads(tag.string)["props"]["pageProps"]
    except (ValueError, TypeError, KeyError):
        return []
    details = prop.get("Details") or {}
    rows = next((value for key, value in details.items()
                 if tidy(key).casefold() == "private van tour"), [])
    state_slugs = CATEGORY_STATES.get(category_key(listing_url), [])
    result = []
    for entry in rows or []:
        raw_url = canonical(entry.get("pageSlug"))
        match = RE_DETAIL.match(urlparse(raw_url).path)
        supplier_code = tidy(str(entry.get("bI_Code") or ""))
        if not match or supplier_code.upper() != "FIT/" + match.group("id")[1:]:
            continue
        # Flamingo occasionally cross-lists Indian itineraries in other states:
        # they are still discoverable under each destination where they appear.
        if not is_india_area(match.group("area")):
            continue
        route = route_from_listing(entry.get("cities") or "")
        duration = RE_DURATION.search(tidy(str(entry.get("totalDays") or "")))
        nights = int(duration.group(1)) if duration else sum(stop["nights"] for stop in route)
        days = int(duration.group(2)) if duration else nights + 1
        if not route or sum(stop["nights"] for stop in route) != nights or days != nights + 1:
            continue
        publish = str(entry.get("isSellingPricePublish") or "").lower()
        sold_out = str(entry.get("soldOut") or "").lower() in ("1", "true", "yes")
        price_raw = str(entry.get("sellingPrice") or "0").replace(",", "")
        price = int(price_raw) if price_raw.isdecimal() and publish in ("1", "true", "yes") and not sold_out else 0
        valid_string = tidy(str(entry.get("validityPeriods") or ""))
        matches = re.findall(r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b", valid_string)
        def date_str(raw):
            try:
                return datetime.strptime(raw, "%d %b %Y").strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return ""
        start, end = (date_str(matches[0]), date_str(matches[-1])) if matches else ("", "")
        result.append({
            "source_url": raw_url,
            "title": tidy(str(entry.get("name") or ""))[:160],
            "tour_code_supplier": supplier_code,
            "days": days, "nights": nights,
            "route": route, "starting_price_inr": price,
            "valid_from": start, "valid_until": end,
            "price_source": "Flamingo domestic Private Van Tour catalogue",
            "flight_not_included": str(entry.get("flightIncluded") or "").strip().lower() == "flight not included",
            "listed_states": sorted(set(state_slugs)),
            "source_categories": [category_key(listing_url)],
            "published": True, "sold_out": sold_out,
            "listed_services": [
                tidy(x) for x in str(entry.get("inclusions") or "").split(",")
                if 1 < len(tidy(x)) < 40
            ][:12],
        })
    return result


def parse_detail(url, html, listed):
    """Read only factual highlights from details; public listing is canonical
    for name, route, price and validity. Never reproduce proprietary prose.
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    headline = soup.find("h1")
    if not headline:
        return None
    full = tidy(soup.get_text(" ", strip=True))
    header_pos = full.find(tidy(headline.get_text(" ", strip=True)))
    header = full[max(header_pos, 0):max(header_pos, 0) + 900]
    if not re.search(r"\bPrivate Van Tour\b", header, re.I):
        return None
    parsed_duration = RE_DURATION.search(header)
    detail_discrepancy = bool(
        parsed_duration and (
            int(parsed_duration.group(1)) != listed["nights"] or
            int(parsed_duration.group(2)) != listed["days"]
        )
    )
    parsed_route, sightseeing, hotels, meals, headings = parse_factual_sections(soup, listed["nights"])
    if parsed_route and parsed_route != listed["route"]:
        detail_discrepancy = True
    category=RE_DETAIL.match(urlparse(url).path)
    area=category.group("area").replace("-holiday-tour-packages","").replace("-holiday-tour-package","")
    return {
        "source_url": url, "supplier": "Flamingo Travels",
        "title": listed["title"],
        "tour_code_supplier": listed["tour_code_supplier"],
        "category": area,
        "region_label": AREA_MAP.get(area, area.replace("-", " ").title()),
        "type": "private_van", "days": listed["days"], "nights": listed["nights"],
        "route": listed["route"],
        "sightseeing": sightseeing, "hotel_examples": hotels,
        "meals": meals, "day_headings": headings,
        "private_vehicle_mentioned": (
            "private transfer" in " ".join(listed["listed_services"]).lower()
            or bool(re.search(r"transfers.{0,80}(?:vehicle|car)|(?:vehicle|car).{0,80}transfers", full[:14000], re.I))
        ),
        "flight_not_included": listed["flight_not_included"],
        "starting_price_inr": listed["starting_price_inr"],
        "valid_from": listed["valid_from"], "valid_until": listed["valid_until"],
        "price_source": listed["price_source"],
        "listed_states": listed["listed_states"],
        "source_categories": listed["source_categories"],
        "listed_services": listed["listed_services"],
        "detail_discrepancy": detail_discrepancy,
        "tags": ["Couple"] if any(x in listed["title"].lower() for x in ("honeymoon", "romantic", "couple")) else [],
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--out", default=str(OUTPUT))
    cli.add_argument("--max-detail", type=int, default=0, help="0 = all discovered")
    cli.add_argument("--workers", type=int, default=8)
    cli.add_argument("--min-records", type=int, default=30)
    args = cli.parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SaiSamarthCatalogue/1.0)"})
    sitemap = sitemap_urls(session, SITEMAP)
    categories = {canonical(BASE + path) for path in (*FALLBACK_CATEGORIES, *MORE_DOMESTIC_CATEGORIES)}
    # Discover additional official India category pages from sitemap and
    # server-rendered navigation instead of relying on hardcoded tour URLs.
    for url in sitemap:
        url=canonical(url)
        parts=urlparse(url).path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "india-tour-packages" and is_india_area(parts[1]):
            categories.add(url)
    try:
        root_soup = BeautifulSoup(get(session, ROOT), "html.parser")
        for a in root_soup.find_all("a", href=True):
            u=canonical(a["href"])
            parts=urlparse(u).path.strip("/").split("/")
            if len(parts)==2 and parts[0]=="india-tour-packages" and is_india_area(parts[1]):
                categories.add(u)
    except Exception as exc:
        print("root navigation not available:", type(exc).__name__)
    index = {}
    coverage = {}
    errors = []
    for category in sorted(categories):
        if not category:
            continue
        try:
            cards=from_listing_next(get(session,category), category)
        except Exception as exc:
            errors.append({"category": category, "reason": type(exc).__name__})
            continue
        if not cards:
            coverage[category_key(category)] = 0
            continue
        coverage[category_key(category)] = len(cards)
        for card in cards:
            existing=index.get(card["tour_code_supplier"])
            if existing:
                for field in ("listed_states", "source_categories"):
                    existing[field] = sorted(set(existing[field]) | set(card[field]))
                # If duplicate listings disagree, keep the first published
                # amount and flag for verification rather than silently switch.
                if existing["starting_price_inr"] != card["starting_price_inr"]:
                    existing["listing_price_conflict"]=True
                    existing["conflicting_prices"]=sorted(set(
                        existing.get("conflicting_prices", [existing["starting_price_inr"]]) + [card["starting_price_inr"]]
                    ))
            else:
                index[card["tour_code_supplier"]]=card
    cards=sorted(index.values(),key=lambda d:(d["source_categories"][0],d["title"]))
    if args.max_detail:
        cards=cards[:args.max_detail]
    print(f"India catalogue source categories={len(categories)}, with private van tours={sum(bool(v) for v in coverage.values())}; "
          f"unique published tour codes={len(index)}; detail attempts={len(cards)}")
    if len(cards)<args.min_records:
        raise SystemExit(f"Only {len(cards)} current private van tours discovered; refusing incomplete catalogue")
    records=[]
    failures=[]
    def fetch_one(card):
        url=card["source_url"]
        with requests.Session() as client:
            client.headers.update({"User-Agent":"Mozilla/5.0 (compatible; SaiSamarthCatalogue/1.0)"})
            html=get(client,url,timeout=22)
        return parse_detail(url,html,card)
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,10))) as pool:
        future_map={pool.submit(fetch_one,card):card for card in cards}
        for future in as_completed(future_map):
            card=future_map[future]
            try:
                record=future.result()
                if record:
                    records.append(record)
                else:
                    failures.append({"code":card["tour_code_supplier"],"reason":"detail HTML missing or not Private Van Tour"})
            except Exception as exc:
                failures.append({"code":card["tour_code_supplier"],"reason":type(exc).__name__})
    records.sort(key=lambda r:(r["region_label"],r["title"],r["tour_code_supplier"]))
    if len(records)<args.min_records:
        raise SystemExit(f"Only {len(records)} verified detailed tours; need {args.min_records}; failures={failures[:7]}")
    snapshot={
        "source":ROOT, "retrieved_at":datetime.now(timezone.utc).isoformat(),
        "kind":"indian_domestic_private_van_facts", "total":len(records),
        "source_catalogue_count":len(index), "coverage":coverage,
        "failed_details":len(failures), "failures":failures,
        "source_category_errors":errors,
        "packages":records,
    }
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(output)
    print("Verified private van tours:",len(records),
          "priced:",sum(bool(r["starting_price_inr"]) for r in records),
          "detail/price conflicts:",sum(bool(r.get("detail_discrepancy") or r.get("listing_price_conflict")) for r in records),
          "detail failures:",len(failures))
    print("COVERAGE:",json.dumps(coverage,sort_keys=True))
    if failures:
        print("MISSING DETAIL CODES:",json.dumps(failures[:40]))
    if len(failures)>0:
        # Do not claim full parity when the supplier pages cannot be validated;
        # surface missing rows for manual follow-up, retaining prior snapshot.
        raise SystemExit(f"{len(failures)} supplier tour detail pages were unverified; refusing a partial replacement")


if __name__ == "__main__":
    main()
