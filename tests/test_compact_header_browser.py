"""Header geometry and session behavior; every request uses local fixtures."""
import json
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER
from test_marketplace_browser import MarketplaceBackend


class CompactHeaderBackend(MarketplaceBackend):
    def route(self, route):
        request = route.request
        path = urlsplit(request.url).path
        if path == '/rest/v1/rpc/cenub_admin_yoxla':
            route.fulfill(content_type='application/json', body=json.dumps(
                request.headers.get('authorization') == 'Bearer admin-token'))
            return
        if path in ('/rest/v1/rpc/ca_record_site_visit', '/rest/v1/rpc/ca_daily_site_visitors'):
            payload = {'day':'2026-11-20','timezone':'Asia/Baku','visitors':47}
            if path.endswith('/ca_record_site_visit'):
                payload['counted'] = False
            route.fulfill(content_type='application/json', body=json.dumps(payload))
            return
        super().route(route)


class CompactHeaderBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 900},
                                                service_workers='block')
        self.context.set_default_timeout(6000)
        self.backend = CompactHeaderBackend()
        self.context.route('**/*', self.backend.route)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors)

    def sign_in(self, phone, owner=OWNER, admin=False):
        self.page.evaluate('''async ({phone,id,token})=>caPersistSession({access_token:token,
          expires_at:4102444800,user:{id,email:'offline@example.invalid',
          user_metadata:{telefon:phone}}})''',
            {'phone': phone, 'id': owner, 'token': 'admin-token' if admin else
             'seller-token' if owner == OWNER else 'other-token'})

    def assert_geometry(self, width, signed_in):
        self.page.set_viewport_size({'width': width, 'height': 900})
        self.page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        result = self.page.evaluate('''()=>{
          const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,
            top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
          const header=document.querySelector('body>header'),logo=header.querySelector('.ca-site-brand');
          const controls=[...header.querySelectorAll('button,.account-chip')]
            .filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(rect);
          return {header:rect(header),logo:rect(logo),sell:rect(header.querySelector('.header-sell')),
            notice:rect(document.getElementById('caNotificationsLaunch')),
            pageFits:document.documentElement.scrollWidth<=innerWidth,
            controlsFit:controls.every(r=>r.left>=-1&&r.right<=innerWidth+1),
            textFits:[...header.querySelectorAll('button')].filter(e=>e.getBoundingClientRect().height)
              .every(e=>e.scrollWidth<=e.clientWidth+1),
            overlap:controls.some((a,i)=>controls.slice(i+1).some(b=>a.left<b.right-1&&
              a.right>b.left+1&&a.top<b.bottom-1&&a.bottom>b.top+1))};
        }''')
        self.assertTrue(result['pageFits'], result)
        self.assertTrue(result['controlsFit'], result)
        self.assertTrue(result['textFits'], result)
        self.assertFalse(result['overlap'], result)
        self.assertLessEqual(result['header']['height'], 92 if width <= 960 else 108, result)
        self.assertGreater(result['logo']['width'], 85, result)
        self.assertLessEqual(result['logo']['width'], 148 if width <= 960 else 210, result)
        if signed_in:
            self.assertGreaterEqual(result['notice']['top'], result['sell']['bottom'] + 2, result)
            self.assertAlmostEqual(result['notice']['left'], result['sell']['left'], delta=1)
            self.assertAlmostEqual(result['notice']['right'], result['sell']['right'], delta=1)
        return result

    def test_logged_out_header_fits_and_login_still_opens(self):
        for width in (320, 390, 430, 1440):
            with self.subTest(width=width):
                self.assert_geometry(width, False)
                self.assertFalse(self.page.locator('#accountStatus').is_visible())
                self.assertFalse(self.page.locator('#caNotificationsLaunch').is_visible())
                self.page.locator('header .back-btn').click()
                self.assertTrue(self.page.locator('#authOverlay').is_visible())
                self.page.evaluate('closeAuth()')

    def test_masked_phone_notifications_and_publishing_work_in_compact_header(self):
        phone = '+994500001234'
        self.sign_in(phone)
        self.page.wait_for_function("document.getElementById('caNotificationBadge').textContent==='1'")
        for width in (320, 390, 430, 1440):
            with self.subTest(width=width):
                self.assert_geometry(width, True)
                status = self.page.locator('#accountStatus')
                self.assertEqual(status.inner_text(), '● ••• 1234')
                self.assertNotIn(phone, status.get_attribute('aria-label'))
                self.page.locator('#caNotificationsLaunch').click()
                self.assertTrue(self.page.locator('#caMarketOverlay').is_visible())
                self.assertEqual(self.page.locator('#caMarketTitle').inner_text(), 'Bildirişlər')
                self.page.locator('#caMarketClose').click()
                self.page.locator('header .header-sell').click()
                self.assertTrue(self.page.locator('#sellPage').is_visible())
                self.assertEqual(self.page.locator('#listingForm input[name="phone"]').input_value(), phone)
                self.page.evaluate('closeSellPage()')

    def test_admin_badge_long_phone_account_switch_and_logout_keep_the_header_compact(self):
        notice = self.backend.notifications[OWNER][0]
        self.backend.notifications[OWNER] = [dict(notice,
            id=f'66666666-6666-4666-8666-{n:012d}') for n in range(123)]
        phone = '+99412345678901234567890121234'
        self.sign_in(phone, admin=True)
        self.page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        self.page.wait_for_function("document.getElementById('caNotificationBadge').textContent==='99+'")
        self.page.locator('#caAdminLaunch').wait_for(state='visible')
        for width in (320, 390, 430, 1440):
            with self.subTest(width=width):
                self.assert_geometry(width, True)
                self.assertEqual(self.page.locator('#accountStatus').inner_text(), '● ••• 1234')
                self.assertEqual(self.page.evaluate('currentUser.phone'), phone)
        self.sign_in('+49 1234567890', owner=OTHER_OWNER)
        self.page.wait_for_function("document.getElementById('caNotificationBadge').textContent==='1'")
        self.assertEqual(self.page.locator('#accountStatus').inner_text(), '● ••• 7890')
        self.assert_geometry(320, True)
        self.page.evaluate('async()=>await logout()')
        self.assertFalse(self.page.locator('#accountStatus').is_visible())
        self.assertFalse(self.page.locator('#caNotificationsLaunch').is_visible())
        self.assertEqual(self.page.locator('header .back-btn').inner_text(), 'Giriş / Qeydiyyat')
        self.assert_geometry(320, False)
