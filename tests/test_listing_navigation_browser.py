"""Numbered server paging and public listing links, with all HTTP mocked."""
import copy
import json
import os
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright
from test_listing_management_browser import OfflineBackend, ORIGIN, owned_row
from test_cards_browser import browse_fixture_response


def listing_rows(count):
    result=[]
    for n in range(count):
        row=owned_row()
        row.update(id=f'75757575-7575-4575-8575-{n:012d}',model=f'Listing-{n:04d}',paket_adi='Pulsuz')
        row['ca_data'].update(model=row['model'],pack='Pulsuz')
        result.append(row)
    return result


class NavigationBackend(OfflineBackend):
    def __init__(self,count=72):
        super().__init__(listing_rows(count))
        self.page_requests=[];self.detail_reads=[];self.fail_page=None;self.fail_detail=False
        self.delay_page=None;self.pending_page=[];self.delay_detail=False;self.pending_detail=[]

    def route(self,route):
        request=route.request;parsed=urlsplit(request.url)
        if parsed.path=='/rest/v1/rpc/ca_browse_listings':
            payload=request.post_data_json;self.page_requests.append(copy.deepcopy(payload))
            data=browse_fixture_response(self.rows,payload)
            if data['total']==0:data['total_pages']=0
            if self.fail_page==payload['p_page']:
                route.fulfill(status=503,content_type='application/json',body='{"message":"Synthetic page unavailable"}');return
            if self.delay_page==payload['p_page']:
                self.pending_page.append((route,data));return
            route.fulfill(content_type='application/json',body=json.dumps(data));return
        if parsed.path=='/rest/v1/elanlar' and request.method=='GET' and 'id' in parse_qs(parsed.query):
            self.detail_reads.append({'query':parse_qs(parsed.query),'headers':dict(request.headers)})
            if self.fail_detail:
                route.fulfill(status=503,content_type='application/json',body='{"message":"Synthetic detail unavailable"}');return
            if self.delay_detail:self.pending_detail.append(route);return
        super().route(route)

    def release_page(self):
        route,data=self.pending_page.pop(0)
        route.fulfill(content_type='application/json',body=json.dumps(data))


class ListingNavigationBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':375,'height':812},has_touch=True)
        self.context.set_default_timeout(6000)
        self.page=self.context.new_page();self.errors=[];self.backend=NavigationBackend()
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.route('**/*',self.backend.route)
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')

    def tearDown(self):
        for route in self.backend.pending_detail:
            try:route.abort()
            except Exception:pass
        self.page.wait_for_timeout(15)
        self.context.close();self.assertFalse(self.errors)
        self.assertFalse([c for c in self.backend.calls if c['method'] in ('PATCH','DELETE')])

    def go(self,suffix=''):
        self.page.goto(ORIGIN+suffix,wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded&&!caBrowseState.loading')

    def page_number(self,n):
        return self.page.locator(f'#caPagination button[data-page="{n}"]')

    def wait_page(self,n):
        self.page.wait_for_function('n=>!caBrowseState.loading&&caBrowseState.page===n',arg=n)

    def open_first(self):
        self.page.locator('#allGrid .ca-visible-car-name').first.tap()
        self.page.locator('#caShareListingBtn').wait_for(state='visible')

    def test_numbered_buttons_appear_only_after_24_and_follow_server_pages(self):
        for count,expected in ((0,[]),(1,[]),(24,[]),(25,['1','2']),(72,['1','2','3'])):
            with self.subTest(count=count):
                self.backend.rows=listing_rows(count);self.go()
                self.assertEqual(self.page.locator('#caPagination .ca-page-number').all_text_contents(),expected)
                self.assertEqual(self.page.locator('#caPagination').is_visible(),count>24)
        self.page_number(3).tap();self.wait_page(3)
        self.assertEqual(self.page.locator('#allGrid .car-card').count(),24)
        self.assertIn('Listing-0048',self.page.locator('#allGrid').inner_text())
        self.assertEqual(self.page_number(3).get_attribute('aria-current'),'page')
        self.assertTrue(self.page.locator('#caPageNext').is_disabled())
        self.page.locator('#caPagePrev').tap();self.wait_page(2)
        self.assertTrue(all(r['p_page_size']==24 for r in self.backend.page_requests))
        self.page.set_viewport_size({'width':320,'height':812})
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),320)

    def test_numbered_last_page_remains_reachable_beyond_500_without_50_buttons(self):
        self.backend.rows=listing_rows(1200);self.go()
        self.assertLessEqual(self.page.locator('#caPagination .ca-page-number').count(),7)
        self.page_number(50).tap();self.wait_page(50)
        self.assertIn('Listing-1176',self.page.locator('#allGrid').inner_text())
        self.assertEqual(self.page.locator('#caPageLabel').inner_text(),'50 / 50')
        self.assertTrue(self.page.locator('#caPageNext').is_disabled())
        self.page.locator('#caPagePrev').tap();self.wait_page(49)
        self.page_number(1).tap();self.wait_page(1)
        self.assertTrue(self.page.locator('#caPagePrev').is_disabled())

    def test_loading_disables_pages_and_failed_fetch_retains_previous_page(self):
        self.go();before=self.page.locator('#allGrid').inner_text()
        self.backend.delay_page=2;self.page_number(2).tap()
        self.page.wait_for_function('caBrowseState.loading')
        self.assertTrue(self.page.locator('#caPagination button').evaluate_all('buttons=>buttons.every(b=>b.disabled)'))
        self.backend.release_page();self.wait_page(2)
        self.backend.fail_page=3;self.page_number(3).tap()
        self.page.wait_for_function('caBrowseState.error&&!caBrowseState.loading')
        self.assertEqual(self.page_number(2).get_attribute('aria-current'),'page')
        self.assertIn('Listing-0024',self.page.locator('#allGrid').inner_text())
        self.assertNotEqual(self.page.locator('#allGrid').inner_text(),before)
        self.backend.fail_page=None
        self.page.locator('#caListingsNotice button').tap();self.wait_page(3)

    def test_fresh_public_link_opens_record_beyond_current_page_with_scoped_anonymous_read(self):
        self.backend.rows=listing_rows(650);target=self.backend.rows[610]
        self.go('?ad='+target['id'])
        self.page.wait_for_function('document.getElementById("detailOverlay").classList.contains("open")')
        self.assertIn('Listing-0610',self.page.locator('#detailTitle').inner_text())
        self.assertEqual(self.page.locator('#allGrid .car-card').count(),24)
        self.assertNotIn('Listing-0610',self.page.locator('#allGrid').inner_text())
        read=self.backend.detail_reads[-1]
        self.assertEqual(read['query'].get('veziyyet'),['eq.aktiv'])
        self.assertEqual(read['query'].get('limit'),['1'])
        self.assertNotIn('authorization',read['headers'])
        self.assertNotIn('*',read['query']['select'][0])
        self.assertNotIn('paket_tesdiq_qeydi',read['query']['select'][0])
        self.assertEqual(self.page.locator('#galleryStage img').get_attribute('src'),target['sekiller'][0])

    def test_private_missing_and_malformed_links_never_render_hidden_records(self):
        for status in ('gozlemede','reddedildi','silindi'):
            with self.subTest(status=status):
                row=listing_rows(1)[0];row.update(model='Hidden listing',veziyyet=status)
                self.backend.rows=[row];self.go('?ad='+row['id'])
                self.page.locator('#caListingLinkNotice').wait_for(state='visible')
                self.page.wait_for_function('document.getElementById("caListingLinkNotice").textContent.includes("tapılmadı")')
                self.assertFalse(self.page.locator('#detailOverlay').is_visible())
                self.assertNotIn('Hidden listing',self.page.locator('body').inner_text())
        reads=len(self.backend.detail_reads)
        self.go('?ad=%3Cscript%3E')
        self.assertIn('düzgün deyil',self.page.locator('#caListingLinkNotice').inner_text())
        self.assertEqual(len(self.backend.detail_reads),reads)

    def test_share_uses_current_public_id_and_never_copies_callback_or_tracking_parameters(self):
        self.page.add_init_script("window.__shares=[];navigator.share=async data=>{window.__shares.push(data)}")
        self.go('?tracking=private-test#unrelated');self.open_first()
        self.page.locator('#caShareListingBtn').tap()
        self.page.wait_for_function('window.__shares.length===1')
        expected=ORIGIN+'?ad='+self.backend.rows[0]['id']
        self.assertEqual(self.page.evaluate('window.__shares[0].url'),expected)
        self.assertNotIn('tracking',self.page.evaluate('window.__shares[0].url'))
        self.page.evaluate("navigator.share=async()=>{throw new DOMException('cancelled','AbortError')};window.__copy=[];Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>window.__copy.push(text)}})")
        self.page.locator('#caShareListingBtn').tap()
        self.page.wait_for_function('document.getElementById("caShareListingStatus").textContent.includes("ləğv")')
        self.assertEqual(self.page.evaluate('window.__copy'),[])
        self.page.evaluate('navigator.share=undefined')
        self.page.locator('#caShareListingBtn').tap()
        self.page.wait_for_function('window.__copy.length===1')
        self.assertEqual(self.page.evaluate('window.__copy[0]'),expected)
        self.page.evaluate("()=>{navigator.clipboard.writeText=async()=>{throw Error('denied')}}")
        self.page.locator('#caShareListingBtn').tap()
        self.assertEqual(self.page.locator('#caListingLinkManual').input_value(),expected)
        self.assertTrue(self.page.locator('#caListingLinkManual').get_attribute('readonly') is not None)

    def test_failed_detail_can_retry_and_admin_preview_never_offers_public_share(self):
        target=self.backend.rows[30];self.backend.fail_detail=True
        self.go('?ad='+target['id'])
        retry=self.page.locator('#caListingLinkNotice button');retry.wait_for(state='visible')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        self.backend.fail_detail=False;retry.tap()
        self.page.wait_for_function('document.getElementById("detailOverlay").classList.contains("open")')
        self.assertIn(target['model'],self.page.locator('#detailTitle').inner_text())
        self.page.evaluate("document.getElementById('detailOverlay').dataset.adminPreview='true'")
        self.page.locator('#caDetailShare').wait_for(state='hidden')
        self.page.evaluate("document.getElementById('detailOverlay').dataset.adminPreview='false'")
        self.page.locator('#caShareListingBtn').wait_for(state='visible')

    def ignore_fetch_abort_for_race_test(self):
        # A response can already be in flight when navigation aborts it. Ignoring
        # the signal exercises the sequence guard rather than only cancellation.
        self.page.add_init_script('''(()=>{const original=window.fetch.bind(window);window.fetch=(url,options={})=>original(url,{...options,signal:undefined})})()''')

    def begin_delayed_link(self):
        self.backend.delay_detail=True
        target=self.backend.rows[49]
        self.go('?ad='+target['id'])
        for _ in range(100):
            if self.backend.pending_detail:
                break
            self.page.wait_for_timeout(10)
        self.assertTrue(self.backend.pending_detail)
        return target

    def finish_delayed_link(self,target):
        self.backend.pending_detail.pop(0).fulfill(content_type='application/json',body=json.dumps([target]))
        self.page.wait_for_timeout(80)

    def test_user_page_navigation_discards_a_late_shared_link_response(self):
        self.ignore_fetch_abort_for_race_test()
        target=self.begin_delayed_link()
        self.page_number(2).tap();self.wait_page(2)
        self.finish_delayed_link(target)
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        self.assertEqual(self.page.evaluate('caBrowseState.page'),2)
        self.assertTrue(self.page.locator('#caListingLinkNotice').is_hidden())

    def test_new_search_filter_brand_sort_or_account_intent_cancels_old_shared_link(self):
        self.ignore_fetch_abort_for_race_test()
        for action in ('search','filter','brand','sort','price-input','cabinet','sell'):
            with self.subTest(action=action):
                target=self.begin_delayed_link()
                if action in ('search','price-input'):self.page.locator('#caFilterLaunch').tap()
                if action=='search':self.page.locator('button[onclick="searchCars()"]').first.tap()
                elif action=='filter':self.page.locator('button.pill').filter(has_text='Önə çıxarılan').tap()
                elif action=='brand':self.page.locator('.mercedes-tile').tap()
                elif action=='sort':
                    self.page.locator('#sortListings').focus()
                    self.page.keyboard.press('ArrowDown');self.page.keyboard.press('Enter')
                elif action=='price-input':self.page.locator('#searchPrice').fill('50000')
                elif action=='cabinet':self.page.locator('header .back-btn').tap()
                elif action=='sell':self.page.locator('header .header-sell').tap()
                self.finish_delayed_link(target)
                self.assertFalse(self.page.locator('#detailOverlay').is_visible())
                self.assertTrue(self.page.locator('#caListingLinkNotice').is_hidden())

    def test_background_render_does_not_cancel_the_initial_shared_link(self):
        self.ignore_fetch_abort_for_race_test()
        target=self.begin_delayed_link()
        self.page.evaluate('render();render()')
        self.finish_delayed_link(target)
        self.page.locator('#detailOverlay').wait_for(state='visible')
        self.assertIn('Listing-0049',self.page.locator('#detailTitle').inner_text())

    def test_manually_opening_the_same_card_keeps_its_photo_viewer_when_old_link_finishes(self):
        self.ignore_fetch_abort_for_race_test()
        self.backend.delay_detail=True
        target=self.backend.rows[0]
        self.go('?ad='+target['id'])
        for _ in range(100):
            if self.backend.pending_detail:break
            self.page.wait_for_timeout(10)
        self.assertTrue(self.backend.pending_detail)
        self.page.locator('#allGrid .car-card .car-cover').first.tap()
        self.page.locator('#galleryStage .ca-gallery-open').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='visible')
        self.finish_delayed_link(target)
        self.assertTrue(self.page.locator('#caPhotoViewer').is_visible())
        self.assertEqual(self.page.locator('#caPhotoViewerCanvas img').get_attribute('src'),target['sekiller'][0])
