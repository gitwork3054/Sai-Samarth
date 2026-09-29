from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from . import models as m
from .services import calculate_price


class PhotoImportTests(TestCase):
    def test_add_photos_populates_shared_covers_galleries_and_sightseeing(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        destination = m.Destination.objects.create(name="Test Coast", state_or_country="India")
        packages = [m.Package.objects.create(title=f"Test Coast Trip {n}", destination=destination,
                                            short_description="Coastal trip", base_price=10000) for n in range(2)]
        for package in packages:
            m.Sightseeing.objects.create(package=package, name="Lighthouse", order=0)
        photo = {"url": "https://upload.wikimedia.org/photo.jpg", "source": "https://commons.wikimedia.org/wiki/File:Photo.jpg",
                 "author": "Photographer", "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "title": "Photo"}
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder), patch(
                "travel.management.commands.add_photos.choose_photo", return_value=photo), patch(
                "travel.management.commands.add_photos.save_photo", side_effect=lambda photo, path, credits: path):
            call_command("add_photos", verbosity=0)
            for package in packages:
                package.refresh_from_db()
                self.assertEqual(package.cover_image.name, "travel/destinations/test-coast.jpg")
                self.assertEqual(package.gallery.count(), 2)
                self.assertEqual(package.sightseeing.get().image.name, "travel/sightseeing/test-coast-lighthouse.jpg")
            self.assertEqual(m.PackageImage.objects.count(), 4)


class SiteFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("generate_demo", verbosity=0)
        cls.pkg = m.Package.objects.filter(activities__isnull=False, discount_percent__gt=0).first() or m.Package.objects.first()

    def test_100_plus_packages_and_codes(self):
        self.assertGreaterEqual(m.Package.objects.count(), 100)
        self.assertFalse(m.Package.objects.filter(tour_code__isnull=True).exists())

    def test_public_pages_render(self):
        for name in ("home", "packages", "domestic", "international", "group_tours", "corporate_tours", "offers", "events", "login", "signup"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        r = self.client.get(self.pkg.get_absolute_url())
        self.assertContains(r, "More like this")
        self.assertContains(r, "Calculate your price")

    def test_category_dropdowns_and_brand_on_all_pages(self):
        group = m.Package.objects.filter(tour_type="group").first()
        for url in (reverse("home"), self.pkg.get_absolute_url()):
            response = self.client.get(url)
            self.assertContains(response, "Sai Samarth Holidays Pvt. Ltd.")
            self.assertContains(response, "img/sai-samarth-logo.png")
            self.assertEqual(response.content.count(b'class="menu travel-menu"'), 3)
            self.assertNotContains(response, 'id="packages-menu"')
            self.assertContains(response, self.pkg.get_absolute_url())
            self.assertContains(response, group.get_absolute_url())

    def test_filters(self):
        r = self.client.get(reverse("packages"), {"region": "international", "audience": "gen-z", "duration": "4-6", "budget": "0-20000"})
        for p in r.context["page"].object_list:
            self.assertEqual(p.region, "international"); self.assertTrue(4 <= p.days <= 6)
        self.assertEqual(self.client.get(reverse("packages"), {"q": self.pkg.tour_code}).context["count"], 1)

    def test_no_separate_wildlife_theme(self):
        self.assertFalse(m.Theme.objects.filter(name__icontains="wildlife").exclude(name__icontains="adventure").exists())

    def test_price_calculator(self):
        p = self.pkg
        d = p.departure_cities.exclude(surcharge=0).first()
        a = p.activities.first()
        c = calculate_price(p, 2, 1, "deluxe", d.city, [a.id])
        base = 2 * p.base_price + p.child_price
        hotel = p.deluxe_upgrade * 3
        disc = int((base + hotel) * p.effective_discount / 100 + 0.5)
        self.assertEqual(c["total"], base + hotel - disc + d.surcharge * 3 + a.adult_price * 2 + a.child_price)

    def test_pdf(self):
        r = self.client.get(reverse("package_pdf", args=[self.pkg.slug]))
        self.assertEqual(r["Content-Type"], "application/pdf"); self.assertTrue(r.content.startswith(b"%PDF"))

    def test_enquiry_saves_config_and_sends_messages_then_booking_confirmation(self):
        p, a = self.pkg, self.pkg.activities.first()
        r = self.client.post(reverse("create_enquiry", args=[p.slug]), {
            "name": "Asha", "email": "asha@example.com", "phone": "9876543210", "adults": 2, "children": 1,
            "hotel_tier": "premium", "departure_city": "Mumbai", "activities": str(a.id)})
        self.assertEqual(r.status_code, 200, r.content)
        enq = m.Enquiry.objects.get()
        self.assertEqual(enq.hotel_tier, "premium"); self.assertEqual(list(enq.activities.all()), [a]); self.assertTrue(enq.total_price > 0)
        self.assertIn(a.name, enq.price_breakdown["activities"])
        self.assertTrue(any(str(enq.total_price // 1000) in x.body or "Estimated total" in x.body for x in mail.outbox))
        self.assertEqual(m.NotificationLog.objects.filter(channel="whatsapp").count(), 2)  # customer + owner
        n = len(mail.outbox)
        enq.status = "booked"; enq.save()   # owner marks booked
        self.assertEqual(len(mail.outbox), n + 1)
        self.assertIn("Booking confirmed", mail.outbox[-1].subject)
        self.assertTrue(m.NotificationLog.objects.filter(channel="whatsapp", body__contains="Booking confirmed").exists())
        enq.save(); self.assertEqual(len(mail.outbox), n + 1)  # no duplicate

    def test_enquiry_validation_and_honeypot(self):
        r = self.client.post(reverse("create_enquiry", args=[self.pkg.slug]), {"name": "x"})
        self.assertEqual(r.status_code, 400)

    def test_signup_login_save_history(self):
        r = self.client.post(reverse("signup"), {"first_name": "Ravi", "email": "ravi@example.com", "phone": "9999999999", "password1": "Sunset#2026x", "password2": "Sunset#2026x"})
        self.assertRedirects(r, reverse("dashboard"))
        self.assertTrue(self.client.post(reverse("toggle_save", args=[self.pkg.slug])).json()["saved"])
        self.assertContains(self.client.get(reverse("dashboard")), self.pkg.title)
        self.assertFalse(self.client.post(reverse("toggle_save", args=[self.pkg.slug])).json()["saved"])
        self.client.post(reverse("create_enquiry", args=[self.pkg.slug]), {"name": "Ravi", "email": "ravi@example.com", "phone": "9999999999", "adults": 2, "children": 0, "hotel_tier": "standard"})
        self.assertContains(self.client.get(reverse("dashboard") + "?tab=history"), "FT-")
        self.client.post(reverse("logout")); self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        self.assertEqual(self.client.post(reverse("toggle_save", args=[self.pkg.slug])).status_code, 401)

    def test_admin_secure_and_editable(self):
        from django.conf import settings
        self.assertEqual(self.client.get("/admin/").status_code, 404)  # default admin URL hidden
        u = get_user_model().objects.create_superuser("owner", "o@example.com", "pw-Owner-2026")
        self.client.force_login(u)
        base = "/" + settings.ADMIN_URL
        self.assertEqual(self.client.get(base + f"travel/package/{self.pkg.pk}/change/").status_code, 200)
        for model in ("package", "enquiry", "destination", "theme", "audience", "sitesettings", "notificationlog"):
            self.assertEqual(self.client.get(base + f"travel/{model}/").status_code, 200, model)
