"""Destination-specific cinematic itinerary brochures for Sai Samarth Holidays.

Uses the selected tour's actual route, day plan, price, hotel options, inclusions,
exclusions and conditions. Never substitutes unrelated destination photography.
"""
import hashlib
import html
import io
import re
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from PIL import Image as PILImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from .curated_photos import SOURCES, photo_url
from .pdf import _fonts, _logo

W, H = 450, 675
LEFT, RIGHT = 27, 423
CARD_W = RIGHT - LEFT
INK = colors.HexColor("#1A1A30")
TOP = colors.HexColor("#29253F")
CARD = colors.HexColor("#303047")
WHITE = colors.HexColor("#FFF9F2")
MUTED = colors.HexColor("#C2BBCD")
ORANGE = colors.HexColor("#F28B5D")
LINE = colors.HexColor("#4D485E")
TRUSTED = {"upload.wikimedia.org", "akhilbharat.in"}
HOME = "https://www.saisamarthholidays.com/"


def txt(value):
    return str(value or "").strip()


def inr(value):
    n = int(value or 0)
    t = str(abs(n))
    a, b = t[:-3], t[-3:]
    result = ""
    while len(a) > 2:
        result = "," + a[-2:] + result
        a = a[:-2]
    return ("-" if n < 0 else "") + "₹" + (a + result + "," if len(t) > 3 else "") + b


def safe_local(field):
    if not field:
        return None
    try:
        path = Path(field.path)
        if path.is_file():
            return path
    except (AttributeError, OSError, NotImplementedError, ValueError):
        pass
    return None


def fetch_trusted_photo(url):
    parsed = urlparse(txt(url))
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED:
        return None
    folder = Path(tempfile.gettempdir()) / "sai-samarth-pdf-cache"
    folder.mkdir(exist_ok=True)
    dest = folder / (hashlib.sha256(url.encode()).hexdigest() + ".jpg")
    if dest.is_file() and dest.stat().st_size > 2000:
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SaiSamarth-CataloguePDF/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            if urlparse(response.geturl()).hostname not in TRUSTED:
                return None
            raw = response.read(7 * 1024 * 1024 + 1)
        if len(raw) > 7 * 1024 * 1024:
            return None
        with PILImage.open(io.BytesIO(raw)) as image:
            fixed = ImageOps.exif_transpose(image).convert("RGB")
            fixed.thumbnail((1800, 1800), PILImage.Resampling.LANCZOS)
            fixed.save(dest, "JPEG", quality=88, optimize=True)
        return dest
    except Exception:
        return None


def matched_photo(package):
    """Only the exact package's image or a named city on its actual route."""
    for field in (package.cover_image, package.destination.image):
        image = safe_local(field)
        if image:
            return image, None
    route = (package.source_details or {}).get("route") or []
    places = [package.destination.name]
    places += [x.get("city", "") for x in route if isinstance(x, dict)]
    places += [day.stay for day in package.itinerary.all() if day.stay]
    urls = [package.cover_url] if package.cover_url else []
    seen = set()
    for place in places:
        if not txt(place) or txt(place).casefold() in seen:
            continue
        seen.add(txt(place).casefold())
        specific = photo_url(place)
        if specific:
            urls.append(specific)
    for url in urls[:7]:
        if not url:
            continue
        image = fetch_trusted_photo(url)
        if image:
            credit = next((value for value in SOURCES.values()
                           if Path(urlparse(url).path).name.lower() in value.lower()), None)
            return image, credit or ("Wikimedia Commons" if "wikimedia" in url else None)
    # User-uploaded gallery photos belong to this exact tour.
    for item in package.gallery.all()[:3]:
        image = safe_local(item.image)
        if image:
            return image, None
    return None, None


def text_style(name, size=9, leading=14, color=WHITE, bold=False):
    return ParagraphStyle(name, fontName="TripBold" if bold else "TripRegular",
                          fontSize=size, leading=leading, textColor=color, splitLongWords=True)


class Brochure:
    def __init__(self, package, site):
        _fonts()
        self.p, self.site = package, site
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(W, H), pageCompression=1)
        self.c.setTitle(f"{package.title} | Sai Samarth Holidays")
        self.c.setAuthor(site.brand_name)
        self.photo, self.credit = matched_photo(package)
        self.logo = _logo(site)
        self.page = 0
        self.section = ("YOUR JOURNEY", "Discover your journey", "")
        self.y = 0
        self.body = text_style("body", 8.8, 14)
        self.small = text_style("small", 7.6, 11.4, MUTED)
        self.heading = text_style("heading", 14.8, 19, WHITE, True)
        self.section_title = text_style("section", 24, 29, WHITE, True)
        self.section_subtitle = text_style("intro", 8.8, 14, MUTED)

    def draw_text(self, words, x, top, style, width):
        safe = html.escape(txt(words), quote=False).replace("\n", "<br/>")
        para = Paragraph(safe, style)
        _, height = para.wrap(width, 20000)
        if top is not None:
            para.drawOn(self.c, x, top-height)
        return height

    def logo_box(self):
        c = self.c
        c.setFillColor(WHITE)
        c.roundRect(324, 608, 100, 41, 11, fill=1, stroke=0)
        if self.logo:
            try:
                c.drawImage(self.logo, 333, 612, width=82, height=32,
                            preserveAspectRatio=True, anchor="c", mask="auto")
                return
            except Exception:
                pass
        c.setFillColor(INK)
        c.setFont("TripBold", 10)
        c.drawCentredString(374, 635, "SAI SAMARTH")
        c.setFont("TripRegular", 6)
        c.drawCentredString(374, 623, "HOLIDAYS")

    def arches(self):
        c = self.c
        c.saveState()
        if hasattr(c, "setStrokeAlpha"):
            c.setStrokeAlpha(.09)
        c.setStrokeColor(ORANGE)
        c.setLineWidth(.7)
        for x in range(-24, 525, 68):
            for n in range(5):
                radius = 34-n*5
                p = c.beginPath()
                p.moveTo(x-radius, 466)
                p.lineTo(x-radius, 583)
                p.curveTo(x-radius, 617+n*3, x+radius, 617+n*3, x+radius, 583)
                p.lineTo(x+radius, 466)
                c.drawPath(p)
        c.restoreState()

    def cover(self):
        c = self.c
        self.page = 1
        c.setFillColor(INK)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        if self.photo:
            try:
                with PILImage.open(self.photo) as img:
                    iw, ih = img.size
                ratio = max(W / iw, H / ih)
                cw, ch = iw*ratio, ih*ratio
                c.drawImage(str(self.photo), (W-cw)/2, (H-ch)/2,
                            width=cw, height=ch)
            except Exception:
                pass
        else:
            c.setFillColor(colors.HexColor("#6A3955"))
            c.rect(0, 0, W, H, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#EE8460"))
            c.circle(350, 365, 155, fill=1, stroke=0)
        c.saveState()
        if hasattr(c, "setFillAlpha"):
            c.setFillAlpha(.44)
        c.setFillColor(INK)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        if hasattr(c, "setFillAlpha"):
            c.setFillAlpha(.42)
        c.rect(0, 0, W, 192, fill=1, stroke=0)
        c.restoreState()
        self.arches()
        self.logo_box()
        c.setFillColor(WHITE)
        c.setFont("TripRegular", 11)
        c.drawCentredString(W/2, 562, "EXPLORE WITH SAI SAMARTH")
        place = txt(self.p.destination.state_or_country or self.p.destination.name).upper()
        if len(place) > 25:
            place = txt(self.p.destination.name).upper()
        parts = [place]
        if len(place) > 16:
            terms = place.replace(" / ", " ").split()
            if len(terms) > 1:
                half = max(1, (len(terms)+1)//2)
                parts = [" ".join(terms[:half]), " ".join(terms[half:])]
        for idx, title in enumerate(parts[:2]):
            size = 103 if len(parts)==1 else 78
            while size > 24 and pdfmetrics.stringWidth(title, "TripBold", size) > W-26:
                size -= 1.6
            c.setFont("TripBold", size)
            c.drawCentredString(W/2, 380 - idx*82, title)
        c.setStrokeColor(ORANGE)
        c.setLineWidth(2)
        c.line(LEFT, 176, LEFT+47, 176)
        self.draw_text(self.p.title, LEFT, 164, text_style("cover-name", 18, 22, WHITE, True), CARD_W)
        c.setFillColor(WHITE)
        c.setFont("TripRegular", 8)
        c.drawString(LEFT, 77, txt(self.p.duration_label).upper())
        code = (self.p.source_details or {}).get("original_code") or self.p.tour_code or ""
        c.setFont("TripBold", 8)
        c.drawRightString(RIGHT, 77, code)
        c.setStrokeColor(MUTED)
        c.line(LEFT, 62, RIGHT, 62)
        c.setFont("TripRegular", 8)
        c.drawString(LEFT, 42, "YOUR DESTINATION. YOUR STORY.")
        c.drawRightString(RIGHT, 42, "SAI SAMARTH HOLIDAYS")
        c.showPage()

    def begin_page(self, kicker, headline, subtitle, continuation=False):
        if self.page >= 2:
            self.c.showPage()
        self.page += 1
        if not continuation:
            self.section = (kicker, headline, subtitle)
        c = self.c
        c.setFillColor(INK)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(TOP)
        c.rect(0, 465, W, 210, fill=1, stroke=0)
        self.arches()
        self.logo_box()
        c.setFillColor(ORANGE)
        c.setFont("TripBold", 8.5)
        c.drawString(LEFT, 629, (kicker+" / CONTINUED" if continuation else kicker).upper())
        self.draw_text(headline, LEFT, 599, self.section_title, CARD_W)
        self.draw_text(subtitle, LEFT, 536, self.section_subtitle, CARD_W)
        c.setStrokeColor(LINE)
        c.line(LEFT, 35, RIGHT, 35)
        c.setFillColor(MUTED)
        c.setFont("TripRegular", 7)
        c.drawString(LEFT, 21, "SAI SAMARTH HOLIDAYS  /  ITINERARY")
        c.setFillColor(ORANGE)
        c.setFont("TripBold", 7)
        c.drawRightString(RIGHT, 21, f"{self.page:02d}")
        self.y = 448

    def next_page(self):
        self.begin_page(*self.section, continuation=True)

    def card_height(self, headline, body, subtitle="", footnote=""):
        inside = CARD_W-36
        title_h = self.draw_text(headline, 0, None, self.heading, inside)
        body_h = self.draw_text(body or "Details confirmed when booking.", 0, None, self.body, inside)
        sub_h = self.draw_text(subtitle, 0, None, self.small, inside) if subtitle else 0
        foot_h = self.draw_text(footnote, 0, None, self.small, inside) if footnote else 0
        return 57 + title_h + body_h + (sub_h+6 if subtitle else 0) + (foot_h+10 if footnote else 0)

    def draw_card(self, eyebrow, headline, body, subtitle="", footnote=""):
        h = self.card_height(headline, body, subtitle, footnote)
        if self.y-h < 55:
            self.next_page()
        x, top = LEFT, self.y
        c = self.c
        c.setFillColor(CARD)
        c.roundRect(x, top-h, CARD_W, h, 12, fill=1, stroke=0)
        c.setFillColor(ORANGE)
        c.setFont("TripBold", 8)
        c.drawString(x+17, top-21, eyebrow.upper()[:65])
        cursor = top-30
        cursor -= self.draw_text(headline, x+17, cursor, self.heading, CARD_W-35)+7
        if subtitle:
            cursor -= self.draw_text(subtitle, x+17, cursor, self.small, CARD_W-35)+7
        cursor -= self.draw_text(body or "Details confirmed when booking.",
                                 x+17, cursor, self.body, CARD_W-35)
        if footnote:
            cursor -= 9
            self.draw_text(footnote, x+17, cursor, self.small, CARD_W-35)
        self.y -= h+12

    def card(self, eyebrow, headline, description, subtitle="", footnote=""):
        """Break any long paragraph into continuation cards; never discard text."""
        original = txt(description)
        if self.card_height(headline, original, subtitle, footnote) <= 342:
            self.draw_card(eyebrow, headline, original, subtitle, footnote)
            return
        rest = original.split()
        first = True
        while rest:
            lo, hi, n = 1, len(rest), 1
            while lo <= hi:
                mid = (lo+hi)//2
                label = headline if first else headline+" (continued)"
                if self.card_height(label, " ".join(rest[:mid]),
                                    subtitle if first else "", footnote if mid==len(rest) else "") <= 330:
                    n = mid
                    lo = mid+1
                else:
                    hi = mid-1
            label = headline if first else headline+" (continued)"
            self.draw_card(eyebrow if first else eyebrow+" / MORE", label,
                           " ".join(rest[:n]), subtitle if first else "",
                           footnote if n==len(rest) else "")
            rest = rest[n:]
            first = False

    def items(self, title, lines, per_card=5, empty=None):
        values = [txt(x) for x in lines if txt(x)]
        if not values and empty:
            self.card("TO CONFIRM", title, empty)
        for index in range(0, len(values), per_card):
            self.card(f"{title} / {index+1:02d}", title,
                      "\n".join("• "+item for item in values[index:index+per_card]))

    def price(self):
        if self.p.price_on_request:
            return "PRICE ON REQUEST"
        return "FROM " + inr(self.p.price_from) + " / PERSON"

    def price_notes(self):
        p = self.p
        details = p.source_details or {}
        if details.get("catalogue_kind")=="domestic_private_van":
            parts = []
            if p.base_price:
                parts.append("Published supplier reference: " + inr(p.base_price) + " per person.")
            if details.get("valid_from") and details.get("valid_until"):
                parts.append("Travel validity: "+details["valid_from"]+" to "+details["valid_until"]+".")
            parts.append("Sai Samarth reconfirms the final amount, inclusions and availability in writing.")
            return " ".join(parts)
        parts = ["Indicative starting price, subject to travel dates, availability and confirmed arrangements."]
        if p.savings and not p.price_on_request:
            parts.append(f"Current discount: {p.effective_discount}%.")
        if p.offer_valid_till:
            parts.append("Offer valid until "+str(p.offer_valid_till)+".")
        return " ".join(parts)

    def route(self):
        src = (self.p.source_details or {}).get("route") or []
        if src:
            return [f"{x.get('city')} ({x.get('nights')} nights)" for x in src
                    if isinstance(x, dict) and x.get("city")]
        return [f"{day.stay} - Day {day.day_number}" for day in self.p.itinerary.all() if day.stay] or [self.p.destination.name]

    def render(self):
        p, site = self.p, self.site
        self.cover()
        self.begin_page("YOUR JOURNEY / 01", "Your holiday at a glance",
                        "Your chosen tour, overnight route and indicative package details.")
        self.card("YOUR SELECTED TOUR", p.title, p.overview or p.short_description,
                  subtitle=f"{p.duration_label}  /  {p.get_tour_type_display()}",
                  footnote=(p.source_details or {}).get("original_code") or p.tour_code or "")
        self.card("THE ROUTE", "Where you'll go", "  •  ".join(self.route()),
                  footnote="Overnight locations based on the selected itinerary.")
        self.card("PUBLISHED PACKAGE RATE", self.price(), self.price_notes())
        if p.departure_list:
            self.items("FIXED DEPARTURES", p.departure_list)

        self.begin_page("YOUR JOURNEY / 02", "Day by day",
                        "The journey unfolds from first arrival to final departure.")
        days=list(p.itinerary.all())
        if days:
            for day in days:
                footer="  •  ".join(x for x in (
                    "MEALS: "+day.meals if day.meals else "",
                    "STAY: "+day.stay if day.stay else "") if x)
                self.card(f"DAY {day.day_number:02d}", day.title or f"Day {day.day_number}",
                          day.description, footnote=footer)
        else:
            self.card("TO CONFIRM", "A personal day-wise itinerary",
                      "An exact schedule will be provided after your enquiry. No unverified activities have been added.")

        places=list(p.sightseeing.all())
        if places:
            self.begin_page("DISCOVER MORE", "Sights & experiences",
                            "Locations featured in this package. Entry and visiting times are subject to confirmation.")
            for i, stop in enumerate(places, 1):
                facts="  •  ".join(f"{name}: {value}" for name,value in (
                    ("Hours", stop.visiting_hours), ("Closed", stop.closed_days),
                    ("Tickets", stop.admission), ("Best time", stop.best_time)) if value)
                self.card(f"SIGHTSEEING / {i:02d}", stop.name,
                          stop.description or "Named sightseeing stop on the published itinerary.",
                          footnote=facts)

        stays=list(p.hotels.all())
        if stays:
            self.begin_page("THE ESSENTIALS / 01", "Where you'll stay",
                            "Example properties and room categories; allocations require confirmation.")
            if (p.source_details or {}).get("catalogue_kind")=="domestic_private_van":
                self.card("IMPORTANT", "Hotel options, not bookings",
                          "The listed hotels are supplier options, not confirmed reservations. "
                          "The final property, room and occupancy are specified in your quotation.")
            for i, h in enumerate(stays, 1):
                meta="  •  ".join(x for x in (
                    h.city, h.get_tier_display(),
                    f"{h.star_rating} stars" if h.star_rating else "",
                    f"{h.nights} nights", h.room_category) if x)
                self.card(f"HOTEL / {i:02d}", h.name,
                          h.description or "Alternative accommodation may be offered subject to availability.",
                          footnote=meta)
                if h.room_list:
                    self.items("ROOM OPTIONS", h.room_list)

        self.begin_page("THE ESSENTIALS / 02", "Travel beautifully",
                        "All package inclusions, exclusions and useful travel information.")
        self.items("INCLUDED", p.inclusion_list, 5,
                   "Confirmed inclusions will be specified in your written quotation.")
        self.items("NOT INCLUDED", p.exclusion_list, 5,
                   "Confirm exclusions, taxes and optional costs before booking.")
        for activity in p.activities.all():
            self.card("OPTIONAL EXPERIENCE", activity.name,
                      activity.description or "Optional activity: confirmation required.",
                      footnote=f"Adult {inr(activity.adult_price)}  •  Child {inr(activity.child_price)}")
        for label, value in p.info_list:
            self.card("GOOD TO KNOW", label or "Tour information", value)
        self.card("BEFORE YOU GO", "Pack thoughtfully",
                  "Carry photo identification, suitable shoes and weather-appropriate clothing. "
                  "Check timing, accessibility and your confirmed arrival point before travelling.")

        if site.booking_terms:
            self.begin_page("PLAN YOUR ESCAPE / 01", "Booking & changes",
                            "Your published booking conditions and practical information.")
            self.card("BOOKING TERMS", "Your travel conditions", site.booking_terms)

        self.begin_page("PLAN YOUR ESCAPE", "Make it yours",
                        "A memorable holiday begins with a carefully confirmed quotation.")
        self.card("YOUR SELECTED TOUR", self.price(), self.price_notes(),
                  subtitle=f"{p.title}  /  {p.duration_label}")
        self.card("WHAT TO CONFIRM", "Travel, thoughtfully arranged",
                  "Ask our team about hotel and room category, transfers, meals, guides, entrance fees, taxes, "
                  "personal costs and optional experiences. All final arrangements are confirmed in writing.")
        self.card("LET'S PLAN YOUR ESCAPE", "Get in touch",
                  "Request your personalised quotation, written payment terms and cancellation policy.",
                  footnote="  •  ".join(x for x in (site.phone, site.email, HOME) if x))
        if self.credit:
            self.card("PHOTO CREDIT", "Destination photography",
                      "Cover photograph: "+self.credit+
                      ". Images illustrate the destination, not a guaranteed hotel or travel service.")
        if p.source_url:
            self.card("SOURCE REFERENCE", "Published supplier reference",
                      p.source_url+"\nSupplier availability, validity and terms may change.")
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


def build_cinematic_pdf(package, site):
    return Brochure(package, site).render()
