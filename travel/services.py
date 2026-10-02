"""Pricing engine + email/WhatsApp notifications."""
import json
import logging
import urllib.request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import NotificationLog, SiteSettings

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ pricing
def calculate_price(package, adults, children, tier="standard", departure_city="", activity_ids=()):
    """Authoritative server-side price. Mirrors the JS calculator in static/js/site.js."""
    adults, children = max(int(adults), 1), max(int(children), 0)
    cfg = package.pricing_config()
    pax = adults + children
    upgrade = cfg["tiers"].get(tier, 0)
    base = adults * cfg["base"] + children * cfg["child"]
    hotel = upgrade * pax
    disc_pct = cfg["discount"]
    discount = int((base + hotel) * disc_pct / 100 + 0.5)
    surcharge = 0
    for d in cfg["departures"]:
        if d["city"] == departure_city:
            surcharge = d["surcharge"] * pax
    acts, acts_total = [], 0
    for a in cfg["activities"]:
        if a["id"] in set(int(i) for i in activity_ids):
            acts.append(a["name"])
            acts_total += a["adult"] * adults + a["child"] * children
    total = base + hotel - discount + surcharge + acts_total
    quote_required = cfg["price_on_request"] or (children > 0 and cfg["child_price_on_request"])
    return {"price_on_request": quote_required, "base": base, "hotel_upgrade": hotel, "discount": discount, "departure_surcharge": surcharge,
            "activities_total": acts_total, "activities": acts, "total": 0 if quote_required else max(total, 0), "adults": adults, "children": children}


# ------------------------------------------------------------------ notifications
def _log(enquiry, channel, to, subject, body, status="sent", error=""):
    NotificationLog.objects.create(enquiry=enquiry, channel=channel, recipient=to, subject=subject, body=body, status=status, error=error[:1000])


def send_email(enquiry, to, subject, body, html=None):
    try:
        msg = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
        if html:
            msg.attach_alternative(html, "text/html")
        msg.send()
        _log(enquiry, "email", to, subject, body)
    except Exception as exc:  # never break the customer flow because of a mail error
        log.exception("email failed")
        _log(enquiry, "email", to, subject, body, "failed", str(exc))


def normalise_phone(phone, default_cc="91"):
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        digits = default_cc + digits
    return digits


def send_whatsapp(enquiry, phone, body, template=None, params=()):
    """WhatsApp Cloud API. Without credentials the message is only logged (dev mode)."""
    to = normalise_phone(phone)
    if not (settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID):
        _log(enquiry, "whatsapp", to, "", body, "logged-only", "WhatsApp API not configured")
        return
    if template:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
                   "template": {"name": template, "language": {"code": "en"},
                                "components": [{"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]}]}}
    else:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}
    req = urllib.request.Request(
        f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_ID}/messages",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10).read()
        _log(enquiry, "whatsapp", to, "", body)
    except Exception as exc:
        log.exception("whatsapp failed")
        _log(enquiry, "whatsapp", to, "", body, "failed", str(exc))


def _params(enq):
    return (enq.name, enq.package.title, enq.package.tour_code, enq.reference,
            f"{enq.travel_date:%d %b %Y}" if enq.travel_date else "To be decided", "Price on request" if enq.price_breakdown.get("price_on_request") else f"Rs. {enq.total_price:,}")


def notify_enquiry_received(enq):
    site = SiteSettings.get()
    details = "\n".join(enq.summary_lines())
    body = (f"Hi {enq.name},\n\nThanks for your enquiry with {site.brand_name}. Our travel expert will contact you shortly.\n\n"
            f"Reference: {enq.reference}\n{details}\n\nNeed help? Call {site.phone} or reply to this email.\n")
    send_email(enq, enq.email, f"We received your enquiry {enq.reference} · {enq.package.title}", body)
    send_whatsapp(enq, enq.phone, f"Hi {enq.name}! We received your enquiry {enq.reference}.\n{details}\nWe'll contact you shortly. – {site.brand_name}",
                  settings.WHATSAPP_TEMPLATE_ENQUIRY, _params(enq))
    # heads-up to the owner
    owner_body = f"New enquiry {enq.reference}\n{enq.name} · {enq.phone} · {enq.email}\n{details}\n\nMessage: {enq.message or '-'}"
    send_email(enq, site.email, f"[New enquiry] {enq.package.tour_code} · {enq.name}", owner_body)
    send_whatsapp(enq, site.whatsapp_number, owner_body)


def notify_booking_confirmed(enq):
    site = SiteSettings.get()
    details = "\n".join(enq.summary_lines())
    body = (f"Hi {enq.name},\n\nGreat news, your booking is CONFIRMED!\n\nBooking reference: {enq.reference}\n{details}\n\n"
            f"Your tour manager will share vouchers and final documents soon. Questions? Call {site.phone}.\n\nHappy travels,\n{site.brand_name}")
    html = (f"<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto;border-radius:16px;overflow:hidden;border:1px solid #f3d9c9'>"
            f"<div style='background:linear-gradient(135deg,#ff7a59,#ff5c9a);color:#fff;padding:28px'><h2 style='margin:0'>Booking confirmed 🎉</h2>"
            f"<p style='margin:6px 0 0'>Reference {enq.reference}</p></div><div style='padding:24px;color:#2a2340'>"
            f"<p>Hi {enq.name}, your holiday is locked in.</p><p>{'<br>'.join(enq.summary_lines())}</p>"
            f"<p>Call us on <b>{site.phone}</b> for anything you need.</p></div></div>")
    send_email(enq, enq.email, f"Booking confirmed {enq.reference} · {enq.package.title}", body, html)
    send_whatsapp(enq, enq.phone, f"🎉 Booking confirmed! Ref {enq.reference}\n{details}\nThank you for choosing {site.brand_name}.",
                  settings.WHATSAPP_TEMPLATE_BOOKING, _params(enq))
