from datetime import date, timedelta
from hashlib import sha1
import json
from urllib.parse import unquote, urlparse

from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import models as m
from .curated_photos import SOURCES
from .forms import EnquiryForm
from .pdf import build_itinerary_pdf
from .services import calculate_price, notify_enquiry_received

ACTIVE = m.Package.objects.filter(is_active=True).select_related("destination").prefetch_related("themes", "audiences")

PRESETS = {
    "domestic": ("Domestic tour packages", {"region": "domestic"}),
    "international": ("International tour packages", {"region": "international"}),
    "group": ("Group tours", {"tour_type": "group"}),
    "corporate": ("Corporate tours", {"tour_type": "corporate"}),
    "offers": ("Offers & discounts", {"offers": "1"}),
    "events": ("Events & festival tours", {"events": "1"}),
}
DURATIONS = {"1-3": (1, 3), "4-6": (4, 6), "7-9": (7, 9), "10-14": (10, 14), "15+": (15, 99)}
BUDGETS = {"0-20000": (0, 20000), "20000-40000": (20000, 40000), "40000-80000": (40000, 80000), "80000-150000": (80000, 150000), "150000+": (150000, 10**9)}
BUDGET_LABELS = {"0-20000": "Under ₹20k", "20000-40000": "₹20k – 40k", "40000-80000": "₹40k – 80k", "80000-150000": "₹80k – 1.5L", "150000+": "Above ₹1.5L"}


def photo_credits(request):
    path = settings.MEDIA_ROOT / "photo-credits.json"
    credits = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    known = {entry.get("source") for entry in credits.values()}
    for source in set(SOURCES.values()) - known:
        title = unquote(urlparse(source).path).split("/File:", 1)[-1].replace("_", " ")
        credits["curated/" + sha1(source.encode("utf-8")).hexdigest()[:12]] = {
            "source": source, "title": title,
            "author": "Creator listed on the file page", "license": "View license",
            "license_url": source,
        }
    return render(request, "travel/photo_credits.html", {"credits": sorted(credits.items())})


def _filter(qs, p):
    q = (p.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(tour_code__iexact=q) | Q(destination__name__icontains=q)
                       | Q(destination__state_or_country__icontains=q) | Q(short_description__icontains=q))
    if p.get("region") in ("domestic", "international"):
        qs = qs.filter(destination__region=p["region"])
    if p.get("destination"):
        qs = qs.filter(Q(destination__slug=p["destination"]) | Q(destination__state_or_country__iexact=p["destination"]))
    if p.get("tour_type") in ("individual", "group", "corporate"):
        qs = qs.filter(tour_type=p["tour_type"])
    if p.get("theme"):
        qs = qs.filter(themes__slug=p["theme"])
    if p.get("audience"):
        qs = qs.filter(audiences__slug=p["audience"])
    if p.get("duration") in DURATIONS:
        lo, hi = DURATIONS[p["duration"]]
        qs = qs.filter(days__gte=lo, days__lte=hi)
    if p.get("budget") in BUDGETS:
        lo, hi = BUDGETS[p["budget"]]
        qs = qs.filter(price_on_request=False, base_price__gte=lo, base_price__lt=hi)
    today = date.today()
    if p.get("offers"):
        qs = qs.filter(discount_percent__gt=0).filter(Q(offer_valid_till__isnull=True) | Q(offer_valid_till__gte=today))
    if p.get("events"):
        qs = qs.filter(is_event=True)
    sort = p.get("sort")
    qs = qs.distinct()
    return {"price_low": qs.order_by("base_price"), "price_high": qs.order_by("-base_price"),
            "duration": qs.order_by("days"), "newest": qs.order_by("-created")}.get(sort, qs)


def home(request):
    today = date.today()
    base = ACTIVE
    offers = base.filter(discount_percent__gt=0).filter(Q(offer_valid_till__isnull=True) | Q(offer_valid_till__gte=today)).order_by("-discount_percent")[:6]
    events = base.filter(is_event=True).order_by("event_date")[:6]
    ctx = {
        "offers": offers, "events": events,
        "domestic": base.filter(destination__region="domestic", is_featured=True)[:6] or base.filter(destination__region="domestic")[:6],
        "international": base.filter(destination__region="international", is_featured=True)[:6] or base.filter(destination__region="international")[:6],
        "group_tours": base.filter(tour_type="group")[:3],
        "audiences": m.Audience.objects.annotate(n=Count("packages")),
        "popular": m.Destination.objects.filter(is_popular=True).annotate(n=Count("packages"))[:8],
        "destinations": m.Destination.objects.annotate(n=Count("packages")).filter(n__gt=0),
        "total_packages": base.count(),
        "durations": DURATIONS.keys(), "budgets": [(k, v) for k, v in BUDGET_LABELS.items()],
    }
    return render(request, "travel/home.html", ctx)


def package_list(request, preset=None):
    params = request.GET.copy()
    title = "All tour packages"
    if preset:
        title, forced = PRESETS[preset]
        for k, v in forced.items():
            params.setdefault(k, v)
    qs = _filter(ACTIVE, params)
    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    ctx = {
        "page": page, "count": page.paginator.count, "title": title, "preset": preset, "params": params,
        "themes": m.Theme.objects.all(), "audiences": m.Audience.objects.all(),
        "destinations": m.Destination.objects.annotate(n=Count("packages", filter=Q(packages__is_active=True))).filter(n__gt=0),
        "durations": DURATIONS.keys(), "budgets": BUDGET_LABELS.items(), "qs_keep": keep.urlencode(),
        "active_filters": any(request.GET.get(k) for k in ("q", "destination", "theme", "audience", "duration", "budget", "region", "tour_type", "offers", "events")),
    }
    return render(request, "travel/package_list.html", ctx)


def package_detail(request, slug):
    pkg = get_object_or_404(ACTIVE.prefetch_related("itinerary", "sightseeing", "gallery", "hotels", "activities", "departure_cities"), slug=slug)
    gallery = list(pkg.gallery.all())
    used_sources = {SOURCES.get(f"{pkg.destination.name}|{g.caption}") for g in gallery}
    gallery_fallback = []
    for spot in pkg.sightseeing.all():
        source = SOURCES.get(f"{pkg.destination.name}|{spot.name}") or SOURCES.get(f"{pkg.destination.name}|")
        if source and source not in used_sources and len(gallery) + len(gallery_fallback) < 6:
            gallery_fallback.append(spot)
            used_sources.add(source)
    theme_ids = [t.id for t in pkg.themes.all()]
    aud_ids = [a.id for a in pkg.audiences.all()]
    similar = (ACTIVE.exclude(pk=pkg.pk)
               .annotate(score=Count("themes", filter=Q(themes__in=theme_ids), distinct=True) * 2 + Count("audiences", filter=Q(audiences__in=aud_ids), distinct=True)
                         + Count("pk", filter=Q(destination__region=pkg.region), distinct=True))
               .order_by("-score", "?")[:4])
    more_here = ACTIVE.filter(Q(destination=pkg.destination) | Q(destination__state_or_country=pkg.destination.state_or_country)).exclude(pk=pkg.pk)[:4]
    hotels_by_tier = {}
    for h in pkg.hotels.all():
        hotels_by_tier.setdefault(h.get_tier_display(), []).append(h)
    ctx = {
        "pkg": pkg, "similar": similar, "more_here": more_here, "hotels_by_tier": hotels_by_tier,
        "gallery_fallback": gallery_fallback,
        "places": m.Destination.objects.filter(region=pkg.region).exclude(pk=pkg.destination_id).annotate(n=Count("packages")).filter(n__gt=0).order_by("-is_popular", "?")[:8],
        "config": pkg.pricing_config(), "tiers_available": [("standard", "Standard", 0), ("deluxe", "Deluxe", pkg.deluxe_upgrade), ("premium", "Premium", pkg.premium_upgrade)],
        "is_saved": request.user.is_authenticated and pkg.saved_by.filter(user=request.user).exists(),
    }
    return render(request, "travel/package_detail.html", ctx)


def package_pdf(request, slug):
    pkg = get_object_or_404(ACTIVE, slug=slug)
    resp = HttpResponse(build_itinerary_pdf(pkg, m.SiteSettings.get()), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{pkg.tour_code}-{pkg.slug}.pdf"'
    return resp


@require_POST
def toggle_save(request, slug):
    if not request.user.is_authenticated:
        return JsonResponse({"login": True}, status=401)
    pkg = get_object_or_404(m.Package, slug=slug, is_active=True)
    obj, created = m.SavedPackage.objects.get_or_create(user=request.user, package=pkg)
    if not created:
        obj.delete()
    return JsonResponse({"saved": created})


@require_POST
def create_enquiry(request, slug):
    pkg = get_object_or_404(ACTIVE, slug=slug)
    form = EnquiryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": {k: v[0] for k, v in form.errors.items()}}, status=400)
    d = form.cleaned_data
    if d["website"]:  # honeypot tripped: pretend success
        return JsonResponse({"ok": True, "reference": "—"})
    valid_ids = set(pkg.activities.values_list("id", flat=True))
    act_ids = [i for i in d["activities"] if i in valid_ids]
    if d["departure_city"] and not pkg.departure_cities.filter(city=d["departure_city"]).exists():
        d["departure_city"] = ""
    calc = calculate_price(pkg, d["adults"], d["children"], d["hotel_tier"], d["departure_city"], act_ids)
    enq = m.Enquiry.objects.create(
        package=pkg, user=request.user if request.user.is_authenticated else None,
        name=d["name"], email=d["email"], phone=d["phone"], travel_date=d["travel_date"], adults=d["adults"], children=d["children"],
        hotel_tier=d["hotel_tier"], departure_city=d["departure_city"], message=d["message"], total_price=calc["total"], price_breakdown=calc)
    enq.activities.set(act_ids)
    notify_enquiry_received(enq)
    return JsonResponse({"ok": True, "reference": enq.reference, "total": calc["total"]})
