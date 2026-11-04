from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Destination, HomeUpdate, Package


class HomeUpdateTests(TestCase):
    def test_publishing_window_order_and_escaped_content(self):
        today = date(2026, 11, 4)
        first = HomeUpdate.objects.create(title="First <script>", starts_on=today, ends_on=today, order=1)
        second = HomeUpdate.objects.create(title="Second", order=2)
        HomeUpdate.objects.create(title="Hidden", is_active=False)
        HomeUpdate.objects.create(title="Expired", ends_on=today - timedelta(days=1))
        HomeUpdate.objects.create(title="Future", starts_on=today + timedelta(days=1))
        with patch("travel.views.timezone.localdate", return_value=today):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.context["home_updates"], [first, second])
        self.assertContains(response, "First &lt;script&gt;")
        self.assertContains(response, "data-update-next")

    def test_single_text_announcement_has_no_rotation_controls(self):
        HomeUpdate.objects.create(title="Office update", description="Contact us for details")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Office update")
        self.assertNotContains(response, "data-update-next")
        self.assertNotContains(response, "data-update-pause")

    def test_fallback_uses_active_packages_and_deduplicates(self):
        Package.objects.all().delete()
        destination = Destination.objects.create(name="Carousel coast")
        package = Package.objects.create(title="New departure", destination=destination,
                                         short_description="Join us", discount_percent=10,
                                         is_event=True, base_price=10000)
        Package.objects.create(title="Hidden trip", destination=destination,
                               short_description="Hidden", is_active=False, base_price=10000)
        response = self.client.get(reverse("home"))
        updates = response.context["home_updates"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["title"], package.title)
        self.assertEqual(updates[0]["category"], "offer")
        package.is_active = False
        package.save()
        self.assertNotContains(self.client.get(reverse("home")), "data-updates-carousel")

    def test_invalid_publishing_window_is_rejected(self):
        with self.assertRaises(ValidationError):
            HomeUpdate(title="Invalid", starts_on=date(2026, 11, 5), ends_on=date(2026, 11, 4)).full_clean()
