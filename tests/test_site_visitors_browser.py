"""Daily visitor browser behavior with every HTTP request intercepted.

Synthetic receipts test client retries and identity reuse; SQL tests separately
verify real deduplication, permissions and concurrency. No real visitor, Auth,
email, provider or database operation is performed.
"""
import json
import os
import re
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from test_listing_management_browser import OfflineBackend, ORIGIN, ROOT


KEY = 'avtounvan.siteVisitor.v1'
VISITOR = '99999999-9999-4999-8999-999999999999'
RPC_PREFIX = '/rest/v1/rpc/'
RPCS = {'ca_record_site_visit', 'ca_daily_site_visitors'}
FIXTURE = 'visitor-fixture.html'
PAGES = ('index.html', 'about.html', 'support.html', 'terms.html',
         'privacy.html', 'reset-password.html')
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

FIXTURE_HTML = '''<!doctype html><html lang="az"><head><meta charset="utf-8">
<meta name="referrer" content="no-referrer"></head><body>
<span class="ca-site-visitors" aria-live="polite">Bu gün:
<strong data-ca-daily-visitors id="caDailyVisitors">—</strong> ziyarətçi</span>
<script defer src="assets/js/22-site-visitors.js"></script></body></html>'''

CLOCK = r'''(() => {
 const RealDate=Date;
 window.__visitorNow=RealDate.parse('2026-11-20T12:00:00Z');
 window.Date=class extends RealDate {
  constructor(...args){super(...(args.length?args:[window.__visitorNow]));}
  static now(){return window.__visitorNow;}
 };
 window.__visitorFetch=[];
 const realFetch=window.fetch;
 window.fetch=function(input,init={}){
  const url=String(input?.url||input);
  if(/\/rpc\/ca_(record_site_visit|daily_site_visitors)(?:\?|$)/.test(url)){
   window.__visitorFetch.push({url,credentials:init.credentials,
      referrerPolicy:init.referrerPolicy,headers:[...new Headers(init.headers).entries()]});
  }
  return realFetch.apply(this,arguments);
 };
})();'''


class VisitorBackend(OfflineBackend):
    def __init__(self):
        super().__init__()
        self.day = '2026-11-20'
        self.totals = {self.day: 500}
        self.receipts = set()
        self.visitor_calls = []
        self.fail_records = False
        self.fail_reads = False
        self.malformed = None
        self.hold_records = False
        self.pending = []

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        filename = parsed.path.lstrip('/')
        if req.url.startswith(ORIGIN) and filename == FIXTURE:
            route.fulfill(content_type='text/html', body=FIXTURE_HTML)
            return
        if req.url.startswith(ORIGIN) and filename in PAGES[1:]:
            source = ROOT / filename
            route.fulfill(content_type='text/html', body=source.read_bytes())
            return
        name = parsed.path.rsplit('/', 1)[-1]
        if parsed.path.startswith(RPC_PREFIX) and name in RPCS:
            body = req.post_data_json if req.post_data else None
            call = {'name': name, 'method': req.method, 'body': body,
                    'headers': dict(req.headers)}
            self.visitor_calls.append(call)
            assert req.method == 'POST'
            if ((name == 'ca_record_site_visit' and self.fail_records)
                    or (name == 'ca_daily_site_visitors' and self.fail_reads)):
                route.fulfill(status=503, content_type='application/json',
                              body='{"message":"Fixture unavailable"}')
                return
            payload = {'day': self.day, 'timezone': 'Asia/Baku',
                       'visitors': self.totals.setdefault(self.day, 0)}
            if name == 'ca_record_site_visit':
                assert set(body) == {'p_visitor'}
                assert UUID.fullmatch(body['p_visitor'])
                receipt = (self.day, body['p_visitor'])
                fresh = receipt not in self.receipts
                self.receipts.add(receipt)
                if fresh:
                    self.totals[self.day] += 1
                payload.update(visitors=self.totals[self.day], counted=fresh)
            else:
                assert body in ({}, None)
            if self.malformed is not None:
                payload = self.malformed
            if name == 'ca_record_site_visit' and self.hold_records:
                self.pending.append((route, payload))
            else:
                route.fulfill(content_type='application/json', body=json.dumps(payload))
            return
        super().route(route)

    def records(self):
        return [c for c in self.visitor_calls if c['name'] == 'ca_record_site_visit']

    def reads(self):
        return [c for c in self.visitor_calls if c['name'] == 'ca_daily_site_visitors']

    def release(self):
        pending, self.pending = self.pending, []
        for route, payload in pending:
            route.fulfill(content_type='application/json', body=json.dumps(payload))


class SiteVisitorBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(service_workers='block')
        self.context.add_init_script(CLOCK)
        self.backend = VisitorBackend()
        self.errors = []
        self.context.on('page', lambda p: p.on('pageerror', lambda e:self.errors.append(str(e))))
        self.context.route('**/*', self.backend.route)
        self.page = self.context.new_page()
        self.page.set_default_timeout(6000)

    def tearDown(self):
        for route, _ in self.backend.pending:
            try:
                route.abort()
            except Exception:
                pass
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')

    def go(self, filename=FIXTURE):
        self.page.goto(ORIGIN+filename, wait_until='load')

    def value(self, value, page=None):
        expect((page or self.page).locator('[data-ca-daily-visitors]')).to_have_text(str(value))

    def wait_calls(self, count):
        # Await observable mocked requests, without imposing fixed render sleeps.
        for _ in range(300):
            if len(self.backend.visitor_calls) >= count:
                return
            self.page.wait_for_timeout(10)
        self.fail(f'Expected {count} visitor calls; got {len(self.backend.visitor_calls)}')

    def state(self, storage='localStorage'):
        return self.page.evaluate('(args)=>JSON.parse(window[args.storage].getItem(args.key))',
                                  {'key':KEY, 'storage':storage})

    def test_first_visit_records_once_and_reload_reads_fresh_shared_count(self):
        self.go()
        self.value(501)
        first = self.state()
        self.assertTrue(UUID.fullmatch(first['visitor']))
        self.assertEqual(first['recordedDay'], self.backend.day)
        self.assertEqual(len(self.backend.records()), 1)
        self.backend.totals[self.backend.day] = 731
        self.page.reload(wait_until='load')
        self.value(731)
        self.assertEqual(self.state(), first)
        self.assertEqual(len(self.backend.records()), 1)
        self.assertEqual(len(self.backend.reads()), 1)

    def test_public_home_displays_real_count_and_all_six_pages_include_tracker(self):
        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.items = []

            def handle_starttag(self, tag, attrs):
                if tag == 'script':
                    self.items.append(dict(attrs))

        for filename in PAGES:
            parser = Scripts()
            parser.feed((ROOT / filename).read_text())
            trackers = [attrs for attrs in parser.items
                        if attrs.get('src', '').split('?')[0] == 'assets/js/22-site-visitors.js']
            self.assertEqual(len(trackers), 1, filename)
            self.assertIn('defer', trackers[0], filename)
        self.go('index.html')
        self.value(501)
        self.assertIn('ziyarətçi', self.page.locator('.ca-site-visitors').inner_text())

    def test_direct_information_page_is_counted_before_home_without_counting_twice(self):
        self.go('support.html')
        self.wait_calls(1)
        self.page.wait_for_function('(key)=>Boolean(JSON.parse(localStorage.getItem(key)||"null")?.recordedDay)', arg=KEY)
        self.assertEqual(len(self.backend.records()), 1)
        self.go()
        self.value(501)
        self.assertEqual(len(self.backend.records()), 1)
        self.assertEqual(len(self.backend.reads()), 1)

    def test_anonymous_rpc_does_not_leak_logged_in_session_cookie_or_referrer(self):
        self.context.add_init_script('''window.currentUser={id:'private-user',email:'private@example.invalid'};
          window.caSession={access_token:'private-auth-token'};''')
        self.context.add_cookies([{'name':'private-session','value':'private-cookie',
                                  'domain':'iqdtehqxusfiwokrzceo.supabase.co',
                                  'path':'/','secure':True,'sameSite':'None'}])
        self.go(FIXTURE+'?private=private-url-marker')
        self.value(501)
        visitor = self.state()['visitor']
        for call in self.backend.visitor_calls:
            self.assertNotIn('authorization', call['headers'])
            self.assertNotIn('cookie', call['headers'])
            self.assertNotIn('referer', call['headers'])
            self.assertNotIn('private-', json.dumps(call))
        transport = self.page.evaluate('window.__visitorFetch')
        self.assertTrue(transport)
        self.assertTrue(all(t['credentials']=='omit' and t['referrerPolicy']=='no-referrer' for t in transport))
        self.page.evaluate('window.currentUser=null;window.caSession=null')
        self.page.reload(wait_until='load')
        self.value(501)
        self.assertEqual(self.state()['visitor'], visitor)
        self.assertEqual(len(self.backend.records()), 1)

    def test_baku_midnight_reuses_browser_id_and_records_the_new_day(self):
        self.context.add_init_script("window.__visitorNow=Date.parse('2026-11-20T19:59:59Z')")
        self.go()
        self.value(501)
        visitor = self.state()['visitor']
        self.backend.day = '2026-11-21'
        self.page.evaluate("window.__visitorNow=Date.parse('2026-11-20T20:00:01Z');document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('pageshow'))")
        self.value(1)
        self.assertEqual(self.state()['visitor'], visitor)
        self.assertEqual(self.state()['recordedDay'], '2026-11-21')
        self.assertEqual([c['body']['p_visitor'] for c in self.backend.records()], [visitor, visitor])

    def test_blocked_local_storage_falls_back_to_session_and_reuses_identity(self):
        self.context.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Blocked','SecurityError')}})")
        self.go()
        self.value(501)
        visitor = self.state('sessionStorage')['visitor']
        self.page.reload(wait_until='load')
        self.value(501)
        self.assertEqual(self.state('sessionStorage')['visitor'], visitor)
        self.assertEqual(len(self.backend.records()), 1)

    def test_both_storages_blocked_uses_read_only_count_instead_of_new_ids(self):
        self.context.add_init_script("for(const name of ['localStorage','sessionStorage'])Object.defineProperty(window,name,{get(){throw new DOMException('Blocked','SecurityError')}})")
        self.go()
        self.value(500)
        self.page.reload(wait_until='load')
        self.value(500)
        self.assertEqual(self.backend.records(), [])
        self.assertEqual(len(self.backend.reads()), 2)

    def test_privacy_storage_and_web_locks_denial_still_reads_without_generating_identity(self):
        self.context.add_init_script('''(() => {
          for(const name of ['localStorage','sessionStorage'])
            Object.defineProperty(window,name,{get(){throw new DOMException('Blocked','SecurityError')}});
          window.__visitorLockAttempts=0;window.__visitorIdGenerations=0;
          Object.defineProperty(navigator,'locks',{value:{request(){
            window.__visitorLockAttempts++;
            return Promise.reject(new DOMException('Privacy policy blocks locks','SecurityError'));
          }}});
          const createId=crypto.randomUUID.bind(crypto);
          Object.defineProperty(crypto,'randomUUID',{value(){
            window.__visitorIdGenerations++;return createId();
          }});
        })();''')
        self.go()
        self.value(500)
        self.assertEqual(self.page.evaluate('window.__visitorLockAttempts'), 1)
        self.assertEqual(self.page.evaluate('window.__visitorIdGenerations'), 0)
        self.assertEqual(self.backend.records(), [])
        self.assertEqual(len(self.backend.reads()), 1)
        self.assertEqual(self.backend.reads()[0]['body'], {})

    def test_failed_record_stays_unknown_and_retries_after_reload(self):
        self.backend.fail_records = True
        self.go()
        self.wait_calls(1)
        self.page.wait_for_function('window.__visitorFetch.length===1')
        self.value('—')
        self.assertFalse(self.state().get('recordedDay'))
        visitor = self.state()['visitor']
        self.backend.fail_records = False
        self.page.reload(wait_until='load')
        self.value(501)
        self.assertEqual(len(self.backend.records()), 2)
        self.assertEqual([c['body']['p_visitor'] for c in self.backend.records()], [visitor, visitor])

    def test_corrupt_persisted_identity_recovers_without_crashing(self):
        self.context.add_init_script("if(!sessionStorage.getItem('seeded')){localStorage.setItem('avtounvan.siteVisitor.v1','{not json');sessionStorage.setItem('seeded','1')}")
        self.go()
        self.value(501)
        self.assertTrue(UUID.fullmatch(self.state()['visitor']))

    def test_invalid_server_count_is_not_displayed_or_acknowledged(self):
        self.backend.malformed = {'day':'2026-11-20','timezone':'Asia/Baku','visitors':-50,'counted':True}
        self.go()
        self.wait_calls(1)
        self.value('—')
        self.assertFalse(self.state().get('recordedDay'))

    def test_concurrent_tabs_reuse_shared_identifier_while_record_is_pending(self):
        # A new tab first has an opaque about:blank origin; seed only the
        # actual fixture origin, whose storage is shared with the first tab.
        self.context.add_init_script("if(location.origin==='http://127.0.0.1:8766'&&!localStorage.getItem('avtounvan.siteVisitor.v1'))localStorage.setItem('avtounvan.siteVisitor.v1',JSON.stringify({visitor:'99999999-9999-4999-8999-999999999999',recordedDay:''}))")
        self.backend.hold_records = True
        self.go()
        self.wait_calls(1)
        other = self.context.new_page()
        other.goto(ORIGIN+FIXTURE, wait_until='load')
        self.assertEqual(self.backend.totals[self.backend.day], 501)
        self.backend.hold_records = False
        self.backend.release()
        self.value(501)
        self.value(501, other)
        self.assertTrue(all(c['body']['p_visitor'] == VISITOR for c in self.backend.records()))
        self.assertEqual(self.backend.totals[self.backend.day], 501)


if __name__ == '__main__':
    unittest.main()
