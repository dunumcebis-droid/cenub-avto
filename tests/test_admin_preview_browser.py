"""Admin preview regressions with complete interception of every API request.

Private photos are read only after the admin-only RPC succeeds; tests never
publish a listing, approve a payment, upload a photo or send mail.
"""
import copy
import json
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, owned_row

PHOTO_BASE = 'https://fixture.invalid/admin-preview-'
PHOTOS = [PHOTO_BASE + str(i) + '.svg' for i in range(36)]
FULL_DESCRIPTION = 'Tam yoxlama mətni. ' * 40 + 'SON TAM TƏSVİR'


class AdminPreviewBackend(AdminAuthBackend):
    def __init__(self):
        super().__init__()
        self.detail_calls = []
        self.pending_details = []
        self.delay_detail = False
        self.fail_detail = False
        self.missing_detail = False
        self.details = {}
        groups = {name: PHOTOS[i * 6:(i + 1) * 6]
                  for i, name in enumerate(('front', 'rear', 'side', 'interior', 'engine', 'other'))}
        for listing in (self.admin_rows[0], self.admin_rows[24], self.admin_rows[-1]):
            row = owned_row()
            row.update(listing)
            row.update(satici_id=OTHER_OWNER, tesvir=FULL_DESCRIPTION,
                       sekiller=PHOTOS, paket_adi='Pulsuz', telefon='+994000000001',
                       paket_tesdiq_qeydi='INTERNAL NOTE MUST NOT APPEAR')
            row['ca_data'].update(model=row['model'], photos=copy.deepcopy(groups),
                                  photo=PHOTOS[0], description=FULL_DESCRIPTION,
                                  pack='Pulsuz', phone=row['telefon'])
            self.details[row['id']] = row

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        if req.url.startswith(PHOTO_BASE):
            assert req.method == 'GET'
            route.fulfill(content_type='image/svg+xml', body=(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800">'
                '<rect width="1200" height="800" fill="#365a70"/></svg>'))
            return
        if parsed.path == '/rest/v1/rpc/ca_admin_listing_detail':
            assert req.method == 'POST'
            body = req.post_data_json
            assert set(body) == {'p_id'}
            admin = req.headers.get('authorization') == 'Bearer admin-token'
            self.detail_calls.append(dict(id=body['p_id'], admin=admin))
            if not admin:
                route.fulfill(status=403, content_type='application/json',
                              body='{"message":"Admin denied"}')
                return
            if self.fail_detail:
                route.fulfill(status=503, content_type='application/json',
                              body='{"message":"Synthetic preview unavailable"}')
                return
            data = None if self.missing_detail else copy.deepcopy(self.details.get(body['p_id']))
            if self.delay_detail:
                self.pending_details.append((route, data))
                return
            route.fulfill(content_type='application/json', body=json.dumps(data))
            return
        super().route(route)

    def finish_detail(self):
        route, data = self.pending_details.pop(0)
        route.fulfill(content_type='application/json', body=json.dumps(data))


class AdminPreviewBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(
            executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 375, 'height': 812}, has_touch=True)
        self.context.set_default_timeout(6000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.backend = AdminPreviewBackend()
        self.original_details = copy.deepcopy(self.backend.details)
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors)
        self.assertEqual(self.backend.details, self.original_details)
        self.assertFalse([call for call in self.backend.admin_calls
                          if call['name'] in ('ca_admin_status', 'ca_admin_paket_tesdiq', 'ca_admin_paket_reddet')])

    def open_admin(self):
        self.page.evaluate('''async id=>{
            currentUser={id,email:'admin@example.invalid',phone:'+994000000000'};
            caSession={access_token:'admin-token',expires_at:4102444800,user:{id}};
            updateAccountUI();await caAdminOpen();
        }''', OWNER)
        self.page.locator('#caAdminPanel').wait_for(state='visible')

    def preview_button(self, listing_id):
        return self.page.locator(f'#caAdminList button[data-preview-id="{listing_id}"]')

    def wait_for_pending(self):
        for _ in range(120):
            if self.backend.pending_details:
                return
            self.page.wait_for_timeout(10)
        self.fail('Preview request did not start')

    def test_pending_listing_full_details_photos_and_fullscreen_are_admin_only(self):
        self.open_admin()
        self.assertFalse(self.backend.detail_calls, 'Opening admin must not download every private photo')
        self.page.evaluate("caAdminFilter('gozlemede')")
        listing_id = self.backend.admin_rows[-1]['id']
        self.preview_button(listing_id).tap()
        self.page.wait_for_function('document.getElementById("detailOverlay").dataset.adminPreview==="true"')
        self.assertEqual(self.page.locator('#detailTitle').inner_text(), 'Toyota Admin-1205')
        self.assertEqual(self.page.locator('#detailDescriptionText').inner_text(), FULL_DESCRIPTION)
        self.assertEqual(self.page.locator('#galleryThumbs img').count(), 36)
        self.assertEqual(self.page.locator('#galleryThumbs img').evaluate_all('els=>els.map(e=>e.getAttribute("src"))'), PHOTOS)
        self.assertNotIn('INTERNAL NOTE MUST NOT APPEAR', self.page.locator('#detailOverlay').inner_text())
        self.assertTrue(self.page.locator('#caDetailShare').is_hidden())
        self.assertIsNone(self.page.evaluate('new URL(location.href).searchParams.get("ad")'))
        self.assertFalse(self.page.evaluate('id=>caRemoteCars.some(c=>c._id===id)||caListingCache.has(id)', listing_id))
        self.assertTrue(self.page.locator('#caToolsBar').is_hidden())
        self.page.locator('#galleryStage img').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='visible')
        self.assertEqual(self.page.locator('#caPhotoViewerCanvas img').get_attribute('src'), PHOTOS[0])
        self.page.locator('[data-ca-viewer="close"]').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='hidden')
        self.page.locator('#detailOverlay .detail-close').tap()
        self.assertTrue(self.page.locator('#caAdminPanel').is_visible())
        self.assertTrue(self.page.evaluate('activeDetailCar===null&&detailPhotos.length===0'))
        self.assertEqual(self.page.locator('#galleryStage img,#galleryThumbs img').count(), 0)
        self.assertEqual(self.page.locator('#detailDescriptionText').text_content(), '')
        self.assertIn('1 elan', self.page.locator('#caAdminMsg').inner_text())
        self.assertEqual(self.backend.detail_calls, [dict(id=listing_id, admin=True)])

    def test_preview_on_second_admin_page_does_not_change_filter_page_or_public_cache(self):
        self.open_admin()
        public_before = self.page.evaluate('caRemoteCars.map(c=>c._id)')
        self.page.evaluate('caAdminPage(1)')
        listing_id = self.backend.admin_rows[24]['id']
        self.preview_button(listing_id).tap()
        self.page.locator('#detailOverlay').wait_for(state='visible')
        self.assertEqual(self.page.locator('#detailTitle').inner_text(), 'Toyota Admin-0025')
        self.page.locator('#detailOverlay .detail-close').tap()
        self.assertIn('25–48', self.page.locator('#caAdminMsg').inner_text())
        self.assertEqual(self.page.evaluate('caRemoteCars.map(c=>c._id)'), public_before)
        self.assertTrue(self.preview_button(listing_id).is_visible())
        self.assertEqual(self.preview_button(listing_id).evaluate('e=>document.activeElement===e'), True)

    def test_closing_admin_discards_a_late_preview_response(self):
        self.open_admin()
        self.backend.delay_detail = True
        listing_id = self.backend.admin_rows[0]['id']
        self.preview_button(listing_id).tap()
        self.wait_for_pending()
        self.page.evaluate('caAdminClose()')
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assertTrue(self.page.locator('#caAdminPanel').is_hidden())
        self.assertTrue(self.page.locator('#detailOverlay').is_hidden())
        self.assertTrue(self.page.evaluate('activeDetailCar===null&&detailPhotos.length===0'))
        self.assertEqual(self.page.locator('#galleryStage img,#galleryThumbs img').count(), 0)
        self.assertEqual(self.page.locator('#detailDescriptionText').text_content(), '')

    def test_account_switch_discards_late_response_and_clears_an_open_private_view(self):
        self.open_admin()
        listing_id = self.backend.admin_rows[0]['id']
        self.preview_button(listing_id).tap()
        self.page.locator('#detailOverlay').wait_for(state='visible')
        self.page.locator('#galleryStage img').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='visible')
        self.page.evaluate('''id=>{currentUser={id,email:'other@example.invalid'};
            caSession={access_token:'user-token',expires_at:4102444800,user:{id}};
            caAdminSessionChanged();}''', OTHER_OWNER)
        self.assertTrue(self.page.locator('#caPhotoViewer').is_hidden())
        self.assertTrue(self.page.locator('#detailOverlay').is_hidden())
        self.assertTrue(self.page.evaluate('activeDetailCar===null&&detailPhotos.length===0'))
        self.assertEqual(self.page.locator('#galleryStage img,#galleryThumbs img').count(), 0)
        self.assertEqual(self.page.locator('#detailDescriptionText').text_content(), '')
        self.open_admin()
        self.backend.delay_detail = True
        self.preview_button(listing_id).tap()
        self.wait_for_pending()
        self.page.evaluate('''id=>{currentUser={id};caSession={access_token:'user-token',expires_at:4102444800,user:{id}};caAdminSessionChanged();}''', OTHER_OWNER)
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assertTrue(self.page.locator('#detailOverlay').is_hidden())

    def test_ordinary_account_cannot_fetch_or_open_private_admin_preview(self):
        listing_id = self.backend.admin_rows[-1]['id']
        self.page.evaluate('''id=>{currentUser={id};caSession={access_token:'user-token',expires_at:4102444800,user:{id}};caAdminSessionChanged();}''', OTHER_OWNER)
        result = self.page.evaluate('''async id=>{try{
            await caRequest('/rest/v1/rpc/ca_admin_listing_detail','POST',{p_id:id},'user-token');return 'unexpected';
        }catch(error){return error.message}}''', listing_id)
        self.assertEqual(result, 'Admin denied')
        self.assertTrue(self.page.locator('#detailOverlay').is_hidden())
        self.assertFalse(self.page.evaluate('id=>caRemoteCars.some(c=>c._id===id)||caListingCache.has(id)', listing_id))
        self.assertEqual(self.backend.detail_calls, [dict(id=listing_id, admin=False)])

    def test_missing_or_failed_detail_keeps_admin_open_without_an_empty_preview(self):
        self.open_admin()
        listing_id = self.backend.admin_rows[0]['id']
        self.backend.missing_detail = True
        button = self.preview_button(listing_id)
        button.tap()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("tapılmadı")')
        self.assertTrue(self.page.locator('#detailOverlay').is_hidden())
        self.assertFalse(button.is_disabled())
        self.backend.missing_detail = False
        self.backend.fail_detail = True
        button.tap()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Synthetic preview unavailable")')
        self.assertTrue(self.page.locator('#caAdminPanel').is_visible())
        self.assertTrue(self.page.locator('#detailOverlay').is_hidden())
        self.assertFalse(button.is_disabled())
