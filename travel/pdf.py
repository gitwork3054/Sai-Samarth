"""Minimal branded itinerary brochures with complete, pointer-wise tour details."""
import hashlib
import io
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

INK = colors.HexColor('#202b30')
MUTED = colors.HexColor('#647078')
ACCENT = colors.HexColor('#28777a')
LINE = colors.HexColor('#dce5e5')
PALE = colors.HexColor('#f1f6f6')
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _esc(text):
    return str(text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _fonts():
    fonts = Path(settings.BASE_DIR) / 'static/fonts'
    if 'TripRegular' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('TripRegular', str(fonts / 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('TripBold', str(fonts / 'DejaVuSans-Bold.ttf')))
        pdfmetrics.registerFontFamily('TripRegular', normal='TripRegular', bold='TripBold', italic='TripRegular', boldItalic='TripBold')


def _photo(pkg):
    """Use the package photo; cache trusted public source images for PDF exports."""
    for field in (pkg.cover_image, pkg.destination.image):
        if field:
            try:
                path = Path(field.path)
                if path.is_file():
                    return path
            except (NotImplementedError, ValueError):
                pass
    key = (pkg.title + ' ' + pkg.destination.name).lower()
    fallback = None
    for names, filename in [(('kerala', 'munnar'), 'kerala-v2.webp'), (('greece', 'santorini'), 'greece-v2.webp'), (('switzerland', 'swiss'), 'switzerland-v2.webp')]:
        if any(name in key for name in names):
            candidate = Path(settings.BASE_DIR) / 'static/img/hero' / filename
            fallback = candidate if candidate.exists() else None
            break
    url = pkg.cover_url
    if not url:
        return fallback
    parsed = urlparse(url)
    # Only the existing photo sources are fetched; uploaded files work offline.
    if parsed.scheme != 'https' or parsed.hostname not in ('akhilbharat.in', 'upload.wikimedia.org'):
        return fallback
    folder = Path(settings.MEDIA_ROOT) / 'pdf-covers'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(url.encode()).hexdigest() + '.jpg')
    if path.exists():
        return path
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'SaiSamarth-Itinerary/1.0'})
        with urllib.request.urlopen(request, timeout=5) as response:
            if urlparse(response.geturl()).hostname not in ('akhilbharat.in', 'upload.wikimedia.org'):
                return fallback
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            return fallback
        with PILImage.open(io.BytesIO(raw)) as photo:
            photo.convert('RGB').save(path, 'JPEG', quality=90)
        return path
    except Exception:
        return fallback


def _logo(site):
    if site.logo:
        try:
            if Path(site.logo.path).is_file():
                return site.logo.path
        except (NotImplementedError, ValueError):
            pass
    path = Path(settings.BASE_DIR) / 'static/img/sai-samarth-logo.png'
    return str(path) if path.exists() else None


def _points(text):
    """Retain every source line, combining scraper-wrapped sentence fragments."""
    result = []
    current = ''
    for raw in str(text or '').splitlines():
        line = raw.strip()
        if not line:
            if current:
                result.append(current)
                current = ''
            continue
        line = re.sub(r'^[•●▪]\s*', '', line)
        current = (current + ' ' + line).strip()
        if re.search(r'[.!?:;]$|\([BLD+ ]+\)$', line):
            result.append(current)
            current = ''
    if current:
        result.append(current)
    return result


def build_itinerary_pdf(pkg, site):
    _fonts()
    photo, logo = _photo(pkg), _logo(site)
    buf = io.BytesIO()
    title = ParagraphStyle('title', fontName='TripBold', fontSize=21, leading=27, textColor=INK, spaceAfter=12)
    body = ParagraphStyle('body', fontName='TripRegular', fontSize=9, leading=14, textColor=INK, spaceAfter=5)
    small = ParagraphStyle('small', parent=body, fontSize=8, leading=12, textColor=MUTED)
    heading = ParagraphStyle('section', parent=body, fontName='TripBold', fontSize=11, leading=15,
                             textColor=ACCENT, spaceBefore=16, spaceAfter=5, keepWithNext=True)
    day_style = ParagraphStyle('day', parent=heading, fontSize=9.5, leading=14, spaceBefore=12)
    bullet = ParagraphStyle('bullet', parent=body, leftIndent=12, firstLineIndent=0, bulletIndent=0, bulletFontName='TripRegular', bulletFontSize=9, spaceAfter=4)

    def para(text, style=body):
        return Paragraph(_esc(text), style)

    def bullets(text):
        return [Paragraph(_esc(point), bullet, bulletText='•') for point in _points(text)]

    def section(name):
        return [para(name.upper(), heading), HRFlowable(width='100%', color=LINE, thickness=.6, spaceAfter=9)]

    price = 'Price on request' if pkg.price_on_request else f'From ₹{pkg.price_from:,} per person'
    if pkg.savings:
        price += f' | Save {pkg.effective_discount}% (regular ₹{pkg.base_price:,})'

    def footer(canvas, doc):
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(.5)
        canvas.line(MARGIN, 37, PAGE_W - MARGIN, 37)
        canvas.setFont('TripRegular', 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 24, f'{site.brand_name}  |  {pkg.tour_code}')
        canvas.drawRightString(PAGE_W - MARGIN, 24, f'{doc.page}')

    def cover_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        if logo:
            canvas.drawImage(logo, PAGE_W / 2 - 92, PAGE_H - 95, width=184, height=70,
                             preserveAspectRatio=True, anchor='c', mask='auto')
        else:
            canvas.setFont('TripBold', 15)
            canvas.setFillColor(ACCENT)
            canvas.drawCentredString(PAGE_W / 2, PAGE_H - 55, site.brand_name)
        image_y, image_h = 252, PAGE_H - 370
        if photo:
            canvas.saveState()
            clip = canvas.beginPath()
            clip.rect(0, image_y, PAGE_W, image_h)
            canvas.clipPath(clip, stroke=0)
            with PILImage.open(photo) as im:
                iw, ih = im.size
            scale = max(PAGE_W / iw, image_h / ih)
            canvas.drawImage(str(photo), (PAGE_W - iw * scale) / 2,
                             image_y + (image_h - ih * scale) / 2, width=iw * scale, height=ih * scale)
            canvas.restoreState()
        else:
            canvas.setFillColor(PALE)
            canvas.rect(0, image_y, PAGE_W, image_h, fill=1, stroke=0)
            canvas.setFont('TripBold', 24)
            canvas.setFillColor(ACCENT)
            canvas.drawCentredString(PAGE_W / 2, image_y + image_h / 2, pkg.destination.name)
        canvas.setFillColor(PALE)
        canvas.rect(0, 42, PAGE_W, 210, fill=1, stroke=0)
        footer(canvas, doc)
        canvas.restoreState()

    def body_page(canvas, doc):
        canvas.saveState()
        canvas.setFont('TripBold', 8)
        canvas.setFillColor(ACCENT)
        canvas.drawString(MARGIN, PAGE_H - 35, site.brand_name)
        canvas.setFont('TripRegular', 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 35, pkg.tour_code or '')
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, PAGE_H - 45, PAGE_W - MARGIN, PAGE_H - 45)
        footer(canvas, doc)
        canvas.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4, title=f'{pkg.title} ({pkg.tour_code})', author=site.brand_name,
                          leftMargin=MARGIN, rightMargin=MARGIN, topMargin=62, bottomMargin=52)
    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[Frame(MARGIN, 52, CONTENT_W, 188, leftPadding=0, rightPadding=0,
                                              topPadding=0, bottomPadding=0)], onPage=cover_page),
        PageTemplate(id='details', frames=[Frame(MARGIN, 52, CONTENT_W, PAGE_H - 114, leftPadding=0,
                                                rightPadding=0, topPadding=0, bottomPadding=0)], onPage=body_page),
    ])
    cover_title = re.sub(r'\s*[-–—]\s*', ' - ', pkg.title)
    cover_style = ParagraphStyle('cover-title', parent=title, fontSize=18 if len(pkg.title) > 50 else 21, leading=24 if len(pkg.title) > 50 else 27)
    story = [para('YOUR HOLIDAY ITINERARY', small), para(cover_title, cover_style),
             para(f'{pkg.duration_label}  |  {pkg.get_tour_type_display()}', body),
             para(price, body), para(f'Tour code: {pkg.tour_code}', small), NextPageTemplate('details'), PageBreak()]
    story += section('Your vacation at a glance')
    summary = [('Duration', pkg.duration_label), ('Destination', pkg.destination.name),
               ('Tour type', pkg.get_tour_type_display()), ('Tour code', pkg.tour_code), ('Tour price', price)]
    if pkg.departure_list:
        summary.append(('Fixed departures', ', '.join(pkg.departure_list)))
    rows = [[para(label, small), para(value, body)] for label, value in summary]
    table = Table(rows, colWidths=[100, CONTENT_W - 100], hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 7), ('LINEBELOW', (0, 0), (-1, -1), .4, LINE)]))
    story += [table]
    if pkg.overview or pkg.short_description:
        story += section('Overview') + bullets(pkg.overview or pkg.short_description)
    days = list(pkg.itinerary.all())
    if days:
        story += section('Day-wise itinerary')
        for day in days:
            story.append(para(f'DAY {day.day_number:02d}  |  {day.title}', day_style))
            story += bullets(day.description)
            meta = '  |  '.join(value for value in (f'Meals: {day.meals}' if day.meals else '',
                                                    f'Stay: {day.stay}' if day.stay else '') if value)
            if meta:
                story.append(para(meta, small))
    spots = list(pkg.sightseeing.all())
    if spots:
        story += section('Sightseeing')
        for spot in spots:
            story.append(Paragraph(f'<b>{_esc(spot.name)}</b>' + (f' - {_esc(spot.description)}' if spot.description else ''), bullet, bulletText='•'))
    hotels = list(pkg.hotels.all())
    if hotels:
        story += section('Hotels & room categories')
        for hotel in hotels:
            story.append(para(f'{hotel.city or pkg.destination.name} | {hotel.name}', day_style))
            story += bullets(f'{hotel.get_tier_display()} - {hotel.star_rating} star\nRoom: {hotel.room_category or "To be confirmed"}\n{hotel.nights} night(s)')
    activities = list(pkg.activities.all())
    if activities:
        story += section('Optional experiences')
        for activity in activities:
            story.append(para(activity.name, day_style))
            story += bullets(activity.description)
            story.append(para(f'Adult ₹{activity.adult_price:,} | Child ₹{activity.child_price:,}', small))
    for name, items in [('Inclusions', pkg.inclusion_list), ('Exclusions', pkg.exclusion_list)]:
        if items:
            story += section(name)
            for item in items:
                story.append(Paragraph(_esc(item), bullet, bulletText='•'))
    if pkg.info_list:
        story += section('Tour information')
        for label, description in pkg.info_list:
            story.append(Paragraph((f'<b>{_esc(label)}:</b> ' if label else '') + _esc(description), bullet, bulletText='•'))
    story += section('Contact & enquiries')
    for contact in (f'Phone: {site.phone}', f'Email: {site.email}', f'WhatsApp: +{site.whatsapp_number}'):
        story.append(Paragraph(_esc(contact), bullet, bulletText='•'))
    story += [Spacer(1, 5), para('Prices are indicative and subject to availability. Your travel expert will confirm the final quote.', small)]
    doc.build(story)
    return buf.getvalue()
