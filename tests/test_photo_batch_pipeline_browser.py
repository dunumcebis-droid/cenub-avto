"""Batch scheduling and cache behavior; every model/storage/DB request is mocked."""
import json,os,unittest
from playwright.sync_api import sync_playwright
import test_photo_review_browser as photos
import test_package_feedback_browser as fields
from test_listing_management_browser import ORIGIN,OWNER

class PhotoBatchPipelineBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.context=self.browser.new_context(viewport={'width':375,'height':812});self.page=self.context.new_page();self.page.set_default_timeout(6000);self.errors=[]
  self.backend=photos.PhotoReviewBackend();self.backend.batch_supported=True
  self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true');self.page.route('**/*',self.backend.route)
  self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded');fields.PackageFeedbackBrowserTests.sign_in(self);self.page.evaluate('openSellPage()')
 def tearDown(self):
  for route,_ in self.backend.pending_reviews:
   try:route.abort()
   except Exception:pass
  self.context.close();self.assertFalse(self.errors)
 def select_photos(self,count=12):
  self.page.evaluate('''async count=>{
   window.__decodeCount=0;const decode=window.createImageBitmap;window.createImageBitmap=(...args)=>{window.__decodeCount++;return decode(...args)};
   window.__batchFiles=[];
   for(let i=0;i<count;i++){const canvas=document.createElement('canvas');canvas.width=32;canvas.height=24;const ctx=canvas.getContext('2d');ctx.fillStyle=`rgb(${(i*19)%255},${(i*37)%255},${(i*53)%255})`;ctx.fillRect(0,0,32,24);const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));window.__batchFiles.push(new File([blob],`fixture-${i}.png`,{type:'image/png',lastModified:i+1}));}
   for(const [n,input] of [...document.querySelectorAll('.photo-input')].entries()){const data=new DataTransfer();for(const file of window.__batchFiles.slice(n*6,n*6+6))data.items.add(file);input.files=data.files;input.dispatchEvent(new Event('change',{bubbles:true}));}
  }''',count)
  self.page.locator('#caPhotoPrecheck').wait_for(state='visible')
 def run_check(self):
  self.page.locator('#caPhotoPrecheck').click();self.page.wait_for_function('document.getElementById("listingForm").getAttribute("aria-busy")!=="true"')
 def held(self,n):
  for _ in range(200):
   if len(self.backend.pending_reviews)>=n:return
   self.page.wait_for_timeout(15)
  self.fail(f'Only {len(self.backend.pending_reviews)} concurrent batches started, expected {n}')
 def release(self):
  route,data=self.backend.pending_reviews.pop(0);route.fulfill(content_type='application/json',body=json.dumps(data))
 def test_twelve_photos_use_two_parallel_requests_instead_of_twelve_roundtrips(self):
  self.select_photos();self.backend.hold_review=True;self.page.locator('#caPhotoPrecheck').click();self.held(2)
  self.assertEqual([len(c['categories']) for c in self.backend.batch_calls],[6,6]);self.assertEqual(len(self.backend.status_calls),1);self.assertTrue(self.page.locator('#submitListingBtn').is_disabled())
  self.release();self.release();self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled');self.assertIn('yoxlamadan keçdi',self.page.locator('#caPhotoPrecheckResult').inner_text())
  self.assertEqual(self.page.evaluate('window.__decodeCount'),12);self.assertFalse(self.backend.uploads);self.assertFalse(self.backend.saves)
 def test_partial_failure_keeps_other_approvals_and_retry_sends_only_rejected_photo(self):
  self.select_photos(6);self.backend.batch_errors={1:'screenshot'};self.run_check();self.assertIn('Ekran',self.page.locator('#listingFeedbackText').inner_text())
  self.assertEqual(self.page.evaluate('window.__batchFiles.filter(f=>caPhotoUploadCache.has(f)).length'),5);self.page.locator('#listingFeedbackClose').click();self.backend.batch_errors={};self.run_check()
  self.assertEqual([len(c['categories']) for c in self.backend.batch_calls],[6,1]);self.assertEqual(self.page.evaluate('window.__decodeCount'),6);self.assertIn('yoxlamadan keçdi',self.page.locator('#caPhotoPrecheckResult').inner_text())
 def test_provider_failure_reuses_prepared_blobs_without_redecoding_or_bypass(self):
  self.select_photos(6);self.backend.error_code='provider_unavailable';self.backend.error_status=503;self.run_check();self.assertFalse(self.backend.saves);self.assertFalse(self.backend.uploads)
  self.assertEqual(self.page.evaluate('window.__decodeCount'),6);self.page.locator('#listingFeedbackClose').click();self.backend.error_code=None;self.run_check();self.assertEqual(self.page.evaluate('window.__decodeCount'),6)
  self.assertEqual([len(c['categories']) for c in self.backend.batch_calls],[6,6]);self.assertIn('yoxlamadan keçdi',self.page.locator('#caPhotoPrecheckResult').inner_text())
 def test_identical_reselected_bytes_reuse_approval_but_changed_category_requires_review(self):
  self.select_photos(1);self.run_check();self.page.evaluate('''()=>{const f=window.__batchFiles[0];const data=new DataTransfer();data.items.add(new File([f],'new-name.png',{type:f.type,lastModified:999}));const input=document.getElementById('photos-front');input.files=data.files;input.dispatchEvent(new Event('change',{bubbles:true}));}''');self.run_check()
  self.assertEqual(len(self.backend.batch_calls),1,'An identical reselected picture must not call the model again')
  self.page.evaluate('''()=>{const input=document.getElementById('photos-front'),data=new DataTransfer();data.items.add(input.files[0]);input.value='';const rear=document.getElementById('photos-rear');rear.files=data.files;rear.dispatchEvent(new Event('change',{bubbles:true}));}''');self.run_check();self.assertEqual(len(self.backend.batch_calls),2);self.assertEqual(self.backend.batch_calls[-1]['categories'],['rear'])
