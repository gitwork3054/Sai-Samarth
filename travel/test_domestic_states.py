from django.test import TestCase
from django.urls import reverse
from .models import Destination, Package
from .domestic_states import domestic_groups


class DomesticStateNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.jaipur = Destination.objects.create(name='State test Jaipur', state_or_country='Rajasthan')
        cls.udaipur = Destination.objects.create(name='State test Udaipur', state_or_country='Rajasthan')
        cls.goa = Destination.objects.create(name='State test Goa', state_or_country='Goa')
        cls.foreign = Destination.objects.create(name='State test foreign', state_or_country='Rajasthan', region='international')
        for number in range(15):
            Package.objects.create(title=f'State test Rajasthan {number:02d}', destination=cls.jaipur if number % 2 else cls.udaipur,
                                   short_description='State test package', base_price=10000 + number)
        Package.objects.create(title='State test Goa trip', destination=cls.goa, short_description='Beach', base_price=12000)
        Package.objects.create(title='State test international trip', destination=cls.foreign, short_description='Foreign', base_price=50000)
        Package.objects.create(title='State test hidden', destination=cls.jaipur, short_description='Hidden', base_price=9000, is_active=False)

    def test_domestic_menu_and_landing_list_states_without_tour_titles(self):
        response = self.client.get(reverse('domestic'))
        self.assertTemplateUsed(response, 'travel/domestic_states.html')
        self.assertContains(response, '?state=rajasthan')
        self.assertNotContains(response, 'State test Rajasthan 00')
        self.assertEqual(sum(1 for g in response.context['states'] if g['name'] == 'Rajasthan'), 1)
        menu = response.content.decode().split('<summary>Domestic</summary>', 1)[1].split('</details>', 1)[0]
        self.assertIn('Rajasthan', menu)
        self.assertNotIn('State test Jaipur', menu)
        self.assertNotIn('State test Rajasthan', menu)

    def test_selected_state_includes_all_destinations_and_preserves_pagination_filters(self):
        response = self.client.get(reverse('domestic'), {'state':'rajasthan', 'sort':'price_low'})
        self.assertEqual(response.context['count'], 15)
        self.assertContains(response, 'Rajasthan tour packages')
        self.assertContains(response, 'name="state" value="rajasthan"')
        self.assertContains(response, 'state=rajasthan&amp;sort=price_low&amp;page=2')
        pages = [response, self.client.get(reverse('domestic'), {'state':'rajasthan','sort':'price_low','page':2})]
        self.assertEqual(sum(len(r.context['page'].object_list) for r in pages), 15)
        for r in pages:
            for package in r.context['page'].object_list:
                self.assertIn(package.destination_id, [self.jaipur.pk, self.udaipur.pk])
                self.assertTrue(package.is_active)
        result = self.client.get(reverse('domestic'), {'state':'rajasthan','q':'00'})
        self.assertEqual(result.context['count'], 1)
        self.assertEqual(self.client.get(reverse('domestic'), {'state':'invalid-state'}).status_code, 404)

    def test_aliases_and_multi_state_routes_are_grouped_consistently(self):
        destination = Destination.objects.create(name='State test circuit', state_or_country='West Bengal & Sikkim')
        package = Package.objects.create(title='State test circuit trip', destination=destination, short_description='Circuit', base_price=15000)
        names = [g['name'] for g in domestic_groups([package])]
        self.assertEqual(names, ['Sikkim','West Bengal'])
        for slug in ('west-bengal','sikkim'):
            result = self.client.get(reverse('domestic'), {'state':slug})
            self.assertIn(package.pk, result.context['page'].paginator.object_list.values_list('pk',flat=True))
