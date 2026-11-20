"""Brochures use the actual package data and are downloadable for any local tour."""
import io
from unittest.mock import patch
import json
import hashlib
from pathlib import Path
from django.conf import settings
from django.test import TestCase
from travel import models as m
from travel.cinematic_pdf import build_cinematic_pdf, matched_photo, W, H

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
            self.assertEqual(len(__import__("re").findall(r"\bscenery\b", text)),140)

    def test_download_is_pdf_attachment(self):
        with patch("travel.cinematic_pdf.matched_photo",return_value=(None,None)):
            response=self.client.get("/package/"+self.pkg.slug+"/pdf/")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response["Content-Type"],"application/pdf")
        self.assertIn("attachment",response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))


class AllDestinationPhotoTests(TestCase):
    def test_every_catalogue_cover_is_approved_and_matches_its_licensed_asset(self):
        folder = Path(settings.BASE_DIR)
        data = json.loads((folder/"travel/data/pdf_destination_photos.json").read_text())
        self.assertEqual(data["approved_cover_count"], len(data["photos"]))
        self.assertGreaterEqual(len(data["photos"]), 50)
        for city, entry in data["photos"].items():
            with self.subTest(city=city):
                self.assertEqual(entry.get("cover_review_status"), "approved")
                self.assertIn("commons.wikimedia.org/wiki/File:", entry["source_url"])
                file = folder/entry["file"]
                self.assertTrue(file.is_file())
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),entry["sha256"])

    def test_shimla_uses_hills_not_police_traffic(self):
        city = m.Destination.objects.create(name="Shimla", region="domestic",
                                            state_or_country="Himachal Pradesh")
        package = m.Package.objects.create(
            destination=city,title="Shimla Corporate Getaway",tour_code="TEST-SH",
            base_price=15000,days=5,nights=4,
            cover_url="https://upload.wikimedia.org/anything-unreviewed.jpg")
        photo,credit=matched_photo(package)
        self.assertIsNotNone(photo)
        self.assertEqual(photo.name,"shimla.jpg")
        self.assertIn("Panoramic_view_of_Shimla_hills",credit)
        self.assertNotIn("Mall_Road_Shimla",credit)

    def test_unreviewed_uploads_and_external_urls_are_not_pdf_covers(self):
        city=m.Destination.objects.create(name="Imaginary Lake City",region="domestic",
                                          state_or_country="Unknown Region")
        package=m.Package.objects.create(destination=city,title="Imaginary Lake Tour",
                                         days=3,nights=2,base_price=5000,
                                         cover_url="https://upload.wikimedia.org/unknown.jpg")
        image,credit=matched_photo(package)
        self.assertIsNone(image)
        self.assertIsNone(credit)

    def test_ayodhya_riverside_cover_is_licensed_and_actually_renderable(self):
        city=m.Destination.objects.create(name="Ayodhya",region="domestic",
                                          state_or_country="Uttar Pradesh")
        pkg=m.Package.objects.create(destination=city,title="Spiritual Ayodhya",
                                     days=3,nights=2,base_price=11000)
        photo,credit=matched_photo(pkg)
        self.assertIsNotNone(photo)
        self.assertEqual(photo.name,"ayodhya.jpg")
        self.assertIn("Saryu",credit)
        self.assertIn("CC BY-SA 4.0",credit)

    def test_all_imported_private_van_routes_have_a_reviewed_city_photo(self):
        data=json.loads((Path(settings.BASE_DIR)/"travel/data/pdf_destination_photos.json").read_text())
        photos=data["photos"]
        tours=json.loads((Path(settings.BASE_DIR)/"travel/data/flamingo_domestic_private_vans.json").read_text())
        for row in tours["packages"]:
            with self.subTest(tour=row["tour_code_supplier"]):
                candidates=[s["city"] for s in row["route"] if s.get("city")]
                self.assertTrue(any(
                    c in photos and
                    photos[c].get("cover_review_status")=="approved" and
                    str(photos[c].get("license","")).lower().startswith(
                        ("cc by", "cc0", "public domain")
                    ) and bool(photos[c].get("sha256"))
                    for c in candidates
                ), "No usable photo for "+row["title"])
