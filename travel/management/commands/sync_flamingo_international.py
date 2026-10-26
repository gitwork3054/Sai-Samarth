import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from travel import models as m


BASE = "https://www.flamingotravels.co.in"
ROOT = BASE + "/international-tour-packages"
SITEMAP = BASE + "/sitemap_in/sitemap.xml"
DEST_RE = re.compile(r"^/international-tour-packages/[^/?#]+-holiday-tour-packages/?$")
DETAIL_RE = re.compile(r"^/international-tour-packages/[^/]+-holiday-tour-packages/[^/]+/[a-z]\d+/?$", re.I)
DURATION_RE = re.compile(r"(\d+)\s*Nights?\s*/\s*(\d+)\s*Days?", re.I)
PRICE_RE = re.compile(r"₹\s*([\d,]+)")

# Flamingo renders much of its destination menu client-side, so crawl
# destination landing pages directly rather than relying only on root-page links.
DESTINATION_PAGES = {
    "Taiwan": "/international-tour-packages/taiwan-holiday-tour-packages",
    "Vietnam": "/international-tour-packages/vietnam-holiday-tour-packages",
    "China": "/international-tour-packages/china-holiday-tour-packages",
    "Hong Kong": "/international-tour-packages/hong-kong-holiday-tour-packages",
    "Japan": "/international-tour-packages/japan-holiday-tour-packages",
    "Macau": "/international-tour-packages/macau-holiday-tour-packages",
    "Philippines": "/international-tour-packages/philippines-holiday-tour-packages",
    "Bali": "/international-tour-packages/bali-holiday-tour-packages",
    "South Korea": "/international-tour-packages/south-korea-holiday-tour-packages",
    "Maldives": "/international-tour-packages/maldives-holiday-tour-packages",
    "Sri Lanka": "/international-tour-packages/sri-lanka-holiday-tour-packages",
    "Singapore": "/international-tour-packages/singapore-holiday-tour-packages",
    "Malaysia": "/international-tour-packages/malaysia-holiday-tour-packages",
    "Thailand": "/international-tour-packages/thailand-holiday-tour-packages",
    "Finland": "/international-tour-packages/finland-holiday-tour-packages",
    "France": "/international-tour-packages/france-holiday-tour-packages",
    "Germany": "/international-tour-packages/germany-holiday-tour-packages",
    "Iceland": "/international-tour-packages/iceland-holiday-tour-packages",
    "Italy": "/international-tour-packages/italy-holiday-tour-packages",
    "Norway": "/international-tour-packages/norway-holiday-tour-packages",
    "Portugal": "/international-tour-packages/portugal-holiday-tour-packages",
    "Spain": "/international-tour-packages/spain-holiday-tour-packages",
    "Switzerland": "/international-tour-packages/switzerland-holiday-tour-packages",
    "Netherlands": "/international-tour-packages/netherlands-holiday-tour-packages",
    "Ireland": "/international-tour-packages/ireland-holiday-tour-packages",
    "Austria": "/international-tour-packages/austria-holiday-tour-packages",
    "Croatia": "/international-tour-packages/croatia-holiday-tour-packages",
    "Czech Republic": "/international-tour-packages/czech-republic-holiday-tour-packages",
    "Greece": "/international-tour-packages/greece-holiday-tour-packages",
    "Hungary": "/international-tour-packages/hungary-holiday-tour-packages",
    "Poland": "/international-tour-packages/poland-holiday-tour-packages",
    "Russia": "/international-tour-packages/russia-holiday-tour-packages",
    "Turkey": "/international-tour-packages/turkey-holiday-tour-packages",
    "Kazakhstan": "/international-tour-packages/kazakhstan-holiday-tour-packages",
    "Georgia": "/international-tour-packages/georgia-holiday-tour-packages",
    "Armenia": "/international-tour-packages/armenia-holiday-tour-packages",
    "Israel - Jordan": "/international-tour-packages/israel-jordan-holiday-tour-packages",
    "Oman Muscat": "/international-tour-packages/oman-holiday-tour-packages",
    "Dubai": "/international-tour-packages/dubai-holiday-tour-packages",
    "Baku - Azerbaijan": "/international-tour-packages/azerbaijan-holiday-tour-packages",
    "Uzbekistan": "/international-tour-packages/uzbekistan-holiday-tour-packages",
    "Saudi Arabia": "/international-tour-packages/saudi-arabia-holiday-tour-packages",
    "Central America": "/international-tour-packages/central-america-holiday-tour-packages",
    "USA": "/international-tour-packages/usa-holiday-tour-packages",
    "Canada": "/international-tour-packages/canada-holiday-tour-packages",
    "Alaska": "/international-tour-packages/alaska-holiday-tour-packages",
    "South America": "/international-tour-packages/south-america-holiday-tour-packages",
    "Mexico": "/international-tour-packages/mexico-holiday-tour-packages",
    "Hawaii": "/international-tour-packages/hawaii-holiday-tour-packages",
    "Australia": "/international-tour-packages/australia-holiday-tour-packages",
    "New Zealand": "/international-tour-packages/new-zealand-holiday-tour-packages",
    "Australia - New Zealand": "/international-tour-packages/australia-newzealand-tour-packages",
    "Botswana": "/international-tour-packages/botswana-holiday-tour-packages",
    "Egypt": "/international-tour-packages/egypt-holiday-tour-packages",
    "Mauritius": "/international-tour-packages/mauritius-holiday-tour-packages",
    "Seychelles": "/international-tour-packages/seychelles-holiday-tour-packages",
    "Zambia": "/international-tour-packages/zambia-holiday-tour-packages",
    "Zimbabwe": "/international-tour-packages/zimbabwe-holiday-tour-packages",
    "South Africa": "/international-tour-packages/south-africa-holiday-tour-packages",
    "Kenya": "/international-tour-packages/kenya-holiday-tour-packages",
    "Tanzania": "/international-tour-packages/tanzania-holiday-tour-packages",
    "Uganda": "/international-tour-packages/uganda-holiday-tour-packages",
    "Morocco": "/international-tour-packages/morocco-holiday-tour-packages",
    "Madagascar": "/international-tour-packages/madagascar-holiday-tour-packages",
}


def sitemap_urls(session, url, timeout, depth=0):
    """Return URL entries from Flamingo's sitemap / sitemap indexes."""
    if depth > 3:
        return []
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception:
        return []

    tag = root.tag.rsplit("}", 1)[-1]
    locs = [
        (node.text or "").strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "loc" and (node.text or "").strip()
    ]
    if tag == "sitemapindex":
        out = []
        for child in locs:
            out.extend(sitemap_urls(session, child, timeout, depth + 1))
        return out
    return locs

def clean(text):
    return " ".join((text or "").split()).strip()


def absolute(url):
    return urljoin(BASE, url or "")


def country_from_path(path):
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return "International"
    slug = parts[1].replace("-holiday-tour-packages", "")
    return " ".join(word.capitalize() for word in slug.split("-"))


def package_from_card(anchor, page_country):
    href = anchor.get("href") or ""
    url = absolute(href)
    title = ""
    duration = ""
    nights = 0
    days = 0
    price = 0
    image = ""
    tour_type = "individual"

    node = anchor
    card = None
    for _ in range(7):
        node = getattr(node, "parent", None)
        if not node:
            break
        text = clean(node.get_text(" ", strip=True))
        if len(text) >= 20 and ("View Details" in text or DURATION_RE.search(text) or PRICE_RE.search(text)):
            card = node
            break

    scope = card or anchor.parent or anchor

    for heading in scope.find_all(["h1", "h2", "h3", "h4", "h5"]):
        candidate = clean(heading.get_text(" ", strip=True))
        if candidate and candidate.lower() not in {"view details", "call now"}:
            title = candidate
            break

    if not title:
        candidate = clean(anchor.get_text(" ", strip=True))
        if candidate and candidate.lower() not in {"view details", "call now"}:
            title = candidate

    text = clean(scope.get_text(" ", strip=True))
    dm = DURATION_RE.search(text)
    if dm:
        nights = int(dm.group(1))
        days = int(dm.group(2))
        duration = f"{nights} Nights / {days} Days"

    pm = PRICE_RE.search(text)
    if pm:
        price = int(pm.group(1).replace(",", ""))

    if "Group Tour" in text:
        tour_type = "group"

    img = scope.find("img")
    if img:
        image = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or img.get("data-lazy")
            or img.get("src")
            or ""
        )
        image = absolute(image)

    if not title:
        slug = [p for p in urlparse(url).path.split("/") if p][-2]
        title = " ".join(word.capitalize() for word in slug.split("-"))

    title = re.sub(r"\\s*\\d+\\s*nights?.*$", "", title, flags=re.I).strip()
    title = re.sub(r"\\s*\\d+\\s*days?.*$", "", title, flags=re.I).strip()

    return {
        "url": url,
        "title": clean(title),
        "country": country_from_path(urlparse(url).path) if page_country == "International" else (page_country or country_from_path(urlparse(url).path)),
        "duration": duration,
        "nights": nights,
        "days": days,
        "price": price,
        "image": image,
        "tour_type": tour_type,
    }


class Command(BaseCommand):
    help = "Replace local international demo packages with Flamingo's live international catalogue."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=25)
        parser.add_argument("--max-destinations", type=int, default=0, help="0 = all destination pages")

    def handle(self, *args, **opts):
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; SaiSamarthHolidays/1.0; +https://sai-samarth-holidays.onrender.com)"
        })
        timeout = opts["timeout"]

        try:
            root = session.get(ROOT, timeout=timeout)
            root.raise_for_status()
        except Exception as exc:
            raise CommandError(f"Could not load Flamingo international catalogue: {exc}")

        soup = BeautifulSoup(root.text, "html.parser")
        destination_links = {}

        # Flamingo publishes the complete catalogue in its official sitemap.
        # This is much more reliable than the client-rendered navigation menu.
        indexed_urls = sitemap_urls(session, SITEMAP, timeout)
        for indexed in indexed_urls:
            path = urlparse(indexed).path
            if DEST_RE.match(path):
                destination_links[indexed] = country_from_path(path)

        # Keep destination URLs visible in server-rendered HTML as a fallback.
        for a in soup.find_all("a", href=True):
            full = absolute(a["href"])
            path = urlparse(full).path
            if DEST_RE.match(path):
                destination_links.setdefault(
                    full,
                    clean(a.get_text(" ", strip=True)) or country_from_path(path),
                )

        # Use verified Flamingo destination routes; never guess slugs.
        for name, path in DESTINATION_PAGES.items():
            destination_links.setdefault(absolute(path), name)

        pages = list(destination_links.items())
        if opts["max_destinations"]:
            pages = pages[: opts["max_destinations"]]

        packages = {}
        for page_url, page_country in pages:
            try:
                response = session.get(page_url, timeout=timeout)
                response.raise_for_status()
            except Exception as exc:
                self.stderr.write(f"Skipping unavailable Flamingo destination {page_country}: {page_url} ({exc})")
                continue

            page = BeautifulSoup(response.text, "html.parser")
            for a in page.find_all("a", href=True):
                path = urlparse(absolute(a["href"])).path
                if not DETAIL_RE.match(path):
                    continue
                data = package_from_card(a, page_country)
                current = packages.get(data["url"])
                if not current or len(data["title"]) > len(current["title"]):
                    packages[data["url"]] = data

        # Some Flamingo listing pages lazy-load cards. Add any package URLs
        # present in the official sitemap even when the card was not rendered in HTML.
        indexed_detail_urls = [
            u for u in indexed_urls
            if DETAIL_RE.match(urlparse(u).path)
        ]
        for url in indexed_detail_urls:
            if url in packages:
                continue
            path = urlparse(url).path
            country = country_from_path(path)
            slug = [p for p in path.split("/") if p][-2]
            title = " ".join(word.capitalize() for word in slug.split("-"))
            title = re.sub(r"\\s*\\d+\\s*nights?.*$", "", title, flags=re.I).strip()
            title = re.sub(r"\\s*\\d+\\s*days?.*$", "", title, flags=re.I).strip()
            packages[url] = {
                "url": url,
                "title": title,
                "country": country,
                "duration": "",
                "nights": 0,
                "days": 0,
                "price": 0,
                "image": "",
                "tour_type": "group" if urlparse(url).path.rstrip("/").split("/")[-1].lower().startswith("g") else "individual",
            }

        if len(packages) < 20:
            raise CommandError(
                f"Only {len(packages)} Flamingo packages were discovered; refusing to replace the catalogue with an incomplete sync."
            )

        ordered = sorted(packages.values(), key=lambda p: (p["country"], p["title"]))

        with transaction.atomic():
            # Keep historical rows/enquiries safe, but remove all old demo international packages from public view.
            m.Package.objects.filter(destination__region="international").update(is_active=False)

            for order, data in enumerate(ordered, start=1):
                country = data["country"][:80] or "International"
                dest, _ = m.Destination.objects.get_or_create(
                    name=country,
                    defaults={
                        "region": "international",
                        "state_or_country": country,
                        "tagline": f"{country} holidays from Flamingo Travels",
                    },
                )
                if dest.region != "international" or dest.state_or_country != country:
                    dest.region = "international"
                    dest.state_or_country = country
                    dest.save(update_fields=["region", "state_or_country"])

                pkg = m.Package.objects.filter(source_url=data["url"]).first()
                if not pkg:
                    pkg = m.Package.objects.filter(
                        destination=dest,
                        title=data["title"],
                        source_details__provider="flamingo",
                    ).first()
                if not pkg:
                    pkg = m.Package(
                        destination=dest,
                        title=data["title"],
                        short_description=f"{data['title']} by Flamingo Travels.",
                        base_price=data["price"] or 0,
                    )

                pkg.destination = dest
                pkg.title = data["title"][:160]
                pkg.tour_type = data["tour_type"]
                pkg.days = data["days"] or max(pkg.days or 1, 1)
                pkg.nights = data["nights"] or max((pkg.days or 1) - 1, 0)
                pkg.short_description = f"{data['title']} by Flamingo Travels."[:240]
                pkg.overview = ""
                pkg.base_price = data["price"] or 0
                pkg.child_price = 0
                pkg.infant_price = 0
                pkg.price_on_request = not bool(data["price"])
                pkg.discount_percent = 0
                pkg.cover_url = data["image"]
                pkg.source_url = data["url"]
                pkg.source_details = {
                    "provider": "flamingo",
                    "duration": data["duration"],
                    "country": country,
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }
                pkg.display_order = order
                pkg.is_featured = order <= 12
                pkg.is_active = True
                pkg.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(ordered)} Flamingo international packages from the official sitemap/catalogue. "
                "Titles and View trip links now match Flamingo."
            )
        )
