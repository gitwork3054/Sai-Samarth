from django import template
from travel.curated_photos import photo_url

register = template.Library()
GRADIENTS = [
    "linear-gradient(135deg,#627d7e,#294950 58%,#1c353c)", "linear-gradient(135deg,#b5a58d,#6f8581 60%,#354f50)",
    "linear-gradient(135deg,#819a93,#486b6b 60%,#2a454d)", "linear-gradient(135deg,#c5b9a1,#849b94 55%,#476763)",
    "linear-gradient(135deg,#7e9495,#526b73 60%,#263f48)", "linear-gradient(135deg,#a9bbae,#77928a 60%,#3f5d59)",
]


@register.filter
def inr(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    s = str(abs(n))
    head, tail = (s[:-3], s[-3:]) if len(s) > 3 else ("", s)
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:]); head = head[:-2]
    if head:
        parts.insert(0, head)
    out = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + "₹" + out


@register.filter
def gradient(pk):
    return GRADIENTS[int(pk or 0) % len(GRADIENTS)]


@register.simple_tag(takes_context=True)
def is_saved(context, pkg):
    return pkg.pk in context.get("saved_ids", ())


@register.simple_tag
def curated_photo_url(destination, spot=""):
    return photo_url(destination, spot)
