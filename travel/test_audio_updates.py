from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from . import models as m
from .services import prepare_quotation
from .enhancements import relevant_tours


class AudioUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.destination = m.Destination.objects.create(name='Audio test Kerala', state_or_country='Kerala')
        cls.package = m.Package.objects.create(title='Audio test Kerala escape', destination=cls.destination, short_description='A test trip', overview='Long overview. '*60, base_price=10000, child_price=6000, deluxe_upgrade=2000)
        m.ItineraryDay.objects.create(package=cls.package, day_number=1, title='Arrive', description='Full itinerary remains unchanged.')
        cls.activity = m.OptionalActivity.objects.create(package=cls.package,name='Guided tour',adult_price=1000,child_price=500)
        cls.staff = get_user_model().objects.create_user(username='audio-staff',email='staff@example.test',password='Staff#2026',is_staff=True,is_superuser=True)

    def enquiry(self, **kwargs):
        values = dict(package=self.package,name='Example Traveller',email='traveller@example.test',phone='9999999999',adults=2,children=1,hotel_tier='deluxe',total_price=1)
        values.update(kwargs)
        enquiry=m.Enquiry.objects.create(**values);enquiry.activities.add(self.activity)
        return enquiry

    def test_custom_order_and_editable_slides(self):
        site=m.SiteSettings.get();site.domestic_state_order='Kerala\nGujarat';site.save()
        response=self.client.get(reverse('domestic'))
        self.assertEqual(response.context['states'][0]['name'],'Kerala')
        m.HomeSlide.objects.all().update(is_active=False)
        slide=m.HomeSlide.objects.create(title='Owner controlled heading',order=1,built_in_image='img/hero/kerala-v2.webp')
        self.assertContains(self.client.get(reverse('home')),slide.title)
        slide.is_active=False;slide.save()
        self.assertContains(self.client.get(reverse('home')),'/static/img/home-beach.jpg')

    def test_countries_and_international_group_scope(self):
        dest=m.Destination.objects.create(name='Audio test Thailand',region='international',state_or_country='Thailand')
        international=m.Package.objects.create(title='Audio test Thailand group',destination=dest,tour_type='group',short_description='Group',base_price=20000)
        response=self.client.get(reverse('group_tours'),{'region':'international','country':'thailand'})
        self.assertEqual(list(response.context['page'].object_list),[international])
        self.assertContains(response,'name="country" value="thailand"')
        self.assertTemplateUsed(self.client.get(reverse('international')),'travel/international_countries.html')

    def test_new_content_renders_safely_and_video_is_lazy(self):
        m.Sightseeing.objects.create(package=self.package,name='Visit',description='D '*500,visiting_hours='09:00 - 17:00',closed_days='Monday',admission='Confirm with venue',questions='When? | In the morning\nUnsafe? | </script><script>alert(1)</script>',youtube_url='https://youtu.be/abcdefghijk')
        m.Hotel.objects.create(package=self.package,name='Example Hotel',website='https://example.test/hotel',room_options='Garden room\nFamily suite',description='Hotel information')
        response=self.client.get(self.package.get_absolute_url())
        self.assertContains(response,'09:00 - 17:00')
        self.assertContains(response,'Family suite')
        self.assertContains(response,'data-readmore')
        self.assertContains(response,'data-youtube="abcdefghijk"')
        self.assertNotContains(response,'<iframe')
        self.assertNotContains(response,'</script><script>alert(1)</script>')

    def test_quote_is_authoritative_snapshot_with_private_margin_and_extras(self):
        enquiry=self.enquiry(quote_margin_percent=Decimal('10'))
        result=prepare_quotation(enquiry)
        # 2 adults + 1 child + Deluxe upgrade for 3 people + selected optional tour.
        self.assertEqual(result['base_cost'],34500)
        self.assertEqual(result['total'],37950)
        self.assertEqual(result['activities'],['Guided tour'])
        self.package.base_price=99999;self.package.save()
        enquiry.refresh_from_db();self.assertEqual(enquiry.quoted_price,37950)
        self.assertEqual(self.client.get(reverse('quotation_pdf',args=[enquiry.reference])).status_code,302)
        self.client.force_login(self.staff)
        response=self.client.get(reverse('quotation_pdf',args=[enquiry.reference]))
        self.assertEqual(response.status_code,200);self.assertTrue(response.content.startswith(b'%PDF'))

    def test_quote_requires_confirmed_cost_for_unknown_prices_and_rejects_bad_margin(self):
        self.package.price_on_request=True;self.package.save()
        enquiry=self.enquiry()
        with self.assertRaises(ValidationError):prepare_quotation(enquiry)
        enquiry.quote_base_override=50000;enquiry.quote_margin_percent=Decimal('9')
        self.assertEqual(prepare_quotation(enquiry)['total'],54500)
        enquiry.quote_margin_percent=101
        with self.assertRaises(ValidationError):prepare_quotation(enquiry)

    def test_contact_leads_and_booking_terms(self):
        payload={'name':'Example','email':'example@example.test','phone':'9999999999','message':'Please help plan a trip','website':''}
        self.assertEqual(self.client.post(reverse('contact'),payload).status_code,302)
        self.assertEqual(m.ContactRequest.objects.count(),1)
        payload['website']='spam';self.client.post(reverse('contact'),payload);self.assertEqual(m.ContactRequest.objects.count(),1)
        site=m.SiteSettings.get();site.booking_terms='Approved example terms';site.save()
        payload={'name':'Example','email':'example@example.test','phone':'9999999999','adults':2,'children':0,'hotel_tier':'standard'}
        url=reverse('create_enquiry',args=[self.package.slug])
        self.assertEqual(self.client.post(url,payload).status_code,400)
        with patch('travel.views.notify_enquiry_received'):
            payload['terms_accepted']='1';self.assertEqual(self.client.post(url,payload).status_code,200)
        self.assertEqual(m.Enquiry.objects.get().terms_snapshot,'Approved example terms')

    def test_analytics_is_optional_deduplicated_and_does_not_identify_anonymous_visitors(self):
        self.client.get(self.package.get_absolute_url());self.assertEqual(m.VisitEvent.objects.count(),0)
        self.client.cookies['sai_analytics']='yes';self.client.cookies['sai_visitor']='12345678-1234-4234-9234-123456789012'
        self.client.get(self.package.get_absolute_url());self.client.get(self.package.get_absolute_url())
        self.assertEqual(m.VisitEvent.objects.count(),1);self.assertIsNone(m.VisitEvent.objects.get().user)
        self.client.cookies['sai_analytics']='no';self.client.get(self.package.get_absolute_url());self.assertEqual(m.VisitEvent.objects.count(),1)

    @override_settings(CRM_API_TOKEN='test-private-token')
    def test_crm_exports_are_protected_and_versioned(self):
        url=reverse('crm_export',args=['enquiries']);self.enquiry()
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.get(url,HTTP_AUTHORIZATION='Bearer wrong').status_code,403)
        response=self.client.get(url,HTTP_AUTHORIZATION='Bearer test-private-token')
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['schema_version'],1)
        self.assertEqual(response.json()['results'][0]['email'],'traveller@example.test')

    def test_related_tours_prefer_same_state_and_nearby_prices(self):
        near=m.Package.objects.create(title='Audio test nearby trip',destination=self.destination,short_description='Near',base_price=11000)
        far=m.Package.objects.create(title='Audio test luxury trip',destination=self.destination,short_description='Far',base_price=90000)
        suggestions,_=relevant_tours(self.package,m.Package.objects.filter(is_active=True).select_related('destination').prefetch_related('themes'))
        self.assertEqual(suggestions[0].pk,near.pk)
        self.package.related_packages.add(far)
        suggestions,_=relevant_tours(self.package,m.Package.objects.filter(is_active=True).select_related('destination').prefetch_related('themes'))
        self.assertEqual(suggestions[0].pk,far.pk)

    def test_search_and_seo_do_not_expose_private_records(self):
        data=self.client.get(reverse('journey_search'),{'q':'Audio test Kerala'}).json()
        self.assertEqual(data['results'][0]['title'],self.package.title)
        self.assertNotIn('email',data['results'][0])
        self.assertContains(self.client.get(reverse('sitemap')),self.package.get_absolute_url())
        self.assertContains(self.client.get(reverse('robots')),'Disallow: /api/crm/')
