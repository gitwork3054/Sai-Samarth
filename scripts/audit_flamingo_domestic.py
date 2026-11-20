"""One-time diagnostic for publicly visible domestic supplier listings.
Prints only package titles, links and DOM structure (no marketing descriptions)."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
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
    out=(f"AREA {area}: http={r.status_code} bytes={len(r.content)} text={len(s.get_text(' ',strip=True))} "
         f"regex_paths={len(matches)} html_anchors={len(anchors)} scripts={scripts} named={named}\n"
         f"  detail_paths={matches[:30]}\n")
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
