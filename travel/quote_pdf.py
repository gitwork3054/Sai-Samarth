"""Customer-facing quote export: internal cost and margin stay in the admin."""
import io
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, HRFlowable
from .pdf import _fonts, _esc, INK, MUTED, ACCENT, LINE, A4, MARGIN


def build_quote_pdf(enquiry, site):
    _fonts()
    buffer = io.BytesIO()
    quote = enquiry.quote_breakdown
    body = ParagraphStyle('quote-body', fontName='TripRegular', fontSize=9, leading=14, spaceAfter=6, textColor=INK)
    title = ParagraphStyle('quote-title', parent=body, fontName='TripBold', fontSize=22, leading=28, spaceAfter=12)
    heading = ParagraphStyle('quote-heading', parent=body, fontName='TripBold', fontSize=12, leading=17, textColor=ACCENT, spaceBefore=14, keepWithNext=True)
    small = ParagraphStyle('quote-small', parent=body, fontSize=8, leading=12, textColor=MUTED)
    def p(value, style=body):
        return Paragraph(_esc(value).replace('\n', '<br/>'), style)
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=45, bottomMargin=48,
                            title=f'Quotation {enquiry.reference}', author=site.brand_name)
    elements = [p(site.brand_name, heading), p('Your travel quotation', title),
        p(f'Reference: {enquiry.reference} | Tour code: {quote["tour_code"]}', small),
        HRFlowable(width='100%', color=LINE, thickness=.5, spaceBefore=8, spaceAfter=12),
        p(quote['package_title'], heading), p(f'Prepared for: {enquiry.name}'),
        p(f'Travellers: {quote["adults"]} adult(s), {quote["children"]} child(ren)'),
        p(f'Hotel category: {quote["hotel_tier"].title()}')]
    if enquiry.travel_date:
        elements.append(p(f'Travel date: {enquiry.travel_date:%d %B %Y}'))
    if quote['departure_city']:
        elements.append(p('Departure city: '+quote['departure_city']))
    elements += [p(f'Total quotation: ₹{quote["total"]:,}', heading), p('Price for the travellers listed above. Subject to final availability.', small)]
    if quote['activities']:
        elements += [p('Selected optional experiences', heading)] + [p('• '+name) for name in quote['activities']]
    if quote['itinerary']:
        elements.append(p('Your itinerary', heading))
        for block in quote['itinerary'].split('\n\n'):
            elements.append(p(block))
    if quote['notes']:
        elements += [p('Quotation notes', heading), p(quote['notes'])]
    if enquiry.terms_snapshot:
        elements += [p('Booking terms', heading), p(enquiry.terms_snapshot)]
    elements += [Spacer(1,12), HRFlowable(width='100%',color=LINE),p(f'{site.phone} | {site.email}',small)]
    def footer(canvas, doc):
        canvas.saveState();canvas.setFont('TripRegular',7);canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN,24,f'{site.brand_name} | {enquiry.reference}');canvas.drawRightString(A4[0]-MARGIN,24,f'{doc.page}');canvas.restoreState()
    doc.build(elements,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
