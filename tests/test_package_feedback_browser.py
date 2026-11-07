"""Package and seller feedback regressions with fully intercepted HTTP.

Fixtures model client behavior only; SQL payment/publication guards have their
own rolled-back database checks. No real emails, payments, or writes occur.
"""
import base64
import copy
import json
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, OWNED_ID, GROUPS, owned_row

PAID_ID='77777777-7777-4777-8777-777777777777'
FREE_ID='88888888-8888-4888-8888-888888888888'
REQUEST_ID='99999999-9999-4999-8999-999999999999'
NEW_ID='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')


class PackageFeedbackBackend(AdminAuthBackend):
    def __init__(self):
        super().__init__()
        self.fail_payment=False;self.fail_save=False;self.fail_storage=False;self.zero_save=False;self.delay_save=False
        self.uploads=[];self.saves=[];self.pending_saves=[]
        self.admin_rows=[];self.payments=[]
        for n in range(50):
            self.admin_rows.append(dict(id=f'12121212-1212-4212-8212-{n:012d}',marka='Toyota',model=f'Free-{n:02d}',
                il=2020,qiymet=20000,seher='Bakı',tesvir='Synthetic free listing',veziyyet='gozlemede',
                yaradildi='2026-11-01T00:00:00Z',requested_package='Pulsuz',package_status='free',package_request_id=None,approved_package='Pulsuz'))
            self.payments.append(dict(id=f'34343434-3434-4434-8434-{n:012d}',elan_id=self.admin_rows[-1]['id'],
                marka='LADA',model='1200',paket_adi='VIP',odenis_veziyyeti='tesdiqlendi',
                yaradilib='2026-11-02T00:00:00Z',tesdiqlenib='2026-11-02T00:00:00Z'))
        paid=dict(id=PAID_ID,marka='LADA',model='1200',il=1980,qiymet=5000,seher='Lənkəran',tesvir='Synthetic paid listing',
            veziyyet='gozlemede',yaradildi='2026-01-01T00:00:00Z',requested_package='VIP',package_status='pending',
            package_request_id=REQUEST_ID,approved_package='Pulsuz')
        free=dict(self.admin_rows[0],id=FREE_ID,model='Free-visible')
        self.admin_rows=[paid,free,*self.admin_rows]
        self.payments.append(dict(id=REQUEST_ID,elan_id=PAID_ID,marka='LADA',model='1200',paket_adi='VIP',
            odenis_veziyyeti='gozlemede',yaradilib='2026-01-01T00:00:00Z',tesdiqlenib=None))
        for info in (paid,free):
            row=owned_row();row.update(info);row.update(satici_id=OWNER,paket_adi='Pulsuz')
            self.rows.append(row)

    def route(self,route):
        req=route.request;parsed=urlsplit(req.url);path=parsed.path
        if path.startswith('/storage/v1/object/'):
            if req.method=='POST':
                assert req.headers.get('authorization')=='Bearer seller-token'
                assert req.headers.get('x-upsert')=='false'
                self.uploads.append(path)
                if self.fail_storage:
                    route.fulfill(status=500,content_type='application/json',body='{"message":"Mock photo upload unavailable"}');return
                route.fulfill(content_type='application/json',body='{}');return
            if req.method=='GET':
                route.fulfill(content_type='image/png',body=PNG);return
            route.abort();return
        body=req.post_data_json if req.post_data else None
        def send(data,status=200):
            route.fulfill(status=status,content_type='application/json',body=json.dumps(data))
        if path=='/rest/v1/elanlar' and req.method=='POST':
            assert req.headers.get('authorization')=='Bearer seller-token'
            assert body['satici_id']==OWNER
            assert 'return=representation' in req.headers.get('prefer','')
            self.saves.append(copy.deepcopy(body))
            if self.fail_save:send({'message':'Mock listing save unavailable'},503);return
            if self.zero_save:send([]);return
            row=dict(body,id=NEW_ID,yaradildi='2026-11-03T00:00:00Z',paket_adi='Pulsuz')
            self.rows.append(row)
            if self.delay_save:self.pending_saves.append((route,[{'id':NEW_ID}]));return
            send([{'id':NEW_ID}]);return
        if path=='/rest/v1/elanlar' and req.method=='PATCH' and self.fail_save and body!={'veziyyet':'silindi'}:
            self.saves.append(copy.deepcopy(body));send({'message':'Mock listing save unavailable'},503);return
        name=path.split('/')[-1]
        if name in ('ca_admin_browse_listings','ca_admin_browse_payments'):
            assert req.headers.get('authorization')=='Bearer admin-token'
            assert set(body)=={'p_status','p_query','p_page','p_page_size'}
            assert body['p_page_size']==24
            self.admin_calls.append(dict(name=name,body=copy.deepcopy(body),admin=True))
            pay=name.endswith('payments');source=self.payments if pay else self.admin_rows
            key='odenis_veziyyeti' if pay else 'veziyyet';query=body['p_query'].lower()
            selected=[row for row in source if (body['p_status']=='all' or row[key]==body['p_status']) and
                query in ' '.join(str(row.get(field,'')) for field in ('id','elan_id','marka','model','seher','paket_adi')).lower()]
            total=len(selected);pages=(total+23)//24;page=max(1,min(body['p_page'],max(1,pages)))
            send(dict(items=copy.deepcopy(selected[(page-1)*24:page*24]),total=total,
                pending_total=sum(row[key]=='gozlemede' for row in source),page=page,page_size=24,total_pages=pages));return
        if name=='ca_admin_paket_tesdiq':
            self.admin_calls.append(dict(name=name,body=copy.deepcopy(body),admin=True))
            assert req.headers.get('authorization')=='Bearer admin-token'
            assert body=={'p_sorgu_id':REQUEST_ID}
            if self.fail_payment:send({'message':'Mock payment confirmation failed'},409);return
            payment=next(row for row in self.payments if row['id']==REQUEST_ID);payment['odenis_veziyyeti']='tesdiqlendi'
            next(row for row in self.admin_rows if row['id']==PAID_ID)['package_status']='confirmed'
            target=next(row for row in self.rows if row['id']==PAID_ID)
            target.update(paket_adi='VIP',paket_bitir='2099-01-01T00:00:00Z')
            send(None);return
        if name=='ca_admin_status':
            self.admin_calls.append(dict(name=name,body=copy.deepcopy(body),admin=True))
            assert req.headers.get('authorization')=='Bearer admin-token'
            target=next(row for row in self.admin_rows if row['id']==body['p_id'])
            if body['p_status']=='aktiv' and target['package_status']=='pending':
                send({'message':'Ödəniş təsdiqlənməyib'},409);return
            target['veziyyet']=body['p_status']
            next(row for row in self.rows if row['id']==target['id'])['veziyyet']=body['p_status']
            self.today_approved+=int(body['p_status']=='aktiv')
            send(None);return
        super().route(route)


class PackageFeedbackBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1280,'height':1000})
        self.context.set_default_timeout(4000)
        self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true')
        self.backend=PackageFeedbackBackend();self.page.route('**/*',self.backend.route)
        self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        self.context.close();self.assertFalse(self.errors)

    def sign_in(self,admin=False):
        self.page.evaluate('''async({id,token})=>await caPersistSession({access_token:token,expires_at:4102444800,
            user:{id,email:'offline@example.invalid',user_metadata:{telefon:'+994000000000'}}})''',
            dict(id=OWNER,token='admin-token' if admin else 'seller-token'))

    def as_admin(self):
        self.sign_in(admin=True);self.page.evaluate('async()=>await caAdminOpen()')
        self.assertTrue(self.page.locator('#caAdminPanel').is_visible())

    def new_listing(self,paid=False):
        self.sign_in();self.page.evaluate('openSellPage()')
        fields={key:value for key,value in owned_row()['ca_data'].items() if key not in ('photos','photo','equipment','pack')}
        self.page.evaluate('''data=>{const form=document.getElementById('listingForm');for(const [key,value] of Object.entries(data)){
            const field=form.elements.namedItem(key);if(field&&'value' in field){field.disabled=false;field.value=String(value);}}
            form.elements.namedItem('package').selectedIndex=0;}''',fields)
        if paid:
            package=self.page.locator('#listingForm [name="package"] option').filter(has_text='15 AZN').evaluate('option=>option.value')
            self.page.locator('#listingForm [name="package"]').select_option(package)
        self.page.locator('#photos-front').set_input_files(dict(name='synthetic.png',mimeType='image/png',buffer=PNG))
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'))

    def submit(self):
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')

    def feedback(self,success=True):
        modal=self.page.locator('#listingFeedback')
        self.assertTrue(modal.is_visible())
        self.assertEqual(modal.get_attribute('role'),'dialog')
        self.assertEqual(self.page.locator('#listingFeedbackText').get_attribute('role'),'status' if success else 'alert')
        self.assertEqual(self.page.evaluate('__alerts'),[],'Submit outcomes must use site feedback rather than native alerts')
        return self.page.locator('#listingFeedbackText').inner_text()

    def paid_card(self):
        return self.page.locator('#caAdminList article[data-ad-row-id="'+PAID_ID+'"]')

    def jump_to_paid_request(self):
        self.paid_card().locator('[data-package-request-id="'+REQUEST_ID+'"]').click()
        self.page.wait_for_function('id=>document.querySelectorAll("#caPayList article").length===1 && !!document.querySelector("#caPayList article[data-pay-row-id=\\\""+id+"\\\"]")',arg=REQUEST_ID)
        return self.page.locator('#caPayList article[data-pay-row-id="'+REQUEST_ID+'"]')

    def test_pending_vip_is_badged_at_top_and_only_free_listing_can_publish(self):
        self.as_admin()
        first=self.page.locator('#caAdminList article').first
        self.assertEqual(first.get_attribute('data-ad-row-id'),PAID_ID)
        badge=first.locator('.ca-package-badge[data-package-status="pending"]')
        self.assertTrue(badge.is_visible());self.assertIn('VIP',badge.inner_text());self.assertIn('gözləyir',badge.inner_text())
        self.assertTrue(first.locator('button[data-status="aktiv"]').is_disabled())
        free=self.page.locator('#caAdminList article[data-ad-row-id="'+FREE_ID+'"]')
        self.assertFalse(free.locator('button[data-status="aktiv"]').is_disabled())
        free.locator('button[data-status="aktiv"]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Dəyişiklik saxlanıldı")')
        calls=[call for call in self.backend.admin_calls if call['name']=='ca_admin_status']
        self.assertEqual([call['body'] for call in calls],[{'p_id':FREE_ID,'p_status':'aktiv'}])
        self.assertFalse(any(call['name']=='ca_admin_paket_tesdiq' for call in self.backend.admin_calls))
        self.assertTrue(self.paid_card().locator('button[data-status="aktiv"]').is_disabled())

    def test_package_jump_targets_exact_offpage_request_despite_same_car_names(self):
        self.as_admin()
        self.assertEqual(self.page.locator('#caPayList article').count(),24)
        self.assertEqual(self.page.locator('#caPayList [data-pay-row-id="'+REQUEST_ID+'"]').count(),0)
        self.page.locator('#caPayFilter').select_option('tesdiqlendi')
        self.page.wait_for_function('document.getElementById("caPayMsg").textContent.startsWith("50 sorğu")')
        target=self.jump_to_paid_request()
        self.assertIn('LADA 1200',target.inner_text())
        self.assertEqual(self.page.locator('#caPaySearch').input_value(),REQUEST_ID)
        self.assertEqual(self.page.locator('#caPayFilter').input_value(),'all')
        self.assertIn('LADA 1200',self.page.locator('#caPayLinkedNotice').inner_text())
        call=next(call for call in reversed(self.backend.admin_calls) if call['name']=='ca_admin_browse_payments')
        self.assertEqual(call['body'],{'p_status':'all','p_query':REQUEST_ID,'p_page':1,'p_page_size':24})

    def test_payment_confirmation_and_publication_require_separate_actions(self):
        self.as_admin();target=self.jump_to_paid_request()
        target.locator('button[data-pay-action="approve"]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Dəyişiklik saxlanıldı")')
        self.assertFalse(any(call['name']=='ca_admin_status' for call in self.backend.admin_calls))
        listing=next(row for row in self.backend.rows if row['id']==PAID_ID)
        self.assertEqual(listing['veziyyet'],'gozlemede')
        self.assertNotIn('LADA 1200',self.page.locator('#allGrid').inner_text())
        self.assertTrue(self.paid_card().locator('.ca-package-badge[data-package-status="confirmed"]').is_visible())
        self.assertFalse(self.paid_card().locator('button[data-status="aktiv"]').is_disabled())
        self.paid_card().locator('button[data-status="aktiv"]').click()
        self.page.wait_for_function('caBrowseState.total===3 && document.getElementById("caTodayApproved").textContent==="1"')
        self.assertEqual(listing['veziyyet'],'aktiv')
        self.assertIn('LADA 1200',self.page.locator('#vipGrid').inner_text())
        status=[call for call in self.backend.admin_calls if call['name']=='ca_admin_status']
        self.assertEqual([call['body'] for call in status],[{'p_id':PAID_ID,'p_status':'aktiv'}])

    def test_failed_payment_confirmation_keeps_listing_blocked_and_pending(self):
        self.as_admin();target=self.jump_to_paid_request();self.backend.fail_payment=True
        target.locator('button[data-pay-action="approve"]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Dəyişiklik saxlanmadı")')
        self.assertIn('Mock payment confirmation failed',self.page.locator('#caAdminActionMsg').inner_text())
        self.assertTrue(self.paid_card().locator('button[data-status="aktiv"]').is_disabled())
        self.assertEqual(next(row for row in self.backend.payments if row['id']==REQUEST_ID)['odenis_veziyyeti'],'gozlemede')
        self.assertEqual(next(row for row in self.backend.rows if row['id']==PAID_ID)['veziyyet'],'gozlemede')
        self.assertFalse(any(call['name']=='ca_admin_status' for call in self.backend.admin_calls))

    def test_vip_success_waits_for_confirmed_save_and_uses_site_feedback(self):
        self.new_listing(paid=True)
        note=self.page.locator('#listingPackageNote')
        self.assertTrue(note.is_visible());self.assertIn('Kartla ödəniş hələ aktiv deyil',note.inner_text())
        self.assertIn('məbləğ tutulmur',note.inner_text())
        self.backend.delay_save=True
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        for _ in range(200):
            if self.backend.pending_saves:break
            self.page.wait_for_timeout(10)
        self.assertEqual(len(self.backend.pending_saves),1)
        self.assertTrue(self.page.locator('#submitListingBtn').is_disabled())
        self.assertFalse(self.page.locator('#listingFeedback').is_visible())
        self.assertEqual(self.page.evaluate('__alerts'),[])
        route,data=self.backend.pending_saves.pop()
        with self.page.expect_response(lambda response:response.request.method=='POST' and urlsplit(response.url).path=='/rest/v1/elanlar') as response:
            route.fulfill(content_type='application/json',body=json.dumps(data))
        response.value.body()
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')
        message=self.feedback()
        self.assertIn('VIP paket müraciətiniz qəbul edildi',message)
        self.assertIn('admin təsdiqini gözləyir',message)
        self.assertNotIn('real ödəniş alınmayıb',message.lower());self.assertNotIn('127.0.0.1',message)
        self.assertEqual(len(self.backend.saves),1);self.assertEqual(len(self.backend.uploads),1)
        expected=self.page.evaluate('CA_URL')+self.backend.uploads[0].replace('/storage/v1/object/','/storage/v1/object/public/',1)
        self.assertEqual(self.backend.saves[0]['sekiller'],[expected])
        self.assertEqual(self.backend.saves[0]['ca_data']['photos'],{'front':[expected]})
        self.assertIn('15 AZN',self.backend.saves[0]['ca_data']['requestedPackage'])
        self.assertFalse(any(call['path'].endswith('/ca_paket_sorgusu_yarat') for call in self.backend.calls))
        self.assertFalse(self.page.evaluate('document.body.classList.contains("sell-open")'))

    def test_free_and_edit_success_use_site_feedback_without_native_alert(self):
        self.new_listing();self.submit()
        self.assertEqual(self.feedback(),'Elanınız qəbul edildi. Admin təsdiqindən sonra yayımlanacaq.')
        self.assertEqual(self.backend.saves[0]['ca_data']['requestedPackage'],'')
        self.page.locator('#listingFeedbackClose').click()
        self.page.evaluate('async()=>await caFetchMyListings()')
        self.page.evaluate('id=>editCar(id)',OWNED_ID)
        self.assertEqual(self.page.locator('#listingForm .photo-preview img').count(),9)
        self.page.locator('#listingForm [name="price"]').fill('44000')
        self.submit()
        self.assertEqual(self.feedback(),'Dəyişikliklər saxlanıldı. Elan yenidən admin təsdiqini gözləyir.')
        updates=[call for call in self.backend.calls if call['method']=='PATCH' and call['path']=='/rest/v1/elanlar']
        self.assertEqual(len(updates),1)
        self.assertEqual(updates[0]['body']['ca_data']['photos'],GROUPS)
        self.assertCountEqual(updates[0]['body']['sekiller'],[url for group in GROUPS.values() for url in group])

    def test_upload_or_save_failures_show_error_and_preserve_same_form_and_photos(self):
        for failure in ('storage','save','unconfirmed'):
            with self.subTest(failure=failure):
                self.page.evaluate('caDismissListingFeedback();caClearListingDraft()')
                self.new_listing(paid=True)
                self.page.locator('#sellerDescription').fill('Retry this exact draft and preserve selected synthetic photo')
                self.page.locator('#listingForm input[name="equipment"]').first.check()
                before=self.page.evaluate('''()=>({photos:Array.from(document.querySelectorAll('#listingForm .photo-preview img'),image=>image.src),
                    file:Array.from(document.getElementById('photos-front').files,file=>({name:file.name,size:file.size,type:file.type})),
                    equipment:Array.from(document.querySelectorAll('#listingForm input[name="equipment"]:checked'),input=>input.value)})''')
                saves_before=len(self.backend.saves)
                self.backend.fail_storage=failure=='storage';self.backend.fail_save=failure=='save';self.backend.zero_save=failure=='unconfirmed'
                self.submit()
                message=self.feedback(success=False)
                self.assertIn('mümkün olmadı',message)
                self.assertNotIn('qəbul edildi',message)
                self.assertTrue(self.page.evaluate('document.body.classList.contains("sell-open")'))
                self.page.locator('#listingFeedbackClose').click()
                self.assertTrue(self.page.locator('#listingForm').is_visible())
                self.assertEqual(self.page.locator('#listingForm [name="price"]').input_value(),'42000')
                self.assertEqual(self.page.locator('#sellerDescription').input_value(),'Retry this exact draft and preserve selected synthetic photo')
                after=self.page.evaluate('''()=>({photos:Array.from(document.querySelectorAll('#listingForm .photo-preview img'),image=>image.src),
                    file:Array.from(document.getElementById('photos-front').files,file=>({name:file.name,size:file.size,type:file.type})),
                    equipment:Array.from(document.querySelectorAll('#listingForm input[name="equipment"]:checked'),input=>input.value)})''')
                self.assertEqual(after,before)
                self.assertEqual(len(self.backend.saves)-saves_before,0 if failure=='storage' else 1)
                self.assertFalse(any(row['id']==NEW_ID for row in self.backend.rows))

    def test_mobile_package_note_and_site_feedback_fit_the_viewport(self):
        self.page.set_viewport_size({'width':375,'height':760})
        self.new_listing(paid=True)
        self.assertTrue(self.page.locator('#listingPackageNote').is_visible())
        self.submit();self.feedback()
        self.assertTrue(self.page.locator('#listingFeedbackClose').is_visible())
        box=self.page.locator('#listingFeedback .auth-box').bounding_box()
        self.assertLessEqual(box['width'],375)
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),375)

    def test_confirmed_save_with_refresh_failure_is_saved_warning_without_duplicate_insert(self):
        self.new_listing(paid=True);self.backend.fail_public=True
        self.submit()
        message=self.feedback()
        self.assertEqual(self.page.locator('#listingFeedback').get_attribute('data-kind'),'warning')
        self.assertIn('müraciətiniz qəbul edildi',message)
        self.assertIn('Siyahı tam yenilənmədi',message)
        self.assertNotIn('göndərmək mümkün olmadı',message)
        self.assertNotIn('Elan göndərilmədi',self.page.locator('#listingFeedbackTitle').inner_text())
        self.assertEqual(len(self.backend.saves),1);self.assertEqual(len(self.backend.uploads),1)
        self.assertEqual(sum(row['id']==NEW_ID for row in self.backend.rows),1)
        self.page.locator('#listingFeedbackClose').click()
        self.assertFalse(self.page.evaluate('document.body.classList.contains("sell-open")'))
        self.backend.fail_public=False
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.assertEqual(len(self.backend.saves),1,'Refreshing the view must not repeat a confirmed insert')

    def test_success_feedback_closes_on_logout_or_account_switch_and_stays_closed(self):
        for action in ('logout','switch'):
            with self.subTest(action=action):
                self.page.evaluate('window.__alerts=[]')
                if action=='logout':
                    self.new_listing();self.submit()
                else:
                    self.sign_in();self.page.evaluate('async()=>await caFetchMyListings()')
                    self.page.evaluate('id=>editCar(id)',OWNED_ID)
                    self.page.locator('#listingForm [name="price"]').fill('45000');self.submit()
                self.feedback()
                if action=='logout':
                    self.page.evaluate('async()=>await logout()')
                else:
                    self.page.evaluate('''async id=>await caPersistSession({access_token:'other-seller-token',expires_at:4102444800,
                        user:{id,email:'other@example.invalid',user_metadata:{telefon:'+994000000001'}}})''',OTHER_OWNER)
                self.assertFalse(self.page.locator('#listingFeedback').is_visible())
                self.assertEqual(self.page.locator('#listingFeedback').get_attribute('aria-hidden'),'true')
                self.page.evaluate('render();updateAccountUI()')
                self.assertFalse(self.page.locator('#listingFeedback').is_visible())
                self.assertEqual(self.page.evaluate('__alerts'),['Hesabdan çıxış edildi.'] if action=='logout' else [])

    def test_expired_session_closes_success_feedback_before_another_account_logs_in(self):
        self.new_listing(paid=True);self.submit();self.feedback()
        self.page.route('**/auth/v1/token*',lambda route:route.fulfill(status=401,
            content_type='application/json',body='{"message":"Mock expired refresh token"}'))
        refreshed=self.page.evaluate('async()=>{caSession.refresh_token="expired-fixture";return await caRefresh()}')
        self.assertFalse(refreshed)
        self.assertIsNone(self.page.evaluate('currentUser'))
        self.assertIsNone(self.page.evaluate('caSession'))
        self.assertFalse(self.page.locator('#listingFeedback').is_visible())
        self.assertEqual(self.page.locator('#listingFeedback').get_attribute('aria-hidden'),'true')
        self.page.evaluate('''async id=>await caPersistSession({access_token:'second-account-token',expires_at:4102444800,
            user:{id,email:'second@example.invalid',user_metadata:{telefon:'+994000000001'}}})''',OTHER_OWNER)
        self.page.evaluate('openSellPage();render();updateAccountUI()')
        self.assertEqual(self.page.evaluate('currentUser.id'),OTHER_OWNER)
        self.assertFalse(self.page.locator('#listingFeedback').is_visible())
        self.assertFalse(self.page.locator('#listingFeedbackText').is_visible())
        self.assertEqual(len(self.backend.saves),1)
        self.assertFalse(any(call['method']=='PUT' for call in self.backend.auth_calls))


if __name__=='__main__':unittest.main(verbosity=2)
