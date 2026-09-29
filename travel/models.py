import re
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class SiteSettings(models.Model):
    """Single row: brand, logo and contact details used across the whole site."""
    brand_name = models.CharField(max_length=80, default="Sai Samarth Holidays Pvt. Ltd.")
    tagline = models.CharField(max_length=160, default="Journeys that feel like golden hour")
    logo = models.ImageField(upload_to="brand/", blank=True, help_text="Upload your logo (PNG with transparent background works best).")
    phone = models.CharField(max_length=30, default="+91 9510088833")
    whatsapp_number = models.CharField(max_length=20, default="919510088833", help_text="Digits only with country code, e.g. 919876543210")
    email = models.EmailField(default="holidays@saisamarthholidays.in", help_text="Enquiries are also sent to this address.")
    address = models.CharField(max_length=250, blank=True)
    instagram = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    hero_title = models.CharField(max_length=140, default="Chase the sunset, anywhere in the world")
    hero_subtitle = models.CharField(max_length=240, default="100+ handcrafted domestic and international holidays with transparent pricing.")

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.brand_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Theme(models.Model):
    """Trip type / interest, e.g. Beach, Adventure & Wildlife, Heritage."""
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=8, blank=True, help_text="An emoji, e.g. 🏖️")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *a, **k):
        self.slug = self.slug or slugify(self.name)
        super().save(*a, **k)


class Audience(models.Model):
    """Traveller category: Gen-Z, Family, Couple, Senior..."""
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=8, blank=True)
    description = models.CharField(max_length=160, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Traveller categories"

    def __str__(self):
        return self.name

    def save(self, *a, **k):
        self.slug = self.slug or slugify(self.name)
        super().save(*a, **k)


class Destination(models.Model):
    REGIONS = [("domestic", "Domestic"), ("international", "International")]
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    region = models.CharField(max_length=15, choices=REGIONS, default="domestic")
    state_or_country = models.CharField(max_length=80, blank=True, help_text="State (domestic) or country (international)")
    tagline = models.CharField(max_length=160, blank=True)
    image = models.ImageField(upload_to="destinations/", blank=True)
    is_popular = models.BooleanField(default=False, help_text="Show in 'Popular places' on the home page")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *a, **k):
        self.slug = self.slug or slugify(self.name)
        super().save(*a, **k)


def _fmt_lines(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


class Package(models.Model):
    TOUR_TYPES = [("individual", "Individual / Customised"), ("group", "Group (fixed departure)"), ("corporate", "Corporate / MICE")]

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    tour_code = models.CharField(max_length=20, unique=True, null=True, blank=True, help_text="Leave blank to auto-generate (e.g. FTD-0012).")
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="packages")
    tour_type = models.CharField(max_length=12, choices=TOUR_TYPES, default="individual")
    themes = models.ManyToManyField(Theme, blank=True, related_name="packages")
    audiences = models.ManyToManyField(Audience, blank=True, related_name="packages")
    days = models.PositiveSmallIntegerField(default=5)
    nights = models.PositiveSmallIntegerField(default=4)
    short_description = models.CharField(max_length=240)
    overview = models.TextField(blank=True)

    # pricing (INR, per person)
    base_price = models.PositiveIntegerField(help_text="Adult price per person, Standard hotels, before discount")
    child_price = models.PositiveIntegerField(default=0, help_text="Child (2-11 yrs) price per person")
    deluxe_upgrade = models.PositiveIntegerField(default=0, help_text="Extra per person for Deluxe hotels")
    premium_upgrade = models.PositiveIntegerField(default=0, help_text="Extra per person for Premium hotels")
    discount_percent = models.PositiveSmallIntegerField(default=0, help_text="0-90. Applied to base + hotel price")
    offer_label = models.CharField(max_length=60, blank=True, help_text="e.g. Early-bird, Monsoon Sale")
    offer_valid_till = models.DateField(null=True, blank=True)

    # events / festivals / group
    is_event = models.BooleanField("Event / festival tour", default=False)
    event_name = models.CharField(max_length=100, blank=True, help_text="e.g. Rann Utsav, Diwali in Jaipur")
    event_date = models.DateField(null=True, blank=True)
    departure_dates = models.TextField(blank=True, help_text="Group tours: one departure date per line")

    # media
    cover_image = models.ImageField(upload_to="packages/", blank=True)
    cover_url = models.URLField(blank=True, help_text="Optional: link to an image instead of uploading")
    youtube_url = models.URLField(blank=True, help_text="Any YouTube link (watch, youtu.be or shorts)")

    # info blocks (one item per line)
    inclusions = models.TextField(blank=True, help_text="One per line")
    exclusions = models.TextField(blank=True, help_text="One per line")
    tour_info = models.TextField(blank=True, help_text="Important notes, one per line (Title: text)")

    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Untick to hide from the website")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-created"]

    def __str__(self):
        return f"{self.tour_code or '—'} · {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:170] or "package"
            slug, n = base, 2
            while Package.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        if self.discount_percent > 90:
            self.discount_percent = 90
        super().save(*args, **kwargs)
        if not self.tour_code:
            prefix = "FTD" if self.destination.region == "domestic" else "FTI"
            code = f"{prefix}-{self.pk:04d}"
            Package.objects.filter(pk=self.pk).update(tour_code=code)
            self.tour_code = code

    def get_absolute_url(self):
        return reverse("package_detail", args=[self.slug])

    # ---- derived ----
    @property
    def region(self):
        return self.destination.region

    @property
    def offer_active(self):
        return self.discount_percent > 0 and (not self.offer_valid_till or self.offer_valid_till >= timezone.localdate())

    @property
    def effective_discount(self):
        return self.discount_percent if self.offer_active else 0

    @property
    def price_from(self):
        return int(round(self.base_price * (100 - self.effective_discount) / 100))

    @property
    def savings(self):
        return self.base_price - self.price_from

    @property
    def cover(self):
        if self.cover_image:
            return self.cover_image.url
        return self.cover_url or (self.destination.image.url if self.destination.image else "")

    @property
    def youtube_id(self):
        m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", self.youtube_url or "")
        return m.group(1) if m else ""

    @property
    def inclusion_list(self):
        return _fmt_lines(self.inclusions)

    @property
    def exclusion_list(self):
        return _fmt_lines(self.exclusions)

    @property
    def info_list(self):
        out = []
        for l in _fmt_lines(self.tour_info):
            t, _, d = l.partition(":")
            out.append((t.strip(), d.strip()) if d else ("", l))
        return out

    @property
    def departure_list(self):
        return _fmt_lines(self.departure_dates)

    def pricing_config(self):
        return {
            "base": self.base_price, "child": self.child_price or self.base_price,
            "discount": self.effective_discount,
            "tiers": {"standard": 0, "deluxe": self.deluxe_upgrade, "premium": self.premium_upgrade},
            "departures": [{"id": d.id, "city": d.city, "surcharge": d.surcharge} for d in self.departure_cities.all()],
            "activities": [{"id": a.id, "name": a.name, "adult": a.adult_price, "child": a.child_price} for a in self.activities.all()],
        }


class ItineraryDay(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="itinerary")
    day_number = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=160)
    description = models.TextField()
    meals = models.CharField(max_length=80, blank=True, help_text="e.g. Breakfast, Dinner")
    stay = models.CharField(max_length=120, blank=True, help_text="Overnight stay city / hotel")

    class Meta:
        ordering = ["day_number"]
        verbose_name = "Day-wise itinerary"

    def __str__(self):
        return f"Day {self.day_number}: {self.title}"


class Sightseeing(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="sightseeing")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to="sightseeing/", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Sightseeing spot"

    def __str__(self):
        return self.name


class PackageImage(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to="gallery/")
    caption = models.CharField(max_length=140, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Gallery photo"

    def __str__(self):
        return self.caption or f"Photo {self.pk}"


class Hotel(models.Model):
    TIERS = [("standard", "Standard"), ("deluxe", "Deluxe"), ("premium", "Premium")]
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="hotels")
    tier = models.CharField(max_length=10, choices=TIERS, default="standard")
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=80, blank=True)
    star_rating = models.PositiveSmallIntegerField(default=3)
    room_category = models.CharField(max_length=120, blank=True, help_text="e.g. Deluxe Sea-view Room")
    nights = models.PositiveSmallIntegerField(default=1)
    image = models.ImageField(upload_to="hotels/", blank=True)

    class Meta:
        ordering = ["tier", "id"]

    def __str__(self):
        return f"{self.name} ({self.tier})"


class OptionalActivity(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="activities")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    adult_price = models.PositiveIntegerField(default=0)
    child_price = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Optional experience"
        verbose_name_plural = "Optional experiences"

    def __str__(self):
        return self.name


class DepartureCity(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="departure_cities")
    city = models.CharField(max_length=80)
    surcharge = models.IntegerField(default=0, help_text="Extra per person from this city (0 = same as base)")

    class Meta:
        verbose_name = "Departure city & surcharge"
        verbose_name_plural = "Departure cities & surcharges"

    def __str__(self):
        return self.city


class Enquiry(models.Model):
    STATUS = [("new", "New enquiry"), ("contacted", "Contacted"), ("booked", "Booked / Confirmed"), ("cancelled", "Cancelled")]
    reference = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name="enquiries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    travel_date = models.DateField(null=True, blank=True)
    adults = models.PositiveSmallIntegerField(default=2)
    children = models.PositiveSmallIntegerField(default=0)
    hotel_tier = models.CharField(max_length=10, choices=Hotel.TIERS, default="standard")
    departure_city = models.CharField(max_length=80, blank=True)
    activities = models.ManyToManyField(OptionalActivity, blank=True)
    message = models.TextField(blank=True)
    total_price = models.PositiveIntegerField(default=0)
    price_breakdown = models.JSONField(default=dict, blank=True, help_text="Snapshot of the calculator at enquiry time")
    status = models.CharField(max_length=10, choices=STATUS, default="new")
    admin_notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name_plural = "Enquiries & bookings"

    def __str__(self):
        return f"{self.reference or 'new'} · {self.name} · {self.package.tour_code}"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._orig_status = self.status

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        became_booked = self.status == "booked" and (is_new or self._orig_status != "booked")
        super().save(*args, **kwargs)
        if not self.reference:
            self.reference = f"FT-{timezone.now():%y}{self.pk:05d}"
            Enquiry.objects.filter(pk=self.pk).update(reference=self.reference)
        self._orig_status = self.status
        if became_booked:  # instant booking confirmation by email + WhatsApp
            from .services import notify_booking_confirmed
            notify_booking_confirmed(self)

    @property
    def travellers(self):
        return self.adults + self.children

    def summary_lines(self):
        b = self.price_breakdown or {}
        lines = [
            f"Package: {self.package.title} ({self.package.tour_code})",
            f"Travellers: {self.adults} adult(s), {self.children} child(ren)",
            f"Hotel: {self.get_hotel_tier_display()}",
        ]
        if self.departure_city:
            lines.append(f"Departure city: {self.departure_city}")
        acts = b.get("activities") or []
        if acts:
            lines.append("Optional experiences: " + ", ".join(acts))
        if self.travel_date:
            lines.append(f"Preferred date: {self.travel_date:%d %b %Y}")
        lines.append(f"Estimated total: Rs. {self.total_price:,}")
        return lines


class NotificationLog(models.Model):
    """Every email / WhatsApp the system sends, so the owner can see delivery status."""
    CHANNELS = [("email", "Email"), ("whatsapp", "WhatsApp")]
    enquiry = models.ForeignKey(Enquiry, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=10, choices=CHANNELS)
    recipient = models.CharField(max_length=120)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="sent")
    error = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.channel} → {self.recipient} ({self.status})"


class SavedPackage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_packages")
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="saved_by")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "package")
        ordering = ["-created"]


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    home_city = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"Profile of {self.user}"
