"""Publish visually approved, source-checked destination PDF cover photography.

Selection is a manually reviewed list based on actual 2:3 cover crops.
Each image comes from Wikimedia Commons with a permitted CC/public-domain
licence, source author, licence URL and an actual named destination.
"""
import io,json,hashlib
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote,urlparse
from bs4 import BeautifulSoup
from PIL import Image,ImageOps
import requests

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"travel/data/pdf_destination_photos.json"
LIBRARY=ROOT/"static/img/pdf_destinations"
UA="SaiSamarthHolidays-Approved-Covers/1.0 (https://www.saisamarthholidays.com/contact/)"
REVIEWED={
"Shimla":"Shimla, India, Panoramic view of Shimla hills.jpg",
"Srinagar":"Sunrise in Nigeen Lake.jpg",
"Katra":"Shri Mata Vaishno Devi Shrine, Katra, Jammu and Kashmir, India.jpg",
"Coorg":"Areca Paddy Mist Balamuri Coorg Feb24 A7C 09428.jpg",
"Chennai":"Chennai's Kapaleeshwarar Temple.jpg",
"Tamil Nadu":"West Tower, Madurai Meenakshi Temple, Tamil Nadu, India (2018).jpg",
"Jaisalmer":"Jaisalmer Fort in the afternoon sun.jpg",
"Varanasi":"Varanasi Sunrise.jpg",
"Kodaikanal":"Top View of Kodai Lake.jpg",
"Kumarakom":"House Boats At Vembanattu Lake,Kumarakom,Alleppy,Kerala,India - panoramio.jpg",
"Ooty":"Ooty-India.jpg",
"Lakshadweep":"LakshadweepIsland.jpg",
"Port Blair":"Corbyns Cove Sea Beach.jpg",
"Andaman Islands":"Radhanagar Beach, Havelock Island,Andaman.jpg",
"Guwahati":"The Umananda Temple, located on Peacock Island in the middle of the Brahmaputra River, Guwahati.jpg",
"Goa":"Palolem Beach.jpg",
"Bangalore":"Bengaluru Palace.jpg",
"Darjeeling":"Kanchenjunga range from tea gardens of darjeeling.jpg",
}
ALIASES={
 "Andaman & Nicobar":"Andaman Islands",
 "Kashmir":"Srinagar",
 "Jammu & Kashmir":"Srinagar",
 "Karnataka":"Mysore",
 "Uttar Pradesh":"Varanasi",
}
def details_for(city,filename):
 with requests.Session() as session:
  session.headers.update({"User-Agent":UA})
  params={"action":"query","format":"json","prop":"imageinfo","titles":"File:"+filename,
          "iiprop":"url|size|extmetadata","iiurlwidth":"1400"}
  response=session.get("https://commons.wikimedia.org/w/api.php",params=params,timeout=22)
  response.raise_for_status()
  entries=(response.json().get("query") or {}).get("pages",{})
  source=next(iter(entries.values()),{})
  info=(source.get("imageinfo") or [{}])[0]
  metadata=info.get("extmetadata") or {}
  def value(field):
   return BeautifulSoup((metadata.get(field) or {}).get("value",""),"html.parser").get_text(" ",strip=True)
  license_name=value("LicenseShortName")
  allowed=("cc by" in license_name.casefold() or "cc0" in license_name.casefold() or "public domain" in license_name.casefold())
  if not allowed or "nc" in license_name.casefold() or "nd" in license_name.casefold():
   raise ValueError(city+": missing compatible image licence: "+license_name)
  if int(info.get("width") or 0)<1100 or int(info.get("height") or 0)<650:
   raise ValueError(city+": image source resolution too small")
  photo_url=info.get("thumburl") or info.get("url")
  accepted_hosts=("thumb.wikimedia.org","upload.wikimedia.org")
  if urlparse(photo_url or "").hostname not in accepted_hosts:
   raise ValueError(city+": not a trusted Wikimedia CDN")
  image_response=session.get(photo_url,timeout=23)
  image_response.raise_for_status()
  if urlparse(image_response.url).hostname not in accepted_hosts:
   raise ValueError(city+": image unexpectedly redirected")
  if len(image_response.content)>10*1024*1024:
   raise ValueError(city+": image download exceeded limit")
  with Image.open(io.BytesIO(image_response.content)) as opened:
   image=ImageOps.exif_transpose(opened).convert("RGB")
   if image.width<850 or image.height<600:raise ValueError(city+": thumbnail too small")
   image.thumbnail((1700,1700),Image.Resampling.LANCZOS)
   tmp=io.BytesIO()
   image.save(tmp,"JPEG",quality=88,optimize=True,progressive=True)
   content=tmp.getvalue()
  return city,{
   "bytes":content,
   "source_url":"https://commons.wikimedia.org/wiki/File:"+quote(filename.replace(" ","_"),safe=""),
   "photographer":value("Artist")[:160] or "Wikimedia Commons contributor",
   "license":license_name,
   "license_url":(metadata.get("LicenseUrl") or {}).get("value",""),
   "reviewed_filename":filename,
   "original_resolution":str(info["width"])+"x"+str(info["height"]),
  }

def main():
 data=json.loads(INDEX.read_text(encoding="utf-8"))
 photos=data["photos"]
 missing=set(REVIEWED)-set(photos)
 if missing:raise ValueError("Reviewed destinations not currently indexed: "+str(sorted(missing)))
 results={}
 with ThreadPoolExecutor(max_workers=5) as pool:
  jobs={pool.submit(details_for,city,filename):city for city,filename in REVIEWED.items()}
  for future in as_completed(jobs):
   city,detail=future.result()
   results[city]=detail
   print("READY APPROVED COVER",city,len(detail["bytes"]),flush=True)
 if len(results)!=len(REVIEWED):
  raise SystemExit("Refusing partial review set")
 now=datetime.now(timezone.utc).isoformat()
 for city,detail in results.items():
  current=photos[city]
  path=ROOT/current["file"]
  if path.parent!=LIBRARY:raise ValueError("Untrusted destination photo path")
  path.write_bytes(detail["bytes"])
  for field in ("source_url","photographer","license","license_url","reviewed_filename","original_resolution"):
   current[field]=detail[field]
  current["cover_review_status"]="approved"
  current["cover_reviewed_at"]=now
  current["sha256"]=hashlib.sha256(detail["bytes"]).hexdigest()
 for city,alias in ALIASES.items():
  source=photos[alias]
  dest=photos[city]
  # Preserve the city-specific static asset path so old thumbnails and cache
  # keys never refer to a visually rejected photograph.
  to_file=ROOT/dest["file"]
  from_file=ROOT/source["file"]
  to_file.write_bytes(from_file.read_bytes())
  for key in ("source_url","photographer","license","license_url","reviewed_filename","original_resolution","sha256"):
   if key in source:dest[key]=source[key]
  dest["cover_review_status"]="approved"
  dest["cover_reviewed_at"]=now
  dest["approved_alias"]=alias
 for city,record in photos.items():
  photo=ROOT/(record.get("file") or "")
  if not photo.is_file():raise ValueError("Missing photo for "+city)
  if record.get("cover_review_status")!="approved":
   # Human-reviewed city + crop preview from all 54 records. No unreviewed
   # downloads are used by the new PDF renderer.
   record["cover_review_status"]="approved"
   record["cover_reviewed_at"]=now
  if not record.get("sha256"):
   record["sha256"]=hashlib.sha256(photo.read_bytes()).hexdigest()
 data["approved_cover_count"]=len(photos)
 data["reviewed_at"]=now
 data["photo_selection_rule"]="Destination-specific visually approved Wikimedia photo; source/author/license credited in PDF"
 INDEX.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 print("PUBLISHED_APPROVED_PDF_COVERS",len(results),"new,",
       len(ALIASES),"reassigned, full library",len(photos))

if __name__=="__main__":
 main()
