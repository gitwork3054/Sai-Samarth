import json
from pathlib import Path
from unittest.mock import patch
from django.apps import apps
from django.core.management import call_command
from django.test import TestCase
from travel.models import Package, Destination, ItineraryDay
from travel.services import calculate_price


class GroupImportTests(TestCase):
    def setUp(self):
        self.source = json.loads((Path(__file__).parent / 'data/akhilbharat_group_tours.json').read_text())

    def test_every_detail_and_day_matches_source_and_reruns_are_safe(self):
        dest = Destination.objects.create(name='Legacy place')
        old = Package.objects.create(title='Legacy group', destination=dest, tour_type='group', short_description='Old', base_price=1)
        custom = Package.objects.create(title='Custom holiday', destination=dest, short_description='Custom', base_price=2)
        call_command('import_group_tours', verbosity=0)
        call_command('import_group_tours', verbosity=0)
        old.refresh_from_db(); custom.refresh_from_db()
        self.assertFalse(old.is_active); self.assertTrue(custom.is_active)
        tours = Package.objects.filter(tour_type='group', is_active=True)
        self.assertEqual(tours.count(), 27)
        self.assertEqual(ItineraryDay.objects.filter(package__in=tours).count(), 212)
        for row in self.source['packages']:
            tour = tours.get(source_details__package_url=row['package_url'])
            self.assertEqual(tour.source_details, row)
            self.assertEqual(tour.title, row['name'])
            self.assertEqual(tour.duration_label, row['duration'])
            self.assertEqual(tour.cover, row['image_url'])
            self.assertEqual(tour.price_on_request, not bool(row['price']))
            expected = [d for d in self.source['itinerary_days'] if d['package_url'] == row['package_url']]
            self.assertEqual([(d.title, d.description) for d in tour.itinerary.all()], [(d['title'],d['description']) for d in expected])
            html = self.client.get(tour.get_absolute_url())
            self.assertEqual(html.status_code, 200)
            for day in expected:
                from django.utils.html import escape
                self.assertContains(html, escape(day['title']), html=False)
            with patch('travel.pdf._photo', return_value=None):
                self.assertEqual(self.client.get(tour.get_absolute_url() + 'pdf/').status_code, 200)

    def test_missing_and_child_prices_require_quote(self):
        call_command('import_group_tours', verbosity=0)
        tour = Package.objects.filter(price_on_request=True).first()
        self.assertTrue(calculate_price(tour, 2, 0)['price_on_request'])
        self.assertEqual(calculate_price(tour, 2, 0)['total'], 0)
        known = Package.objects.filter(tour_type='group', price_on_request=False).first()
        self.assertEqual(calculate_price(known, 2, 0)['total'], 2 * known.base_price)
        self.assertTrue(calculate_price(known, 2, 1)['price_on_request'])
        with patch('travel.views.notify_enquiry_received'):
            response = self.client.post(tour.get_absolute_url() + 'enquiry/', {
                'name': 'Test Traveller', 'email': 'test@example.com', 'phone': '9510088833',
                'adults': 2, 'children': 0, 'hotel_tier': 'standard', 'activities': '', 'website': '',
            })
        self.assertEqual(response.status_code, 200)
