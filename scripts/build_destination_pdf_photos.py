#!/usr/bin/env python3
"""Download vetted city-specific Wikimedia travel photographs for PDF brochures.

Only official English Wikipedia city lead images are considered. Images are
resized to a practical print-ready resolution, with their Commons source and
licensing metadata stored alongside. Never fetch unnamed random stock photos.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup
from PIL import Image, ImageOps
import requests

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"travel/data/flamingo_domestic_private_vans.json"
INDEX=ROOT/"travel/data/pdf_destination_photos.json"
OUT=ROOT/"static/img/pdf_destinations"
OUT.mkdir(parents=True,exist_ok=True)
UA="SaiSamarthHolidaysBrochure/1.0 (https://www.saisamarthholidays.com/contact/; destination photo attribution)"
TITLE_FIX={
 "Cochin":"Kochi","Bangalore":"Bengaluru","Mysore":"Mysuru",
 "Katra":"Katra, Jammu and Kashmir","Port Blair":"Port Blair",
 "Ooty":"Ooty","Gangtok":"Gangtok","Srinagar":"Srinagar",
 "New Delhi":"New Delhi","Kashmir":"Srinagar",
 "Andaman Islands":"Port Blair","Andaman & Nicobar":"Port Blair",
 "Kerala Backwaters":"Alappuzha","North East India":"Shillong",
 "West Bengal & Sikkim":"Gangtok",
 "Delhi / Agra / Rajasthan":"Agra",
 "Jammu & Kashmir":"Srinagar",
 "Himachal Pradesh":"Shimla","Rajasthan":"Jaipur","Gujarat":"Dwarka",
 "Odisha":"Puri","Uttar Pradesh":"Varanasi","Uttarakhand":"Nainital",
 "Karnataka":"Mysore","Kerala":"Munnar","Maharashtra":"Mumbai",
 "Tamil Nadu":"Chennai","Ladakh":"Leh","Goa":"Goa",
 "Meghalaya":"Shillong","Sikkim":"Gangtok","Punjab":"Amritsar",
 "Lakshadweep":"Agatti Island",
}
ADDITIONAL=[
 "Jaipur","Goa","Kerala Backwaters","Rajasthan","Jaisalmer",
 "Hampi","Darjeeling","Kashmir","Ladakh","Andaman Islands",
 "Meghalaya","Agra","Delhi","Mumbai","Lakshadweep"
]

# Location-checked, openly licensed Commons files for places whose Wikipedia
# summaries do not expose a reliable high-resolution image.
SPECIAL_PHOTOS = {
    "Shimla": ("Mall Road Shimla.jpg", "Satyamrai7777", "CC BY-SA 4.0"),
    "Srinagar": ("View of Dal lake Srinagar.jpg", "Harvinder Chandigarh", "CC BY 4.0"),
    "Mysore": ("Mysore Palace, Mysore, Karnataka, India.jpg", "Wikimedia Commons contributor", "CC BY-SA 4.0"),
    "Ooty": ("Lake in Ooty.jpg", "Barkave Balusamy", "CC BY-SA 4.0"),
    "Kodaikanal": ("Kodaikanal Lake, Tamil Nadu.jpg", "Sinash", "CC BY-SA 4.0"),
    "Mahabalipuram": ("Shore Temple at Mahabalipuram Tamilnadu.jpg", "Rafflord", "CC BY-SA 4.0"),
    "Tirupati": ("Tirupati temple.jpg", "Kajal Dhanotia", "CC BY-SA 4.0"),
    "Puri": ("Bird view of Jagannath Temple, Puri.jpg", "Government of Odisha", "CC BY 4.0"),
    "Nainital": ("Nainital-1.jpg", "Lalitgupta isgec", "CC BY-SA 4.0"),
    "Goa": ("Baga Beach, Calangute, Goa.jpg", "Wikimedia Commons contributor", "See Commons file page"),
    "Diu": ("Diu fort, India.JPG", "Aditya Mahar", "CC BY-SA 4.0"),
    "Kovalam": ("Kovalam Beach in Kerala.jpg", "Salman2018", "CC BY-SA 4.0"),
    "Munnar": ("Munnar Tea gardens.jpg", "Sajith1sas", "CC BY-SA 4.0"),
    "Kumarakom": ("Kumarakom Backwaters.jpg", "Rajkrishnan R", "CC BY-SA 4.0"),
    "Coorg": ("Coorg landscape.jpg", "Cppfront", "CC0 1.0"),
    "Shillong": ("The-Umiam-Lake.jpg", "Eurich B Nongsteng", "CC0 1.0"),
    "Rishikesh": ("Ram Jhula footbridge - Rishikesh.jpg", "Paradise Chronicle", "CC BY-SA 4.0"),
}

SKIP=re.compile(r"flag|logo|coat.of.arms|seal|blank.map|political.map|locator.map|district.map|municipal.emblem",re.I)


def slug(text):
    return re.sub(r"[^a-z0-9]+","-",text.lower()).strip("-")


def get(session,url,**kw):
    r=session.get(url,timeout=16,**kw)
    r.raise_for_status()
    return r


def thumbnail_urls(photo):
    thumb=(photo.get("thumbnail") or {}).get("source","")
    if not thumb or urlparse(thumb).hostname != "upload.wikimedia.org":
        return []
    # Thumbnail API hosts may not have all size variants cached; try several
    # print-appropriate widths and the official thumbnail as a last resort.
    result=[re.sub(r"/\d+px-",f"/{size}px-",thumb) for size in (1280,960,640)]
    result.append(thumb)
    return list(dict.fromkeys(result))


def commons_credit(session,url):
    raw=unquote(urlparse(url).path.split("/")[-1])
    file_name=re.sub(r"^\d+px-","",raw)
    page="https://commons.wikimedia.org/wiki/File:"+quote(file_name,safe="")
    artist=""
    license_name=""
    license_url=""
    try:
        json_data=get(session,"https://commons.wikimedia.org/w/api.php",params={
            "action":"query","format":"json","prop":"imageinfo","iiprop":"extmetadata",
            "titles":"File:"+file_name
        }).json()
        pages=(json_data.get("query") or {}).get("pages") or {}
        entry=next(iter(pages.values()))
        details=((entry.get("imageinfo") or [{}])[0].get("extmetadata") or {})
        def field(key):
            return BeautifulSoup((details.get(key) or {}).get("value",""),"html.parser").get_text(" ",strip=True)
        artist=field("Artist")[:150]
        license_name=field("LicenseShortName")[:80] or field("UsageTerms")[:80]
        license_url=(details.get("LicenseUrl") or {}).get("value","")[:400]
    except Exception:
        pass
    return {"source_url":page,"photographer":artist,"license":license_name,
            "license_url":license_url}



def targeted_commons_photo(session,name):
    record=SPECIAL_PHOTOS.get(name)
    if not record:
        return None
    filename,author,license_name=record
    file_page="https://commons.wikimedia.org/wiki/File:"+quote(filename.replace(" ","_"),safe="").replace("%2C",",")
    download="https://commons.wikimedia.org/wiki/Special:FilePath/"+quote(filename.replace(" ","_"),safe="").replace("%2C",",")+"?width=1280"
    try:
        response=get(session,download)
        content=response.content
        if not response.headers.get("content-type","").lower().startswith("image/"):
            return None
        if len(content)<3000 or len(content)>16*1024*1024:
            return None
        with Image.open(BytesIO(content)) as photo:
            if photo.width<600 or photo.height<400:
                return None
            image=ImageOps.exif_transpose(photo).convert("RGB")
            image.thumbnail((1500,1900),Image.Resampling.LANCZOS)
            path=OUT/(slug(name)+".jpg")
            image.save(path,"JPEG",quality=85,optimize=True)
        licence_links={
            "CC BY-SA 4.0":"https://creativecommons.org/licenses/by-sa/4.0/",
            "CC BY 4.0":"https://creativecommons.org/licenses/by/4.0/",
            "CC0 1.0":"https://creativecommons.org/publicdomain/zero/1.0/",
        }
        return {"file":"static/img/pdf_destinations/"+path.name,
                "city":name,"source_url":file_page,"photographer":author,
                "license":license_name,"license_url":licence_links.get(license_name,file_page),
                "downloaded_at":datetime.now(timezone.utc).isoformat(),
                "wikipedia_page":""}
    except Exception as exc:
        print("SPECIAL PHOTO UNAVAILABLE",name,type(exc).__name__,str(exc)[:160],flush=True)
        return None


def collect(name):
    resolved=TITLE_FIX.get(name,name)
    with requests.Session() as session:
        session.headers.update({"User-Agent":UA})
        special=targeted_commons_photo(session,name)
        if special:
            return name,special,"ok-special"
        endpoint="https://en.wikipedia.org/api/rest_v1/page/summary/"+quote(resolved.replace(" ","_"),safe=",()_")
        try:
            data=get(session,endpoint).json()
            original=(data.get("originalimage") or {}).get("source","")
            thumbnails=thumbnail_urls(data)
            if not original or not original.startswith("https://upload.wikimedia.org/"):
                return name,None,"no Wikimedia image"
            if SKIP.search(original):
                return name,None,"non-photo lead image"
            candidates=[*thumbnails,original]
            raw=None
            selected=""
            for url in candidates:
                if not url:
                    continue
                try:
                    response=get(session,url)
                    content=response.content
                    if len(content)<3000 or len(content)>16*1024*1024:
                        continue
                    if not response.headers.get("content-type","").lower().startswith("image/"):
                        continue
                    with Image.open(BytesIO(content)) as img:
                        if img.width<600 or img.height<400:
                            continue
                        img.verify()
                    raw=content
                    selected=url
                    break
                except Exception:
                    continue
            if not raw:
                return name,None,"image download unavailable"
            with Image.open(BytesIO(raw)) as opened:
                image=ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((1500,1900),Image.Resampling.LANCZOS)
                path=OUT/(slug(name)+".jpg")
                image.save(path,"JPEG",quality=85,optimize=True)
            credit=commons_credit(session,original)
            credit.update({"file":"static/img/pdf_destinations/"+path.name,
                           "city":name,"wikipedia_page":(data.get("content_urls",{}).get("desktop") or {}).get("page",""),
                           "downloaded_at":datetime.now(timezone.utc).isoformat()})
            return name,credit,"ok"
        except Exception as exc:
            return name,None,type(exc).__name__


def main():
    snapshot=json.loads(DB.read_text(encoding="utf-8"))
    city_names={row["route"][0]["city"] for row in snapshot["packages"]
                if row.get("route") and row["route"][0].get("city")}
    city_names.update(ADDITIONAL)
    city_names.update(("Shimla","Udaipur","Jodhpur","Varanasi","Nainital","Srinagar","Gangtok","Puri","Munnar","Port Blair"))
    city_names.update(TITLE_FIX.keys())
    existing={}
    if INDEX.exists():
        try:
            existing=json.loads(INDEX.read_text(encoding="utf-8")).get("photos",{})
        except Exception:
            pass
    all_names=sorted(city_names)
    ready={name:entry for name,entry in existing.items()
           if name in all_names and (ROOT/entry.get("file","")).is_file()}
    failed={}
    remaining=[name for name in all_names if name not in ready]
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(collect,name):name for name in remaining}
        for task in as_completed(pending):
            city,entry,status=task.result()
            if entry:
                ready[city]=entry
            elif city in existing and (ROOT/existing[city]["file"]).exists():
                ready[city]=existing[city]
            else:
                failed[city]=status
    result={"provider":"Wikimedia Commons / English Wikipedia","kind":"city_mapped_photo_credits",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "photos":dict(sorted(ready.items())),"unavailable":dict(sorted(failed.items()))}
    INDEX.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DESTINATION PHOTO AUDIT",len(ready),"photos /",len(all_names),"cities",
          "unavailable",len(failed),flush=True)
    print("PHOTO MISSING",json.dumps(failed,ensure_ascii=False)[:6500],flush=True)
    if len(ready)<18:
        raise SystemExit("Too few verified destination photographs; do not publish partial photo catalogue.")


if __name__=="__main__":
    main()
