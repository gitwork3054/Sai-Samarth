import io
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase
from unittest import skipUnless
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
from travel.models import Package, SiteSettings
from travel.pdf import build_itinerary_pdf


@skipUnless(PdfReader, 'Install pypdf for PDF text verification')
class ItineraryBrochureTests(TestCase):
    def test_all_imported_itineraries_export_complete_with_unicode_and_bullets(self):
        site = SiteSettings.get()
        for package in Package.objects.filter(tour_type='group', is_active=True):
            with self.subTest(package=package.title), patch('travel.pdf._photo', return_value=None):
                reader = PdfReader(io.BytesIO(build_itinerary_pdf(package, site)))
                self.assertGreaterEqual(len(reader.pages), 2)
                texts = [page.extract_text() for page in reader.pages]
                all_text = ' '.join(' '.join(texts).split())
                self.assertIn('YOUR HOLIDAY ITINERARY', texts[0])
                self.assertIn('YOUR VACATION AT A GLANCE', texts[1])
                self.assertIn('Price on request' if package.price_on_request else f'₹{package.price_from:,}', all_text)
                for day in package.itinerary.all():
                    self.assertIn(f'DAY {day.day_number:02d}', all_text)
                    # All source words survive line wrapping and the pointer formatting.
                    for word in day.description.split():
                        self.assertIn(word, all_text)
                self.assertIn('•', all_text)
                for page in reader.pages:
                    for font in page['/Resources']['/Font'].values():
                        self.assertIn('Font', font.get_object()['/Type'])
