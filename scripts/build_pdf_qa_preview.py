"""Render two representative brochures to a visual QA contact sheet."""
import io
import os
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

import fitz
from PIL import Image
from travel import models as m
from travel.pdf import build_itinerary_pdf
from travel.curated_photos import photo_url

destination,_=m.Destination.objects.get_or_create(name="Jaipur",defaults={"region":"domestic","state_or_country":"Rajasthan"})
pkg=m.Package.objects.create(
    title="Jaipur Cultural Heritage Journey",destination=destination,
    short_description="Explore Jaipur, its hilltop forts and colourful local markets.",
    overview="Discover the Pink City with visits to historic forts, elegant palaces and lively bazaars. This privately planned tour stays in Jaipur for three nights.",
    days=4,nights=3,base_price=14500,cover_url=photo_url("Jaipur"),
    inclusions="Hotel accommodation\nBreakfast where specified\nPrivate transport on scheduled sightseeing days",
    exclusions="Airfare and railway tickets\nPersonal expenses\nOptional shows and non-included entry tickets",
)
for day,title,description,meals,stay in [
(1,"Arrive & explore Jaipur","Your first day begins in Jaipur, followed by check-in and a gentle exploration of the old city's heritage streets.","Dinner","Jaipur"),
(2,"Amber Fort & lake views","Explore Amber Fort and the nearby historic precinct. View Jal Mahal and enjoy the lakeside scenery.","Breakfast","Jaipur"),
(3,"Palaces & local markets","Visit City Palace, Jantar Mantar and Jaipur's celebrated shopping streets. Browse local textiles and crafts.","Breakfast, Dinner","Jaipur"),
(4,"Until next time","Enjoy breakfast if included, check out and continue to the airport or station for your onward journey.","Breakfast","")]:
    m.ItineraryDay.objects.create(package=pkg,day_number=day,title=title,description=description,stay=stay,meals=meals)
m.Sightseeing.objects.create(package=pkg,name="Amber Fort",description="Jaipur's hilltop palace-fort.")
m.Sightseeing.objects.create(package=pkg,name="Hawa Mahal",description="The Pink City's iconic facade.")
m.Hotel.objects.create(package=pkg,name="Jaipur Heritage Stay",city="Jaipur",nights=3,
                      star_rating=3,description="Example hotel; final allocation is on written confirmation.")
site=m.SiteSettings.get()
from travel.cinematic_pdf import matched_photo,fetch_trusted_photo
print("PHOTO CANDIDATES",photo_url("Jaipur"),flush=True)
jaipur_photo, jaipur_credit=matched_photo(pkg)
print("PHOTO JAIPUR",str(jaipur_photo),str(jaipur_credit),flush=True)
pdf=build_itinerary_pdf(pkg,site)
Path("docs").mkdir(exist_ok=True)
Path("docs/jaipur-design-qa.pdf").write_bytes(pdf)
kerala=m.Destination.objects.filter(slug="kerala").first()
if not kerala:
    kerala=m.Destination.objects.create(name="Kerala Tour QA",slug="kerala-tour-qa",region="domestic",state_or_country="Kerala")
sea=m.Package.objects.create(title="Kerala Backwaters and Hills",destination=kerala,days=3,nights=2,
    short_description="Tea gardens and tranquil backwaters.",overview="An easy-paced Kerala escape.",
    base_price=12500)
for i in range(1,4):
    m.ItineraryDay.objects.create(package=sea,day_number=i,title=f"Kerala day {i}",
                                  description="Relax and explore the scenery.",stay="Kerala" if i<3 else "")
cover=Path("static/img/hero/kerala-v2.webp").resolve()
print("PHOTO KERALA",str(cover),cover.exists(),flush=True)
with patch("travel.cinematic_pdf.matched_photo",return_value=(cover,None)):
    kerala_pdf=build_itinerary_pdf(sea,site)
Path("docs/kerala-design-qa.pdf").write_bytes(kerala_pdf)
pages=[]
for raw,numbers in ((pdf,[0,1,2,-1]),(kerala_pdf,[0])):
    document=fitz.open(stream=raw,filetype="pdf")
    for n in numbers:
        pix=document[n].get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False)
        pages.append(Image.frombytes("RGB",(pix.width,pix.height),pix.samples))
tw,th=pages[0].size
sheet=Image.new("RGB",(tw*3+24,th*2+24),(237,235,239))
for idx,im in enumerate(pages):
    px=8+(idx%3)*tw
    py=8+(idx//3)*th
    sheet.paste(im,(px,py))
sheet.save("docs/itinerary-design-qa.png",optimize=True)
print("PREVIEW READY",len(pdf),len(kerala_pdf),len(pages))
