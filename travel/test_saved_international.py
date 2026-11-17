from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .flamingo_cards import trip_key
from .models import SavedInternationalTrip


class InternationalSaveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='save-test', password='test-password')
        self.trip = {'title': 'Baltic Test Journey', 'url': 'https://www.flamingotravels.co.in/international-tour-packages/baltic/test/f123', 'duration': '5 Days', 'price': 0, 'image': '', 'code': 'F123', 'country': 'Baltic', 'style': 'individual'}
        self.key = trip_key(self.trip['url'])
        self.trip['save_key'] = self.key
        self.endpoint = reverse('toggle_international_save', args=[self.key])

    def test_login_is_required(self):
        self.assertEqual(self.client.post(self.endpoint).status_code, 401)
        self.assertEqual(SavedInternationalTrip.objects.count(), 0)

    @patch('travel.views.partner_trips')
    def test_save_persists_and_can_be_removed(self, catalog):
        catalog.return_value = {self.key: self.trip}
        self.client.force_login(self.user)
        self.assertTrue(self.client.post(self.endpoint).json()['saved'])
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Baltic Test Journey')
        self.assertContains(response, 'Saved trips (1)')
        self.assertContains(response, self.trip['url'])
        self.assertContains(response, 'aria-pressed="true"')
        self.assertFalse(self.client.post(self.endpoint).json()['saved'])
        self.assertEqual(SavedInternationalTrip.objects.count(), 0)

    @patch('travel.views.partner_trips', return_value={})
    def test_rejects_unknown_trip(self, catalog):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.endpoint).status_code, 404)
        self.assertEqual(SavedInternationalTrip.objects.count(), 0)

    @patch('travel.views.load_catalog')
    def test_international_listing_has_save_control(self, catalog):
        catalog.return_value = {'countries': {'baltic': [self.trip]}}
        response = self.client.get(reverse('international'), {'country': 'baltic'})
        self.assertContains(response, self.endpoint)
        self.assertContains(response, self.trip['url'])
