"""Validation for sourced, independently written private-van catalogue imports."""
import json
import os
import tempfile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from travel import models as m
from travel.management.commands.import_flamingo_domestic_private import (
    independently_written_days, validated_records,
)

SOURCE = "https://www.flamingotravels.co.in/india-tour-packages/himachal-pradesh-holiday-tour-packages/scenic-himachal-7nights/f1360"


def example_row():
    return {
        "source_url": SOURCE, "supplier": "Flamingo Travels",
        "title": "Scenic Himachal", "tour_code_supplier": "FIT/1360",
        "type": "private_van", "region_label": "Himachal Pradesh",
        "category": "himachal-pradesh",
        "days": 3, "nights": 2,
        "route": [{"city": "Shimla", "nights": 1}, {"city": "Manali", "nights": 1}],
        "sightseeing": [{"city": "Shimla", "name": "Kufri Valley"},
                        {"city": "Manali", "name": "Solang Valley"}],
        "hotel_examples": [], "meals": {"breakfast": 2},
        "day_headings": {}, "private_vehicle_mentioned": True,
        "flight_not_included": False, "starting_price_inr": 15000,
        "valid_from": "2027-04-01", "valid_until": "2027-09-30",
        "listed_states": ["Himachal Pradesh","Rajasthan"],
        "source_categories": ["himachal-pradesh","rajasthan"],
        "price_source": "supplier catalogue listing", "tags": [],
    }


class DomesticPrivateVanTests(TestCase):
    def test_fact_validation_rejects_international_and_bad_routes(self):
        row = example_row()
        self.assertEqual(len(validated_records({"kind": "indian_domestic_private_van_facts", "packages": [row]}, 1)), 1)
        row["source_url"] = row["source_url"].replace("www.flamingotravels.co.in", "another.example")
        with self.assertRaises(CommandError):
            validated_records({"kind": "indian_domestic_private_van_facts", "packages": [row]}, 1)
        row = example_row()
        row["route"][0]["nights"] = 2
        with self.assertRaises(CommandError):
            validated_records({"kind": "indian_domestic_private_van_facts", "packages": [row]}, 1)

    def test_independent_wording_and_last_day(self):
        days = list(independently_written_days(example_row()))
        self.assertEqual(len(days), 3)
        self.assertIn("Shimla", days[0]["description"])
        self.assertIn("Manali", days[1]["description"])
        self.assertEqual(days[2]["stay"], "")
        self.assertNotIn("Get ready for tour", " ".join(x["description"] for x in days))

    def test_structured_day_facts_preserve_meals_and_place_names(self):
        row = example_row()
        row["day_facts"]=[
            {"day_number":1,"route_label":"Shimla","meals":"Dinner","attractions":["Kufri Valley"]},
            {"day_number":2,"route_label":"Shimla to Manali","meals":"Breakfast, Dinner","attractions":["Solang Valley"]},
            {"day_number":3,"route_label":"Manali Departure","meals":"Breakfast","attractions":[]},
        ]
        days=list(independently_written_days(row))
        self.assertEqual(days[0]["meals"],"Dinner")
        self.assertIn("Kufri Valley",days[0]["description"])
        self.assertIn("Solang Valley",days[1]["description"])
        self.assertEqual(days[2]["meals"],"Breakfast")

    def test_northeast_circuit_has_its_own_directory_group(self):
        from travel.domestic_states import destination_states
        dest=m.Destination(name="North East India",region="domestic",state_or_country="North East India")
        self.assertEqual(destination_states(dest), ["North East India"])

    def test_import_preserves_group_and_removes_only_demo(self):
        dest = m.Destination.objects.create(name="Goa", region="domestic", state_or_country="Goa")
        demo = m.Package.objects.create(
            destination=dest, title="Goa Family Holiday", short_description="test",
            overview="This is a demo description: edit it in the admin panel.",
            base_price=19999, tour_type="individual")
        group = m.Package.objects.create(
            destination=dest, title="Goa Group Tour", short_description="group trip",
            overview="Real group details", base_price=12000, tour_type="group")
        manual = m.Package.objects.create(
            destination=dest, title="Custom Goa Escape", short_description="private tailored",
            overview="Original independently designed trip", base_price=17500, tour_type="individual")
        row = example_row()
        snapshot = {"kind": "indian_domestic_private_van_facts", "retrieved_at": "2026-11-20T06:00:00Z",
                    "packages": [row]}
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as out:
                json.dump(snapshot, out)
            call_command("import_flamingo_domestic_private", "--file", path, "--min-records", "1")
            demo.refresh_from_db()
            group.refresh_from_db()
            manual.refresh_from_db()
            imported = m.Package.objects.get(source_url=SOURCE)
            self.assertFalse(demo.is_active)
            self.assertTrue(group.is_active)
            self.assertTrue(manual.is_active)
            self.assertTrue(imported.is_active)
            self.assertEqual(imported.base_price, 15000)
            self.assertEqual(imported.itinerary.count(), 3)
            self.assertEqual(imported.sightseeing.count(), 2)
            self.assertEqual(imported.tour_type, "individual")
            self.assertTrue(imported.cover_url or imported.destination.name)
            from travel.domestic_states import domestic_groups
            groups = domestic_groups(m.Package.objects.filter(
                destination__region="domestic", is_active=True
            ).select_related("destination"))
            rajasthan = next(group for group in groups if group["slug"] == "rajasthan")
            self.assertIn(imported.pk, rajasthan["package_ids"])
            self.assertEqual(imported.source_details["listed_states"], ["Himachal Pradesh", "Rajasthan"])
            self.assertEqual(imported.audiences.count(), 1)
            self.assertEqual(imported.source_details["original_code"], "FIT/1360")
            call_command("import_flamingo_domestic_private", "--file", path, "--min-records", "1")
            self.assertEqual(m.Package.objects.filter(source_url=SOURCE).count(), 1)
        finally:
            os.remove(path)
