from django.contrib import admin, messages
from django.utils.html import format_html

from . import models as m


class ItineraryInline(admin.StackedInline):
    model = m.ItineraryDay
    extra = 1
    classes = ["collapse"]


class SightseeingInline(admin.TabularInline):
    model = m.Sightseeing
    extra = 1
    classes = ["collapse"]


class GalleryInline(admin.TabularInline):
    model = m.PackageImage
    extra = 1
    classes = ["collapse"]


class HotelInline(admin.TabularInline):
    model = m.Hotel
    extra = 1
    classes = ["collapse"]


class ActivityInline(admin.TabularInline):
    model = m.OptionalActivity
    extra = 1
    classes = ["collapse"]


class DepartureInline(admin.TabularInline):
    model = m.DepartureCity
    extra = 1
    classes = ["collapse"]


@admin.register(m.Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("thumb", "tour_code", "title", "destination", "tour_type", "days", "base_price", "discount_percent", "is_event", "is_featured", "is_active")
    list_display_links = ("thumb", "tour_code", "title")
    list_editable = ("base_price", "discount_percent", "is_featured", "is_active")
    list_filter = ("is_active", "destination__region", "tour_type", "themes", "audiences", "is_featured", "is_event", "destination")
    search_fields = ("title", "tour_code", "destination__name", "short_description")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("themes", "audiences")
    list_per_page = 25
    save_on_top = True
    actions = ["duplicate", "activate", "deactivate"]
    inlines = [ItineraryInline, SightseeingInline, GalleryInline, HotelInline, ActivityInline, DepartureInline]
    fieldsets = (
        ("Basics", {"fields": ("title", "slug", "tour_code", "destination", "tour_type", "themes", "audiences", ("days", "nights"), "short_description", "overview")}),
        ("Pricing (₹ per person)", {"fields": (("base_price", "child_price", "price_on_request"), ("deluxe_upgrade", "premium_upgrade"), ("discount_percent", "offer_label", "offer_valid_till"))}),
        ("Events & group departures", {"classes": ["collapse"], "fields": ("is_event", "event_name", "event_date", "departure_dates")}),
        ("Media", {"fields": ("cover_image", "cover_url", "youtube_url")}),
        ("Inclusions, exclusions & tour information", {"fields": ("inclusions", "exclusions", "tour_info")}),
        ("Visibility", {"fields": ("is_featured", "is_active")}),
    )

    @admin.display(description="")
    def thumb(self, obj):
        return format_html('<img src="{}" style="width:54px;height:38px;object-fit:cover;border-radius:8px">', obj.cover) if obj.cover else "🌅"

    @admin.action(description="Duplicate selected packages (with itinerary, hotels, etc.)")
    def duplicate(self, request, queryset):
        for pkg in queryset:
            related = {n: list(getattr(pkg, n).all()) for n in ("itinerary", "sightseeing", "gallery", "hotels", "activities", "departure_cities")}
            themes, auds = list(pkg.themes.all()), list(pkg.audiences.all())
            pkg.pk = None
            pkg.slug, pkg.tour_code = "", None
            pkg.title = f"{pkg.title} (copy)"
            pkg.is_active = False
            pkg.save()
            pkg.themes.set(themes)
            pkg.audiences.set(auds)
            for objs in related.values():
                for o in objs:
                    o.pk, o.package = None, pkg
                    o.save()
        self.message_user(request, "Duplicated. Copies are hidden until you tick 'Active'.", messages.SUCCESS)

    @admin.action(description="Show on website")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Hide from website")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(m.Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "state_or_country", "is_popular")
    list_filter = ("region", "is_popular")
    search_fields = ("name", "state_or_country")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_popular",)


@admin.register(m.Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(m.Audience)
class AudienceAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}


class NotificationInline(admin.TabularInline):
    model = m.NotificationLog
    extra = 0
    can_delete = False
    readonly_fields = ("channel", "recipient", "subject", "status", "error", "created")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(m.Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("reference", "created", "name", "phone", "package", "travel_date", "travellers", "total_price", "status")
    list_editable = ("status",)
    list_filter = ("status", "hotel_tier", "package__destination__region", "created")
    search_fields = ("reference", "name", "email", "phone", "package__tour_code", "package__title")
    date_hierarchy = "created"
    readonly_fields = ("reference", "created", "updated", "price_breakdown")
    inlines = [NotificationInline]
    actions = ["mark_booked"]
    fieldsets = (
        ("Customer", {"fields": ("reference", "user", "name", "email", "phone")}),
        ("Trip", {"fields": ("package", "travel_date", ("adults", "children"), "hotel_tier", "departure_city", "activities", "message")}),
        ("Price", {"fields": ("total_price", "price_breakdown")}),
        ("Status", {"description": "Setting status to 'Booked / Confirmed' instantly emails and WhatsApps the customer.", "fields": ("status", "admin_notes", "created", "updated")}),
    )

    @admin.action(description="Mark as Booked and send confirmation (email + WhatsApp)")
    def mark_booked(self, request, queryset):
        n = 0
        for enq in queryset.exclude(status="booked"):
            enq.status = "booked"
            enq.save()
            n += 1
        self.message_user(request, f"{n} booking confirmation(s) sent.", messages.SUCCESS)


@admin.register(m.NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created", "channel", "recipient", "subject", "status")
    list_filter = ("channel", "status")
    search_fields = ("recipient", "subject", "body")
    readonly_fields = [f.name for f in m.NotificationLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(m.SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not m.SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(m.SavedPackage)
class SavedAdmin(admin.ModelAdmin):
    list_display = ("user", "package", "created")


admin.site.register(m.Profile)
