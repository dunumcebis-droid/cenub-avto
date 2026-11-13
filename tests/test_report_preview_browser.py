"""Admin report previews with fully intercepted HTTP and private off-page rows.

No real account, listing, image, report, notification or payment is changed.
"""
import copy
import json
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, OTHER_ID, owned_row
from test_marketplace_browser import MarketplaceBackend, REPORT_ID

PRIVATE_ID = '99999999-9999-4999-8999-999999999999'
PRIVATE_DESCRIPTION = 'Yalnız admin üçün tam şikayət elanı. ' * 30 + 'SON MƏTN'


class ReportPreviewBackend(MarketplaceBackend):
    def __init__(self):
        super().__init__()
        self.detail_calls = []
        self.pending_details = []
        self.hold_detail = False
        self.fail_detail = False
        self.missing_detail = False
        self.wrong_detail_id = False
        self.reports[0].update(elan_id=PRIVATE_ID, marka='Toyota', model='Report-Private')
        self.private_row = owned_row()
        self.private_row.update(id=PRIVATE_ID, satici_id=OTHER_OWNER, marka='Toyota', model='Report-Private',
                                veziyyet='gozlemede', tesvir=PRIVATE_DESCRIPTION,
                                paket_tesdiq_qeydi='INTERNAL NOTE NOT FOR DETAIL')
        self.private_row['ca_data'].update(make='Toyota', model='Report-Private', description=PRIVATE_DESCRIPTION)
        self.detail_rows = {PRIVATE_ID: self.private_row}

    def route(self, route):
        req = route.request
        if urlsplit(req.url).path == '/rest/v1/rpc/ca_admin_listing_detail':
            assert req.method == 'POST'
            body = req.post_data_json
            assert set(body) == {'p_id'}
            authorized = req.headers.get('authorization') == 'Bearer admin-token'
            self.detail_calls.append(dict(id=body['p_id'], authorized=authorized))
            if not authorized:
                route.fulfill(status=403, content_type='application/json', body='{"message":"Admin denied"}')
                return
            if self.fail_detail:
                route.fulfill(status=503, content_type='application/json', body='{"message":"Synthetic preview unavailable"}')
                return
            value = copy.deepcopy(self.detail_rows.get(body['p_id'])) if not self.missing_detail else None
            if self.wrong_detail_id and value is not None:
                value['id'] = OTHER_ID
            if self.hold_detail:
                self.pending_details.append((route, value))
                return
            route.fulfill(content_type='application/json', body=json.dumps(value))
            return
        super().route(route)

    def finish_detail(self, index=0):
        route, value = self.pending_details.pop(index)
        route.fulfill(content_type='application/json', body=json.dumps(value))


class ReportPreviewBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 1000}, has_touch=True)
        self.context.set_default_timeout(5000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error:self.errors.append(str(error)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>__alerts.push(String(m));window.confirm=()=>true')
        self.backend = ReportPreviewBackend()
        self.original_private_row = copy.deepcopy(self.backend.private_row)
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertEqual(self.backend.private_row, self.original_private_row)
        self.assertFalse([c for c in self.backend.admin_calls if c['name'] in
                          ('ca_admin_status', 'ca_admin_paket_tesdiq', 'ca_admin_paket_reddet')])
        self.assertFalse(self.backend.calls_for('ca_record_listing_event'), 'Private previews cannot count public views/clicks')

    def sign_in(self, admin=True):
        self.page.evaluate('''async ({id,token})=>await caPersistSession({access_token:token,expires_at:4102444800,
            user:{id,email:'offline@example.invalid',user_metadata:{telefon:'+994000000000'}}})''',
                           dict(id=OWNER if admin else OTHER_OWNER, token='admin-token' if admin else 'other-token'))

    def open_admin(self):
        self.sign_in()
        self.page.evaluate('async()=>await caAdminOpen()')
        expect(self.page.locator('#caReportsAdmin')).to_be_visible()
        expect(self.preview_button()).to_be_visible()

    def preview_button(self):
        return self.page.locator('[data-ca-report-preview="'+REPORT_ID+'"]')

    def open_preview(self):
        self.open_admin()
        self.preview_button().click()
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.assertEqual(self.page.locator('#detailOverlay').get_attribute('data-admin-preview'), 'true')

    def start_held_preview(self):
        self.open_admin()
        self.backend.hold_detail = True
        self.preview_button().click()
        for _ in range(200):
            if self.backend.pending_details:
                return
            self.page.wait_for_timeout(10)
        self.fail('Expected held private preview RPC')

    def assert_private_closed(self):
        expect(self.page.locator('#detailOverlay')).not_to_be_visible()
        self.assertTrue(self.page.evaluate('activeDetailCar===null&&detailPhotos.length===0'))
        self.assertEqual(self.page.locator('#galleryStage img,#galleryThumbs img').count(), 0)
        self.assertFalse(self.page.evaluate('id=>caListingCache.has(id)||caRemoteCars.some(c=>c._id===id)', PRIVATE_ID))

    def test_offpage_report_opens_exact_private_id_with_full_photos_and_returns_to_report(self):
        self.open_admin()
        self.assertEqual(self.page.locator('#caAdminList [data-ad-row-id="'+PRIVATE_ID+'"]').count(), 0)
        self.assertFalse(self.backend.detail_calls, 'Opening reports must not fetch every private listing')
        public_before = self.page.evaluate('caRemoteCars.map(c=>c._id)')
        self.preview_button().click()
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.assertEqual(self.backend.detail_calls, [dict(id=PRIVATE_ID, authorized=True)])
        self.assertEqual(self.page.locator('#detailTitle').inner_text(), 'Toyota Report-Private')
        self.assertEqual(self.page.locator('#detailDescriptionText').inner_text(), PRIVATE_DESCRIPTION)
        self.assertEqual(self.page.locator('#galleryThumbs img').count(), len(self.backend.private_row['sekiller']))
        self.assertNotIn('INTERNAL NOTE NOT FOR DETAIL', self.page.locator('#detailOverlay').inner_text())
        self.assertTrue(self.page.locator('#caDetailShare').is_hidden())
        self.assertIsNone(self.page.evaluate('new URL(location.href).searchParams.get("ad")'))
        self.assertEqual(self.page.evaluate('caRemoteCars.map(c=>c._id)'), public_before)
        self.page.locator('#detailOverlay .detail-close').click()
        self.assert_private_closed()
        expect(self.page.locator('#caReportsAdmin')).to_be_visible()
        expect(self.preview_button()).to_be_focused()

    def test_failure_and_missing_listing_preserve_report_filter_and_allow_retry(self):
        self.open_admin()
        self.page.locator('#caReportsFilter').select_option('all')
        self.backend.fail_detail = True
        self.preview_button().click()
        expect(self.page.locator('#caReportsMessage')).to_contain_text('Elan açılmadı')
        expect(self.preview_button()).to_be_enabled()
        self.assert_private_closed()
        self.backend.fail_detail = False
        self.backend.missing_detail = True
        self.preview_button().click()
        expect(self.page.locator('#caReportsMessage')).to_contain_text('Elan tapılmadı')
        expect(self.preview_button()).to_be_enabled()
        expect(self.page.locator('#caReportsFilter')).to_have_value('all')
        self.assert_private_closed()
        self.backend.missing_detail = False
        self.preview_button().click()
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        expect(self.page.locator('#caReportsFilter')).to_have_value('all')
        self.assertEqual(len(self.backend.detail_calls), 3)

    def test_mismatched_returned_listing_id_is_rejected(self):
        self.backend.wrong_detail_id = True
        self.open_admin()
        self.preview_button().click()
        expect(self.page.locator('#caReportsMessage')).to_contain_text('Elan açılmadı')
        self.assert_private_closed()
        self.assertEqual(self.backend.detail_calls, [dict(id=PRIVATE_ID, authorized=True)])

    def test_invalid_uuid_and_stale_callback_do_not_request_private_data(self):
        self.backend.reports[0]['elan_id'] = 'not-a-uuid'
        self.open_admin()
        expect(self.preview_button()).to_be_disabled()
        for identifier in ('not-a-uuid', PRIVATE_ID):
            result = self.page.evaluate('''id=>caAdminPreviewReportListing(id,
                document.querySelector('[data-ca-report-preview]'),()=>false)''', identifier)
            self.assertFalse(result)
        outside = self.page.evaluate('''id=>{const b=document.createElement('button');document.body.append(b);
            return caAdminPreviewReportListing(id,b,()=>true)}''', PRIVATE_ID)
        self.assertFalse(outside, 'A disconnected/unrelated button must not start a report preview')
        self.assertFalse(self.backend.detail_calls)

    def test_nonadmin_cannot_use_private_report_preview_entrypoint(self):
        self.sign_in(admin=False)
        self.page.evaluate('async()=>await caAdminOpen()')
        self.assertTrue(self.page.locator('#caReportsAdmin').is_hidden())
        result = self.page.evaluate('''id=>{const b=document.createElement('button');
            document.getElementById('caReportsAdmin').append(b);return caAdminPreviewReportListing(id,b,()=>true)}''', PRIVATE_ID)
        self.assertFalse(result)
        self.assertFalse(self.backend.detail_calls)
        self.assert_private_closed()

    def test_late_preview_after_account_switch_is_discarded(self):
        self.start_held_preview()
        self.sign_in(admin=False)
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assert_private_closed()
        expect(self.page.locator('#caReportsAdmin')).not_to_be_visible()

    def test_late_preview_after_admin_close_is_discarded(self):
        self.start_held_preview()
        self.page.evaluate('caAdminClose()')
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assert_private_closed()
        expect(self.page.locator('#caAdminPanel')).not_to_be_visible()

    def test_late_preview_after_report_filter_change_is_discarded(self):
        self.start_held_preview()
        self.page.locator('#caReportsFilter').select_option('resolved')
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assert_private_closed()
        expect(self.page.locator('#caReportsFilter')).to_have_value('resolved')

    def test_late_preview_after_ad_filter_change_is_discarded(self):
        self.start_held_preview()
        self.page.evaluate("async()=>await caAdminFilter('gozlemede')")
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assert_private_closed()
        self.assertNotIn('yüklənir', self.page.locator('#caReportsMessage').inner_text().lower())
        expect(self.preview_button()).to_be_enabled()

    def test_open_report_preview_is_cleared_on_account_change(self):
        self.open_preview()
        self.sign_in(admin=False)
        self.assert_private_closed()
        expect(self.page.locator('#caReportsAdmin')).not_to_be_visible()

    def test_open_report_preview_is_cleared_on_admin_close(self):
        self.open_preview()
        self.page.evaluate('caAdminClose()')
        self.assert_private_closed()
        expect(self.page.locator('#caAdminPanel')).not_to_be_visible()

    def test_report_refresh_closes_only_its_active_private_preview(self):
        self.open_preview()
        self.page.evaluate("document.getElementById('caReportsFilter').dispatchEvent(new Event('change'))")
        self.assert_private_closed()
        expect(self.page.locator('#caReportsAdmin')).to_be_visible()

    def test_report_refresh_does_not_close_an_unrelated_ad_list_preview(self):
        self.open_admin()
        listing_id = self.backend.admin_rows[0]['id']
        clone = copy.deepcopy(self.backend.private_row)
        clone['id'] = listing_id
        self.backend.detail_rows[listing_id] = clone
        self.page.locator('#caAdminList [data-preview-id="'+listing_id+'"]').click()
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.page.evaluate("document.getElementById('caReportsFilter').dispatchEvent(new Event('change'))")
        self.page.wait_for_timeout(50)
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.assertEqual(self.page.evaluate('activeDetailCar._id'), listing_id)
        self.page.locator('#detailOverlay .detail-close').click()
        self.assert_private_closed()

    def test_newest_report_preview_wins_when_older_response_arrives_last(self):
        second_listing = '99999999-9999-4999-8999-888888888888'
        second_report = '77777777-7777-4777-8777-888888888888'
        clone = copy.deepcopy(self.backend.private_row)
        clone.update(id=second_listing, model='Second-Report')
        clone['ca_data']['model'] = 'Second-Report'
        self.backend.detail_rows[second_listing] = clone
        self.backend.reports.append(dict(self.backend.reports[0], id=second_report,
                                         elan_id=second_listing, model='Second-Report'))
        self.start_held_preview()
        self.page.locator('[data-ca-report-preview="'+second_report+'"]').click()
        for _ in range(200):
            if len(self.backend.pending_details) == 2:
                break
            self.page.wait_for_timeout(10)
        self.assertEqual(len(self.backend.pending_details), 2)
        self.backend.finish_detail(1)
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.assertEqual(self.page.evaluate('activeDetailCar._id'), second_listing)
        expect(self.page.locator('#caReportsMessage')).to_have_text('')
        self.backend.finish_detail()
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.evaluate('activeDetailCar._id'), second_listing)
        expect(self.page.locator('#detailTitle')).to_have_text('Toyota Second-Report')
        expect(self.page.locator('#caReportsMessage')).to_have_text('')
        self.assertFalse(self.page.evaluate('id=>caListingCache.has(id)', second_listing))

    def test_ad_preview_overtakes_pending_report_without_stuck_report_loading(self):
        self.start_held_preview()
        listing_id = self.backend.admin_rows[0]['id']
        clone = copy.deepcopy(self.backend.private_row)
        clone['id'] = listing_id
        self.backend.detail_rows[listing_id] = clone
        self.page.locator('#caAdminList [data-preview-id="'+listing_id+'"]').click()
        for _ in range(200):
            if len(self.backend.pending_details) == 2:
                break
            self.page.wait_for_timeout(10)
        self.assertEqual(len(self.backend.pending_details), 2)
        self.backend.finish_detail()  # Old report finishes while the ad preview is loading.
        self.page.wait_for_timeout(100)
        self.assertNotIn('yüklənir', self.page.locator('#caReportsMessage').inner_text().lower())
        self.assert_private_closed()
        self.backend.finish_detail()
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.assertEqual(self.page.evaluate('activeDetailCar._id'), listing_id)
        self.assertNotIn('yüklənir', self.page.locator('#caReportsMessage').inner_text().lower())

    def test_report_preview_button_is_usable_on_320px_and_photo_viewer_works(self):
        self.page.set_viewport_size({'width':320,'height':780})
        self.open_admin()
        self.preview_button().scroll_into_view_if_needed()
        rect = self.preview_button().bounding_box()
        self.assertGreaterEqual(rect['x'], 0)
        self.assertLessEqual(rect['x']+rect['width'], 320)
        self.assertGreaterEqual(rect['height'], 40)
        self.preview_button().tap()
        expect(self.page.locator('#detailOverlay')).to_be_visible()
        self.page.locator('#galleryStage img').tap()
        expect(self.page.locator('#caPhotoViewer')).to_be_visible()
        self.page.locator('[data-ca-viewer="close"]').tap()
        self.page.locator('#detailOverlay .detail-close').tap()
        self.assert_private_closed()


if __name__ == '__main__':
    unittest.main()
