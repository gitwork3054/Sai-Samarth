"""Consent-aware first-party events and relevant, deterministic tour suggestions."""
import json
import uuid
from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from . import models as m
from .domestic_states import destination_states


def record_event(request, package, event):
    if not m.SiteSettings.get().analytics_enabled or request.COOKIES.get('sai_analytics') != 'yes':
        return
    visitor = request.COOKIES.get('sai_visitor', '')
    try:
        visitor = str(uuid.UUID(visitor))
    except (ValueError, AttributeError):
        return
    user = request.user if request.user.is_authenticated else None
    # Count an action once per visitor/package/type every 30 minutes.
    if not m.VisitEvent.objects.filter(package=package, visitor=visitor, event=event, created__gte=timezone.now()-timedelta(minutes=30)).exists():
        m.VisitEvent.objects.create(package=package, visitor=visitor, event=event, user=user)


def relevant_tours(package, queryset):
    configured = list(package.related_packages.filter(is_active=True).select_related('destination')[:4])
    candidates = list(queryset.filter(destination__region=package.region).exclude(pk=package.pk)
                      .annotate(recent_interest=Count('visit_events', filter=Q(visit_events__created__gte=timezone.now()-timedelta(days=30)), distinct=True)))
    states = set(destination_states(package.destination)) if package.region == 'domestic' else {package.destination.state_or_country}
    theme_ids = set(package.themes.values_list('pk', flat=True))
    def same_region(candidate):
        other = set(destination_states(candidate.destination)) if package.region == 'domestic' else {candidate.destination.state_or_country}
        return bool(states & other)
    def rank(candidate):
        distance = abs(candidate.price_from-package.price_from) / max(package.price_from, 1)
        return (-int(same_region(candidate)), -len(theme_ids & {t.pk for t in candidate.themes.all()}), distance, -candidate.recent_interest, candidate.pk)
    candidates.sort(key=rank)
    seen = {p.pk for p in configured}
    similar = (configured + [p for p in candidates if p.pk not in seen])[:4]
    return similar, [p for p in candidates if same_region(p)][:4]


def sightseeing_schema(package):
    questions = []
    for spot in package.sightseeing.all():
        for question, answer in spot.faq_list:
            questions.append({'@type':'Question','name':question,'acceptedAnswer':{'@type':'Answer','text':answer}})
    value = {'@context':'https://schema.org','@type':'FAQPage','mainEntity':questions} if questions else None
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026') if value else ''
