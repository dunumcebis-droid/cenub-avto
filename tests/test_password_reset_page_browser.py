"""Dedicated reset-page regressions with every HTTP request intercepted.

No real mail, account change, or password update occurs. API responses and
credentials are synthetic fixtures; existing account storage must stay intact.
"""
import copy
import json
import mimetypes
import os
import re
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright
from test_listing_management_browser import ORIGIN, ROOT, safe_local_asset

RESET_URL = ORIGIN + 'reset-password.html'
REDIRECT = 'https://dunumcebis-droid.github.io/cenub-avto/reset-password.html'
USER_A = {'id': '33333333-3333-4333-8333-333333333333', 'email': 'recover-a@example.invalid'}
USER_B = {'id': '44444444-4444-4444-8444-444444444444', 'email': 'recover-b@example.invalid'}
STORED_SESSION = json.dumps({'access_token': 'existing-owner-session', 'refresh_token': 'owner-refresh',
                            'user': {'id': '11111111-1111-4111-8111-111111111111'}})


class ResetPageBackend:
    def __init__(self):
        self.calls = []
        self.unexpected = []
        self.leaks = []
        self.pending_get = []
        self.pending_put = []
        self.pending_recover = []
        self.delay_get = 0
        self.delay_put = False
        self.delay_recover = False
        self.fail_recover = False
        self.wrong_put_user = False
        self.public_key = re.search(r"const CA_KEY='([^']+)'", (ROOT/'assets/js/01-main.js').read_text()).group(1)

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        if req.resource_type != 'document':
            for value in (req.url, req.headers.get('referer', '')):
                if any(secret in value for secret in ('query-private-refresh', 'fragment-private-refresh', 'fixture-token-hash')):
                    self.leaks.append(req.resource_type)
        local = safe_local_asset(req.url)
        if parsed.scheme == 'http' and parsed.netloc == '127.0.0.1:8766' and parsed.path == '/reset-password.html':
            local = ROOT/'reset-password.html'
        if local is not None:
            if req.method == 'GET' and local.is_file():
                route.fulfill(content_type=mimetypes.guess_type(local.name)[0] or 'application/octet-stream', body=local.read_bytes())
            else:
                route.fulfill(status=404, body='')
            return
        if parsed.netloc == '127.0.0.1:8766' and parsed.path == '/favicon.ico':
            route.fulfill(status=204, body='')
            return
        if parsed.netloc != 'iqdtehqxusfiwokrzceo.supabase.co' or not parsed.path.startswith('/auth/v1/'):
            self.unexpected.append({'method': req.method, 'path': parsed.path})
            route.abort()
            return
        body = req.post_data_json if req.post_data else None
        call = {'path': parsed.path, 'method': req.method, 'body': copy.deepcopy(body),
                'query': parse_qs(parsed.query), 'authorization': req.headers.get('authorization')}
        self.calls.append(call)
        assert req.headers.get('apikey') == self.public_key

        def send(data, status=200):
            route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

        if parsed.path == '/auth/v1/user' and req.method == 'GET':
            token = req.headers.get('authorization')
            if token in ('Bearer expired-token', 'Bearer invalid-token'):
                send({'message': 'Expired synthetic token'}, 401)
                return
            assert token in ('Bearer recovery-token', 'Bearer recovery-token-b')
            data = USER_B if token.endswith('-b') else USER_A
            if self.delay_get:
                self.delay_get -= 1
                self.pending_get.append((route, copy.deepcopy(data)))
                return
            send(data)
            return
        if parsed.path == '/auth/v1/verify' and req.method == 'POST':
            assert body == {'type': 'recovery', 'token_hash': 'fixture-token-hash'}
            assert call['authorization'] is None
            send({'access_token': 'recovery-token'})
            return
        if parsed.path == '/auth/v1/user' and req.method == 'PUT':
            assert set(body) == {'password'}
            token = req.headers.get('authorization')
            assert token in ('Bearer recovery-token', 'Bearer recovery-token-b')
            data = USER_B if token.endswith('-b') else USER_A
            if self.wrong_put_user:
                data = dict(data, id='99999999-9999-4999-8999-999999999999')
            if self.delay_put:
                self.pending_put.append((route, copy.deepcopy(data)))
                return
            send(data)
            return
        if parsed.path == '/auth/v1/recover' and req.method == 'POST':
            assert set(body) == {'email'}
            assert call['authorization'] is None
            assert call['query']['redirect_to'] == [REDIRECT]
            data, status = ({'message': 'Mock email limit'}, 429) if self.fail_recover else ({}, 200)
            if self.delay_recover:
                self.pending_recover.append((route, data, status))
                return
            send(data, status)
            return
        self.unexpected.append({'method': req.method, 'path': parsed.path})
        route.abort()


class PasswordResetPageBrowserTests(unittest.TestCase):
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
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script("localStorage.setItem('cenub_supabase_session'," + json.dumps(STORED_SESSION) + ")")
        self.backend = ResetPageBackend()
        self.page.route('**/*', self.backend.route)

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors)
        self.assertFalse(self.backend.unexpected)
        self.assertFalse(self.backend.leaks)

    def go(self, suffix=''):
        self.page.goto(RESET_URL + suffix, wait_until='load')

    def verified(self, suffix='#type=recovery&access_token=recovery-token&expires_in=3600'):
        self.go(suffix)
        self.page.wait_for_function('document.getElementById("resetForm").hidden===false&&document.getElementById("resetSubmit").disabled===false')
        self.assertEqual(self.page.locator('#resetTitle').inner_text(), 'Yeni parol yarat')

    def assert_session_preserved(self):
        self.assertEqual(self.page.evaluate("localStorage.getItem('cenub_supabase_session')"), STORED_SESSION)

    def puts(self):
        return [call for call in self.backend.calls if call['method'] == 'PUT']

    def fill_passwords(self, first='Fixture-new-pass-123', second='Fixture-new-pass-123'):
        self.page.locator('#resetPassword').fill(first)
        self.page.locator('#resetPassword2').fill(second)

    def wait_for_pending(self, pending):
        # Browser fetches reach Python routes asynchronously. Pump Playwright's
        # event loop until the deliberately held request has actually arrived.
        for _ in range(300):
            if pending:
                return
            self.page.wait_for_timeout(10)
        self.fail('The deliberately delayed offline request did not start')

    def fulfill(self, pending):
        self.wait_for_pending(pending)
        self.assertTrue(pending)
        route, data = pending.pop(0)
        route.fulfill(content_type='application/json', body=json.dumps(data))

    def test_form_stays_disabled_until_fragment_token_is_verified(self):
        self.backend.delay_get = 1
        self.go('#type=recovery&access_token=recovery-token&refresh_token=fragment-private-refresh')
        self.assertEqual(self.page.url, RESET_URL)
        self.assertTrue(self.page.locator('#resetForm').is_hidden())
        self.assertFalse(self.puts())
        self.fulfill(self.backend.pending_get)
        self.page.wait_for_function('document.getElementById("resetSubmit").disabled===false')
        self.assertEqual(self.page.locator('#resetEmail').input_value(), USER_A['email'])
        self.assertTrue(self.page.locator('#resetEmail').evaluate('input=>input.disabled||input.readOnly'))
        self.assertTrue(self.page.locator('#resetPassword').is_visible())
        self.assertTrue(self.page.locator('#resetPassword2').is_visible())
        self.assertFalse(self.puts())
        self.assert_session_preserved()

    def test_token_hash_and_explicit_query_tokens_are_verified_and_scrubbed(self):
        for suffix, expected in (
            ('?type=recovery&token_hash=fixture-token-hash&keep=1', ['/auth/v1/verify', '/auth/v1/user']),
            ('?auth=recovery&type=recovery&access_token=recovery-token&refresh_token=query-private-refresh&keep=1', ['/auth/v1/user']),
        ):
            with self.subTest(suffix=suffix.split('&')[0]):
                start = len(self.backend.calls)
                self.verified(suffix)
                self.assertEqual(self.page.url, RESET_URL + '?keep=1')
                self.assertEqual([c['path'] for c in self.backend.calls[start:]], expected)
                self.assertIsNone(self.page.evaluate('window.__caAuthCallback'))
                self.assertFalse(self.puts())
                self.assert_session_preserved()

    def test_missing_used_and_expired_links_show_retry_without_automatic_mail(self):
        for suffix in ('', '?auth=recovery', '#error=access_denied&error_code=otp_expired',
                       '#type=recovery&access_token=expired-token'):
            with self.subTest(suffix=suffix):
                self.go(suffix)
                self.page.wait_for_function('document.getElementById("recoveryRequestForm").hidden===false')
                self.assertEqual(self.page.locator('#resetTitle').inner_text(), 'Parolun bərpası')
                self.assertTrue(self.page.locator('#resetForm').is_hidden())
                self.assertFalse(self.puts())
                self.assertFalse(any(c['path'] == '/auth/v1/recover' for c in self.backend.calls))
                self.assertEqual(self.page.url, RESET_URL)
                self.assert_session_preserved()

    def test_retry_is_explicit_lowercases_email_and_does_not_use_existing_session(self):
        self.go()
        self.assertFalse(self.backend.calls)
        self.backend.fail_recover = True
        self.page.locator('#recoveryEmail').fill('User@Example.invalid')
        self.page.locator('#recoverySubmit').click()
        self.page.wait_for_function('document.getElementById("recoverySubmit").disabled===false&&document.getElementById("resetMessage").getAttribute("role")==="alert"')
        self.assertEqual(self.page.locator('#recoveryEmail').input_value(), 'User@Example.invalid')
        self.backend.fail_recover = False
        self.page.locator('#recoverySubmit').click()
        self.page.wait_for_function('document.getElementById("resetMessage").textContent.includes("mümkündürsə")')
        calls = [c for c in self.backend.calls if c['path'] == '/auth/v1/recover']
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c['body'] == {'email': 'user@example.invalid'} and c['authorization'] is None for c in calls))
        self.assert_session_preserved()

    def test_validation_duplicate_submit_and_success_only_update_verified_account(self):
        self.verified()
        self.fill_passwords('short', 'short')
        self.page.locator('#resetForm').evaluate('form=>form.requestSubmit()')
        self.assertFalse(self.puts())
        self.fill_passwords(second='Different-pass-123')
        self.page.locator('#resetForm').evaluate('form=>form.requestSubmit()')
        self.assertIn('eyni deyil', self.page.locator('#resetMessage').inner_text())
        self.assertFalse(self.puts())
        self.backend.delay_put = True
        self.fill_passwords()
        self.page.locator('#resetForm').evaluate('form=>{form.requestSubmit();form.requestSubmit()}')
        self.wait_for_pending(self.backend.pending_put)
        self.assertEqual(len(self.backend.pending_put), 1)
        self.assertEqual(len(self.puts()), 1)
        self.assertEqual(self.puts()[0]['authorization'], 'Bearer recovery-token')
        self.assertEqual(self.puts()[0]['body'], {'password': 'Fixture-new-pass-123'})
        self.fulfill(self.backend.pending_put)
        self.page.wait_for_function('document.getElementById("resetSuccess").hidden===false')
        self.assertEqual(self.page.locator('#resetTitle').inner_text(), 'Parol yeniləndi')
        self.assertEqual(self.page.locator('#resetPassword').input_value(), '')
        self.assertEqual(self.page.locator('#resetPassword2').input_value(), '')
        self.assertTrue(self.page.locator('#resetForm').is_hidden())
        self.assertTrue(self.page.locator('#resetLogin').is_visible())
        self.assert_session_preserved()

    def test_wrong_returned_user_id_never_shows_success(self):
        self.backend.wrong_put_user = True
        self.verified()
        self.fill_passwords()
        self.page.locator('#resetSubmit').click()
        self.page.wait_for_function('document.getElementById("resetMessage").getAttribute("role")==="alert"')
        self.assertTrue(self.page.locator('#resetSuccess').is_hidden())
        self.assertNotEqual(self.page.locator('#resetTitle').inner_text(), 'Parol yeniləndi')
        self.assertEqual(len(self.puts()), 1)
        self.assert_session_preserved()

    def test_late_old_verification_cannot_replace_a_new_recovery_account(self):
        self.backend.delay_get = 1
        self.go('#type=recovery&access_token=recovery-token')
        self.wait_for_pending(self.backend.pending_get)
        self.assertEqual(len(self.backend.pending_get), 1)
        self.page.evaluate("location.hash='type=recovery&access_token=recovery-token-b'")
        self.page.wait_for_function('document.getElementById("resetEmail").value==="recover-b@example.invalid"')
        self.fulfill(self.backend.pending_get)
        self.page.wait_for_timeout(60)
        self.assertEqual(self.page.locator('#resetEmail').input_value(), USER_B['email'])
        self.fill_passwords()
        self.page.locator('#resetSubmit').click()
        self.page.wait_for_function('document.getElementById("resetSuccess").hidden===false')
        self.assertEqual(self.puts()[0]['authorization'], 'Bearer recovery-token-b')
        self.assert_session_preserved()

    def test_late_old_password_response_does_not_hide_new_recovery_form(self):
        self.verified()
        self.backend.delay_put = True
        self.fill_passwords()
        self.page.locator('#resetSubmit').click()
        self.wait_for_pending(self.backend.pending_put)
        self.assertEqual(len(self.backend.pending_put), 1)
        self.page.evaluate("location.hash='type=recovery&access_token=recovery-token-b'")
        self.page.wait_for_function('document.getElementById("resetEmail").value==="recover-b@example.invalid"')
        self.fulfill(self.backend.pending_put)
        self.page.wait_for_timeout(60)
        self.assertTrue(self.page.locator('#resetSuccess').is_hidden())
        self.assertEqual(self.page.locator('#resetTitle').inner_text(), 'Yeni parol yarat')
        self.assertEqual(self.page.locator('#resetEmail').input_value(), USER_B['email'])
        self.assert_session_preserved()

    def test_late_retry_response_cannot_replace_a_new_valid_recovery(self):
        self.backend.delay_recover = True
        self.go()
        self.page.locator('#recoveryEmail').fill('owner@example.invalid')
        self.page.locator('#recoverySubmit').click()
        self.wait_for_pending(self.backend.pending_recover)
        self.assertEqual(len(self.backend.pending_recover), 1)
        self.page.evaluate("location.hash='type=recovery&access_token=recovery-token'")
        self.page.wait_for_function('document.getElementById("resetEmail").value==="recover-a@example.invalid"')
        route, data, status = self.backend.pending_recover.pop()
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))
        self.page.wait_for_timeout(60)
        self.assertEqual(self.page.locator('#resetTitle').inner_text(), 'Yeni parol yarat')
        self.assertFalse('mümkündürsə' in self.page.locator('#resetMessage').inner_text())
        self.assertTrue(self.page.locator('#recoveryRequestForm').is_hidden())
        self.assert_session_preserved()

    def test_mobile_and_landscape_forms_fit_and_submit_stays_reachable(self):
        self.verified()
        for width, height in ((320, 812), (375, 812), (568, 320)):
            with self.subTest(viewport=(width, height)):
                self.page.set_viewport_size({'width': width, 'height': height})
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                for selector in ('#resetEmail', '#resetPassword', '#resetPassword2', '#resetSubmit'):
                    element = self.page.locator(selector)
                    element.scroll_into_view_if_needed()
                    box = element.bounding_box()
                    self.assertIsNotNone(box)
                    self.assertGreaterEqual(box['x'], 0)
                    self.assertLessEqual(box['x'] + box['width'], width)
                self.assertTrue(self.page.locator('#resetSubmit').evaluate('button=>{const r=button.getBoundingClientRect();return button.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'))
        self.assertFalse(self.puts())


if __name__ == '__main__':
    unittest.main()
