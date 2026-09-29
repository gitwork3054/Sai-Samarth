"""Fill demo package covers, galleries and sightseeing with Commons photos.

Run after generate_demo: python manage.py add_photos
The command is resumable and leaves photos uploaded in the admin untouched.
"""

import html
import hashlib
import ipaddress
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.html import strip_tags
from django.utils.text import slugify

from travel.curated_photos import SOURCES
from travel.models import Destination, PackageImage


API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "SaiSamarthHolidays/1.0 (travel photo attribution; contact: photo-credits page)"
UNWANTED = {"map", "flag", "logo", "poster", "illustration", "drawing", "painting", "coat of arms"}
REQUEST_INTERVAL = 2.5
_last_request = 0.0


class RateLimited(Exception):
    """Stop the import as soon as Wikimedia asks us to slow down."""


def safe_image_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return "." in host


def reusable_license(meta):
    license_name = meta.get("License", {}).get("value", "").lower()
    return (license_name == "cc0" or bool(re.fullmatch(r"cc-by(?:-sa)?-\d+(?:\.\d+)?", license_name))
            or license_name.startswith("pd-"))


def open_wikimedia(request, timeout, interval=REQUEST_INTERVAL):
    global _last_request
    pause = interval - (time.monotonic() - _last_request)
    if pause > 0:
        time.sleep(pause)
    _last_request = time.monotonic()
    try:
        return urlopen(request, timeout=timeout)
    except HTTPError as error:
        if error.code == 429:
            raise RateLimited from error
        raise


def curated_photo(source):
    """Build direct CDN links from a reviewed Commons file page, without API calls."""
    path = unquote(urlparse(source).path)
    if urlparse(source).hostname != "commons.wikimedia.org" or "/File:" not in path:
        raise ValueError("Invalid Commons file page")
    filename = path.split("/File:", 1)[1].replace(" ", "_")
    digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
    base = f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{quote(filename, safe='')}"
    thumb = base.replace("/commons/", "/commons/thumb/", 1) + "/960px-" + quote(filename, safe="")
    return {"url": thumb, "fallback_url": base, "source": source,
            "author": "See photographer on source page", "license": "See license on source page",
            "license_url": source, "title": filename.replace("_", " "), "curated": True}


def api_search(query):
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": "12",
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": "1200",
    }
    request = Request(API + "?" + urlencode(params), headers={"User-Agent": USER_AGENT})
    with open_wikimedia(request, timeout=25) as response:
        return json.load(response).get("query", {}).get("pages", [])


def wikipedia_photo(title):
    """Use the article's lead photo, then verify its license on Commons."""
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"), safe="")
    try:
        with open_wikimedia(Request(url, headers={"User-Agent": USER_AGENT}), timeout=25) as response:
            article = json.load(response)
    except HTTPError as error:
        if error.code >= 400:
            return None
        raise
    source = article.get("originalimage", {}).get("source", "")
    if urlparse(source).hostname != "upload.wikimedia.org":
        return None
    filename = unquote(urlparse(source).path.rsplit("/", 1)[-1])
    params = {"action": "query", "format": "json", "formatversion": "2", "titles": "File:" + filename,
              "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": "1200"}
    with open_wikimedia(Request(API + "?" + urlencode(params), headers={"User-Agent": USER_AGENT}), timeout=25) as response:
        pages = json.load(response).get("query", {}).get("pages", [])
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        if info.get("mime") == "image/jpeg" and reusable_license(meta) and safe_image_url(info.get("thumburl", "")):
            return photo_data(page, info, meta)
    return None


def photo_data(page, info, meta):
    author = html.unescape(strip_tags(meta.get("Artist", {}).get("value", "Unknown"))).strip()
    author = re.sub(r"\s+", " ", author)[:200]
    return {
        "url": info["thumburl"],
        "source": info.get("descriptionurl") or "https://commons.wikimedia.org/wiki/" + page["title"].replace(" ", "_"),
        "author": author or "Unknown", "license": meta.get("LicenseShortName", {}).get("value", meta["License"]["value"]),
        "license_url": meta.get("LicenseUrl", {}).get("value", ""),
        "title": page["title"],
    }


def choose_photo(query, terms, article_titles=()):
    for title in dict.fromkeys(article_titles):
        photo = wikipedia_photo(title)
        if photo:
            return photo
    words = [w for w in re.findall(r"[a-z0-9]+", terms.lower()) if len(w) > 2]
    choices = []
    for page in api_search(query):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        license_name = meta.get("License", {}).get("value", "").lower()
        title = page.get("title", "")
        name = title.lower()
        if (info.get("mime") != "image/jpeg" or not reusable_license(meta)
                or not info.get("thumburl")
                or not safe_image_url(info["thumburl"])
                or not info.get("width") or not info.get("height")
                or info["width"] < 1000 or info["height"] < 650
                or any(word in name for word in UNWANTED)):
            continue
        score = sum(3 for word in words if word in name)
        score += min(info["width"] / info["height"], 3)
        score -= page.get("index", 20) / 100  # Commons search relevance breaks ties
        choices.append((score, page, info, meta))
    if choices:
        _, page, info, meta = max(choices, key=lambda item: item[0])
        return photo_data(page, info, meta)
    return None


def save_photo(photo, relative, credits):
    """Download a small image under MEDIA_ROOT, then record its attribution."""
    path = Path(settings.MEDIA_ROOT) / relative
    if not path.exists():
        data = None
        for url in (photo["url"], photo.get("fallback_url")):
            if not url:
                continue
            if not safe_image_url(url):
                raise ValueError("Unexpected image URL")
            request = Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with open_wikimedia(request, timeout=45, interval=0.9 if photo.get("curated") else REQUEST_INTERVAL) as response:
                    if not safe_image_url(response.geturl()):
                        raise ValueError("Unexpected redirected image URL")
                    if not response.headers.get("Content-Type", "").lower().startswith("image/jpeg"):
                        raise ValueError("Unexpected image type")
                    data = response.read(8_000_001)
                break
            except HTTPError as error:
                if error.code != 404 or not photo.get("fallback_url") or url == photo["fallback_url"]:
                    raise
        if not data or len(data) > 8_000_000 or not data.startswith(b"\xff\xd8"):
            raise ValueError("Image exceeds limit or is not JPEG")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    credits[relative] = {key: photo[key] for key in ("source", "author", "license", "license_url", "title")}
    return relative


class Command(BaseCommand):
    help = "Download destination and sightseeing photos for existing demo packages"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Process only this many destinations")
        parser.add_argument("--links-only", action="store_true", help="Put curated cover links on all package cards immediately, without downloading")
        parser.add_argument("--covers-only", action="store_true", help="Get package card photos first; run again without this option for galleries and sightseeing")
        parser.add_argument("--search-new", action="store_true", help="Search Commons for owner-created places without a curated photo")

    def handle(self, *args, **options):
        credit_file = Path(settings.MEDIA_ROOT) / "photo-credits.json"
        credits = json.loads(credit_file.read_text(encoding="utf-8")) if credit_file.exists() else {}
        destinations = Destination.objects.filter(packages__isnull=False).distinct().order_by("name")
        if options["limit"]:
            destinations = destinations[:options["limit"]]
        for destination in destinations:
            packages = list(destination.packages.prefetch_related("sightseeing", "gallery"))
            if options["links_only"]:
                source = SOURCES.get(f"{destination.name}|")
                if source:
                    photo = curated_photo(source)
                    link = photo["url"]
                    credits[f"remote/{slugify(destination.name)}"] = {
                        key: photo[key] for key in ("source", "author", "license", "license_url", "title")}
                    for package in packages:
                        if not package.cover_image and not package.cover_url:
                            package.cover_url = link
                            package.save(update_fields=["cover_url"])
                self.stdout.write(f"{destination.name}: cover link set for {len(packages)} packages")
                continue
            prefix = slugify(destination.name)
            place = destination.state_or_country or destination.name
            spots = list(packages[0].sightseeing.all())
            photos = []
            queries = [(destination.name, f"{destination.name} {place}", f"travel/destinations/{prefix}.jpg")]
            if not options["covers_only"]:
                queries += [(spot.name, f"{spot.name} {destination.name}", f"travel/sightseeing/{prefix}-{slugify(spot.name)}.jpg") for spot in spots]
            for label, query, relative in queries:
                path = Path(settings.MEDIA_ROOT) / relative
                if path.exists() and relative in credits:
                    photo_path = relative
                else:
                    try:
                        source = SOURCES.get(f"{destination.name}|{'' if label == destination.name else label}")
                        if not source and not options["search_new"]:
                            source = SOURCES.get(f"{destination.name}|")  # regional photo for rare sights
                        if source:
                            photo = curated_photo(source)
                        elif options["search_new"]:
                            article_titles = (destination.name, place, spots[0].name) if label == destination.name and spots else (label,)
                            photo = choose_photo(query, label, article_titles)
                        else:
                            self.stderr.write(f"No curated photo: {destination.name} / {label}")
                            continue
                        if not photo:
                            self.stderr.write(f"No suitable photo: {destination.name} / {label}")
                            continue
                        photo_path = save_photo(photo, relative, credits)
                        credit_file.parent.mkdir(parents=True, exist_ok=True)
                        credit_file.write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
                    except RateLimited:
                        raise CommandError("Wikimedia returned HTTP 429. Saved photos are safe. Wait 15–30 minutes, then rerun this command to resume.")
                    except (OSError, ValueError, KeyError, TimeoutError) as error:
                        self.stderr.write(f"Photo unavailable: {destination.name} / {label}: {error}")
                        continue
                photos.append((label, photo_path))
            cover_path = next((path for label, path in photos if label == destination.name), "")
            if cover_path and not destination.image:
                destination.image = cover_path
                destination.save(update_fields=["image"])
            spot_images = {label: path for label, path in photos if label != destination.name}
            for package in packages:
                curated_cover = SOURCES.get(f"{destination.name}|")
                is_curated_link = (curated_cover and package.cover_url == curated_photo(curated_cover)["url"])
                if not package.cover_image and (not package.cover_url or is_curated_link) and cover_path:
                    package.cover_image = cover_path
                    package.save(update_fields=["cover_image"])
                for sightseeing in package.sightseeing.all():
                    if not sightseeing.image and sightseeing.name in spot_images:
                        sightseeing.image = spot_images[sightseeing.name]
                        sightseeing.save(update_fields=["image"])
                existing = {image.image.name for image in package.gallery.all()}
                for order, (caption, image_path) in enumerate(photos[:6]):
                    if image_path not in existing:
                        PackageImage.objects.create(package=package, image=image_path, caption=caption, order=order)
                        existing.add(image_path)
            credit_file.parent.mkdir(parents=True, exist_ok=True)
            credit_file.write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
            self.stdout.write(f"{destination.name}: {len(photos)} photos for {len(packages)} packages")
        if options["links_only"]:
            credit_file.parent.mkdir(parents=True, exist_ok=True)
            credit_file.write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS("Photo import finished. See /photo-credits/ for sources."))
