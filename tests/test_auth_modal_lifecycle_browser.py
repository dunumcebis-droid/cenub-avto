"""Actual-touch auth modal lifecycle, recovery priority, and focus regressions.

Every request is intercepted; no real mail, password or account change occurs.
"""
import json
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN, OWNER
from test_photo_viewer_browser import PHOTO_BASE, viewer_rows


class AuthLifecycleBackend(AdminAuthBackend):
    def __init__(self):
        super().__init__()
        self.rows = viewer_rows()

    def route(self, route):
        request = route.request
        parsed = urlsplit(request.url)
        if request.url.startswith(PHOTO_BASE):
            route.fulfill(content_type='image/svg+xml', body=(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800">'
                '<rect width="100%" height="100%" fill="#365a70"/></svg>'))
            return
        if parsed.path == '/auth/v1/settings':
            route.fulfill(content_type='application/json', body='{"external":{"phone":false,"email":true}}')
            return
        if parsed.path == '/auth/v1/user' and request.headers.get('authorization') == 'Bearer user-token':
            route.fulfill(content_type='application/json', body=json.dumps({
                'id': OWNER, 'email': 'owner@example.invalid', 'phone': None,
                'phone_confirmed_at': None, 'user_metadata': {'telefon': '+994000000000'}}))
            return
        super().route(route)


class AuthModalLifecycleBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 375, 'height': 812}, has_touch=True, is_mobile=True)
        self.page = self.context.new_page()
        self.page.set_default_timeout(6000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.backend = AuthLifecycleBackend()
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        for route, _ in self.backend.pending_recovery:
            try:
                route.abort()
            except Exception:
                pass
        self.page.wait_for_timeout(20)
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')

    def open_from_header(self):
        self.page.locator('header .header-actions .back-btn').tap()
        self.page.locator('#authOverlay').wait_for(state='visible')

    def touch_background(self, height):
        client = self.context.new_cdp_session(self.page)
        client.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'id': 1, 'x': 3, 'y': height * .8}]})
        for y in (height * .65, height * .5, height * .35, height * .2):
            client.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'id': 1, 'x': 3, 'y': y}]})
            self.page.wait_for_timeout(25)
        client.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        client.detach()
        self.page.wait_for_timeout(100)

    def test_phone_and_landscape_auth_locks_background_swipe_and_restores_scroll(self):
        for width, height in ((320, 812), (375, 812), (812, 375)):
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({'width': width, 'height': height})
                self.page.evaluate('window.scrollTo({top:600,behavior:"instant"})')
                self.open_from_header()
                before = self.page.evaluate('scrollY')
                self.assertEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')
                self.assertEqual(self.page.locator('#authOverlay').get_attribute('aria-hidden'), 'false')
                self.assertEqual(self.page.evaluate('document.activeElement.id'), 'authEmail')
                self.touch_background(height)
                self.assertAlmostEqual(self.page.evaluate('scrollY'), before, delta=1)
                self.page.keyboard.press('Escape')
                self.assertTrue(self.page.locator('#authOverlay').is_hidden())
                self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
                self.assertAlmostEqual(self.page.evaluate('scrollY'), before, delta=1)
                self.assertTrue(self.page.locator('header .header-actions .back-btn').evaluate('e=>e===document.activeElement'))
        self.assertFalse(self.backend.auth_calls)

    def test_tab_focus_and_mode_switches_remain_in_auth_and_preserve_original_return_target(self):
        self.open_from_header()
        for _ in range(20):
            self.page.keyboard.press('Tab')
            self.assertTrue(self.page.evaluate('document.getElementById("authOverlay").contains(document.activeElement)'))
        for _ in range(20):
            self.page.keyboard.press('Shift+Tab')
            self.assertTrue(self.page.evaluate('document.getElementById("authOverlay").contains(document.activeElement)'))
        self.page.evaluate('document.getElementById("caFilterLaunch").focus()')
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'authEmail')
        self.page.locator('#authModeSwitch').tap()
        self.page.locator('#authForgot').tap()
        self.page.locator('#authModeSwitch').tap()
        self.assertEqual(self.page.evaluate('authMode'), 'login')
        self.page.keyboard.press('Escape')
        self.assertTrue(self.page.locator('header .header-actions .back-btn').evaluate('e=>e===document.activeElement'))
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.page.set_viewport_size({'width': 812, 'height': 375})
        self.open_from_header()
        self.page.locator('#authOverlay .auth-box').evaluate('box=>box.scrollTop=box.scrollHeight')
        self.page.keyboard.press('Escape')
        self.open_from_header()
        self.assertTrue(self.page.locator('#authEmail').evaluate('''input=>{
            const r=input.getBoundingClientRect(),box=input.closest('.auth-box').getBoundingClientRect();
            return r.top>=box.top&&r.bottom<=box.bottom&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===input;
        }'''))

    def test_scrim_close_clears_sensitive_fields_and_releases_scroll(self):
        self.open_from_header()
        self.page.locator('#authPassword').fill('Synthetic-secret-123')
        self.page.locator('#authPassword2').fill('Synthetic-secret-123')
        self.page.locator('#authOverlay').tap(position={'x': 3, 'y': 3})
        self.assertTrue(self.page.locator('#authOverlay').is_hidden())
        self.assertEqual(self.page.locator('#authPassword').input_value(), '')
        self.assertEqual(self.page.locator('#authPassword2').input_value(), '')
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.assertEqual(self.page.locator('#authOverlay').get_attribute('aria-hidden'), 'true')

    def test_same_tab_recovery_takes_priority_above_detail_and_fullscreen_viewer(self):
        for fullscreen in (False, True):
            with self.subTest(fullscreen=fullscreen):
                self.page.locator('#allGrid .car-card').first.locator('.car-cover').tap()
                if fullscreen:
                    self.page.locator('#galleryStage img').tap()
                    self.page.locator('#caPhotoViewer').wait_for(state='visible')
                self.page.evaluate("location.hash='error=access_denied&error_code=otp_expired&error_description=synthetic-expired-link'")
                self.page.wait_for_function('authMode==="recover"&&document.getElementById("authOverlay").classList.contains("open")')
                self.assertTrue(self.page.locator('#detailOverlay').is_hidden())
                self.assertTrue(self.page.locator('#caPhotoViewer').is_hidden())
                self.assertTrue(self.page.locator('#authOverlay .auth-box').evaluate('''box=>{
                    const r=box.getBoundingClientRect();return box.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));
                }'''))
                self.assertEqual(self.page.evaluate('document.activeElement.id'), 'authEmail')
                self.assertEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')
                self.assertFalse(self.page.locator('#authOverlay').evaluate('e=>e.inert'))
                self.assertNotIn('#', self.page.url)
                self.page.keyboard.press('Escape')
                self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.assertFalse(self.backend.auth_calls)

    def test_late_recovery_read_cannot_reopen_dismissed_modal_or_relock_page(self):
        self.backend.delay_recovery = True
        self.page.evaluate("location.hash='type=recovery&access_token=recovery-token'")
        for _ in range(100):
            if self.backend.pending_recovery:
                break
            self.page.wait_for_timeout(10)
        self.assertTrue(self.backend.pending_recovery)
        self.assertTrue(self.page.locator('#authSubmit').is_disabled())
        self.page.keyboard.press('Escape')
        route, user = self.backend.pending_recovery.pop(0)
        route.fulfill(content_type='application/json', body=json.dumps(user))
        self.page.wait_for_timeout(80)
        self.assertTrue(self.page.locator('#authOverlay').is_hidden())
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.assertIsNone(self.page.evaluate('caRecovery'))
        self.assertFalse([call for call in self.backend.auth_calls if call['method'] != 'GET'])

    def test_successful_login_unlocks_page_before_entering_cabinet(self):
        self.open_from_header()
        self.page.locator('#authModeSwitch').tap()
        self.page.locator('#authEmail').fill('owner@example.invalid')
        self.page.locator('#authPassword').fill('Synthetic-password-123')
        self.page.locator('#authSubmit').tap()
        self.page.wait_for_function('currentUser&&document.body.classList.contains("cabinet-open")')
        self.assertTrue(self.page.locator('#authOverlay').is_hidden())
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.assertEqual(self.page.evaluate('currentUser.id'), OWNER)

    def test_existing_feedback_lock_is_preserved_and_stale_lock_is_not_restored(self):
        self.page.evaluate("caShowListingFeedback('Synthetic feedback')")
        self.page.evaluate("openAuth('login')")
        self.page.keyboard.press('Escape')
        self.assertTrue(self.page.locator('#listingFeedback').is_visible())
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')
        self.page.evaluate('caDismissListingFeedback()')
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
        self.page.evaluate("caShowListingFeedback('Synthetic feedback');openAuth('login');caDismissListingFeedback(false)")
        self.page.wait_for_function('document.body.style.overflow==="hidden"')
        self.page.keyboard.press('Escape')
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), '')
