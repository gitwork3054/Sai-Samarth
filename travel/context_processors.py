from .models import Audience, Package, SiteSettings, Theme


def site(request):
    s = SiteSettings.get()
    logo = s.logo.url if s.logo else "/static/img/sai-samarth-logo.png"
    saved = set()
    if request.user.is_authenticated:
        saved = set(request.user.saved_packages.values_list("package_id", flat=True))
    packages = Package.objects.filter(is_active=True).select_related("destination")
    return {"site": s, "logo_url": logo, "saved_ids": saved,
            "nav_audiences": Audience.objects.all(), "nav_themes": Theme.objects.all(),
            "nav_domestic_packages": packages.filter(destination__region="domestic").order_by("destination__name", "title"),
            "nav_international_packages": packages.filter(destination__region="international").order_by("destination__name", "title"),
            "nav_group_packages": packages.filter(tour_type="group").order_by("title")}
