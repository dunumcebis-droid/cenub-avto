"""Offline admin/recovery regressions. Every request is intercepted.

No real email is sent, password changed, or administrative mutation performed.
Actual admin authorization/paging is covered by admin-pagination-db.sql.
"""
import copy
import json
import os
import unittest
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright
from test_listing_management_browser import OfflineBackend, ORIGIN, OWNER, OTHER_OWNER, owned_row

RECOVERY_USER = '33333333-3333-4333-8333-333333333333'


class AdminAuthBackend(OfflineBackend):
    def __init__(self):
        super().__init__()
        self.auth_calls=[]
        self.admin_calls=[]
        self.invalid_recovery=False
        self.fail_recover=False
        self.fail_public=False
        self.delay_recovery=False
        self.pending_recovery=[]
        self.delay_admin=False
        self.pending_admin=[]
        self.pending_password=[]
        self.delay_password=False
        self.admin_rows=[dict(id=f'44444444-4444-4444-8444-{n:012d}',marka='Toyota',
            model=f'Admin-{n:04d}',il=2020,qiymet=10000+n,seher='Bakı',tesvir='Admin fixture',
            veziyyet='gozlemede' if n==1205 else 'aktiv',yaradildi='2026-01-01T00:00:00Z',
            requested_package='Pulsuz',package_status='free',package_request_id=None,approved_package='Pulsuz')
            for n in range(1,1206)]
        self.payments=[dict(id=f'55555555-5555-4555-8555-{n:012d}',elan_id=row['id'],
            marka=row['marka'],model=row['model'],paket_adi='VIP',
            odenis_veziyyeti='gozlemede' if n==1205 else 'tesdiqlendi',
            yaradilib='2026-01-01T00:00:00Z',tesdiqlenib=None) for n,row in enumerate(self.admin_rows,1)]
        pending=owned_row();pending.update(self.admin_rows[-1]);pending.update(satici_id=OTHER_OWNER,paket_adi='Pulsuz',sekiller=[])
        self.rows.append(pending)
        self.today_approved=0

    def route(self,route):
        req=route.request;parsed=urlsplit(req.url)
        body=req.post_data_json if req.post_data else None

        def send(data,status=200):
            route.fulfill(status=status,content_type='application/json',body=json.dumps(data))

        if parsed.path.startswith('/auth/v1/'):
            self.auth_calls.append(dict(path=parsed.path,method=req.method,body=body,
                query=parse_qs(parsed.query),authorization=req.headers.get('authorization')))
            if parsed.path=='/auth/v1/recover':
                send({'message':'Email limit exceeded'} if self.fail_recover else {},429 if self.fail_recover else 200);return
            if parsed.path=='/auth/v1/user' and req.method=='GET':
                data={'id':RECOVERY_USER,'email':'recover@example.invalid'}
                if self.delay_recovery:self.pending_recovery.append((route,data));return
                send({'message':'Expired token'} if self.invalid_recovery else data,401 if self.invalid_recovery else 200);return
            if parsed.path=='/auth/v1/user' and req.method=='PUT':
                assert req.headers.get('authorization')=='Bearer recovery-token'
                assert set(body)=={'password'}
                data={'id':RECOVERY_USER,'email':'recover@example.invalid'}
                if self.delay_password:self.pending_password.append((route,data));return
                send(data);return
            if parsed.path=='/auth/v1/verify':
                assert body.get('type')=='recovery'
                send({'access_token':'recovery-token'});return
            if parsed.path=='/auth/v1/signup':
                send({'user':{'id':OWNER}});return
            if parsed.path=='/auth/v1/token':
                send({'access_token':'user-token','refresh_token':'user-refresh','expires_at':4102444800,
                    'user':{'id':OWNER,'email':body['email'],'user_metadata':{'telefon':'+994000000000'}}});return
            if parsed.path=='/auth/v1/logout':send({});return
            raise AssertionError('Unexpected mocked auth request '+parsed.path)
        if parsed.path=='/rest/v1/profiller':send({});return
        if parsed.path=='/rest/v1/rpc/ca_browse_listings' and self.fail_public:
            send({'message':'Mock refresh unavailable'},503);return
        name=parsed.path.split('/')[-1]
        if parsed.path.startswith('/rest/v1/rpc/') and (name.startswith('ca_admin_') or name=='cenub_admin_yoxla'):
            admin=req.headers.get('authorization')=='Bearer admin-token'
            self.admin_calls.append(dict(name=name,body=body,admin=admin))
            if name=='cenub_admin_yoxla':send(admin);return
            if not admin:send({'message':'Admin denied'},403);return
            if name in ('ca_admin_browse_listings','ca_admin_browse_payments'):
                assert set(body)=={'p_status','p_query','p_page','p_page_size'}
                assert body['p_page_size']==24
                pay=name.endswith('payments');source=self.payments if pay else self.admin_rows
                key='odenis_veziyyeti' if pay else 'veziyyet'
                selected=[r for r in source if (body['p_status']=='all' or r[key]==body['p_status']) and
                    body['p_query'].lower() in (' '.join(str(r.get(k,'')) for k in ('marka','model','seher','paket_adi'))).lower()]
                total=len(selected);pages=(total+23)//24;page=max(1,min(body['p_page'],max(1,pages)))
                data={'items':selected[(page-1)*24:page*24],'total':total,'pending_total':sum(r[key]=='gozlemede' for r in source),
                    'page':page,'page_size':24,'total_pages':pages}
                if self.delay_admin:self.delay_admin=False;self.pending_admin.append((route,copy.deepcopy(data)));return
                send(data);return
            if name=='ca_admin_status':
                row=next(r for r in self.admin_rows if r['id']==body['p_id']);row['veziyyet']=body['p_status']
                target=next(r for r in self.rows if r['id']==row['id']);target['veziyyet']=body['p_status']
                self.today_approved=1 if body['p_status']=='aktiv' else 0
                send(None);return
            if name=='ca_admin_paket_tesdiq':
                payment=next(p for p in self.payments if p['id']==body['p_sorgu_id']);payment['odenis_veziyyeti']='tesdiqlendi'
                target=next(r for r in self.rows if r['id']==payment['elan_id']);target.update(paket_adi='VIP',paket_bitir='2099-01-01T00:00:00Z')
                send(None);return
            if name=='ca_admin_paket_reddet':
                next(p for p in self.payments if p['id']==body['p_sorgu_id'])['odenis_veziyyeti']='reddedildi';send(None);return
            raise AssertionError('Unexpected admin RPC '+name)
        super().route(route)


class AdminAuthBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1280,'height':1000})
        self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.add_init_script("window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true")
        self.backend=AdminAuthBackend();self.page.route('**/*',self.backend.route)

    def tearDown(self):
        self.context.close();self.assertFalse(self.errors)

    def go(self,suffix=''):
        self.page.goto(ORIGIN+suffix,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')

    def as_admin(self):
        self.go();self.page.evaluate('''async id=>{currentUser={id,email:'admin@example.invalid',phone:'+994000000000'};
            caSession={access_token:'admin-token',expires_at:4102444800,user:{id}};updateAccountUI();await caAdminOpen();}''',OWNER)
        self.assertTrue(self.page.locator('#caAdminPanel').is_visible())

    def recovery(self):
        self.go('#access_token=recovery-token&refresh_token=fixture-secret&type=recovery&expires_in=3600')
        self.page.wait_for_function('authMode==="reset"&&!document.getElementById("authSubmit").disabled')

    def wait_for_pending(self, pending):
        for _ in range(100):
            if pending:
                return
            self.page.wait_for_timeout(10)
        self.fail('The deliberately delayed offline request did not start')

    def test_forgot_password_sends_only_email_with_canonical_redirect(self):
        self.go();self.page.evaluate("openAuth('login')");self.page.locator('#authForgot').click()
        self.assertFalse(self.page.locator('#authPassword').is_visible())
        self.page.locator('#authEmail').fill('User@Example.invalid');self.page.locator('#authSubmit').click()
        self.page.wait_for_function('document.getElementById("authMessage").textContent.includes("mümkündürsə")')
        call=next(c for c in self.backend.auth_calls if c['path']=='/auth/v1/recover')
        self.assertEqual(call['body'],{'email':'user@example.invalid'})
        self.assertEqual(call['query']['redirect_to'],['https://dunumcebis-droid.github.io/cenub-avto/?auth=recovery'])
        self.assertIsNone(call['authorization'])

    def test_recovery_verifies_user_scrubs_url_and_updates_only_recovery_account(self):
        self.recovery();self.assertEqual(self.page.url,ORIGIN)
        self.assertIn('recover@example.invalid',self.page.locator('#authIntro').inner_text())
        self.assertEqual(self.page.evaluate('localStorage.getItem(CA_SESSION_KEY)'),None)
        self.assertFalse(any(c['method']=='PUT' for c in self.backend.auth_calls))
        self.page.locator('#authPassword').fill('Fixture-new-pass-123');self.page.locator('#authPassword2').fill('Different-pass-123')
        self.page.locator('#authSubmit').click();self.assertIn('eyni deyil',self.page.locator('#authMessage').inner_text())
        self.assertFalse(any(c['method']=='PUT' for c in self.backend.auth_calls))
        self.page.locator('#authPassword2').fill('Fixture-new-pass-123');self.page.locator('#authSubmit').click()
        self.page.wait_for_function('authMode==="login"')
        self.assertIn('Parol yeniləndi',self.page.locator('#authMessage').inner_text())
        puts=[c for c in self.backend.auth_calls if c['method']=='PUT'];self.assertEqual(len(puts),1)
        self.assertEqual(puts[0]['authorization'],'Bearer recovery-token')
        self.assertIsNone(self.page.evaluate('localStorage.getItem(CA_SESSION_KEY)'))
        self.assertIsNone(self.page.evaluate('window.__caAuthCallback'))

    def test_expired_recovery_and_unsupported_code_show_retry_without_password_write(self):
        self.backend.invalid_recovery=True;self.go('#type=recovery&access_token=expired')
        self.page.wait_for_function('authMode==="recover"')
        self.assertIn('vaxtı bitib',self.page.locator('#authMessage').inner_text())
        self.assertEqual(self.page.url,ORIGIN);self.assertFalse(any(c['method']=='PUT' for c in self.backend.auth_calls))
        self.go('?type=recovery&code=not-our-pkce-code')
        self.page.wait_for_function('authMode==="recover"');self.assertEqual(self.page.url,ORIGIN)

    def test_callback_token_hash_uses_verify_then_verified_user(self):
        self.go('?type=recovery&token_hash=fixture-hash')
        self.page.wait_for_function('authMode==="reset"&&!document.getElementById("authSubmit").disabled')
        self.assertEqual(self.page.url,ORIGIN)
        self.assertEqual([c['path'] for c in self.backend.auth_calls],['/auth/v1/verify','/auth/v1/user'])

    def test_explicit_query_recovery_token_is_verified_and_never_saved_as_a_session(self):
        self.go('?auth=recovery&type=recovery&access_token=recovery-token&refresh_token=fixture-secret')
        self.page.wait_for_function('authMode==="reset"&&!document.getElementById("authSubmit").disabled')
        self.assertEqual(self.page.url,ORIGIN)
        self.assertEqual(self.page.locator('#authTitle').inner_text(),'Yeni parol yarat')
        self.assertIsNone(self.page.evaluate('localStorage.getItem(CA_SESSION_KEY)'))
        self.assertEqual([c['path'] for c in self.backend.auth_calls],['/auth/v1/user'])

    def test_existing_tab_handles_new_recovery_fragment_without_replacing_signed_in_account(self):
        self.go()
        self.page.evaluate('''id=>{currentUser={id,email:'owner@example.invalid',phone:'+994000000000'};
            caSession={access_token:'owner-token',expires_at:4102444800,user:{id}};
            localStorage.setItem(CA_SESSION_KEY,JSON.stringify(caSession));updateAccountUI();}''',OWNER)
        original=self.page.evaluate('localStorage.getItem(CA_SESSION_KEY)')
        self.page.evaluate("location.hash='type=recovery&access_token=recovery-token&refresh_token=fixture-secret'")
        self.page.wait_for_function('authMode==="reset"&&!document.getElementById("authSubmit").disabled',timeout=3000)
        self.assertTrue(self.page.locator('#authOverlay').is_visible())
        self.assertEqual(self.page.locator('#authTitle').inner_text(),'Yeni parol yarat')
        self.assertEqual(self.page.url,ORIGIN)
        self.assertEqual(self.page.evaluate('currentUser.id'),OWNER)
        self.assertEqual(self.page.evaluate('caSession.access_token'),'owner-token')
        self.assertEqual(self.page.evaluate('localStorage.getItem(CA_SESSION_KEY)'),original)
        self.assertIsNone(self.page.evaluate('window.__caAuthCallback'))
        self.assertEqual([c['path'] for c in self.backend.auth_calls],['/auth/v1/user'])

    def test_recovery_entry_without_credentials_shows_a_visible_retry_instead_of_homepage(self):
        self.go('?auth=recovery')
        self.page.wait_for_function('authMode==="recover"&&document.getElementById("authMessage").getAttribute("role")==="alert"',timeout=3000)
        self.assertTrue(self.page.locator('#authOverlay').is_visible())
        self.assertIn('link',self.page.locator('#authMessage').inner_text())
        self.assertEqual(self.page.url,ORIGIN)
        self.assertFalse(self.backend.auth_calls)

    def test_used_link_error_arriving_in_existing_tab_shows_retry_without_an_auth_write(self):
        self.go()
        self.page.evaluate("location.hash='error=access_denied&error_code=otp_expired&error_description=Email+link+invalid+or+expired'")
        self.page.wait_for_function('authMode==="recover"&&document.getElementById("authMessage").getAttribute("role")==="alert"',timeout=3000)
        self.assertTrue(self.page.locator('#authOverlay').is_visible())
        self.assertIn('istifadə olunub',self.page.locator('#authMessage').inner_text())
        self.assertFalse(self.page.locator('#authPassword').is_visible())
        self.assertEqual(self.page.url,ORIGIN)
        self.assertFalse(self.backend.auth_calls)

    def test_closing_recovery_ignores_late_user_verification(self):
        self.backend.delay_recovery=True;self.go('#type=recovery&access_token=recovery-token')
        self.assertEqual(len(self.backend.pending_recovery),1)
        self.page.evaluate("closeAuth();openAuth('login')")
        route,data=self.backend.pending_recovery.pop();route.fulfill(content_type='application/json',body=json.dumps(data))
        self.page.wait_for_timeout(80)
        self.assertEqual(self.page.evaluate('authMode'),'login');self.assertIsNone(self.page.evaluate('caRecovery'))

    def test_late_password_update_cannot_replace_new_login_or_clear_its_draft(self):
        self.recovery();self.backend.delay_password=True
        self.page.locator('#authPassword').fill('Fixture-old-recovery-123')
        self.page.locator('#authPassword2').fill('Fixture-old-recovery-123')
        self.page.locator('#authSubmit').click()
        self.wait_for_pending(self.backend.pending_password)
        self.page.evaluate("closeAuth();openAuth('login')")
        self.page.locator('#authEmail').fill('different-account@example.invalid')
        self.page.locator('#authPassword').fill('Fixture-current-login-123')
        self.page.locator('#authSubmit').click()
        self.page.wait_for_function('currentUser?.id=== "'+OWNER+'" && !document.getElementById("authOverlay").classList.contains("open")',timeout=3000)
        self.page.evaluate('openSellPage()')
        self.page.locator('#listingForm [name="price"]').fill('47000')
        self.page.locator('#sellerDescription').fill('New account draft must survive an old recovery response')
        before=self.page.evaluate('({session:localStorage.getItem(CA_SESSION_KEY),message:document.getElementById("authMessage").textContent,epoch:caListingSubmissionSequence})')
        route,data=self.backend.pending_password.pop()
        with self.page.expect_response(lambda response:response.request.method=='PUT' and urlsplit(response.url).path=='/auth/v1/user',timeout=3000) as response:
            route.fulfill(content_type='application/json',body=json.dumps(data))
        response.value.body()
        self.page.evaluate('async()=>{await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)}')
        self.assertEqual(self.page.evaluate('currentUser.id'),OWNER)
        self.assertEqual(self.page.evaluate('caSession.access_token'),'user-token')
        self.assertEqual(self.page.evaluate('localStorage.getItem(CA_SESSION_KEY)'),before['session'])
        self.assertFalse(self.page.locator('#authOverlay').is_visible())
        self.assertIsNone(self.page.evaluate('caRecovery'))
        self.assertEqual(self.page.locator('#authMessage').inner_text(),before['message'])
        self.assertEqual(self.page.locator('#listingForm [name="price"]').input_value(),'47000')
        self.assertEqual(self.page.locator('#sellerDescription').input_value(),'New account draft must survive an old recovery response')
        self.assertEqual(self.page.evaluate('caDraftOwner'),OWNER)
        self.assertEqual(self.page.evaluate('caListingSubmissionSequence'),before['epoch'])
        self.assertFalse(self.page.locator('#submitListingBtn').is_disabled())
        self.assertEqual(len([call for call in self.backend.auth_calls if call['method']=='PUT']),1)
        self.assertFalse([call for call in self.backend.writes if call['path']!='/rest/v1/rpc/ca_browse_listings'],
                         'Recovery and login must not submit the new listing draft')

    def test_recovery_rate_error_does_not_claim_email_sent(self):
        self.backend.fail_recover=True;self.go();self.page.evaluate("openAuth('recover')")
        self.page.locator('#authEmail').fill('user@example.invalid');self.page.locator('#authSubmit').click()
        self.page.wait_for_function('document.getElementById("authMessage").getAttribute("role")==="alert"')
        self.assertIn('göndərilmədi',self.page.locator('#authMessage').inner_text())

    def test_existing_signup_and_login_modes_still_work(self):
        self.go();self.page.evaluate("openAuth('register')")
        self.page.locator('#authEmail').fill('user@example.invalid');self.page.locator('#authPhone').fill('+994000000000')
        self.page.locator('#authPassword').fill('Fixture-password-123');self.page.locator('#authPassword2').fill('Fixture-password-123')
        self.page.locator('#authSubmit').click();self.page.wait_for_function('authMode==="login"')
        self.assertIn('təsdiq',self.page.locator('#authMessage').inner_text())
        self.page.locator('#authPassword').fill('Fixture-password-123');self.page.locator('#authSubmit').click()
        self.page.wait_for_function('currentUser?.id=== "'+OWNER+'" && !document.getElementById("authOverlay").classList.contains("open")')
        self.assertTrue(any(c['path']=='/auth/v1/signup' for c in self.backend.auth_calls))
        self.assertTrue(any(c['path']=='/auth/v1/token' for c in self.backend.auth_calls))

    def test_admin_and_payment_paging_reach_record_1205_and_filter_server_side(self):
        self.as_admin();self.assertIn('1205 elan',self.page.locator('#caAdminMsg').inner_text())
        self.page.locator('#caAdminPager button').last.click();self.page.wait_for_function('document.getElementById("caAdminPager").textContent.includes("2 / 51")')
        self.page.evaluate('caAdminPage(49)');self.page.wait_for_function('document.getElementById("caAdminList").textContent.includes("Admin-1205")')
        self.page.evaluate("caAdminFilter('gozlemede')");self.page.wait_for_function('document.querySelectorAll("#caAdminList article").length===1')
        self.assertIn('Admin-1205',self.page.locator('#caAdminList').inner_text())
        self.page.evaluate('caPayPage(50)');self.page.wait_for_function('document.getElementById("caPayList").textContent.includes("Admin-1205")')
        self.page.locator('#caPayFilter').select_option('gozlemede');self.page.wait_for_function('document.querySelectorAll("#caPayList article").length===1')
        self.assertIn('Admin-1205',self.page.locator('#caPayList').inner_text())

    def test_old_admin_success_or_error_cannot_overwrite_latest_pending_filter(self):
        self.as_admin()
        for status in (200,503):
            with self.subTest(old_response_status=status):
                self.backend.delay_admin=True
                self.page.evaluate("()=>{window.__oldAdminFilter=caAdminFilter('all')}")
                self.wait_for_pending(self.backend.pending_admin)
                self.page.evaluate("async()=>await caAdminFilter('gozlemede')")
                self.assertEqual(self.page.locator('#caAdminList article').count(),1)
                self.assertIn('Admin-1205',self.page.locator('#caAdminList').inner_text())
                latest_message=self.page.locator('#caAdminMsg').inner_text()
                self.assertTrue(latest_message.startswith('1 elan'))
                route,data=self.backend.pending_admin.pop()
                self.assertEqual(data['total'],1205)
                route.fulfill(status=status,content_type='application/json',body=json.dumps(data if status==200 else {'message':'Old offline request failed'}))
                self.assertFalse(self.page.evaluate('async()=>await window.__oldAdminFilter'))
                self.assertEqual(self.page.locator('#caAdminMsg').inner_text(),latest_message)
                self.assertEqual(self.page.locator('#caAdminList article').count(),1)
                self.assertIn('Admin-1205',self.page.locator('#caAdminList').inner_text())
                self.assertEqual(self.page.locator('#caAdminPager').inner_text(),'')

    def test_real_admin_and_payment_search_forms_win_over_older_1205_record_requests(self):
        self.as_admin()
        for input_id,list_id,msg_id,pager_id,load_function,rpc_name in (
            ('caAdminSearch','caAdminList','caAdminMsg','caAdminPager','caAdminLoad','ca_admin_browse_listings'),
            ('caPaySearch','caPayList','caPayMsg','caPayPager','caAdminPaymentsLoad','ca_admin_browse_payments'),
        ):
            with self.subTest(form=input_id):
                self.backend.delay_admin=True
                self.page.evaluate('name=>{window.__oldAdminSearch=window[name]()} ',load_function)
                self.wait_for_pending(self.backend.pending_admin)
                self.page.locator('#'+input_id).fill('Admin-1205')
                self.page.locator('#'+input_id).press('Enter')
                self.page.wait_for_function('id=>document.getElementById(id).querySelectorAll("article").length===1',arg=list_id,timeout=3000)
                self.assertIn('Admin-1205',self.page.locator('#'+list_id).inner_text())
                latest_message=self.page.locator('#'+msg_id).inner_text()
                searches=[call for call in self.backend.admin_calls if call['name']==rpc_name and call['body']['p_query']=='Admin-1205']
                self.assertEqual(len(searches),1)
                self.assertEqual(searches[0]['body'],{'p_status':'all','p_query':'Admin-1205','p_page':1,'p_page_size':24})
                route,data=self.backend.pending_admin.pop()
                self.assertEqual(data['total'],1205)
                route.fulfill(content_type='application/json',body=json.dumps(data))
                self.assertFalse(self.page.evaluate('async()=>await window.__oldAdminSearch'))
                self.assertEqual(self.page.locator('#'+msg_id).inner_text(),latest_message)
                self.assertEqual(self.page.locator('#'+list_id+' article').count(),1)
                self.assertIn('Admin-1205',self.page.locator('#'+list_id).inner_text())
                self.assertEqual(self.page.locator('#'+pager_id).inner_text(),'')
        self.assertFalse([call for call in self.backend.writes if call['path']!='/rest/v1/rpc/ca_browse_listings'])
        self.assertFalse(any(call['name'] in ('ca_admin_status','ca_admin_paket_tesdiq','ca_admin_paket_reddet') for call in self.backend.admin_calls))

    def test_admin_approval_and_payment_refresh_public_cards_vip_and_today(self):
        self.as_admin();self.page.evaluate("caPaySearch()")
        self.page.locator('#caPayFilter').select_option('gozlemede');self.page.wait_for_function('document.querySelectorAll("#caPayList article").length===1')
        self.page.locator('#caPayList button[data-pay-action="approve"]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("yeniləndi")')
        self.page.evaluate("caAdminFilter('gozlemede')");self.page.wait_for_function('document.querySelectorAll("#caAdminList article").length===1')
        self.page.locator('#caAdminList button[data-status="aktiv"]').click()
        self.page.wait_for_function('caBrowseState.total===3 && document.getElementById("caTodayApproved").textContent==="1"')
        self.assertEqual(self.page.locator('#vipGrid .car-card').count(),2)
        self.assertIn('Admin-1205',self.page.locator('#allGrid').inner_text())

    def test_successful_admin_write_is_not_reported_failed_when_public_refresh_fails(self):
        self.as_admin();self.page.evaluate("caAdminFilter('gozlemede')")
        self.page.wait_for_function('document.querySelectorAll("#caAdminList article").length===1');self.backend.fail_public=True
        self.page.locator('#caAdminList button[data-status="aktiv"]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Bəzi siyahılar")')
        self.assertIn('Dəyişiklik saxlanıldı',self.page.locator('#caAdminActionMsg').inner_text())
        self.assertEqual(sum(c['name']=='ca_admin_status' for c in self.backend.admin_calls),1)

    def test_late_admin_response_cannot_reappear_after_logout(self):
        self.as_admin();self.backend.delay_admin=True;self.page.evaluate('void caAdminLoad()')
        self.page.wait_for_timeout(60);self.assertEqual(len(self.backend.pending_admin),1)
        self.page.evaluate('logout()');route,data=self.backend.pending_admin.pop()
        route.fulfill(content_type='application/json',body=json.dumps(data));self.page.wait_for_timeout(80)
        self.assertFalse(self.page.locator('#caAdminPanel').is_visible());self.assertEqual(self.page.locator('#caAdminList').inner_text(),'')

    def test_non_admin_never_loads_private_admin_pages(self):
        self.go();self.page.evaluate('''async id=>{currentUser={id,phone:''};caSession={access_token:'user-token',expires_at:4102444800,user:{id}};updateAccountUI();await caAdminOpen();}''',OTHER_OWNER)
        self.assertFalse(self.page.locator('#caAdminLaunch').is_visible())
        self.assertFalse(any(c['name'].startswith('ca_admin_browse') for c in self.backend.admin_calls))

    def test_mobile_password_recovery_form_fits_and_shows_inline_message(self):
        self.page.set_viewport_size({'width':375,'height':760});self.recovery()
        self.assertLessEqual(self.page.locator('#authOverlay .auth-box').bounding_box()['width'],375)
        self.page.locator('#authPassword').fill('Fixture-mobile-123');self.page.locator('#authPassword2').fill('Fixture-mobile-123')
        self.page.locator('#authSubmit').click();self.page.wait_for_function('authMode==="login"')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),375)


if __name__=='__main__':unittest.main()
