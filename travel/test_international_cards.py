import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .flamingo_cards import parse_cards


class InternationalCardTests(TestCase):
    def setUp(self):
        self.url = "https://www.flamingotravels.co.in/international-tour-packages/bali-holiday-tour-packages/bali-escape-7nights/g2357"
        self.card = dict(title="Bali Escape", url=self.url, image="", duration="7 Nights / 8 Days",
                         days=8, price=100000, code="G2357", style="group",
                         style_label="Group Tour", cities="Bali", flight="Main Flight Included")
        self.catalogue = {"countries": {"bali": [self.card], "japan": [
            {**self.card, "title": "Japan Journey", "url": self.url.replace("bali", "japan"), "price": 200000}
        ]}}
        self.loader = patch("travel.views.load_catalog", return_value=self.catalogue)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_directory_and_menu_link_to_local_country_listing(self):
        response = self.client.get(reverse("international"))
        self.assertTemplateUsed(response, "travel/international_countries.html")
        self.assertContains(response, 'href="/international/?country=bali"')
        self.assertNotContains(response, 'href="https://www.flamingotravels.co.in/international-tour-packages/bali-holiday-tour-packages"')

    def test_country_page_contains_only_its_trips_and_exact_partner_links(self):
        response = self.client.get(reverse("international"), {"country": "bali"})
        self.assertTemplateUsed(response, "travel/international_trips.html")
        self.assertEqual(response.context["count"], 1)
        self.assertEqual(response.context["page"].object_list[0]["title"], "Bali Escape")
        self.assertContains(response, 'href="' + self.url + '" target="_blank" rel="noopener"')
        self.assertContains(response, "Bali tour packages")
        self.assertContains(response, "₹1,00,000")

    def test_filters_sort_and_pagination_keep_country(self):
        self.catalogue["countries"]["bali"] = [
            {**self.card, "title": f"Bali {i}", "url": self.url + str(i), "price": 100000 + i}
            for i in range(14)
        ]
        response = self.client.get(reverse("international"), {"country": "bali", "sort": "price_high"})
        self.assertEqual(response.context["page"].object_list[0]["price"], 100013)
        self.assertContains(response, "country=bali&amp;sort=price_high&amp;page=2")
        response = self.client.get(reverse("international"), {"country": "bali", "budget": "0-20000"})
        self.assertEqual(response.context["count"], 0)
        response = self.client.get(reverse("international"), {"country": "bali", "duration": "7-9", "tour_type": "group", "q": "Bali"})
        self.assertEqual(response.context["count"], 14)

    def test_invalid_country_and_empty_destination(self):
        self.assertEqual(self.client.get(reverse("international"), {"country": "made-up"}).status_code, 404)
        response = self.client.get(reverse("international"), {"country": "taiwan"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No trips match this selection")

    def test_unpublished_price_and_html_are_handled(self):
        self.catalogue["countries"]["bali"] = [{**self.card, "title": "<script>Trip</script>", "price": 0}]
        response = self.client.get(reverse("international"), {"country": "bali"})
        self.assertContains(response, "&lt;script&gt;Trip&lt;/script&gt;")
        self.assertContains(response, "Price on request")

    def test_parser_reads_real_next_data_fields_and_rejects_external_urls(self):
        row = dict(name="Bali Escape", pageSlug=self.url, totalDays="7 Nights / 8 Days",
                   imageNamePath="Images/City/bali.jpg", sellingPrice="106360",
                   isSellingPricePublish="1", currencySymbol="&#x20b9;", typeOfTour="Group Tour")
        rows = [row, row, {**row, "pageSlug": "https://example.test/itinerary"}]
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"props": {"pageProps": {"packageCount": rows}}}) + "</script>"
        cards = parse_cards(html)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["url"], self.url)
        self.assertEqual(cards[0]["price"], 106360)
        self.assertEqual(cards[0]["days"], 8)
        self.assertEqual(cards[0]["image"], "https://imgcdn.flamingotravels.co.in/Images/City/bali.jpg")
