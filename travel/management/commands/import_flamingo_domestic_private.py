"""Import factual domestic private-van data; publish original summaries, not copied prose.

The reference snapshot is prepared from supplier pages by a separate GitHub Action.
This command never downloads a partner page during web-service startup. Never
disable source-specific group tours or remove past enquiries when refreshing.
"""
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from travel import models as m

DATA_PATH = Path(__file__).resolve().parents[2] / "data/flamingo_domestic_private_vans.json"
SOURCE_HOST = "www.flamingotravels.co.in"
DEMO_MARKER = "This is a demo description:"
REGION_FIXES = {
    "Andaman Holiday Tour Package": "Andaman & Nicobar",
    "Golden Triangle Tour Packages": "Delhi / Agra / Rajasthan",
    "West Bengal Sikkim": "West Bengal & Sikkim",
}


def validated_records(snapshot, minimum):
    if snapshot.get("kind") != "indian_domestic_private_van_facts":
        raise CommandError("Unexpected or incomplete domestic supplier snapshot.")
    rows = snapshot.get("packages", [])
    if len(rows) < minimum:
        raise CommandError(f"Refusing to hide demos: {len(rows)} verified tours; need at least {minimum}.")
    seen = set()
    result = []
    for row in rows:
        url = row.get("source_url", "")
        match = re.fullmatch(
            r"/india-tour-packages/[^/]+/[^/]+/f(\d+)",
            urlparse(url).path, flags=re.I
        )
        if urlparse(url).hostname != SOURCE_HOST or not match:
            raise CommandError(f"Unexpected source URL for package {row.get('title', '')[:60]}")
        if row.get("type") != "private_van":
            raise CommandError("Only verified Private Van Tour products may be imported.")
        nights = int(row.get("nights", 0))
        days = int(row.get("days", 0))
        route = row.get("route", [])
        if not (1 <= nights <= 24 and days == nights + 1 and
                sum(int(stop["nights"]) for stop in route) == nights):
            raise CommandError(f"Invalid overnight route for {row.get('title', '')}.")
        if match.group(1) in seen:
            raise CommandError("Duplicate partner tour code: " + match.group(1))
        seen.add(match.group(1))
        result.append(row)
    return result


def night_plan(route):
    """One genuine overnight location per night, followed by final departure."""
    nights = []
    for stop in route:
        nights.extend([stop["city"]] * int(stop["nights"]))
    return nights


def independently_written_days(row):
    nights = night_plan(row["route"])
    source_headings = row.get("day_headings", {})
    attractions_by_city = {}
    for place in row.get("sightseeing", []):
        city = place.get("city", "").strip().casefold()
        if city:
            attractions_by_city.setdefault(city, []).append(place.get("name", "").strip())
    for day_number in range(1, int(row["days"]) + 1):
        if day_number == len(nights) + 1:
            previous = nights[-1]
            yield {
                "day_number": day_number,
                "title": f"Complete the journey from {previous}",
                "description": (
                    f"The final day marks the end of the published route after {previous}. "
                    "Check your confirmed travel documents for departure timing and onward transfer arrangements."
                ),
                "stay": "",
                "meals": "",
            }
            continue
        city = nights[day_number - 1]
        previous = nights[day_number - 2] if day_number > 1 else ""
        first_here = day_number == 1 or city != previous
        if day_number == 1:
            title = f"Begin your holiday in {city}"
            lead = f"The first overnight stop on this route is {city}. "
        elif first_here:
            title = f"Continue from {previous} to {city}"
            lead = f"The overnight route moves from {previous} to {city}. "
        else:
            title = f"Explore the {city} region"
            lead = f"This part of the journey is based in {city}. "
        attractions = attractions_by_city.get(city.lower(), [])
        if len(attractions) > 1:
            # Place names are geographical facts; do not invent day-specific inclusions.
            attractions_text = (
                f"The published sightseeing overview mentions {attractions[0]} and {attractions[1]} "
                f"in the {city} area; please confirm the day and whether tickets are included. "
            )
        elif attractions:
            attractions_text = (
                f"The published sightseeing overview also identifies {attractions[0]} in this region. "
            )
        else:
            attractions_text = ""
        description = (
            lead + attractions_text +
            "Daily stops, hotel check-in arrangements and admission costs are subject to the final confirmed itinerary."
        )
        yield {
            "day_number": day_number, "title": title,
            "description": description, "stay": city, "meals": "",
        }


def package_overview(row):
    route = ", ".join(f"{entry['city']} ({entry['nights']} nights)" for entry in row["route"])
    return (
        f"An independently written {row['days']}-day private-vehicle holiday outline following "
        f"the published overnight route: {route}. This page presents verifiable destination "
        "facts rather than a copy of the supplier's descriptive text. The actual hotel, "
        "sightseeing sequence, transport details and final price will be confirmed in your enquiry."
    )


def fact_based_terms(row):
    included = []
    if row.get("hotel_examples"):
        included.append("Hotel accommodation according to the selected itinerary; property options are not guaranteed.")
    if row.get("private_vehicle_mentioned"):
        included.append("Private vehicle for transfers and sightseeing where indicated in the supplier's itinerary.")
    for meal in ("breakfast", "lunch", "dinner"):
        amount = int(row.get("meals", {}).get(meal) or 0)
        if amount:
            included.append(f"{amount} {meal} meal(s), as listed in the supplier's overview.")
    excluded = []
    if row.get("flight_not_included"):
        excluded.append("Airfare is not included in the published starting price.")
    price = int(row.get("starting_price_inr", 0) or 0)
    expiry = row.get("valid_until") or ""
    info = [
        "Source: Public Flamingo Travels tour listing; no booking is confirmed through this page",
        "Supplier tour code: " + row["tour_code_supplier"],
        "Price status: Published starting amount is indicative, not a Sai Samarth confirmed quotation",
        "Price validity: " + (expiry or "Not provided; confirm with travel team"),
        "Checked: " + timezone.localdate().isoformat(),
        "Travel style: Private vehicle tour; confirm vehicle size for your party",
        "Conditions: Hotel availability, optional entries, route timings and tax are reconfirmed before booking",
    ]
    if price:
        info.insert(3, f"Published starting amount: INR {price:,} per person (subject to change)")
    return "\n".join(included), "\n".join(excluded), "\n".join(info)


def audience_labels(row):
    title = row.get("title", "").lower()
    tags = " ".join(row.get("tags", [])).lower()
    labels = ["Family"]
    if any(x in title + " " + tags for x in ("honeymoon", "romantic", "couple")):
        labels.append("Couple")
    return labels


class Command(BaseCommand):
    help = "Replace only domestic autogenerated Individual/Family/Couple demos with verified, copyright-safe private-van tour facts."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DATA_PATH))
        parser.add_argument("--min-records", type=int, default=12)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            # The first code deploy may precede the snapshot-writing GitHub Action.
            self.stdout.write("No verified private van snapshot yet; demo data retained.")
            return
        snapshot = json.loads(file_path.read_text(encoding="utf-8"))
        records = validated_records(snapshot, options["min_records"])
        if options["dry_run"]:
            prices = sum(bool(r.get("starting_price_inr")) for r in records)
            self.stdout.write(f"Verified {len(records)} private-van records ({prices} with published prices); no changes made.")
            return

        family, _ = m.Audience.objects.get_or_create(
            name="Family", defaults={"description": "Travel with family and friends"}
        )
        couple, _ = m.Audience.objects.get_or_create(
            name="Couple", defaults={"description": "Holidays for two"}
        )
        updated = 0
        skipped = 0
        with transaction.atomic():
            for order, row in enumerate(records, 1):
                source = row["source_url"]
                code = re.search(r"/f(\d+)$", urlparse(source).path).group(1)
                external_code = f"SPV-{code}"
                digest = hashlib.sha256(
                    json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest()[:20]
                state = REGION_FIXES.get(row["region_label"], row["region_label"])[:80]
                dest, _ = m.Destination.objects.get_or_create(
                    name=state, defaults={
                        "region": "domestic", "state_or_country": state,
                        "tagline": "Private-vehicle holiday routes",
                    }
                )
                if dest.region != "domestic":
                    raise CommandError(f"Destination {dest.name} is not domestic.")
                package = m.Package.objects.filter(source_url=source).first()
                if not package:
                    package = m.Package.objects.filter(tour_code=external_code).first()
                if (package and
                        (package.source_details or {}).get("sync_fingerprint") == digest):
                    skipped += 1
                    continue
                if not package:
                    package = m.Package(
                        slug=f"private-van-{code}-{slugify(row['title'])[:75]}",
                        tour_code=external_code,
                        destination=dest,
                    )
                amount = int(row.get("starting_price_inr", 0) or 0)
                valid = row.get("valid_until")
                expiry = None
                if valid:
                    try:
                        expiry = date.fromisoformat(valid)
                    except ValueError:
                        expiry = None
                note = f"Reference amount ₹{amount:,} per person; final rate subject to availability." if amount else "Current amount confirmed on enquiry."
                details = {
                    "provider": "flamingo",
                    "catalogue_kind": "domestic_private_van",
                    "managed_by": "sai_samarth_private_van_import",
                    "original_code": row["tour_code_supplier"],
                    "route": row["route"],
                    "duration": f"{row['nights']} Nights / {row['days']} Days",
                    "price_source": row.get("price_source", ""),
                    "valid_until": valid,
                    "price_note": note,
                    "synced_at": snapshot.get("retrieved_at"),
                    "sync_fingerprint": digest,
                }
                inclusions, exclusions, info = fact_based_terms(row)
                package.destination = dest
                package.title = row["title"][:160]
                package.tour_type = "individual"
                package.days, package.nights = int(row["days"]), int(row["nights"])
                package.short_description = (
                    f"{row['days']}-day independent private-vehicle route across "
                    f"{', '.join(stop['city'] for stop in row['route'])}. {note}"
                )[:240]
                package.overview = package_overview(row)
                package.source_details = details
                package.base_price = amount
                package.price_on_request = not amount or bool(expiry and expiry < timezone.localdate())
                package.child_price = package.infant_price = 0
                package.deluxe_upgrade = package.premium_upgrade = 0
                package.discount_percent = 0
                package.offer_label = ""
                package.offer_valid_till = None
                package.source_url = source
                # Never copy supplier-owned photographs or thumbnails by default.
                package.cover_url = ""
                package.inclusions = inclusions
                package.exclusions = exclusions
                package.tour_info = info
                package.display_order = order + 10
                package.is_featured = order <= 9
                package.is_active = True
                package.save()
                package.audiences.set([family, couple] if "Couple" in audience_labels(row) else [family])
                package.itinerary.all().delete()
                m.ItineraryDay.objects.bulk_create(
                    [m.ItineraryDay(package=package, **day) for day in independently_written_days(row)]
                )
                package.sightseeing.all().delete()
                m.Sightseeing.objects.bulk_create([
                    m.Sightseeing(
                        package=package, name=spot["name"][:120], order=index,
                        description="A place listed in the published sightseeing overview. Confirm timing and ticket arrangements."
                    )
                    for index, spot in enumerate(row.get("sightseeing", [])[:80], 1)
                    if spot.get("name")
                ])
                package.hotels.all().delete()
                m.Hotel.objects.bulk_create([
                    m.Hotel(
                        package=package, tier="standard", name=hotel["example"][:120],
                        city=hotel["city"][:80], nights=int(hotel["nights"]),
                        star_rating=0,
                        description="Example property from a public supplier listing, not an allocation or booking guarantee."
                    )
                    for hotel in row.get("hotel_examples", [])[:12] if hotel.get("example")
                ])
                package.departure_cities.all().delete()
                package.activities.all().delete()
                updated += 1
            # Protect previously placed enquiries and group products: deactivate
            # only the generator's unmistakable placeholder domestic individuals.
            demo = m.Package.objects.filter(
                destination__region="domestic", tour_type="individual",
                overview__icontains=DEMO_MARKER
            )
            # A missing key in JSONField can yield SQL NULL and cause exclude()
            # to discard every legacy demo. The unique generator-only marker
            # already positively identifies placeholders; no JSON exclusion needed.
            hidden = demo.update(is_active=False)
        self.stdout.write(self.style.SUCCESS(
            f"Verified domestic private-van catalogue: {len(records)} records; "
            f"updated {updated}, unchanged {skipped}; hid {hidden} generated individual demos. "
            "All group, corporate, manually created and historical booking records preserved."
        ))
