"""Fetch CC-licensed destination-specific candidate photographs for human review.

Candidate images are not published automatically. Only contact-sheet previews and
source/author/licence metadata are saved. Selection is performed separately.
"""
import html,io,json,re
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image,ImageOps,ImageDraw,ImageFont
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs/pdf-photo-candidates"
OUT.mkdir(parents=True,exist_ok=True)
QUERIES={
 "Shimla":"Shimla",
 "Srinagar":"Srinagar",
 "Katra":"Vaishno Devi",
 "Coorg":"Coorg",
 "Chennai":"Chennai",
 "Tamil Nadu":"Madurai",
 "Jaisalmer":"Jaisalmer",
 "Varanasi":"Varanasi",
 "Kodaikanal":"Kodaikanal",
 "Kumarakom":"Kumarakom",
 "Ooty":"Ooty",
 "Lakshadweep":"Lakshadweep",
 "Port Blair":"Port Blair",
 "Andaman":"Havelock",
 "Guwahati":"Guwahati",
 "Goa":"Goa",
 "Diu":"Diu",
 "Bangalore":"Bangalore",
 "Darjeeling":"Darjeeling",
 "Rishikesh":"Rishikesh",
 "Tezpur":"Tezpur",
}
ACCEPT={
 "Shimla":["shimla","simla"],
 "Srinagar":["srinagar","dal lake","shikara","kashmir"],
 "Katra":["vaishno devi","katra","trikuta"],
 "Coorg":["coorg","kodagu"],
 "Chennai":["chennai","madras","marina beach"],
 "Tamil Nadu":["madurai","meenakshi"],
 "Jaisalmer":["jaisalmer"],
 "Varanasi":["varanasi","banaras","benares","ghats"],
 "Kodaikanal":["kodaikanal"],
 "Kumarakom":["kumarakom","vembanad"],
 "Ooty":["ooty","udhagamandalam","nilgiri"],
 "Lakshadweep":["agatti","lakshadweep","bangaram island"],
 "Port Blair":["port blair","corbyn"],
 "Andaman":["havelock","radhanagar","andaman"],
 "Guwahati":["guwahati","kamakhya","umananda"],
 "Goa":["goa","palolem","agonda","colva"],
 "Diu":["diu","nagoa beach"],
 "Bangalore":["bangalore","bengaluru","lalbagh"],
 "Darjeeling":["darjeeling","kanchenjunga"],
 "Rishikesh":["rishikesh","laxman jhula","lakshman jhula"],
 "Tezpur":["tezpur"],
}
UA="SaiSamarthVisualPhotoAudit/1.0 (https://www.saisamarthholidays.com/)"
def strip(raw):
 return BeautifulSoup(raw or "","html.parser").get_text(" ",strip=True)[:170]
def valid_license(short):
 value=short.casefold()
 return ("cc by" in value or "cc0" in value or "public domain" in value or "pd-" in value) and "nc" not in value and "nd" not in value
def search_and_collect(city,query):
 candidates=[]
 try:
  with requests.Session() as s:
   s.headers.update({"User-Agent":UA})
   params={"action":"query","format":"json","generator":"search",
           "gsrsearch":query,"gsrnamespace":"6","gsrlimit":65,
           "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":"1000"}
   response=s.get("https://commons.wikimedia.org/w/api.php",params=params,timeout=22)
   response.raise_for_status()
   pages=list((response.json().get("query") or {}).get("pages",{}).values())
   scenic=re.compile(r"lake|mountain|panorama|hill|ridge|cityscape|valley|sunset|sunrise|tea|fort|palace|temple|beach|landscape|backwater|river|view|forest|island|harbour|coast|snow|green|aerial|scenic",re.I)
   avoid=re.compile(r"police|traffic|road sign|congestion|station|railway|crowd|nightlife|bike|selfie|tourist|logo|map|coat.of.arms|flag|poster",re.I)
   def rank(page):
    name=page.get("title","")
    details=(page.get("imageinfo") or [{}])[0]
    score=(4 if scenic.search(name) else 0)+(1 if int(details.get("width",0))>=1800 else 0)
    if avoid.search(name):score-=10
    return (-score,page.get("index",100))
   pages.sort(key=rank)
   for item in pages:
    if len(candidates)>=3:break
    title=item.get("title","")
    if not any(term in title.casefold().replace("_"," ") for term in ACCEPT[city]):
     continue
    if not re.search(r"\.(jpg|jpeg|png|webp)$",title,re.I):continue
    if avoid.search(title):continue
    info=(item.get("imageinfo") or [{}])[0]
    if int(info.get("width",0))<1100 or int(info.get("height",0))<720:continue
    meta=info.get("extmetadata") or {}
    short=strip((meta.get("LicenseShortName") or {}).get("value",""))
    if not valid_license(short):continue
    url=info.get("thumburl") or info.get("url")
    if not url or urlparse(url).hostname!="upload.wikimedia.org":continue
    try:
     raw=s.get(url,timeout=18)
     raw.raise_for_status()
     if len(raw.content)>6*1024*1024:continue
     with Image.open(io.BytesIO(raw.content)) as image:
      if image.width<540 or image.height<430:continue
      im=ImageOps.exif_transpose(image).convert("RGB")
      im.thumbnail((1200,1350),Image.Resampling.LANCZOS)
      bio=io.BytesIO()
      im.save(bio,"JPEG",quality=80,optimize=True)
     filepage="https://commons.wikimedia.org/wiki/"+title.replace(" ","_")
     candidates.append({"city":city,"source":filepage,
      "file_title":title,"photographer":strip((meta.get("Artist") or {}).get("value","")) or "Commons contributor",
      "license":short,"license_url":(meta.get("LicenseUrl") or {}).get("value",""),
      "original_width":info.get("width"),"original_height":info.get("height"),
      "picture":bio.getvalue()})
    except Exception:continue
 except Exception as exc:
  return city,[],type(exc).__name__+": "+str(exc)[:180]
 return city,candidates,"ok" if candidates else "no qualifying candidates"

results={}
with ThreadPoolExecutor(max_workers=5) as pool:
 futures={pool.submit(search_and_collect,city,query):city for city,query in QUERIES.items()}
 for fut in as_completed(futures):
  city,pictures,state=fut.result()
  results[city]={"pictures":pictures,"status":state}
  print("SEARCH_RESULT",city,len(pictures),state,flush=True)

try:
 font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",15)
 bold=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",18)
except Exception:
 font=ImageFont.load_default();bold=font
selected={}
citylist=list(QUERIES)
for city in citylist:
 selected[city]=[]
 for j,item in enumerate(results.get(city,{}).get("pictures") or []):
  selected[city].append({k:v for k,v in item.items() if k!="picture"})
for block in range((len(citylist)+3)//4):
 cities=citylist[block*4:(block+1)*4]
 sheet=Image.new("RGB",(3*410,4*425),(243,245,247))
 pen=ImageDraw.Draw(sheet)
 for yrow,city in enumerate(cities):
  items=results.get(city,{}).get("pictures") or []
  for col in range(3):
   x,y=col*410,yrow*425
   pen.rounded_rectangle((x+4,y+4,x+405,y+420),radius=11,fill="white",outline=(204,209,216),width=2)
   pen.text((x+12,y+12),f"{city} — option {col+1}",font=bold,fill=(25,40,54))
   if col>=len(items):
    pen.text((x+18,y+175),"No qualifying image",font=font,fill=(165,60,70))
    continue
   entry=items[col]
   pic=Image.open(io.BytesIO(entry["picture"]))
   portrait=ImageOps.fit(pic,(281,325),Image.Resampling.LANCZOS)
   sheet.paste(portrait,(x+10,y+41))
   title=entry["file_title"].replace("File:","").replace("_"," ")
   pen.text((x+302,y+80),title[:11],font=font,fill=(28,45,56))
   pen.text((x+302,y+103),title[11:21],font=font,fill=(28,45,56))
   pen.text((x+302,y+145),entry["license"][:13],font=font,fill=(65,70,82))
   pen.text((x+12,y+389),title[:42],font=font,fill=(38,50,62))
   pen.text((x+12,y+405),title[42:80],font=font,fill=(38,50,62))
 dest=OUT/f"candidate-sheet-{block+1:02d}.jpg"
 sheet.save(dest,"JPEG",quality=80,optimize=True)
photo_metadata={
 "generated":datetime.now(timezone.utc).isoformat(),
 "queries":QUERIES,
 "results":{city:{"status":results.get(city,{}).get("status"),"candidates":selected[city]}
            for city in citylist}
}
(OUT/"candidate-index.json").write_text(json.dumps(photo_metadata,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("CANDIDATE_SUMMARY",json.dumps({city:len(selected[city]) for city in citylist}))
