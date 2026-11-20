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
