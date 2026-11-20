"""Brochures use the actual package data and are downloadable for any local tour."""
import io
from unittest.mock import patch
from django.test import TestCase
from travel import models as m
from travel.cinematic_pdf import build_cinematic_pdf, W, H

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class CinematicPdfTests(TestCase):
    def setUp(self):
        self.destination=m.Destination.objects.create(name="Jaipur",state_or_country="Rajasthan",region="domestic")
        self.pkg=m.Package.objects.create(destination=self.destination,title="Jaipur Heritage Weekend",
            tour_code="FTD-T01",short_description="Explore Jaipur's heritage.",
            overview="Visit forts and gardens around Jaipur.",nights=2,days=3,base_price=10500,
            inclusions="Hotel stay\nGround transportation",exclusions="Flights\nPersonal shopping",
            tour_info="Availability: Confirm before booking")
        m.ItineraryDay.objects.create(package=self.pkg,day_number=1,title="City arrival",
            description="Arrive and explore Hawa Mahal.",stay="Jaipur",meals="Dinner")
        m.ItineraryDay.objects.create(package=self.pkg,day_number=2,title="Fort day",
            description="Visit historic Amber Fort.",stay="Jaipur",meals="Breakfast")
        m.ItineraryDay.objects.create(package=self.pkg,day_number=3,title="Departure",
            description="Depart from Jaipur.",meals="Breakfast")
        m.Sightseeing.objects.create(package=self.pkg,name="Amber Fort",description="Historic Jaipur fortress.")
        self.site=m.SiteSettings.get()

    def get_pdf(self):
        with patch("travel.cinematic_pdf.matched_photo",return_value=(None,None)):
            return build_cinematic_pdf(self.pkg,self.site)

    def test_correct_document_with_all_package_details(self):
        raw=self.get_pdf()
        self.assertTrue(raw.startswith(b"%PDF"))
        if PdfReader:
            reader=PdfReader(io.BytesIO(raw))
            self.assertGreaterEqual(len(reader.pages),5)
            self.assertEqual(float(reader.pages[0].mediabox.width),W)
            self.assertEqual(float(reader.pages[0].mediabox.height),H)
            all_text=" ".join(p.extract_text() or "" for p in reader.pages)
            for phrase in ("JAIPUR","Jaipur Heritage Weekend","Hawa Mahal","Amber Fort",
                           "DAY 01","DAY 02","Hotel stay","Ground transportation",
                           "Flights","10,500"):
                self.assertIn(phrase,all_text)

    def test_long_itinerary_does_not_truncate(self):
        day=self.pkg.itinerary.get(day_number=2)
        day.description=" ".join(["Explore culture and local scenery."]*140)
        day.save(update_fields=["description"])
        if PdfReader:
            text=" ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(self.get_pdf())).pages)
            self.assertEqual(" ".join(text.split()).count("Explore culture and local scenery."),140)

    def test_download_is_pdf_attachment(self):
        with patch("travel.cinematic_pdf.matched_photo",return_value=(None,None)):
            response=self.client.get("/package/"+self.pkg.slug+"/pdf/")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response["Content-Type"],"application/pdf")
        self.assertIn("attachment",response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
