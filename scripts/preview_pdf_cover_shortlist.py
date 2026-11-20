"""Compare specific CC-licensed scenic Wikimedia Commons photographs before publishing.

Nothing replaces a live PDF cover until the resulting crop sheets are reviewed.
"""
import io,json,re
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote,urlparse
from PIL import Image,ImageOps,ImageDraw,ImageFont
from bs4 import BeautifulSoup
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs/pdf-photo-shortlist"
OUT.mkdir(parents=True,exist_ok=True)
CANDIDATES={
"Shimla":["Shimla, India, Panoramic view of Shimla hills.jpg","Shimla Hills.jpg"],
"Srinagar":["Dal-Lake, Srinagar, Kashmir.jpg","Dal Lake, Srinagar, Jammu and Kashmir.jpg"],
"Katra":["Shri Mata Vaishno Devi Shrine, Katra, Jammu and Kashmir, India.jpg"],
"Coorg":["Coorg view.jpg","Areca Paddy Mist Balamuri Coorg Feb24 A7C 09428.jpg"],
"Chennai":["Chennai's Kapaleeshwarar Temple.jpg"],
"Tamil Nadu":["West Tower, Madurai Meenakshi Temple, Tamil Nadu, India (2018).jpg"],
"Jaisalmer":["Golden Jaisalmer Fort.jpg","Jaisalmer Fort in the afternoon sun.jpg"],
"Varanasi":["Varanasi ghats at the sunrise.JPG","Varanasi Sunrise.jpg"],
"Kodaikanal":["Top View of Kodai Lake.jpg","Upper Lake View in Kodaikanal.jpg"],
"Kumarakom":["Kumarkom.jpg","House Boats At Vembanattu Lake,Kumarakom,Alleppy,Kerala,India - panoramio.jpg"],
"Ooty":["Ooty-India.jpg","Tea plantations and rainforests Nilgiris.jpg"],
"Lakshadweep":["Agatti Island Lakshadweep.jpg","LakshadweepIsland.jpg"],
"Port Blair":["Corbyn's Cove beach Port Blair.jpg"],
"Andaman":["Havelock Island, Radhanagar Beach, tropical bliss, Andaman Islands.jpg","Radhanagar Beach, Havelock Island,Andaman.jpg"],
"Guwahati":["The Umananda Temple, located on Peacock Island in the middle of the Brahmaputra River, Guwahati.jpg"],
"Goa":["Palolem Beach, south Goa.jpg","Palolem Beach.jpg"],
"Diu":["Nagoa Beach, Diu.jpg"],
"Bangalore":["Bengaluru Palace.jpg","Aerial view of Bangalore Palace and Palace Grounds (2).jpg"],
"Darjeeling":["Kanchenjunga range from tea gardens of darjeeling.jpg","Tea Garden, Darjeeling.jpg"],
"Rishikesh":["Ram Jhula footbridge - Rishikesh.jpg"],
}
UA="SaiSamarthCoverAudit/2.0 (https://www.saisamarthholidays.com/contact/)"

def fetch_one(city,name):
 try:
  with requests.Session() as ses:
   ses.headers.update({"User-Agent":UA})
   params={"action":"query","format":"json","prop":"imageinfo",
            "titles":"File:"+name,"iiprop":"url|size|extmetadata","iiurlwidth":"1400"}
   res=ses.get("https://commons.wikimedia.org/w/api.php",params=params,timeout=20)
   res.raise_for_status()
   pages=(res.json().get("query") or {}).get("pages") or {}
   page=next(iter(pages.values()),{})
   details=(page.get("imageinfo") or [{}])[0]
   metadata=details.get("extmetadata") or {}
   def field(key):
    return BeautifulSoup((metadata.get(key) or {}).get("value",""),"html.parser").get_text(" ",strip=True)
   lic=field("LicenseShortName")
   approved=("cc by" in lic.casefold() or "cc0" in lic.casefold() or "public domain" in lic.casefold()) and "nc" not in lic.casefold() and "nd" not in lic.casefold()
   if not approved:
    return (city,name,None,"unlicensed or not found: "+lic)
   if int(details.get("width") or 0)<1024 or int(details.get("height") or 0)<600:
    return (city,name,None,"resolution too low")
   url=details.get("thumburl") or details.get("url")
   if urlparse(url or "").hostname!="upload.wikimedia.org":
    return (city,name,None,"untrusted host")
   response=ses.get(url,timeout=22)
   response.raise_for_status()
   if len(response.content)>9*1024*1024:return (city,name,None,"too large")
   with Image.open(io.BytesIO(response.content)) as image:
    im=ImageOps.exif_transpose(image).convert("RGB")
    if im.width<650 or im.height<500:return (city,name,None,"thumbnail too small")
    im.thumbnail((1400,1400),Image.Resampling.LANCZOS)
    thumbnail=ImageOps.fit(im,(288,348),Image.Resampling.LANCZOS,centering=(.5,.5))
    info={"city":city,"filename":name,"file_page":"https://commons.wikimedia.org/wiki/File:"+quote(name.replace(" ","_"),safe=""),
          "license":lic,"license_url":(metadata.get("LicenseUrl") or {}).get("value",""),
          "author":field("Artist")[:120] or "Wikimedia Commons contributor",
          "width":details.get("width"),"height":details.get("height")}
   return (city,name,{"data":thumbnail,"meta":info},"ok")
 except Exception as exc:
  return (city,name,None,type(exc).__name__+": "+str(exc)[:120])

results={}
with ThreadPoolExecutor(max_workers=6) as pool:
 jobs=[pool.submit(fetch_one,city,title) for city,items in CANDIDATES.items() for title in items]
 for f in as_completed(jobs):
  city,name,entry,status=f.result()
  results[(city,name)]={"entry":entry,"status":status}
  print("COVER_CANDIDATE",city,name,status,flush=True)

try:
 headline=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",21)
 font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
except Exception:
 headline=font=ImageFont.load_default()

metadata={}
cities=list(CANDIDATES)
for sheet_index in range((len(cities)+3)//4):
 canvas=Image.new("RGB",(940,4*422),(244,246,249))
 draw=ImageDraw.Draw(canvas)
 for rr,city in enumerate(cities[sheet_index*4:(sheet_index+1)*4]):
  metadata.setdefault(city,[])
  for col in (0,1):
   x,y=col*470,rr*422
   draw.rounded_rectangle((x+5,y+5,x+464,y+416),radius=12,fill="white",outline=(205,211,219),width=2)
   name=CANDIDATES[city][col] if col<len(CANDIDATES[city]) else None
   draw.text((x+13,y+12),f"{city} / {col+1}",font=headline,fill=(22,38,53))
   if not name:
    draw.text((x+20,y+170),"No second candidate",font=font,fill=(115,126,139))
    continue
   item=results[(city,name)]
   if not item["entry"]:
    draw.text((x+20,y+170),item["status"][:40],font=font,fill=(178,48,40))
    metadata[city].append({"file":name,"error":item["status"]})
    continue
   picture=item["entry"]["data"]
   canvas.paste(picture,(x+11,y+42))
   info=item["entry"]["meta"]
   metadata[city].append(info)
   draw.text((x+307,y+95),f"{info['width']}x{info['height']}",font=font,fill=(65,69,74))
   draw.text((x+307,y+120),info["license"][:15],font=font,fill=(65,69,74))
   draw.text((x+307,y+145),info["filename"][:18],font=font,fill=(40,55,75))
   draw.text((x+307,y+164),info["filename"][18:35],font=font,fill=(40,55,75))
   draw.text((x+11,y+393),info["filename"][:55],font=font,fill=(57,60,67))
 path=OUT/f"shortlist-sheet-{sheet_index+1:02d}.jpg"
 canvas.save(path,"JPEG",quality=79,optimize=True)
(OUT/"shortlist-index.json").write_text(json.dumps({
 "generated_at":datetime.now(timezone.utc).isoformat(),"entries":metadata},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("SHORTLIST_RESULT",json.dumps({city:len([x for x in rows if "error" not in x]) for city,rows in metadata.items()}))
