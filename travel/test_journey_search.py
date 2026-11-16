from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from .models import Destination, Package


class JourneySearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        destination = Destination.objects.create(name='Helper Test Coast', state_or_country='Kerala', region='domestic')
        Package.objects.create(title='Helper Test Kerala Escape', destination=destination, short_description='Sample', base_price=10000)

    def test_domestic_suggestion_and_results(self):
        response = self.client.get(reverse('journey_search'), {'q': 'Kerala'})
        self.assertTrue(any(item['title'] == 'Helper Test Kerala Escape' for item in response.json()['results']))
        self.assertContains(self.client.get(reverse('journey_results'), {'q': 'Kerala'}), 'Helper Test Kerala Escape')

    def test_international_search_uses_internal_destination_and_partner_cards(self):
        card = {'title': 'Vietnam Discovery', 'code': 'V123', 'cities': 'Hanoi', 'url': 'https://www.flamingotravels.co.in/trip', 'duration': '5 Days', 'price': 0, 'image': ''}
        with patch('travel.integration_views.load_catalog', return_value={'countries': {'vietnam': [card]}}):
            response = self.client.get(reverse('journey_search'), {'q': 'Vietnam'})
            results = response.json()['results']
            self.assertTrue(any(item['url'].startswith('/international/?country=vietnam') for item in results))
            self.assertTrue(any(item['url'].startswith('/international/?q=V123') for item in results))
            page = self.client.get(reverse('journey_results'), {'q': 'Vietnam'})
            self.assertContains(page, 'Vietnam Discovery')
            self.assertContains(page, card['url'])

    def test_short_query(self):
        self.assertEqual(self.client.get(reverse('journey_search'), {'q': 'v'}).json()['results'], [])
        self.assertContains(self.client.get(reverse('journey_results'), {'q': 'v'}), 'Enter at least two characters')
