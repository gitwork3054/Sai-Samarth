"""One-time diagnostic for publicly visible domestic supplier listings.
Prints only package titles, links and DOM structure (no marketing descriptions)."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
import json
import requests
from bs4 import BeautifulSoup

base="https://www.flamingotravels.co.in"
categories=[
"rajasthan-holiday-tour-packages","gujarat-holiday-tour-packages","kerala-holiday-tour-packages",
"himachal-pradesh-holiday-tour-packages","andaman-holiday-tour-packages",
"kashmir-holiday-tour-packages","uttranchal-holiday-tour-packages",
"maharashtra-holiday-tour-packages","karnataka-holiday-tour-packages",
"odisha-holiday-tour-packages","madhya-pradesh-holiday-tour-packages",
"leh-holiday-tour-packages","west-bengal-sikkim-holiday-tour-packages",
"goa-holiday-tour-packages","golden-triangle-tour-packages",
"uttar-pradesh-holiday-tour-packages"
]
DETAIL=re.compile(r"/india-tour-packages/[^/'\"? ]+/[^/'\"? ]+/f\d+",re.I)
def inspect(area):
    url=base+"/india-tour-packages/"+area
    r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"})
    s=BeautifulSoup(r.text,"html.parser")
    matches=sorted(set(DETAIL.findall(r.text)))
    anchors=[x.get("href","") for x in s.find_all("a",href=True) if DETAIL.search(x.get("href",""))]
    named=[x for x in ("Lakes & Forts Of Rajasthan","Whole of Rajasthan","Simplicity Rajasthan","Exotic Rajasthan","Scenic Himachal","Complete Kerala")
           if x.lower() in r.text.lower()]
    scripts=len(s.find_all("script"))
    raw=s.find("script", id="__NEXT_DATA__")
    next_data=json.loads(raw.string) if raw and raw.string else {}
    def find_package_arrays(x, path="$", depth=0):
        if depth>18: return []
        if isinstance(x,list):
            if x and isinstance(x[0],dict) and ("bI_Code" in x[0] or "pageSlug" in x[0] or "bIId" in x[0]):
                return [(path,x)]
            hits=[]
            for i,v in enumerate(x[:5]): hits.extend(find_package_arrays(v,path+f"[{i}]",depth+1))
            return hits
        if isinstance(x,dict):
            hits=[]
            for k,v in x.items(): hits.extend(find_package_arrays(v,path+"."+k,depth+1))
            return hits
        return []
    package_arrays=find_package_arrays(next_data)
    out=(f"AREA {area}: http={r.status_code} bytes={len(r.content)} text={len(s.get_text(' ',strip=True))} "
         f"regex_paths={len(matches)} html_anchors={len(anchors)} scripts={scripts} named={named}\n"
         f"  detail_paths={matches[:30]}\n")
    out+="  NEXT_PAGE topkeys="+str(list(next_data.keys()))+" package_arrays="+str([(path,len(items)) for path,items in package_arrays[:20]])+"\\n"
    for path,items in package_arrays[:3]:
        if items:
            out+="  NEXT_ITEM keys="+str(list(items[0].keys()))+"\\n"
            out+="  NEXT_ITEM example="+str({k:items[0].get(k) for k in ["name","bI_Code","pageSlug","cities","tourType","tourTypeId","category","tourOrder","price","rate","sellingPrice","priceAdult","validity"]})+"\\n"
            out+="  NEXT_TITLES "+str([(str(item.get("name",""))[:55],item.get("bI_Code"),item.get("pageSlug")) for item in items[:24]])+"\\n"
    if area=="rajasthan-holiday-tour-packages":
        sample=package_arrays[0][1][0] if package_arrays else {}
        out+="  RATES SAMPLE "+str({k: str(sample.get(k))[:350] for k in ("sellingPrice","totalDays","flightIncluded","isSellingPricePublish","validityPeriods","validityMonth","inclusions","exclusions","highlights")})+"\\n"
        out+="  ALL RAJASTHAN RATES "+str([{"code":item.get("bI_Code"),"title":item.get("name"),"sell":item.get("sellingPrice"),"days":item.get("totalDays"),"validity":str(item.get("validityPeriods"))[:100]} for item in (package_arrays[0][1] if package_arrays else [])])+"\\n"
    if area=="rajasthan-holiday-tour-packages":
        for needle in ("Lakes & Forts", "Whole of Rajasthan","Simplicity Rajasthan","Exotic Rajasthan","f1402"):
            i=r.text.lower().find(needle.lower())
            if i>=0:
                out+=f"  MARKER {needle!r}: pos={i}, context={r.text[max(0,i-100):i+170].replace(chr(10),' ')[:270]}\n"
                node=s.find(string=lambda txt: isinstance(txt,str) and needle.lower() in txt.lower())
                if node:
                    out+=f"  MARKER_NODE {needle!r}: parent={node.parent.name}, attrs={dict(node.parent.attrs)}, grandparent={node.parent.parent.name}\n"
            else:
                out+=f"  MARKER {needle!r}: ABSENT\n"
        out+="  HTML_ANCHORS "+str(anchors[:20])+"\n"
    return out

with ThreadPoolExecutor(max_workers=7) as pool:
    futures={pool.submit(inspect,area):area for area in categories}
    for f in as_completed(futures):
        try:
            print(f.result(),flush=True)
        except Exception as exc:
            print("AREA_ERR",futures[f],str(exc),flush=True)


# Focused structural inspection for day-wise schedule extraction. Never print
# supplier's long written descriptions; only the layout and short city headings.
detail_urls=[
  base+"/india-tour-packages/rajasthan-holiday-tour-packages/udaipur-with-kumbhalgarh-4nights/f2025",
  base+"/india-tour-packages/himachal-pradesh-holiday-tour-packages/scenic-himachal-7nights/f1360",
]
for detail_url in detail_urls:
    response=requests.get(detail_url,timeout=25,headers={"User-Agent":"Mozilla/5.0"})
    doc=BeautifulSoup(response.text,"html.parser")
    lines=[x.strip() for x in doc.get_text("\n",strip=True).splitlines() if x.strip()]
    marks=[i for i,x in enumerate(lines) if "day wise travel itinerary" in x.lower()]
    print("DETAIL_STRUCTURE",detail_url.split("/")[-1],response.status_code,
          "lines",len(lines),"day_markers",marks[:4],
          "tag_headings",[(t.name,t.get_text(" ",strip=True)[:75]) for t in doc.find_all(["h2","h3","h4","h5"]) if re.match(r"^Day\s*\d+",t.get_text(" ",strip=True),re.I)][:15],
          flush=True)
    for mark in marks[:1]:
        print("DAY_LINES",detail_url.split("/")[-1],
              [(i,lines[i][:95]) for i in range(max(0,mark-2),min(len(lines),mark+42))],flush=True)
    next_tag=doc.find("script",id="__NEXT_DATA__")
    if next_tag:
        data=json.loads(next_tag.string or "{}")
        props=data.get("props",{}).get("pageProps",{})
        itinerary=props.get("data",{}).get("itinerary") or []
        hotels=props.get("data",{}).get("hotels") or []
        hotel_listing=props.get("HotelListingArray") or []
        print("ITINERARY_ITEM",detail_url.split("/")[-1],
              [{"day":i+1, "from":str(x.get("from"))[:80],"mealPlan":str(x.get("mealPlan"))[:80],
                "description_length":len(str(x.get("description") or "")),
                "description_sample":str(BeautifulSoup(str(x.get("description") or ""),"html.parser").get_text(" ",strip=True))[:90]} for i,x in enumerate(itinerary[:8])],flush=True)
        print("HOTEL_OPTIONS",detail_url.split("/")[-1],
              [{"keys":list(h.keys()),"data_keys":list((h.get("data") or {}).keys()) if isinstance(h.get("data"),dict) else [],
                "names":[{k:t.get(k) for k in ("hotelName","cityName","hotelCity","hotelStar","city","night")}
                         for t in ((h.get("data") or {}).get("data") or [])[:3] if isinstance(t,dict)]}
               for h in hotels[:2]],"hotel_list_examples",
              [{k:t.get(k) for k in ("HotelName","CityName","Category","StarRating")} for t in hotel_listing[:3]],flush=True)
        print("DETAIL_PAGE_KEYS",detail_url.split("/")[-1],list(props.keys()),flush=True)
        def drill(value,path="",depth=0):
            if depth>8: return
            if isinstance(value,dict):
                for k,v in value.items():
                    if any(key in k.lower() for key in ("itinerary","daywise","hotel","tourday","sightseeing","meal")):
                        print("DETAIL_FIELD",path+"."+k,"type",type(v).__name__,
                              "len",len(v) if isinstance(v,(list,dict)) else None,
                              "sample_keys",list(v[0].keys())[:16] if isinstance(v,list) and v and isinstance(v[0],dict) else (list(v.keys())[:15] if isinstance(v,dict) else []),flush=True)
                    drill(v,path+"."+k,depth+1)
            elif isinstance(value,list) and value:
                drill(value[0],path+"[0]",depth+1)
        drill(props,"$.props.pageProps")
