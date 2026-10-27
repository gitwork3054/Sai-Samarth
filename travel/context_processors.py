from django.conf import settings
from .models import Audience, Package, SiteSettings, Theme, HomeSlide
from .domestic_states import domestic_groups, international_groups
from .flamingo_catalog import FLAMINGO_COUNTRIES, flamingo_grouped_countries


def site(request):
    s = SiteSettings.get()
    logo = s.logo.url if s.logo else "/static/img/sai-samarth-logo.png"
    saved = set()
    if request.user.is_authenticated:
        saved = set(request.user.saved_packages.values_list("package_id", flat=True))
    packages = Package.objects.filter(is_active=True).select_related("destination")
    google = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]
    return {"google_login_enabled": bool(google["client_id"] and google["secret"]), "site": s, "logo_url": logo, "saved_ids": saved,
            "nav_audiences": Audience.objects.all(), "nav_themes": Theme.objects.all(),
            "nav_domestic_states": domestic_groups(packages.filter(destination__region="domestic")),
            "nav_domestic_packages": packages.filter(destination__region="domestic").order_by("destination__name", "title"),
            "nav_international_packages": packages.filter(destination__region="international").order_by("destination__name", "title"),
            "nav_group_packages": packages.filter(tour_type="group").order_by("title"),
            "nav_international_countries": sorted(FLAMINGO_COUNTRIES, key=lambda item: item["name"].lower()),
            "nav_international_region_groups": flamingo_grouped_countries(),
            "nav_international_groups": international_groups(packages.filter(tour_type="group", destination__region="international")),
            "hero_slides": HomeSlide.objects.filter(is_active=True), "preview_characters": max(100, s.preview_characters),
            "hero_interval": max(1000, min(30000, s.slideshow_interval))}
