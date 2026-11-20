"""Replace Ayodhya PDF cover with a verified scenic Sarayu river image.

The previous government-event photo was excluded at runtime by the approved
licence allowlist. This selects a genuinely destination-specific riverside
photograph that has a verified CC BY-SA 4.0 licence.
"""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import time

import requests
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parents[1]
PHOTO = BASE / "static/img/pdf_destinations/ayodhya.jpg"
INDEX = BASE / "travel/data/pdf_destination_photos.json"
TITLE = "File:Ayodhya city at night.jpg"
PAGE = "https://commons.wikimedia.org/wiki/File:Ayodhya_city_at_night.jpg"
LICENCE = "CC BY-SA 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
AUTHOR = "Mishra12krati"


def download():
    session = requests.Session()
    session.headers["User-Agent"] = "SaiSamarthHolidays/1.0 (tour brochure image with attribution)"
    api = "https://commons.wikimedia.org/w/api.php"
    details = None
    last_error = None
    for attempt in range(4):
        try:
            response = session.get(
                api,
                params={
                    "action": "query", "format": "json", "prop": "imageinfo",
                    "iiprop": "url|extmetadata|size", "titles": TITLE,
                },
                timeout=24,
            )
            response.raise_for_status()
            pages = response.json()["query"]["pages"]
            details = next(iter(pages.values()))["imageinfo"][0]
            break
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            last_error = exc
            time.sleep(min(attempt * 2, 4))
    if details is None:
        raise RuntimeError(f"Unable to verify Wikimedia source: {last_error}")
    meta = details.get("extmetadata") or {}
    listed_licence = (meta.get("LicenseShortName") or {}).get("value", "").upper()
    if "CC BY-SA 4.0" not in listed_licence:
        raise RuntimeError(f"Wrong or missing licence for {TITLE}: {listed_licence}")
    url = details["url"]
    if not url.startswith("https://upload.wikimedia.org/"):
        raise RuntimeError("Image URL is not an original Wikimedia Commons file")
    response = session.get(url, timeout=35)
    response.raise_for_status()
    if not response.headers.get("content-type","").lower().startswith("image/"):
        raise RuntimeError("Source is not an image")
    if len(response.content) > 12_000_000:
        raise RuntimeError("Source image is too large")
    with Image.open(BytesIO(response.content)) as opened:
        if opened.width < 1200 or opened.height < 800:
            raise RuntimeError("Destination photograph is too small")
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        PHOTO.parent.mkdir(parents=True, exist_ok=True)
        image.save(PHOTO, "JPEG", quality=89, optimize=True)
        print("Reviewed Ayodhya cover:", image.size, "image from", PAGE, flush=True)
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    entry = data["photos"]["Ayodhya"]
    entry.update({
        "city": "Ayodhya",
        "file": "static/img/pdf_destinations/ayodhya.jpg",
        "source_url": PAGE,
        "photographer": AUTHOR,
        "license": LICENCE,
        "license_url": LICENCE_URL,
        "wikipedia_page": "https://en.wikipedia.org/wiki/Ayodhya",
        "description": "Illuminated historic Ayodhya city at night",
        "reviewed_filename": "Ayodhya city at night.jpg",
        "cover_review_status": "approved",
        "cover_reviewed_at": datetime.now(timezone.utc).isoformat(),
        "sha256": sha256(PHOTO.read_bytes()).hexdigest(),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    })
    data["approved_cover_count"] = len(data["photos"])
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Photo SHA256:", entry["sha256"], "catalogued licensed covers:", data["approved_cover_count"])


if __name__ == "__main__":
    download()
