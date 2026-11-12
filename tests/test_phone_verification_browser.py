"""Phone verification UI with synthetic Auth responses; never sends real SMS."""
import copy,json,os,unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN,OWNER,OTHER_OWNER
OLD='+994501234567';NEW='+994701234567'
class PhoneBackend(AdminAuthBackend):
 def __init__(self):
  super().__init__();self.provider=False;self.phone_calls=[];self.profile_calls=[];self.proof=True;self.fail_send=False;self.hold_get=False;self.held=[]
  self.user={'id':OWNER,'email':'phone@example.invalid','phone':None,'phone_confirmed_at':None,'user_metadata':{'telefon':OLD,'phone_verified':True}}
 def route(self,route):
  req=route.request;p=urlsplit(req.url);path=p.path;body=req.post_data_json if req.post_data else None
  if path=='/auth/v1/settings':route.fulfill(content_type='application/json',body=json.dumps({'external':{'phone':self.provider,'email':True}}));return
  if path in ('/auth/v1/user','/auth/v1/verify'):
   self.phone_calls.append({'path':path,'method':req.method,'body':body,'authorization':req.headers.get('authorization')})
   if req.headers.get('authorization')!='Bearer phone-token':route.fulfill(status=401,content_type='application/json',body='{"message":"Wrong account"}');return
   if path.endswith('/user') and req.method=='GET':
    if self.hold_get:self.held.append(route);return
    route.fulfill(content_type='application/json',body=json.dumps(self.user));return
   if path.endswith('/user') and req.method=='PUT':
    if body.get('phone'):
     if self.fail_send:route.fulfill(status=429,headers={'retry-after':'120'},content_type='application/json',body='{"message":"Too many SMS"}');return
     self.pending=body['phone']
    if 'data' in body:self.user['user_metadata'].update(body['data'])
    route.fulfill(content_type='application/json',body=json.dumps(self.user));return
   if path.endswith('/verify') and req.method=='POST':
    if body.get('token')!='123456':route.fulfill(status=400,content_type='application/json',body='{"message":"Invalid verification code"}');return
    if self.proof:self.user.update(phone=self.pending,phone_confirmed_at='2026-11-12T12:00:00Z')
    route.fulfill(content_type='application/json',body=json.dumps({'user':self.user,'access_token':'ignored-verify-token','refresh_token':'ignored-verify-refresh'}));return
  if path=='/rest/v1/profiller' and req.method=='POST':self.profile_calls.append(body);route.fulfill(status=204,body='');return
  super().route(route)
class PhoneVerificationBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.context=self.browser.new_context(viewport={'width':375,'height':812});self.page=self.context.new_page();self.page.set_default_timeout(6000);self.errors=[]
  self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true');self.backend=PhoneBackend();self.page.route('**/*',self.backend.route)
  self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')
 def tearDown(self):
  for route in self.backend.held:
   try:route.abort()
   except Exception:pass
  self.page.wait_for_timeout(20)
  self.context.close();self.assertFalse(self.errors)
 def login(self):
  self.page.evaluate('''({id,phone})=>{currentUser={id,email:'phone@example.invalid',phone};caSession={access_token:'phone-token',expires_at:4102444800,user:{id,email:'phone@example.invalid',user_metadata:{telefon:phone}}};updateAccountUI()}''',{'id':OWNER,'phone':OLD})
 def open(self):
  self.login();self.page.evaluate('openCabinet()');self.page.wait_for_function("!document.getElementById('caPhoneVerificationStatus').textContent.includes('yoxlanılır')&&document.getElementById('caPhoneVerificationStatus').textContent.length>0")
 def send(self):
  self.page.locator('#caPhoneNumber').fill('0701234567');self.page.locator('#caPhoneSend').click();self.page.wait_for_function("!document.getElementById('caPhoneOtpForm').hidden")
 def test_provider_disabled_never_claims_sms_sent_or_sends_request(self):
  self.open();self.assertIn('hazırda aktiv deyil',self.page.locator('#caPhoneVerificationStatus').inner_text());self.assertTrue(self.page.locator('#caPhoneForm').is_hidden())
  self.page.evaluate("document.getElementById('caPhoneNumber').value='0701234567';document.getElementById('caPhoneForm').dispatchEvent(new Event('submit',{cancelable:true}))")
  self.assertFalse([c for c in self.backend.phone_calls if c['method']!='GET'])
 def test_sms_verified_only_by_trusted_server_proof_and_existing_session_is_preserved(self):
  self.backend.provider=True;self.open();self.page.evaluate("localStorage.setItem(caFavoriteStorageKey(),'[\"owned-favorite\"]')");self.send()
  self.assertTrue(self.page.locator('#caPhoneResend').is_disabled());self.assertTrue(self.page.locator('#caPhoneSend').is_disabled())
  call=[c for c in self.backend.phone_calls if c['method']=='PUT'][0];self.assertEqual(call['body'],{'phone':NEW})
  self.page.locator('#caPhoneOtp').fill('123456');self.page.locator('#caPhoneVerify').click();self.page.wait_for_function("document.getElementById('caPhoneVerificationStatus').textContent.includes('SMS ilə təsdiqləndi')")
  self.assertEqual(self.page.evaluate('currentUser.phone'),NEW);self.assertEqual(self.page.evaluate('caSession.access_token'),'phone-token')
  self.assertEqual(self.backend.profile_calls[-1]['telefon'],NEW);self.assertIn('owned-favorite',self.page.evaluate('localStorage.getItem(caFavoriteStorageKey())'))
  self.assertEqual([c['body'] for c in self.backend.phone_calls if c['path'].endswith('/verify')],[{'phone':NEW,'token':'123456','type':'phone_change'}])
 def test_editable_metadata_is_not_a_verified_phone_badge(self):
  self.backend.provider=True;self.backend.user['user_metadata'].update(phone_confirmed_at='2026-11-12T12:00:00Z',verified=True);self.open()
  self.assertNotIn('SMS ilə təsdiqlənib',self.page.locator('#caPhoneVerificationStatus').inner_text());self.assertTrue(self.page.locator('#caPhoneForm').is_visible())
 def test_wrong_code_or_missing_server_confirmation_cannot_verify_phone(self):
  self.backend.provider=True;self.open();self.send();self.page.locator('#caPhoneOtp').fill('111111');self.page.locator('#caPhoneVerify').click()
  self.page.wait_for_function("document.getElementById('caPhoneVerificationStatus').getAttribute('role')==='alert'");self.assertEqual(self.page.evaluate('currentUser.phone'),OLD)
  self.backend.proof=False;self.page.locator('#caPhoneOtp').fill('123456');self.page.locator('#caPhoneVerify').click();self.page.wait_for_function("document.getElementById('caPhoneVerificationStatus').textContent.includes('serverdə tamamlanmayıb')")
  self.assertEqual(self.page.evaluate('currentUser.phone'),OLD);self.assertFalse(self.backend.profile_calls)
 def test_invalid_number_and_server_rate_limit_show_real_failure_and_cooldown(self):
  self.backend.provider=True;self.open();self.page.locator('#caPhoneNumber').fill('123');self.page.locator('#caPhoneSend').click();self.assertFalse([c for c in self.backend.phone_calls if c['method']=='PUT'])
  self.backend.fail_send=True;self.page.locator('#caPhoneNumber').fill('0701234567');self.page.locator('#caPhoneSend').click();self.page.wait_for_function("document.getElementById('caPhoneVerificationStatus').textContent.includes('Çox tez')")
  self.assertTrue(self.page.locator('#caPhoneSend').is_disabled());self.assertTrue(self.page.locator('#caPhoneOtpForm').is_hidden())
 def test_account_switch_discards_pending_trusted_read_and_clears_phone(self):
  self.backend.provider=True;self.backend.hold_get=True;self.login();self.page.evaluate('openCabinet()')
  for _ in range(100):
   if self.backend.held:break
   self.page.wait_for_timeout(15)
  self.assertTrue(self.backend.held);self.page.evaluate('currentUser=null;caSession=null;updateAccountUI()');self.page.wait_for_timeout(70)
  self.assertTrue(self.page.locator('#caPhoneVerification').is_hidden());self.assertEqual(self.page.locator('#caPhoneNumber').input_value(),'')
  self.assertFalse([c for c in self.backend.phone_calls if c['method']!='GET'])
