"""Retry/frozen-form regressions; all uploads and listing writes are mocked."""
import copy,json,os,unittest
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright
import test_package_feedback_browser as feedback_tests
from test_package_feedback_browser import PackageFeedbackBackend
from test_listing_management_browser import ORIGIN,OWNER,OTHER_OWNER
class RetryBackend(PackageFeedbackBackend):
 def __init__(self):
  super().__init__();self.created=[];self.attempts=[];self.package_creates=[];self.abort_response=False;self.fail_lookup=False;self.fail_commit=False;self.hold=False;self.held=[]
 def route(self,route):
  req=route.request;p=urlsplit(req.url);query=parse_qs(p.query)
  if p.path=='/rest/v1/elanlar' and req.method=='GET' and 'ca_data->>_submission_id' in query:
   if self.fail_lookup and self.created:route.fulfill(status=503,content_type='application/json',body='{"message":"Lookup unavailable"}');return
   key=query['ca_data->>_submission_id'][0][3:];owner=query['satici_id'][0][3:]
   rows=[row for row in self.rows if row['satici_id']==owner and row.get('ca_data',{}).get('_submission_id')==key]
   route.fulfill(content_type='application/json',body=json.dumps(rows));return
  if p.path=='/rest/v1/elanlar' and req.method=='POST':
   body=req.post_data_json;self.attempts.append(copy.deepcopy(body));self.saves.append(copy.deepcopy(body))
   if self.fail_commit:route.fulfill(status=503,content_type='application/json',body='{"message":"Save unavailable"}');return
   key=body['ca_data']['_submission_id'];existing=[r for r in self.rows if r['satici_id']==body['satici_id'] and r.get('ca_data',{}).get('_submission_id')==key]
   if existing:route.fulfill(status=409,content_type='application/json',body='{"message":"Unique submission"}');return
   row=dict(body,id=f'67676767-6767-4767-8767-{len(self.created)+1:012d}',yaradildi='2026-11-12T12:00:00Z',paket_adi='Pulsuz');self.rows.append(row);self.created.append(row)
   if body['ca_data'].get('requestedPackage'):self.package_creates.append(row['id'])
   if self.hold:self.held.append((route,row));return
   if self.abort_response:route.abort('connectionreset');return
   route.fulfill(content_type='application/json',body=json.dumps([{'id':row['id']}]));return
  super().route(route)
class SubmissionRetryBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.context=self.browser.new_context(viewport={'width':375,'height':812});self.page=self.context.new_page();self.page.set_default_timeout(6000);self.errors=[];self.backend=RetryBackend()
  self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true');self.page.route('**/*',self.backend.route)
  self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')
 def tearDown(self):
  for route,row in self.backend.held:
   try:route.abort()
   except Exception:pass
  self.page.wait_for_timeout(20);self.context.close();self.assertFalse(self.errors)
 def sign_in(self,admin=False):feedback_tests.PackageFeedbackBrowserTests.sign_in(self,admin)
 def new_listing(self,paid=False):feedback_tests.PackageFeedbackBrowserTests.new_listing(self,paid)
 def submit(self):self.page.locator('#submitListingBtn').click()
 def feedback(self):self.page.locator('#listingFeedback').wait_for(state='visible')
 def dismiss(self):self.page.locator('#listingFeedback').get_by_role('button',name='Bağla',exact=False).click()
 def wait_held(self):
  for _ in range(100):
   if self.backend.held:return
   self.page.wait_for_timeout(20)
  self.fail('Synthetic delayed POST did not start')
 def test_server_commit_with_lost_response_is_reconciled_without_duplicate_ad_or_package(self):
  self.backend.abort_response=True;self.new_listing(paid=True);self.submit();self.feedback()
  self.assertEqual(len(self.backend.created),1);self.assertEqual(len(self.backend.attempts),1);self.assertEqual(len(self.backend.uploads),1);self.assertEqual(len(self.backend.package_creates),1)
  self.assertIn('qəbul edildi',self.page.locator('#listingFeedback').inner_text());self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(),'')
 def test_uncertain_failed_lookup_retry_reuses_submission_and_uploaded_photos(self):
  self.backend.abort_response=True;self.backend.fail_lookup=True;self.new_listing(paid=True);self.submit();self.feedback();self.assertIn('mümkün olmadı',self.page.locator('#listingFeedback').inner_text())
  self.dismiss();self.backend.fail_lookup=False;self.submit();self.feedback()
  self.assertEqual(len(self.backend.created),1);self.assertEqual(len(self.backend.attempts),1);self.assertEqual(len(self.backend.uploads),1);self.assertEqual(len(self.backend.package_creates),1)
  self.assertIn('qəbul edildi',self.page.locator('#listingFeedback').inner_text())
 def test_pending_save_disables_fields_then_restores_new_draft_controls(self):
  self.backend.hold=True;self.new_listing();self.submit();self.wait_held()
  self.assertTrue(self.page.locator('#listingForm [name=price]').is_disabled());self.assertTrue(self.page.locator('#photos-front').is_disabled());self.assertTrue(self.page.locator('#listingForm [name=description]').is_disabled())
  self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(),'42000');route,row=self.backend.held.pop();route.fulfill(content_type='application/json',body=json.dumps([{'id':row['id']}]))
  self.feedback();self.dismiss();self.page.evaluate('openSellPage()');self.assertTrue(self.page.locator('#listingForm [name=price]').is_enabled());self.assertTrue(self.page.locator('#photos-front').is_enabled())
 def test_new_changes_after_uncertain_commit_are_retained_and_resume_as_edit(self):
  self.backend.abort_response=True;self.backend.fail_lookup=True;self.new_listing(paid=True);self.submit();self.feedback();self.dismiss();self.page.locator('#listingForm [name=price]').fill('45000')
  self.backend.fail_lookup=False;self.submit();self.feedback();self.assertIn('Yeni dəyişikliklərin formadadır',self.page.locator('#listingFeedback').inner_text())
  self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(),'45000');self.assertEqual(self.page.evaluate('editingCarId'),self.backend.created[0]['id']);self.assertEqual(len(self.backend.created),1)
  self.dismiss();self.backend.abort_response=False;self.submit();self.feedback();self.assertEqual(next(row for row in self.backend.rows if row['id']==self.backend.created[0]['id'])['qiymet'],45000);self.assertEqual(len(self.backend.uploads),1);self.assertEqual(len(self.backend.package_creates),1)
 def test_rejected_first_insert_keeps_same_intent_on_retry_and_saves_once(self):
  self.backend.fail_commit=True;self.new_listing();self.submit();self.feedback();self.dismiss();self.backend.fail_commit=False;self.submit();self.feedback()
  self.assertEqual(len(self.backend.created),1);self.assertEqual(len(self.backend.uploads),1);self.assertEqual(self.backend.attempts[0]['ca_data']['_submission_id'],self.backend.attempts[1]['ca_data']['_submission_id'])
 def test_old_account_completion_cannot_unlock_or_clear_new_account_form(self):
  self.backend.hold=True;self.new_listing();self.submit();self.wait_held()
  self.page.evaluate('''async id=>{await caPersistSession({access_token:'second-token',expires_at:4102444800,user:{id,email:'second@example.invalid',user_metadata:{telefon:'+994000000002'}}});openSellPage();document.querySelector('#listingForm [name=price]').value='55555'}''',OTHER_OWNER)
  route,row=self.backend.held.pop();route.fulfill(content_type='application/json',body=json.dumps([{'id':row['id']}]))
  self.page.wait_for_timeout(100);self.assertEqual(self.page.evaluate('currentUser.id'),OTHER_OWNER);self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(),'55555');self.assertTrue(self.page.locator('#listingForm [name=price]').is_enabled());self.assertTrue(self.page.locator('#listingFeedback').is_hidden())

 def test_discarded_same_account_completion_cannot_reset_new_draft_or_navigation(self):
  self.backend.hold=True;self.new_listing();self.submit();self.wait_held()
  self.page.evaluate("caClearListingDraft();openSellPage();document.querySelector('#listingForm [name=price]').value='55555'")
  before=len(self.backend.calls);route,row=self.backend.held.pop();route.fulfill(content_type='application/json',body=json.dumps([{'id':row['id']}]))
  self.page.wait_for_timeout(100);self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(),'55555');self.assertTrue(self.page.locator('#listingForm [name=price]').is_enabled());self.assertTrue(self.page.locator('#listingFeedback').is_hidden())
  self.assertEqual(len(self.backend.calls),before,'Discarded form completion must not launch refreshes over the new navigation')
