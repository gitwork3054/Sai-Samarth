import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CORAL, DUSK = colors.HexColor("#ff6a4d"), colors.HexColor("#2b1f55")


def _esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_itinerary_pdf(pkg, site):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{pkg.title} ({pkg.tour_code})", author=site.brand_name)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=DUSK, fontSize=22, leading=26, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=CORAL, fontSize=13, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13.5)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, textColor=colors.HexColor("#6b6480"))
    el = [Paragraph(_esc(site.brand_name), ParagraphStyle("brand", parent=body, textColor=CORAL, fontSize=11, fontName="Helvetica-Bold")),
          Paragraph(_esc(pkg.title), h1),
          Paragraph(f"Tour code <b>{pkg.tour_code}</b> &nbsp;|&nbsp; {pkg.days} Days / {pkg.nights} Nights &nbsp;|&nbsp; {_esc(pkg.destination.name)} "
                    f"&nbsp;|&nbsp; {pkg.get_tour_type_display()}", small)]
    price = f"From Rs. {pkg.price_from:,} per person"
    if pkg.savings:
        price += f"  (was Rs. {pkg.base_price:,}, save {pkg.effective_discount}%)"
    el += [Spacer(1, 6), Paragraph(f"<b>{price}</b>", ParagraphStyle("p", parent=body, fontSize=12, textColor=DUSK)),
           HRFlowable(width="100%", color=CORAL, thickness=1.2, spaceBefore=4, spaceAfter=4)]
    if pkg.overview or pkg.short_description:
        el += [Paragraph("Overview", h2), Paragraph(_esc(pkg.overview or pkg.short_description), body)]
    days = list(pkg.itinerary.all())
    if days:
        el.append(Paragraph("Day-wise itinerary", h2))
        for d in days:
            meta = " | ".join(x for x in [f"Meals: {d.meals}" if d.meals else "", f"Stay: {d.stay}" if d.stay else ""] if x)
            el += [Paragraph(f"<b>Day {d.day_number}: {_esc(d.title)}</b>", body), Paragraph(_esc(d.description), body)]
            if meta:
                el.append(Paragraph(_esc(meta), small))
            el.append(Spacer(1, 5))
    spots = list(pkg.sightseeing.all())
    if spots:
        el.append(Paragraph("Sightseeing", h2))
        el += [Paragraph(f"&bull; <b>{_esc(s.name)}</b> {_esc(s.description)}", body) for s in spots]
    hotels = list(pkg.hotels.all())
    if hotels:
        el.append(Paragraph("Hotels & room categories", h2))
        rows = [["Category", "Hotel", "City", "Room", "Nights"]] + [[h.get_tier_display(), h.name, h.city, h.room_category, str(h.nights)] for h in hotels]
        t = Table(rows, repeatRows=1, colWidths=[24 * mm, 52 * mm, 30 * mm, 50 * mm, 14 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), DUSK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                               ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#e6dccf")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        el.append(t)
    acts = list(pkg.activities.all())
    if acts:
        el.append(Paragraph("Optional experiences", h2))
        el += [Paragraph(f"&bull; {_esc(a.name)}: Rs. {a.adult_price:,} adult / Rs. {a.child_price:,} child", body) for a in acts]
    if pkg.inclusion_list:
        el.append(Paragraph("Inclusions", h2))
        el += [Paragraph(f"&bull; {_esc(i)}", body) for i in pkg.inclusion_list]
    if pkg.exclusion_list:
        el.append(Paragraph("Exclusions", h2))
        el += [Paragraph(f"&bull; {_esc(i)}", body) for i in pkg.exclusion_list]
    if pkg.info_list:
        el.append(Paragraph("Tour information", h2))
        el += [Paragraph(f"&bull; <b>{_esc(t)}</b> {_esc(d)}" if t else f"&bull; {_esc(d)}", body) for t, d in pkg.info_list]
    el += [Spacer(1, 12), HRFlowable(width="100%", color=CORAL), Spacer(1, 4),
           Paragraph(f"Enquire: {_esc(site.phone)} | {_esc(site.email)} | WhatsApp +{_esc(site.whatsapp_number)}. Prices are indicative and subject to availability.", small)]

    def footer(c, d):
        c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#6b6480"))
        c.drawString(18 * mm, 9 * mm, f"{site.brand_name} | {pkg.tour_code}"); c.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}"); c.restoreState()

    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
