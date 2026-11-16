"""First-party contact, staff quote export, and a protected CRM read interface."""
import hmac
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from urllib.parse import urlencode
from .flamingo_catalog import FLAMINGO_COUNTRIES
from .flamingo_cards import load_catalog
from django.views.decorators.http import require_GET
from . import models as m
from .forms import ContactForm


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if not form.cleaned_data['website']:
            m.ContactRequest.objects.create(**{key:form.cleaned_data[key] for key in ('name','email','phone','message')})
        return redirect('contact_thanks')
    return render(request, 'travel/contact.html', {'contact_form':form, 'sent':request.resolver_match.url_name=='contact_thanks'})


def _journey_matches(query):
    from django.db.models import Q
    packages = m.Package.objects.filter(is_active=True).select_related('destination').filter(
        Q(title__icontains=query) | Q(tour_code__icontains=query) |
        Q(destination__name__icontains=query) | Q(destination__state_or_country__icontains=query)
    )
    term = query.casefold()
    countries = [c for c in FLAMINGO_COUNTRIES if term in c['name'].casefold()]
    country_names = {country['slug']: country['name'] for country in FLAMINGO_COUNTRIES}
    trips = {}
    for slug, cards in load_catalog().get('countries', {}).items():
        for card in cards:
            if term in ' '.join(str(card.get(key, '')) for key in ('title', 'code', 'cities')).casefold() or term in country_names.get(slug, '').casefold():
                trips.setdefault(card['url'], {**card, 'country': country_names.get(slug, '')})
    return packages, countries, list(trips.values())


@require_GET
def journey_search(request):
    query = request.GET.get('q', '').strip()[:120]
    if len(query) < 2:
        return JsonResponse({'results': []})
    packages, countries, trips = _journey_matches(query)
    results = [{'title': c['name'], 'url': reverse('international') + '?' + urlencode({'country': c['slug']}), 'duration': 'International destination'} for c in countries[:3]]
    results += [{'title': p.title, 'url': p.get_absolute_url(), 'duration': p.duration_label} for p in packages[:3]]
    results += [{'title': t['title'], 'url': reverse('international') + '?' + urlencode({'q': t.get('code') or t['title']}), 'duration': t.get('duration') or 'International trip'} for t in trips[:3]]
    return JsonResponse({'results': results[:9]})


@require_GET
def journey_results(request):
    query = request.GET.get('q', '').strip()[:120]
    packages, countries, trips = _journey_matches(query) if len(query) >= 2 else ([], [], [])
    return render(request, 'travel/journey_results.html', {
        'query': query, 'packages': packages[:12], 'countries': countries, 'trips': trips[:12],
    })


@staff_member_required
def quotation_pdf(request, reference):
    if not request.user.has_perm('travel.view_enquiry'):
        return HttpResponseForbidden('You do not have permission to view enquiries.')
    enquiry = get_object_or_404(m.Enquiry.objects.select_related('package__destination'), reference=reference)
    if not enquiry.quote_breakdown:
        return HttpResponse('Generate the quotation from the enquiry admin action first.', status=409)
    from .quote_pdf import build_quote_pdf
    response = HttpResponse(build_quote_pdf(enquiry, m.SiteSettings.get()), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{enquiry.reference}-quotation.pdf"'
    return response


@require_GET
def crm_export(request, resource):
    expected = getattr(settings, 'CRM_API_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    token_ok = bool(expected) and supplied.startswith('Bearer ') and hmac.compare_digest(supplied[7:], expected)
    permission = {'packages':'travel.view_package','enquiries':'travel.view_enquiry'}.get(resource, '')
    staff_ok = request.user.is_authenticated and request.user.is_staff and permission and request.user.has_perm(permission)
    if not staff_ok and not token_ok:
        return JsonResponse({'error':'Staff authentication or a configured CRM bearer token is required.'}, status=403)
    if resource == 'packages':
        qs = m.Package.objects.select_related('destination').order_by('pk')
        def serialise(p):
            return {'id':p.pk,'tour_code':p.tour_code,'title':p.title,'active':p.is_active,'destination':p.destination.name,
                    'region':p.region,'tour_type':p.tour_type,'duration':p.duration_label,'base_price':p.base_price,
                    'price_on_request':p.price_on_request,'source_url':p.source_url,
                    'itinerary':list(p.itinerary.values('day_number','title','description','meals','stay')),
                    'activities':list(p.activities.values('id','name','description','adult_price','child_price')),
                    'hotels':list(p.hotels.values('id','tier','name','city','room_category','room_options','website'))}
    elif resource == 'enquiries':
        qs = m.Enquiry.objects.order_by('pk')
        def serialise(e):
            return {'id':e.pk,'reference':e.reference,'package_id':e.package_id,'name':e.name,'email':e.email,'phone':e.phone,
                    'status':e.status,'travel_date':e.travel_date,'adults':e.adults,'children':e.children,'estimated_total':e.total_price,
                    'selected_activities':list(e.activities.values_list('pk',flat=True)), 'quote':e.quote_breakdown,'created':e.created.isoformat()}
    else:
        return JsonResponse({'error':'Unknown resource'}, status=404)
    page = Paginator(qs, 50).get_page(request.GET.get('page'))
    return JsonResponse({'schema_version':1,'count':page.paginator.count,'page':page.number,'pages':page.paginator.num_pages,'results':[serialise(obj) for obj in page]})


def sitemap(request):
    from xml.etree.ElementTree import Element, SubElement, tostring
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    from django.urls import reverse
    paths = [reverse(name) for name in ('home','domestic','international','group_tours','corporate_tours','contact')]
    paths += [p.get_absolute_url() for p in m.Package.objects.filter(is_active=True)]
    for path in paths:
        node = SubElement(root, 'url');SubElement(node, 'loc').text=request.build_absolute_uri(path)
    return HttpResponse(tostring(root, encoding='utf-8',xml_declaration=True), content_type='application/xml')


def robots(request):
    text = 'User-agent: *\nDisallow: /'+settings.ADMIN_URL+'\nDisallow: /staff/\nDisallow: /accounts/\nDisallow: /api/crm/\nSitemap: '+request.build_absolute_uri('/sitemap.xml')+'\n'
    return HttpResponse(text,content_type='text/plain')

