"""Inspect *every* destination PDF cover in both original and 2:3 PDF crop.

Creates annotated, inspectable visual contact sheets and an image audit JSON.
This must run on a non-production audit branch before choosing curated images.
"""
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageStat,ImageFilter

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/"travel/data/pdf_destination_photos.json"
data=json.loads(source.read_text(encoding="utf-8"))
photos=data["photos"]
out=ROOT/"docs/pdf-photo-audit"
out.mkdir(parents=True,exist_ok=True)

try:
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",16)
    bold=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",21)
    small=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",12)
except Exception:
    font=ImageFont.load_default()
    bold=small=font

tile_w,tile_h=438,444
crop_w,crop_h=262,363
raw_w,raw_h=150,185
rows=[]
for city,entry in sorted(photos.items(),key=lambda x:x[0].casefold()):
    file=ROOT/(entry.get("file") or "")
    record={"city":city,"file":str(file.relative_to(ROOT)) if file.is_relative_to(ROOT) else str(file),
            "source":entry.get("source_url"),"license":entry.get("license"),"photographer":entry.get("photographer")}
    if not file.is_file():
        record["error"]="FILE MISSING"
        rows.append(record)
        continue
    try:
        with Image.open(file) as image:
            im=ImageOps.exif_transpose(image).convert("RGB")
            record["width"],record["height"]=im.size
            gray=im.convert("L").resize((192,192),Image.Resampling.LANCZOS)
            e=gray.filter(ImageFilter.FIND_EDGES)
            record["edge_std"]=round(ImageStat.Stat(e).stddev[0],2)
            record["pixel_count"]=im.width*im.height
            record["aspect"]=round(im.width/im.height,3)
            record["crop"]=ImageOps.fit(im,(crop_w,crop_h),Image.Resampling.LANCZOS,centering=(.5,.5))
            record["uncropped"]=ImageOps.contain(im,(raw_w,raw_h),Image.Resampling.LANCZOS)
    except Exception as exc:
        record["error"]=type(exc).__name__+": "+str(exc)[:100]
    rows.append(record)

by_page=[]
for sheet_no in range(math.ceil(len(rows)/9)):
    sheet=Image.new("RGB",(tile_w*3,tile_h*3),(245,246,245))
    d=ImageDraw.Draw(sheet)
    for ix,r in enumerate(rows[sheet_no*9:(sheet_no+1)*9]):
        col,rr=ix%3,ix//3
        x,y=col*tile_w,rr*tile_h
        d.rounded_rectangle((x+5,y+5,x+tile_w-6,y+tile_h-7),radius=10,fill=(250,251,251),outline=(203,207,211),width=2)
        d.text((x+15,y+11),r["city"][:29],font=bold,fill=(25,36,47))
        if r.get("crop"):
            sheet.paste(r["crop"],(x+12,y+49))
            sheet.paste(r["uncropped"],(x+280,y+55+(raw_h-r["uncropped"].height)//2))
            d.text((x+284,y+252),f"{r['width']} × {r['height']}",font=font,fill=(55,60,70))
            d.text((x+284,y+275),f"detail {r['edge_std']}",font=font,fill=(55,60,70))
            d.text((x+284,y+301),r["license"][:22] if r.get("license") else "licence missing",font=small,fill=(55,60,70))
            d.text((x+284,y+324),"original ↑",font=small,fill=(57,69,88))
            d.text((x+17,y+416),"PDF crop ↑  •  exact destination label, check image content",font=small,fill=(53,58,63))
        else:
            d.text((x+12,y+85),r.get("error","no image"),font=font,fill=(180,30,30))
    target=out/f"contact-sheet-{sheet_no+1:02d}.jpg"
    sheet.save(target,format="JPEG",quality=79,optimize=True)
    by_page.append(target.name)

for row in rows:
    row.pop("crop",None)
    row.pop("uncropped",None)
snapshot=json.loads((ROOT/"travel/data/flamingo_domestic_private_vans.json").read_text(encoding="utf-8"))
groups={}
for row in snapshot["packages"]:
    route=[stop["city"] for stop in row.get("route",[]) if stop.get("city")]
    available=[city for city in route if city in photos]
    groups[row.get("tour_code_supplier")]={
        "title":row["title"],"region":row.get("region_label"),
        "route_cities":route,"photo_candidates":available,
    }
report={"count":len(photos),"missing_files":[r["city"] for r in rows if r.get("error")],
        "low_resolution":[r["city"] for r in rows if r.get("width",0)<800 or r.get("height",0)<500],
        "photos":rows,"sheets":by_page,
        "private_van_coverage":groups}
(out/"audit.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("AUDIT_RESULT",json.dumps({"total_images":len(photos),"missing":report["missing_files"],
 "low_resolution":report["low_resolution"],"sheets":by_page,
 "tours_without_photo":[k for k,v in groups.items() if not v["photo_candidates"]]},ensure_ascii=False))

# Reviewed scenic replacements are re-checked against the exact PDF cover crops.
