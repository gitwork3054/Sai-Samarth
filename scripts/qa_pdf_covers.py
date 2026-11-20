"""Check the cinematic text/photo overlay on six real destination covers.

Renders PDF pages with the same installed fonts and licensed destination image
library used in production. Produces a reviewable, compressed montage.
"""
import io
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

import fitz
from PIL import Image, ImageDraw
from travel import models as m
from travel.cinematic_pdf import build_cinematic_pdf, matched_photo

SAMPLES = [
    ("Jaipur", "Rajasthan", "Jaipur Royal Escape"),
    ("Shimla", "Himachal Pradesh", "Shimla Corporate Getaway"),
    ("Srinagar", "Jammu & Kashmir", "Kashmir Lakes and Mountains"),
    ("Goa", "Goa", "Goa Beach Escape"),
    ("Munnar", "Kerala", "Kerala Tea Gardens Tour"),
    ("Ayodhya", "Uttar Pradesh", "Spiritual Ayodhya"),
]
site = m.SiteSettings.get()
pictures = []
for city, state, title in SAMPLES:
    destination, _ = m.Destination.objects.get_or_create(
        name=city,
        defaults={"region": "domestic", "state_or_country": state},
    )
    tour = m.Package.objects.create(
        destination=destination, title=title,
        short_description="Private guided holiday with local experiences.",
        overview="An immersive, flexible holiday planned around the destination.",
        days=4, nights=3, base_price=15000,
        inclusions="Stay at selected hotels\nGround transport",
        exclusions="Flights\nPersonal purchases",
    )
    for day in range(1,5):
        m.ItineraryDay.objects.create(
            package=tour, day_number=day,
            title=f"{city} Day {day}",
            description=f"Explore the most memorable attractions and local culture of {city}.",
            stay=city if day<4 else "", meals="Breakfast" if day>1 else "",
        )
    photo, credit = matched_photo(tour)
    assert photo and photo.is_file(), f"No licensed photograph for {city}"
    assert credit and "Wikimedia Commons" in credit, f"No valid photo credit for {city}"
    data = build_cinematic_pdf(tour, site)
    doc=fitz.open(stream=data, filetype="pdf")
    cover=doc[0]
    assert city.upper() in cover.get_text("text").upper(), f"Lost {city} title"
    assert cover.get_images(full=True), f"No photo embedded for {city}"
    pix=cover.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
    image=Image.frombytes("RGB", (pix.width,pix.height), pix.samples)
    pictures.append((image,city))
    print(f"OK {city}: {len(data)} bytes, {len(doc)} pages, {photo.name}",flush=True)
    doc.close()

w,h=pictures[0][0].size
pad=10
montage=Image.new("RGB", ((w+pad)*3+pad, (h+pad)*2+pad), (238,234,232))
for i,(im,label) in enumerate(pictures):
    montage.paste(im, (pad+(i%3)*(w+pad),pad+(i//3)*(h+pad)))
montage.thumbnail((1680,1500),Image.Resampling.LANCZOS)
output=BASE/"docs/illustrated-cover-qa.jpg"
output.parent.mkdir(exist_ok=True)
montage.save(output,quality=81,optimize=True)
print("COVER_MONTAGE",str(output),output.stat().st_size,flush=True)
