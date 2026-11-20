"""PDF first-page visual regression for known destination-labelled tours."""
import io,json,os,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
import fitz
from travel import models as m
from travel.pdf import build_itinerary_pdf
from travel.cinematic_pdf import matched_photo
from travel.data import __file__ as _unused

TESTS=[
 {"place":"Shimla","state":"Himachal Pradesh","tour":"Shimla Corporate Getaway","route":"Shimla","expected":"shimla.jpg"},
 {"place":"Jammu & Kashmir","state":"Jammu & Kashmir","tour":"Kashmir Corridor","route":"Srinagar","expected":"srinagar.jpg"},
 {"place":"Katra","state":"Jammu & Kashmir","tour":"Vaishno Devi Scenic Escape","route":"Katra","expected":"katra.jpg"},
 {"place":"Goa","state":"Goa","tour":"Goa Romantic Retreat","route":"Goa","expected":"goa.jpg"},
 {"place":"Jaisalmer","state":"Rajasthan","tour":"Golden Jaisalmer Heritage","route":"Jaisalmer","expected":"jaisalmer.jpg"},
 {"place":"Varanasi","state":"Uttar Pradesh","tour":"Varanasi River Sunrise","route":"Varanasi","expected":"varanasi.jpg"},
 {"place":"Coorg","state":"Karnataka","tour":"Coorg Coffee Hills","route":"Coorg","expected":"coorg.jpg"},
 {"place":"Chennai","state":"Tamil Nadu","tour":"Chennai City Heritage","route":"Chennai","expected":"chennai.jpg"},
]
OUTPUT=Path(__file__).resolve().parents[1]/"docs/pdf-photo-audit"
OUTPUT.mkdir(parents=True,exist_ok=True)
img=Image.new("RGB",(4*390,2*635),(240,243,247))
pen=ImageDraw.Draw(img)
try:
 title_font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",18)
except Exception:
 title_font=ImageFont.load_default()
site=m.SiteSettings.get()
for i,t in enumerate(TESTS):
 dest,created=m.Destination.objects.get_or_create(
  name=t["place"],defaults={"region":"domestic","state_or_country":t["state"]})
 pkg=m.Package.objects.create(destination=dest,title=t["tour"],
  tour_code="QA-COVER-"+str(i),short_description=t["tour"],days=3,nights=2,
  base_price=15000,overview="A destination-centred tour with carefully reviewed scenery.",
  source_details={"catalogue_kind":"domestic_private_van",
  "route":[{"city":t["route"],"nights":2}],"original_code":"FIT-QA-"+str(i)})
 for day in (1,2,3):
  m.ItineraryDay.objects.create(package=pkg,day_number=day,title=f"Explore {t['route']} day {day}",
   stay=t["route"] if day!=3 else "",meals="Breakfast",
   description=f"Explore locally confirmed attractions around {t['route']}.")
 photo,credit=matched_photo(pkg)
 assert photo is not None and photo.is_file(),t["tour"]+" no approved photo"
 assert photo.name==t["expected"],f"{t['tour']}: expected {t['expected']} got {photo.name}"
 assert "Wikimedia Commons" in (credit or ""),t["tour"]+" no licence credit"
 data=build_itinerary_pdf(pkg,site)
 document=fitz.open(stream=data,filetype="pdf")
 assert document.page_count>=3,t["tour"]+" too few pages"
 assert t["place"].upper() in document[0].get_text().upper(),t["tour"]+" missing destination title"
 png=document[0].get_pixmap(matrix=fitz.Matrix(0.82,0.82),alpha=False)
 cover=Image.frombytes("RGB",(png.width,png.height),png.samples)
 cover.thumbnail((370,568),Image.Resampling.LANCZOS)
 x=(i%4)*390+10; y=(i//4)*635+43
 img.paste(cover,(x,y))
 pen.text((x,y-29),t["place"]+" • PDF VERIFIED",font=title_font,fill=(27,47,58))
 print("COVER_PDF_PASS",t["place"],photo.name,len(data),document.page_count,flush=True)
img.save(OUTPUT/"final-cover-pdfs.jpg","JPEG",quality=81,optimize=True)
print("COVER_PDF_REVIEW_DONE",len(TESTS))
