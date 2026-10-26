import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from travel import models as m


BASE = "https://www.flamingotravels.co.in"
ROOT = BASE + "/international-tour-packages"
DEST_RE = re.compile(r"^/international-tour-packages/[^/?#]+-holiday-tour-packages/?$")
DETAIL_RE = re.compile(r"^/international-tour-packages/[^/]+-holiday-tour-packages/[^/]+/g\d+/?$")
DURATION_RE = re.compile(r"(\d+)\s*Nights?\s*/\s*(\d+)\s*Days?", re.I)
PRICE_RE = re.compile(r"₹\s*([\d,]+)")

# Flamingo renders much of its destination menu client-side, so crawl
# destination landing pages directly rather than relying only on root-page links.
DESTINATION_SLUGS = [
    "taiwan","vietnam","china","hong-kong","japan","macau","philippines","bali",
    "south-korea","maldives","sri-lanka","singapore","malaysia","thailand",
    "singapore-malaysia","singapore-bali","finland","france","germany","iceland",
    "italy","norway","portugal","spain","switzerland","uk-scotland","netherlands",
    "ireland","scandinavia","austria","all-of-europe","switzerland-paris",
    "croatia","czech-republic","greece","hungary","poland","russia","turkey",
    "greece-turkey","baltic","all-of-east-europe","kazakhstan","georgia","armenia",
    "israel-jordan","oman-muscat","uae-dubai","baku-azerbaijan","uzbekistan",
    "saudi-arabia","central-america","usa-united-states","canada","alaska",
    "south-america","mexico","hawaii","australia","new-zealand","fiji-bora-bora",
    "australia-new-zealand","botswana","egypt","mauritius","seychelles","zambia",
    "zimbabwe","south-africa","kenya","tanzania","uganda","morocco","madagascar",
]


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
        for a in soup.find_all("a", href=True):
            path = urlparse(absolute(a["href"])).path
            if DEST_RE.match(path):
                name = clean(a.get_text(" ", strip=True)) or country_from_path(path)
                destination_links[absolute(path)] = name

        for slug in DESTINATION_SLUGS:
            path = f"/international-tour-packages/{slug}-holiday-tour-packages"
            destination_links.setdefault(
                absolute(path),
                " ".join(word.capitalize() for word in slug.replace("uae-dubai", "dubai").split("-")),
            )

        pages = [(ROOT, "International")]
        items = list(destination_links.items())
        if opts["max_destinations"]:
            items = items[: opts["max_destinations"]]
        pages.extend(items)

        packages = {}
        for page_url, page_country in pages:
            try:
                response = session.get(page_url, timeout=timeout)
                response.raise_for_status()
            except Exception as exc:
                self.stderr.write(f"Skipping {page_url}: {exc}")
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

        if len(packages) < 5:
            raise CommandError(
                f"Only {len(packages)} Flamingo packages were discovered; existing international catalogue was left unchanged."
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
                f"Synced {len(ordered)} Flamingo international packages. "
                "Titles and View trip links now match Flamingo."
            )
        )
