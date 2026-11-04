"""Refresh the versioned, read-only partner card snapshot without changing bookings."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError

from travel.flamingo_cards import CATALOG_PATH, load_catalog, parse_cards
from travel.flamingo_catalog import FLAMINGO_COUNTRIES


class Command(BaseCommand):
    help = "Refresh Flamingo international trip cards; commit the resulting JSON to publish."

    def add_arguments(self, parser):
        parser.add_argument("--country", action="append", choices=[country["slug"] for country in FLAMINGO_COUNTRIES],
                            help="Refresh only this destination; can be repeated.")

    def handle(self, *args, **options):
        previous = json.loads(CATALOG_PATH.read_text()) if CATALOG_PATH.exists() else {}
        countries = dict(previous.get("countries", {}))
        failures = []

        def fetch(country):
            request = Request(country["url"], headers={"User-Agent": "SaiSamarthHolidays/1.0"})
            with urlopen(request, timeout=25) as response:
                return country["slug"], parse_cards(response.read().decode("utf-8"))

        with ThreadPoolExecutor(max_workers=5) as pool:
            selected = [country for country in FLAMINGO_COUNTRIES
                        if not options.get("country") or country["slug"] in options["country"]]
            pending = {pool.submit(fetch, country): country for country in selected}
            for future in as_completed(pending):
                country = pending[future]
                try:
                    slug, cards = future.result()
                    countries[slug] = cards
                    self.stdout.write(f"{slug}: {len(cards)} cards")
                except Exception as error:
                    failures.append(country["slug"])
                    self.stderr.write(f"{country['slug']}: {type(error).__name__}; previous cards retained")
        if not sum(map(len, countries.values())):
            raise CommandError("No cards found; existing catalogue was not replaced")
        result = {"fetched_at": datetime.now(timezone.utc).isoformat(), "countries": countries}
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = CATALOG_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(CATALOG_PATH)
        load_catalog.cache_clear()
        self.stdout.write(f"Saved {sum(map(len, countries.values()))} cards; {len(failures)} destinations could not refresh")
