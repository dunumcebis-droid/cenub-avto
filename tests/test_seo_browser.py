"""Public listing SEO and privacy, with every HTTP request intercepted.

Synthetic rows exercise browser behavior, not database RLS or Google indexing.
No real account, email, advertisement, storage object, or provider is changed.
"""
import copy
import json
import mimetypes
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from test_listing_management_browser import ORIGIN, ROOT, OWNER, OTHER_OWNER, safe_local_asset
from test_listing_navigation_browser import NavigationBackend, listing_rows
from test_admin_preview_browser import AdminPreviewBackend, FULL_DESCRIPTION, PHOTOS


CONFIG = json.loads((ROOT / 'seo.config.json').read_text())
BASE = CONFIG['baseUrl']
HOME = next(page for page in CONFIG['pages'] if page['file'] == 'index.html')


class SEOBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
                                             headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 1000})
        self.context.set_default_timeout(6000)
        self.backend = NavigationBackend()
        self.errors = []
        self.requests = []
        # Context routing also covers the first document of a modifier-clicked tab.
        self.context.route('**/*', self.route)
        self.context.on('page', lambda page: page.on('pageerror', lambda error: self.errors.append(str(error))))
        self.page = self.context.new_page()
        self.context.on('request', lambda request: self.requests.append((request.method, urlsplit(request.url).path)))
        self.context.add_init_script('window.alert=()=>{};window.confirm=()=>true')

    def route(self, route):
        # Also intercept configured production URLs if any native navigation
        # reaches one; no request is allowed to leave this test.
        if route.request.url.startswith(BASE):
            local = safe_local_asset(ORIGIN + route.request.url[len(BASE):])
            if local is not None and local.is_file() and route.request.method == 'GET':
                route.fulfill(content_type=mimetypes.guess_type(local.name)[0] or 'application/octet-stream',
                              body=local.read_bytes())
            else:
                route.abort()
            return
        self.backend.route(route)

    def tearDown(self):
        for item in getattr(self.backend, 'pending_detail', []):
            try:
                item.abort()
            except Exception:
                pass
        for item in getattr(self.backend, 'pending_details', []):
            try:
                item[0].abort()
            except Exception:
                pass
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertFalse([call for call in self.backend.calls if call['method'] in ('PATCH', 'DELETE')])
        self.assertFalse([request for request in self.requests
                          if request[0] != 'GET' and request[1].startswith('/auth/')])

    def go(self, suffix=''):
        self.page.goto(ORIGIN + suffix, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded&&!caBrowseState.loading')

    def open_first(self):
        self.page.locator('#allGrid .ca-visible-car-name').first.click()
        self.page.locator('#detailOverlay').wait_for(state='visible')

    def meta(self, key):
        return self.page.locator(f'head meta[name="{key}"],head meta[property="{key}"]').get_attribute('content')

    def canonical(self):
        self.assertEqual(self.page.locator('head link[rel="canonical"]').count(), 1)
        return self.page.locator('head link[rel="canonical"]').get_attribute('href')

    def listing_data(self):
        self.page.locator('#ca-seo-listing-data').wait_for(state='attached')
        return json.loads(self.page.locator('#ca-seo-listing-data').text_content())

    def assert_home_metadata(self, noindex=False):
        self.page.wait_for_function('title=>document.title===title', arg=HOME['title'])
        self.assertEqual(self.canonical(), BASE)
        self.assertEqual(self.meta('description'), HOME['description'])
        self.assertEqual(self.meta('og:url'), BASE)
        self.assertEqual(self.meta('og:title'), HOME['title'])
        self.assertEqual(self.meta('twitter:title'), HOME['title'])
        self.assertEqual(self.meta('og:image:type'), 'image/png')
        self.assertEqual(self.page.locator('#ca-seo-listing-data').count(), 0)
        self.assertEqual('noindex' in self.meta('robots'), noindex)

    def test_valid_public_link_sets_clean_canonical_social_and_car_offer_data(self):
        target = self.backend.rows[31]
        self.go('?ad=' + target['id'] + '&utm_source=private-test#private-fragment')
        self.page.locator('#detailOverlay').wait_for(state='visible')
        data = self.listing_data()
        expected = BASE + '?ad=' + target['id']
        self.assertEqual(self.canonical(), expected)
        self.assertEqual(self.meta('og:url'), expected)
        self.assertIn(target['model'], self.page.title())
        self.assertIn(str(target['il']), self.page.title())
        self.assertIn(self.page.locator('#detailPrice').inner_text(), self.page.title())
        self.assertEqual(self.meta('og:title'), self.page.title())
        self.assertEqual(self.meta('twitter:title'), self.page.title())
        self.assertEqual(self.meta('og:image:type'), '')
        self.assertNotIn('noindex', self.meta('robots'))
        self.assertEqual(data['@context'], 'https://schema.org')
        self.assertEqual(data['@type'], 'Car')
        self.assertEqual(data['url'], expected)
        self.assertIn(target['model'], data['name'])
        self.assertEqual(data['offers']['@type'], 'Offer')
        self.assertEqual(data['offers']['priceCurrency'], 'AZN')
        self.assertEqual(float(data['offers']['price']), target['qiymet'])
        self.assertEqual(data['offers']['url'], expected)
        self.assertIn(target['sekiller'][0], json.dumps(data))
        self.assertNotIn('private-test', self.page.locator('head').inner_html())
        self.assertNotIn('private-fragment', self.page.locator('head').inner_html())
        read = self.backend.detail_reads[-1]
        self.assertEqual(read['query'].get('veziyyet'), ['eq.aktiv'])
        self.assertNotIn('authorization', read['headers'])
        # Ownership affects analytics/report actions, not public availability.
        self.page.evaluate('''async id=>caPersistSession({access_token:'seller-token',expires_at:4102444800,
            user:{id,email:'owner@example.invalid',user_metadata:{telefon:'+994000000000'}}})''', OWNER)
        self.assertEqual(self.listing_data()['url'], expected)
        self.assertEqual(self.canonical(), expected)
        self.assertNotIn('noindex', self.meta('robots'))

    def test_public_cards_have_real_links_and_support_regular_and_new_tab_navigation(self):
        self.go()
        anchors = self.page.locator('#allGrid .car-card a[href*="?ad="]')
        self.assertEqual(anchors.count(), 24)
        target = self.backend.rows[0]
        expected = BASE + '?ad=' + target['id']
        link_url = ORIGIN + '?ad=' + target['id']
        self.assertEqual(anchors.first.get_attribute('href'), link_url)
        self.assertIn(target['model'], anchors.first.inner_text())
        anchors.first.click()
        self.listing_data()
        self.assertEqual(self.canonical(), expected)
        self.assertTrue(self.page.locator('#detailOverlay').is_visible())
        self.page.locator('#detailOverlay .detail-close').click()
        self.assert_home_metadata()
        # A browser-created modifier tab may have no opener, unlike window.open.
        with self.context.expect_page() as popup_event:
            self.page.locator('#allGrid .car-card a[href*="?ad="]').first.click(modifiers=['Control'])
        popup = popup_event.value
        # Chromium's browser-created tab can issue its first localhost document
        # before Playwright installs interception. Explicit navigation exercises
        # the same href through the controlled fixture route.
        popup.goto(link_url, wait_until='load')
        popup.locator('#ca-seo-listing-data').wait_for(state='attached')
        self.assertEqual(popup.url, link_url)
        self.assertEqual(popup.locator('head link[rel="canonical"]').get_attribute('href'), expected)
        popup.close()
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())

    def test_closing_public_detail_restores_home_metadata_without_listing_schema(self):
        self.go()
        self.assert_home_metadata()
        self.open_first()
        self.listing_data()
        self.page.locator('#detailOverlay .detail-close').click()
        self.assert_home_metadata()
        self.assertEqual(self.page.locator('#seo-structured-data').count(), 1)

    def test_unavailable_private_malformed_and_sold_links_never_publish_listing_metadata(self):
        for status in ('gozlemede', 'reddedildi', 'silindi', 'sold', 'missing', 'malformed'):
            with self.subTest(status=status):
                target = listing_rows(1)[0]
                target.update(model='PRIVATE SEO SENTINEL', tesvir='PRIVATE DESCRIPTION SENTINEL')
                target['ca_data'].update(model=target['model'], description=target['tesvir'])
                if status in ('gozlemede', 'reddedildi', 'silindi'):
                    target['veziyyet'] = status
                elif status == 'sold':
                    target['is_sold'] = True
                self.backend.rows = [] if status == 'missing' else [target]
                self.go('?ad=' + ('not-a-uuid' if status == 'malformed' else target['id']))
                self.page.wait_for_function('document.querySelector("#caListingLinkNotice[role=alert]")')
                self.assert_home_metadata(noindex=True)
                head = self.page.locator('head').inner_html()
                self.assertNotIn('PRIVATE SEO SENTINEL', head)
                self.assertNotIn('PRIVATE DESCRIPTION SENTINEL', head)
                self.assertFalse(self.page.locator('#detailOverlay').is_visible())

    def test_private_options_and_preview_flags_clear_previous_public_metadata(self):
        self.go()
        self.open_first()
        self.listing_data()
        private = copy.deepcopy(self.backend.rows[0])
        private.update(model='ACTIVE PRIVATE PREVIEW', tesvir='PRIVATE PREVIEW DESCRIPTION')
        private['ca_data'].update(model=private['model'], description=private['tesvir'])
        self.page.evaluate('row=>caOpenCarRecord(caRemoteToCar(row),{adminPreview:true})', private)
        self.assert_home_metadata(noindex=True)
        self.assertNotIn('ACTIVE PRIVATE PREVIEW', self.page.locator('head').inner_html())
        self.page.locator('#detailOverlay .detail-close').click()
        self.assert_home_metadata()
        for flag in ('privatePreview', 'adminPreview'):
            with self.subTest(flag=flag):
                self.open_first()
                self.listing_data()
                self.page.evaluate('flag=>document.getElementById("detailOverlay").dataset[flag]="true"', flag)
                self.assert_home_metadata(noindex=True)
                self.page.locator('#detailOverlay .detail-close').click()
                self.assert_home_metadata()

    def test_real_admin_preview_and_account_switch_never_put_private_fields_in_head(self):
        self.backend = AdminPreviewBackend()
        self.go()
        self.page.evaluate('''async id=>{
            currentUser={id,email:'admin@example.invalid',phone:'+994000000000'};
            caSession={access_token:'admin-token',expires_at:4102444800,user:{id}};
            updateAccountUI();await caAdminOpen();
        }''', OWNER)
        self.page.locator('#caAdminPanel').wait_for(state='visible')
        self.page.evaluate("caAdminFilter('gozlemede')")
        listing_id = self.backend.admin_rows[-1]['id']
        self.page.locator(f'#caAdminList button[data-preview-id="{listing_id}"]').click()
        self.page.wait_for_function('document.getElementById("detailOverlay").dataset.adminPreview==="true"')
        self.assert_home_metadata(noindex=True)
        head = self.page.locator('head').inner_html()
        for value in (FULL_DESCRIPTION, PHOTOS[0], 'Admin-1205', listing_id):
            self.assertNotIn(value, head)
        self.page.evaluate('''id=>{
            currentUser={id,email:'other@example.invalid'};
            caSession={access_token:'other-token',expires_at:4102444800,user:{id}};
            updateAccountUI();
        }''', OTHER_OWNER)
        self.page.locator('#detailOverlay').wait_for(state='hidden')
        self.assert_home_metadata()
        self.assertFalse([call for call in self.backend.admin_calls
                          if call['name'] in ('ca_admin_status', 'ca_admin_paket_tesdiq', 'ca_admin_paket_reddet')])

    def test_cancelled_shared_link_response_cannot_restore_listing_metadata(self):
        self.page.add_init_script('''(()=>{const original=window.fetch.bind(window);window.fetch=(url,options={})=>original(url,{...options,signal:undefined})})()''')
        target = self.backend.rows[49]
        self.backend.delay_detail = True
        self.go('?ad=' + target['id'])
        for _ in range(100):
            if self.backend.pending_detail:
                break
            self.page.wait_for_timeout(10)
        self.assertTrue(self.backend.pending_detail)
        self.page.locator('#caPagination [data-page="2"]').click()
        self.page.wait_for_function('!caBrowseState.loading&&caBrowseState.page===2')
        self.backend.pending_detail.pop(0).fulfill(content_type='application/json', body=json.dumps([target]))
        self.page.wait_for_timeout(80)
        self.page.wait_for_function('document.querySelector("head link[rel=canonical]")?.href.endsWith("?page=2")')
        self.assertEqual(self.canonical(), BASE + '?page=2')
        self.assertEqual(self.page.locator('#ca-seo-listing-data').count(), 0)
        self.assertNotIn(target['model'], self.page.title())
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())

    def test_admin_entry_url_is_noindex_and_canonical_excludes_private_parameters(self):
        self.go('?admin-email=1&utm_source=private-test#private-fragment')
        self.assert_home_metadata(noindex=True)
        self.assertNotIn('private-test', self.page.locator('head').inner_html())
        self.assertNotIn('private-fragment', self.page.locator('head').inner_html())

    def test_numbered_pages_are_crawlable_and_filters_do_not_publish_duplicate_page_urls(self):
        self.go('?page=2')
        self.page.wait_for_function('!caBrowseState.loading&&caBrowseState.page===2')
        self.assertIn('Listing-0024', self.page.locator('#allGrid').inner_text())
        self.page.wait_for_function('document.querySelector("head link[rel=canonical]")?.href.endsWith("?page=2")')
        self.assertEqual(self.canonical(), BASE + '?page=2')
        self.assertIn('2', self.page.title())
        next_page = self.page.locator('#caPagination a[data-page="3"]')
        self.assertEqual(next_page.get_attribute('href'), ORIGIN + '?page=3')
        next_page.click()
        self.page.wait_for_function('!caBrowseState.loading&&caBrowseState.page===3')
        self.assertEqual(self.canonical(), BASE + '?page=3')
        self.assertIn('Listing-0048', self.page.locator('#allGrid').inner_text())
        self.page.evaluate("document.getElementById('searchMake').value='BMW';searchCars()")
        self.page.wait_for_function('!caBrowseState.loading&&currentSearch?.make==="BMW"')
        self.assertEqual(self.page.locator('#caPagination a[data-page]').count(), 0)
        self.assertEqual(self.canonical(), BASE)
        self.assertIn('noindex', self.meta('robots'))
        self.page.evaluate('async()=>await clearCarSearch()')
        self.page.locator('#sortListings').select_option('priceAsc')
        self.page.wait_for_function('!caBrowseState.loading&&document.getElementById("sortListings").value==="priceAsc"')
        self.assertEqual(self.page.locator('#caPagination a[data-page]').count(), 0)
        self.assertEqual(self.canonical(), BASE)
        self.assertIn('noindex', self.meta('robots'))


if __name__ == '__main__':
    unittest.main()
