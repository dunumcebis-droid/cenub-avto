"""Admin email changes require an explicit click and a matching server result.

Every request is intercepted. No real account, password, or email is changed.
Server authorization and Auth Admin API behavior are tested separately.
"""
import copy
import json
import os
import re
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, ROOT


EMAIL = 'avtounvan@gmail.com'
EMAIL_TOKEN = re.compile(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
ENDPOINT = '/functions/v1/ca-admin-email-change'
PUBLIC_PAGES = ('index.html', 'about.html', 'support.html',
                'reset-password.html', 'terms.html', 'privacy.html')


def fixture_session(owner=OWNER, token='admin-token'):
    return {
        'access_token': token, 'refresh_token': token + '-refresh',
        'expires_at': 4102444800, 'token_type': 'bearer',
        'user': {
            'id': owner, 'email': 'admin@example.invalid',
            'user_metadata': {'telefon': '+994000000000', 'fixture': 'preserve'},
            'app_metadata': {'provider': 'email'},
        },
    }


class AdminEmailBackend(AdminAuthBackend):
    def __init__(self):
        super().__init__()
        self.email_calls = []
        self.pending_email = []
        self.delay_email = False
        self.email_network_error = False
        self.email_status = 200
        self.email_result = {'status': 'updated', 'user_id': OWNER, 'email': EMAIL}

    def route(self, route):
        request = route.request
        parsed = urlsplit(request.url)
        if parsed.path == ENDPOINT:
            call = {'method': request.method, 'body': request.post_data_json,
                    'authorization': request.headers.get('authorization')}
            self.email_calls.append(call)
            assert call['method'] == 'POST'
            assert call['body'] == {}, 'The target and password must not be supplied by the browser'
            if self.email_network_error:
                route.abort('failed')
                return
            result, status = copy.deepcopy(self.email_result), self.email_status
            if call['authorization'] != 'Bearer admin-token':
                result, status = {'code': 'admin_required', 'message': 'Admin denied'}, 403
            if self.delay_email:
                self.pending_email.append((route, result, status))
                return
            route.fulfill(status=status, content_type='application/json', body=json.dumps(result))
            return
        # The shared fixture only serves index.html; allow these exact public pages.
        if parsed.scheme == 'http' and parsed.netloc == '127.0.0.1:8766' and parsed.path.lstrip('/') in PUBLIC_PAGES:
            assert request.method == 'GET'
            route.fulfill(content_type='text/html', body=(ROOT / parsed.path.lstrip('/')).read_bytes())
            return
        super().route(route)


class AdminEmailBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 1000})
        self.page = self.context.new_page()
        self.page.set_default_timeout(6000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true')
        self.backend = AdminEmailBackend()
        self.page.route('**/*', self.backend.route)

    def tearDown(self):
        for route, _, _ in self.backend.pending_email:
            try:
                route.abort()
            except Exception:
                pass
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')

    def go(self, suffix=''):
        self.page.goto(ORIGIN + suffix, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def as_admin(self):
        self.go()
        self.page.evaluate('''async session=>{
            await caPersistSession(session);await caAdminOpen();
        }''', fixture_session())
        self.assertTrue(self.page.locator('#caAdminPanel').is_visible())

    def saved_session(self):
        return self.page.evaluate('JSON.parse(localStorage.getItem(CA_SESSION_KEY))')

    def wait_for_pending(self):
        for _ in range(100):
            if self.backend.pending_email:
                return
            self.page.wait_for_timeout(10)
        self.fail('The deliberately delayed offline email request did not start')

    def release_pending(self):
        route, result, status = self.backend.pending_email.pop(0)
        with self.page.expect_response(lambda response: urlsplit(response.url).path == ENDPOINT) as response:
            route.fulfill(status=status, content_type='application/json', body=json.dumps(result))
        response.value.body()
        self.page.evaluate('async()=>{await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)}')

    def assert_no_auth_mutation(self):
        self.assertFalse([call for call in self.backend.auth_calls if call['method'] != 'GET'])

    def test_loading_and_opening_admin_panel_never_changes_email(self):
        self.go()
        self.assertFalse(self.page.locator('#caAdminEmailSection').is_visible())
        self.assertFalse(self.page.evaluate('async()=>await caAdminChangeEmail()'))
        self.as_admin()
        self.assertTrue(self.page.locator('#caAdminEmailButton').is_enabled())
        self.assertFalse(self.backend.email_calls)
        self.assert_no_auth_mutation()

    def test_guest_deep_link_opens_login_without_email_mutation(self):
        self.go('?admin-email=1')
        self.page.locator('#authOverlay').wait_for(state='visible')
        self.assertEqual(self.page.evaluate('authMode'), 'login')
        self.assertIn('admin', self.page.locator('#authMessage').inner_text().lower())
        self.assertFalse(self.backend.email_calls)
        self.assertFalse(self.backend.auth_calls)

    def test_admin_deep_link_focuses_button_without_email_mutation(self):
        session = fixture_session()
        self.page.add_init_script('localStorage.setItem("cenub_supabase_session", ' + json.dumps(json.dumps(session)) + ')')
        self.go('?admin-email=1')
        self.page.wait_for_function('document.activeElement.id==="caAdminEmailButton"')
        self.assertTrue(self.page.locator('#caAdminPanel').is_visible())
        self.assertFalse(self.backend.email_calls)
        self.assert_no_auth_mutation()

    def test_explicit_admin_click_updates_only_email_and_prevents_duplicate_writes(self):
        self.as_admin()
        original = self.saved_session()
        self.page.evaluate('document.getElementById("authPassword").value="Synthetic-unchanged-password"')
        self.page.locator('#caAdminEmailButton').click()
        self.page.wait_for_function('document.getElementById("caAdminEmailStatus").textContent.includes("Əvvəlki parolunla")')
        expected = copy.deepcopy(original)
        expected['user']['email'] = EMAIL
        self.assertEqual(self.saved_session(), expected)
        self.assertEqual(self.page.evaluate('caSession'), expected)
        self.assertEqual(self.page.evaluate('currentUser.email'), EMAIL)
        self.assertEqual(self.page.evaluate('currentUser.id'), OWNER)
        self.assertEqual(self.page.locator('#authPassword').input_value(), 'Synthetic-unchanged-password')
        self.assertTrue(self.page.locator('#caAdminEmailButton').is_disabled())
        self.assertEqual(self.backend.email_calls, [{'method': 'POST', 'body': {}, 'authorization': 'Bearer admin-token'}])
        self.assertFalse(self.page.evaluate('async()=>await caAdminChangeEmail()'))
        self.assertEqual(len(self.backend.email_calls), 1)
        self.assert_no_auth_mutation()

    def test_already_current_response_is_success_without_replacing_session(self):
        self.backend.email_result['status'] = 'already_current'
        self.as_admin()
        original = self.saved_session()
        self.page.locator('#caAdminEmailButton').click()
        self.page.wait_for_function('document.getElementById("caAdminEmailButton").textContent.includes("yeniləndi")')
        self.assertTrue(self.page.locator('#caAdminEmailButton').is_disabled())
        self.assertEqual(self.saved_session()['access_token'], original['access_token'])
        self.assertEqual(self.saved_session()['refresh_token'], original['refresh_token'])
        self.assertEqual(self.page.evaluate('currentUser.id'), OWNER)
        self.assertEqual(self.page.evaluate('currentUser.email'), EMAIL)
        self.assert_no_auth_mutation()

    def test_non_admin_cannot_show_or_invoke_email_action(self):
        self.go()
        self.page.evaluate('''async session=>{
            await caPersistSession(session);await caAdminOpen();
        }''', fixture_session(OTHER_OWNER, 'user-token'))
        self.assertFalse(self.page.locator('#caAdminLaunch').is_visible())
        self.assertFalse(self.page.locator('#caAdminEmailSection').is_visible())
        self.assertFalse(self.page.evaluate('async()=>await caAdminChangeEmail()'))
        self.assertFalse(self.backend.email_calls)
        self.assertFalse(any(call['name'].startswith('ca_admin_browse') for call in self.backend.admin_calls))

    def test_server_denial_and_network_failure_keep_email_and_allow_retry(self):
        for failure in ('denied', 'network'):
            with self.subTest(failure=failure):
                self.as_admin()
                original = self.saved_session()
                self.backend.email_network_error = failure == 'network'
                self.backend.email_status = 403 if failure == 'denied' else 200
                self.backend.email_result = {'code': 'admin_required', 'message': 'Admin denied'}
                self.page.locator('#caAdminEmailButton').click()
                self.page.wait_for_function('document.getElementById("caAdminEmailStatus").textContent.includes("dəyişdirilmədi")')
                self.assertTrue(self.page.locator('#caAdminEmailButton').is_enabled())
                self.assertEqual(self.saved_session(), original)
                self.assertEqual(self.page.evaluate('currentUser.email'), original['user']['email'])
                self.backend.email_network_error = False
                self.backend.email_status = 200
                self.backend.email_result = {'status': 'updated', 'user_id': OWNER, 'email': EMAIL}
                self.page.locator('#caAdminEmailButton').click()
                self.page.wait_for_function('currentUser.email==="' + EMAIL + '"')
                self.assertTrue(self.page.locator('#caAdminEmailButton').is_disabled())
        self.assertEqual(len(self.backend.email_calls), 4)
        self.assert_no_auth_mutation()

    def test_mismatched_user_email_or_status_never_claims_success(self):
        for invalid in ({'user_id': OTHER_OWNER}, {'email': 'unexpected@example.invalid'}, {'status': 'pending'}):
            with self.subTest(invalid=invalid):
                self.as_admin()
                original = self.saved_session()
                self.backend.email_result = {'status': 'updated', 'user_id': OWNER, 'email': EMAIL, **invalid}
                self.page.locator('#caAdminEmailButton').click()
                self.page.wait_for_function('document.getElementById("caAdminEmailStatus").textContent.includes("dəyişdirilmədi")')
                self.assertEqual(self.saved_session(), original)
                self.assertEqual(self.page.evaluate('currentUser.email'), original['user']['email'])
                self.assertTrue(self.page.locator('#caAdminEmailButton').is_enabled())
                self.assertNotIn('✓', self.page.locator('#caAdminEmailButton').inner_text())
        self.assertEqual(len(self.backend.email_calls), 3)
        self.assert_no_auth_mutation()

    def test_pending_change_sends_one_request_even_if_action_is_called_again(self):
        self.as_admin()
        self.backend.delay_email = True
        self.page.locator('#caAdminEmailButton').click()
        self.wait_for_pending()
        self.assertTrue(self.page.locator('#caAdminEmailButton').is_disabled())
        self.assertFalse(self.page.evaluate('async()=>await caAdminChangeEmail()'))
        self.assertEqual(len(self.backend.email_calls), 1)
        self.release_pending()
        self.assertEqual(self.page.evaluate('currentUser.email'), EMAIL)
        self.assertTrue(self.page.locator('#caAdminEmailButton').is_disabled())

    def test_late_response_after_logout_does_not_restore_account_or_success(self):
        self.as_admin()
        self.backend.delay_email = True
        self.page.locator('#caAdminEmailButton').click()
        self.wait_for_pending()
        self.page.evaluate('async()=>await logout()')
        self.release_pending()
        self.assertIsNone(self.page.evaluate('currentUser'))
        self.assertIsNone(self.saved_session())
        self.assertFalse(self.page.locator('#caAdminPanel').is_visible())
        self.assertEqual(self.page.locator('#caAdminEmailStatus').inner_text(), '')
        self.assertEqual(len(self.backend.email_calls), 1)

    def test_late_response_cannot_overwrite_another_account_or_its_draft(self):
        self.as_admin()
        self.backend.delay_email = True
        self.page.locator('#caAdminEmailButton').click()
        self.wait_for_pending()
        session = fixture_session(OTHER_OWNER, 'user-token')
        session['user']['email'] = 'other@example.invalid'
        self.page.evaluate('''async session=>{
            await caPersistSession(session);openSellPage();
            document.getElementById('sellerDescription').value='Other account draft';
        }''', session)
        before = self.saved_session()
        self.release_pending()
        self.assertEqual(self.saved_session(), before)
        self.assertEqual(self.page.evaluate('currentUser.id'), OTHER_OWNER)
        self.assertEqual(self.page.evaluate('currentUser.email'), 'other@example.invalid')
        self.assertEqual(self.page.locator('#sellerDescription').input_value(), 'Other account draft')
        self.assertEqual(self.page.evaluate('caDraftOwner'), OTHER_OWNER)
        self.assertFalse(self.page.locator('#caAdminPanel').is_visible())
        self.assertEqual(self.page.locator('#caAdminEmailStatus').inner_text(), '')

    def test_late_response_cannot_change_same_user_after_logout_and_new_session(self):
        self.as_admin()
        self.backend.delay_email = True
        self.page.locator('#caAdminEmailButton').click()
        self.wait_for_pending()
        self.page.evaluate('async()=>await logout()')
        session = fixture_session(OWNER, 'new-session-token')
        self.page.evaluate('async session=>await caPersistSession(session)', session)
        before = self.saved_session()
        self.release_pending()
        self.assertEqual(self.saved_session(), before)
        self.assertEqual(self.page.evaluate('currentUser.email'), session['user']['email'])
        self.assertEqual(self.page.evaluate('caSession.access_token'), 'new-session-token')
        self.assertEqual(self.page.locator('#caAdminEmailStatus').inner_text(), '')

    def test_public_pages_and_policy_modal_use_new_contact_and_existing_phone(self):
        link_count = phone_count = 0
        for name in PUBLIC_PAGES:
            with self.subTest(page=name):
                self.page.goto(ORIGIN + name, wait_until='load')
                self.assertLessEqual(set(EMAIL_TOKEN.findall(self.page.locator('body').inner_text())), {EMAIL})
                links = self.page.locator('a[href^="mailto:"]')
                for link in links.all():
                    self.assertTrue(link.is_visible())
                    self.assertEqual(link.get_attribute('href'), 'mailto:' + EMAIL)
                    self.assertIn(EMAIL, link.inner_text())
                link_count += links.count()
                if name in ('support.html', 'terms.html', 'privacy.html'):
                    for link in self.page.locator('a[href^="tel:"]').all():
                        self.assertTrue(link.is_visible())
                        self.assertEqual(link.get_attribute('href'), 'tel:+994709091997')
                        self.assertIn('0709091997', link.inner_text())
                        phone_count += 1
        self.assertEqual(link_count, 4)
        self.assertEqual(phone_count, 4)
        self.go()
        self.page.evaluate('caShowPolicy()')
        self.assertEqual(self.page.locator('#caDialogBody a[href^="mailto:"]').get_attribute('href'), 'mailto:' + EMAIL)
        self.assertIn(EMAIL, self.page.locator('#caDialogBody').inner_text())
        self.assertEqual(set(EMAIL_TOKEN.findall(self.page.locator('#caDialogBody').inner_text())), {EMAIL})
        self.assertEqual(self.page.locator('#caDialogBody a[href^="tel:"]').get_attribute('href'), 'tel:+994709091997')
        self.assertIn('0709091997', self.page.locator('#caDialogBody').inner_text())
        self.assertFalse(self.backend.email_calls)
        self.assert_no_auth_mutation()


if __name__ == '__main__':
    unittest.main()
