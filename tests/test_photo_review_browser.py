"""Provider-controlled photo review paths. Every HTTP request uses fixtures.
No real images, emails, model requests, database rows or uploads are sent.
"""
import json
import os
import unittest
from email import policy
from email.parser import BytesParser
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import test_package_feedback_browser as fixtures
from test_listing_management_browser import ORIGIN, ROOT, OWNER, OTHER_OWNER, owned_row


class PhotoReviewBackend(fixtures.PackageFeedbackBackend):
    def __init__(self):
        super().__init__()
        self.enabled = True
        self.configured = True
        self.status_calls = []
        self.reviews = []
        self.error_code = None
        self.error_status = 422
        self.bad_status = False
        self.abort_status = False
        self.bad_url = False
        self.bad_category = False
        self.hold_review = False
        self.pending_reviews = []
        self.batch_supported = False
        self.batch_max = 6
        self.batch_calls = []
        self.batch_errors = {}
        self.batch_reverse = False
        self.batch_bad_kind = None
        self.bad_batch_cap = False

    def approved(self, req, category):
        owner = OTHER_OWNER if req.headers.get('authorization') == 'Bearer second-token' else OWNER
        identifier = f'91919191-9191-4919-8919-{len(self.reviews):012d}'
        host = urlsplit(req.url)
        url = (f'{host.scheme}://{host.netloc}/storage/v1/object/public/elan-sekilleri/'
               f'{owner}/checked/{identifier}-ca-wm1.jpg')
        return dict(url='https://untrusted.invalid/photo.jpg' if self.bad_url else url,
                    review_id=identifier,
                    category='rear' if self.bad_category else category)

    def route(self, route):
        req = route.request
        path = urlsplit(req.url).path
        if path == '/functions/v1/ca-photo-review/status':
            self.status_calls.append(dict(headers=dict(req.headers)))
            if self.abort_status:
                route.abort('connectionreset')
                return
            value = dict(enabled='yes', configured=True) if self.bad_status else dict(enabled=self.enabled, configured=self.configured)
            if self.batch_supported or self.bad_batch_cap:
                value.update(batch_supported='yes' if self.bad_batch_cap else True, batch_max=self.batch_max)
            route.fulfill(content_type='application/json', body=json.dumps(value))
            return
        if path == '/functions/v1/ca-photo-review/batch':
            assert req.method == 'POST'
            assert req.headers.get('authorization') in ('Bearer seller-token', 'Bearer second-token')
            message = BytesParser(policy=policy.default).parsebytes(
                ('Content-Type: '+req.headers['content-type']+'\r\n\r\n').encode()+req.post_data_buffer)
            parts = {part.get_param('name', header='content-disposition'): part for part in message.iter_parts()}
            categories = json.loads(parts['categories'].get_content())
            assert 1 <= len(categories) <= 6
            assert set(parts) == {'categories', *(f'file_{i}' for i in range(len(categories)))}
            self.batch_calls.append(dict(categories=categories, headers=dict(req.headers)))
            for i in range(len(categories)):
                part = parts[f'file_{i}']
                assert part.get_filename() == 'photo.jpg'
                assert part.get_content_type() == 'image/jpeg'
                assert part.get_payload(decode=True).startswith(b'\xff\xd8')
            if self.error_code:
                route.fulfill(status=self.error_status, content_type='application/json',
                              body=json.dumps(dict(code=self.error_code, message='Synthetic batch rejection')))
                return
            results = []
            for i, category in enumerate(categories):
                self.reviews.append(dict(category=category, batch=True))
                if i in self.batch_errors:
                    results.append(dict(index=i, ok=False, category=category, code=self.batch_errors[i]))
                else:
                    results.append(dict(index=i, ok=True, **self.approved(req, category)))
            if self.batch_bad_kind == 'duplicate_index':
                results[1]['index'] = results[0]['index']
            elif self.batch_bad_kind == 'missing_result':
                results.pop()
            elif self.batch_bad_kind == 'wrong_category':
                results[0]['category'] = 'rear'
            elif self.batch_bad_kind == 'untrusted_url':
                results[-1]['url'] = 'https://untrusted.invalid/other-owner.jpg'
            elif self.batch_bad_kind == 'failed_url':
                results[1] = dict(index=1, ok=False, category=categories[1], code='screenshot', url=results[0]['url'])
            elif self.batch_bad_kind == 'bad_ok':
                results[0]['ok'] = 'true'
            if self.batch_reverse:
                results.reverse()
            body = dict(results=results)
            if self.hold_review:
                self.pending_reviews.append((route, body))
                return
            route.fulfill(content_type='application/json', body=json.dumps(body))
            return
        if path == '/functions/v1/ca-photo-review':
            assert req.method == 'POST'
            assert req.headers.get('authorization') in ('Bearer seller-token', 'Bearer second-token')
            message = BytesParser(policy=policy.default).parsebytes(
                ('Content-Type: '+req.headers['content-type']+'\r\n\r\n').encode()+req.post_data_buffer)
            parts = {part.get_param('name', header='content-disposition'): part for part in message.iter_parts()}
            assert set(parts) == {'category', 'file'}
            assert parts['file'].get_filename() == 'photo.jpg'
            assert parts['file'].get_content_type() == 'image/jpeg'
            assert parts['file'].get_payload(decode=True).startswith(b'\xff\xd8')
            category = parts['category'].get_content().strip()
            self.reviews.append(dict(category=category, bytes=len(parts['file'].get_payload(decode=True))))
            if self.hold_review:
                self.pending_reviews.append((route, self.approved(req, category)))
                return
            if self.error_code:
                route.fulfill(status=self.error_status, content_type='application/json',
                              body=json.dumps(dict(code=self.error_code, message='Synthetic review rejection')))
                return
            route.fulfill(content_type='application/json', body=json.dumps(self.approved(req, category)))
            return
        super().route(route)


class PhotoReviewBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={'width': 375, 'height': 812})
        self.page = self.context.new_page()
        self.page.set_default_timeout(6000)
        self.backend = PhotoReviewBackend()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')
        if not self.page.evaluate('typeof caReviewPreparedPhoto==="function"'):
            self.page.add_script_tag(path=str(ROOT/'assets/js/18-photo-review.js'))

    def tearDown(self):
        for route, _ in self.backend.pending_reviews:
            try:
                route.abort()
            except Exception:
                pass
        self.page.wait_for_timeout(20)
        self.context.close()
        self.assertFalse(self.errors)

    def sign_in(self, admin=False):
        fixtures.PackageFeedbackBrowserTests.sign_in(self, admin)

    def new_listing(self):
        fixtures.PackageFeedbackBrowserTests.new_listing(self)

    def submit(self):
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.locator('#listingFeedback').wait_for(state='visible')

    def dismiss(self):
        self.page.locator('#listingFeedbackClose').click()

    def test_disabled_mode_is_explicit_manual_moderation_without_fake_semantic_approval(self):
        self.backend.enabled = False
        self.backend.configured = False
        self.new_listing()
        self.page.wait_for_function('document.getElementById("caPhotoReviewNote").dataset.reviewMode==="manual"')
        self.assertIn('admin tərəfindən yoxlanacaq', self.page.locator('#caPhotoReviewNote').inner_text())
        self.assertNotIn('avtomatik yoxlanacaq', self.page.locator('#caPhotoReviewNote').inner_text())
        self.assertEqual(self.page.locator('.ca-photo-review-guide').count(), 6)
        self.assertIn('faralar', self.page.locator('#caPhotoGuide-front').inner_text())
        self.assertIn('arxa işıqlar', self.page.locator('#caPhotoGuide-rear').inner_text())
        self.submit()
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertEqual(len(self.backend.saves), 1)
        self.assertFalse(self.backend.reviews)
        self.assertEqual(self.page.locator('#caPhotoReview-front').inner_text(), '')

    def test_accepted_photo_uses_verified_server_url_instead_of_direct_storage_upload(self):
        self.new_listing()
        self.submit()
        self.assertIn('qəbul edildi', self.page.locator('#listingFeedbackText').inner_text())
        self.assertEqual(len(self.backend.reviews), 1)
        self.assertFalse(self.backend.uploads)
        self.assertEqual(len(self.backend.saves), 1)
        saved = self.backend.saves[0]
        self.assertIn(f'/{OWNER}/checked/', saved['sekiller'][0])
        self.assertEqual(saved['sekiller'], saved['ca_data']['photos']['front'])
        self.assertEqual(self.backend.reviews[0]['category'], 'front')
        self.assertEqual(len(self.backend.status_calls), 1)

    def test_wrong_view_screenshot_nonvehicle_and_uncertain_are_blocked_with_form_retained(self):
        self.new_listing()
        for code, text in (('category_mismatch', 'bu bölməyə uyğun deyil'),
                           ('screenshot', 'Ekran görüntüsü'),
                           ('not_vehicle', 'avtomobil və ya ona aid hissə görünmür'),
                           ('uncertain', 'uyğunluğu aydın deyil')):
            with self.subTest(code=code):
                self.backend.error_code = code
                self.submit()
                self.assertIn(text, self.page.locator('#listingFeedbackText').inner_text())
                self.assertIn(text, self.page.locator('#caPhotoReview-front').inner_text())
                self.assertEqual(self.page.locator('#photos-front').get_attribute('aria-invalid'), 'true')
                self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '42000')
                self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 1)
                self.assertFalse(self.backend.uploads)
                self.assertFalse(self.backend.saves)
                self.dismiss()
        self.page.locator('#photos-front').set_input_files(dict(name='replacement.png', mimeType='image/png', buffer=fixtures.PNG))
        self.assertIsNone(self.page.locator('#photos-front').get_attribute('aria-invalid'))
        self.assertEqual(self.page.locator('#caPhotoReview-front').inner_text(), '')

    def test_provider_failure_never_falls_back_and_explicit_retry_can_succeed(self):
        self.backend.error_code = 'provider_unavailable'
        self.backend.error_status = 503
        self.new_listing()
        self.submit()
        self.assertIn('hazırda mümkün deyil', self.page.locator('#listingFeedbackText').inner_text())
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)
        self.assertTrue(self.page.locator('#listingForm [name=price]').is_enabled())
        self.dismiss()
        self.backend.error_code = None
        self.submit()
        self.assertEqual(len(self.backend.saves), 1)
        self.assertFalse(self.backend.uploads)

    def test_enabled_but_unconfigured_mode_blocks_before_upload_or_model_call(self):
        self.backend.configured = False
        self.new_listing()
        self.submit()
        self.assertIn('hazırda mümkün deyil', self.page.locator('#listingFeedbackText').inner_text())
        self.assertEqual(self.page.locator('#caPhotoReviewNote').get_attribute('data-review-mode'), 'unavailable')
        self.assertFalse(self.backend.reviews)
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_malformed_status_or_network_failure_does_not_skip_review(self):
        for name in ('bad_status', 'abort_status'):
            with self.subTest(failure=name):
                setattr(self.backend, name, True)
                self.new_listing()
                self.submit()
                self.assertFalse(self.backend.reviews)
                self.assertFalse(self.backend.uploads)
                self.assertFalse(self.backend.saves)
                self.dismiss()
                setattr(self.backend, name, False)

    def test_untrusted_approved_url_or_wrong_response_category_cannot_be_saved(self):
        self.new_listing()
        for name in ('bad_url', 'bad_category'):
            with self.subTest(failure=name):
                setattr(self.backend, name, True)
                self.submit()
                self.assertIn('təsdiqlənmədi', self.page.locator('#listingFeedbackText').inner_text())
                self.assertFalse(self.backend.uploads)
                self.assertFalse(self.backend.saves)
                self.dismiss()
                setattr(self.backend, name, False)

    def test_parallel_file_reviews_share_status_and_all_verified_urls_are_saved(self):
        self.new_listing()
        # Distinct pixels: identical files may legitimately reuse an approval.
        self.page.locator('#photos-front').evaluate('''async input=>{
            const files=new DataTransfer();
            for(let i=0;i<4;i++){
                const canvas=document.createElement('canvas');canvas.width=32;canvas.height=24;
                const context=canvas.getContext('2d');context.fillStyle=`rgb(${i*60},${30+i*40},${180-i*30})`;context.fillRect(0,0,32,24);
                const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
                files.items.add(new File([blob],`view-${i}.png`,{type:'image/png'}));
            }
            input.files=files.files;input.dispatchEvent(new Event('change',{bubbles:true}));
        }''')
        self.submit()
        self.assertEqual(len(self.backend.reviews), 4)
        self.assertEqual(len(self.backend.status_calls), 1)
        self.assertFalse(self.backend.uploads)
        urls = self.backend.saves[0]['sekiller']
        self.assertEqual(len(set(urls)), 4)
        self.assertTrue(all(f'/{OWNER}/checked/' in url for url in urls))

    def test_late_review_from_old_account_does_not_save_or_clear_new_account_draft(self):
        self.backend.hold_review = True
        self.new_listing()
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        for _ in range(100):
            if self.backend.pending_reviews:
                break
            self.page.wait_for_timeout(20)
        self.assertTrue(self.backend.pending_reviews)
        self.page.evaluate('''async id=>{
            await caPersistSession({access_token:'second-token',expires_at:4102444800,
                user:{id,email:'second@example.invalid',user_metadata:{telefon:'+994000000002'}}});
            openSellPage();document.querySelector('#listingForm [name=price]').value='55555';
        }''', OTHER_OWNER)
        route, response = self.backend.pending_reviews.pop()
        route.fulfill(content_type='application/json', body=json.dumps(response))
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '55555')
        self.assertTrue(self.page.locator('#listingFeedback').is_hidden())
        self.assertEqual(self.page.locator('#caPhotoReview-front').inner_text(), '')
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)

    def test_rear_group_reports_its_own_mismatched_view_and_preserves_selected_file(self):
        self.new_listing()
        self.page.locator('#photos-front').set_input_files([])
        self.page.locator('#photos-rear').set_input_files(dict(name='wrong-front.png', mimeType='image/png', buffer=fixtures.PNG))
        self.backend.error_code = 'category_mismatch'
        self.submit()
        self.assertEqual(self.backend.reviews[-1]['category'], 'rear')
        self.assertIn('Arxa görünüş', self.page.locator('#listingFeedbackText').inner_text())
        self.assertIn('arxa işıqlar', self.page.locator('#caPhotoReview-rear').inner_text())
        self.assertEqual(self.page.locator('#photos-rear').get_attribute('aria-invalid'), 'true')
        self.assertIsNone(self.page.locator('#photos-front').get_attribute('aria-invalid'))
        self.assertEqual(self.page.locator('#photos-rear').evaluate('input=>input.files[0].name'), 'wrong-front.png')
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_explicit_retry_clears_previous_error_while_the_new_review_is_pending(self):
        self.new_listing()
        self.backend.error_code = 'screenshot'
        self.submit()
        self.dismiss()
        self.backend.error_code = None
        self.backend.hold_review = True
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        for _ in range(100):
            if self.backend.pending_reviews:
                break
            self.page.wait_for_timeout(20)
        self.assertTrue(self.backend.pending_reviews)
        self.assertEqual(self.page.locator('#caPhotoReview-front').get_attribute('data-review-state'), 'checking')
        self.assertIsNone(self.page.locator('#photos-front').get_attribute('aria-invalid'))
        self.assertNotIn('Ekran görüntüsü', self.page.locator('#caPhotoReview-front').inner_text())
        route, response = self.backend.pending_reviews.pop()
        route.fulfill(content_type='application/json', body=json.dumps(response))
        self.page.locator('#listingFeedback').wait_for(state='visible')
        self.assertIn('qəbul edildi', self.page.locator('#listingFeedbackText').inner_text())
        self.assertEqual(len(self.backend.saves), 1)

    def test_aborted_provider_connection_keeps_azerbaijani_warning_and_never_falls_back(self):
        self.new_listing()
        self.page.wait_for_function('document.getElementById("caPhotoReviewNote").dataset.reviewMode==="automatic"')
        self.page.evaluate("""()=>{
            const original=window.fetch;
            window.fetch=function(url,options){
                if(String(url).endsWith('/functions/v1/ca-photo-review')&&options?.method==='POST')
                    return Promise.reject(new DOMException('synthetic native abort text','AbortError'));
                return original.call(this,url,options);
            };
        }""")
        self.submit()
        message = self.page.locator('#listingFeedbackText').inner_text()
        self.assertIn('İnternet bağlantını yoxlayıb', message)
        self.assertNotIn('synthetic native abort text', message)
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_activating_review_invalidates_cached_unreviewed_uploads_before_retry(self):
        self.backend.enabled = False
        self.backend.configured = False
        self.backend.fail_save = True
        self.new_listing()
        self.submit()
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertFalse(self.backend.reviews)
        self.dismiss()
        self.backend.fail_save = False
        self.backend.enabled = True
        self.backend.configured = True
        self.page.evaluate('''()=>{const original=Date.now;Date.now=()=>original()+11000;}''')
        self.submit()
        self.assertEqual(len(self.backend.reviews), 1)
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertIn(f'/{OWNER}/checked/', self.backend.saves[-1]['sekiller'][0])

    def test_same_file_moved_from_front_to_rear_requires_a_new_category_review(self):
        self.backend.fail_save = True
        self.new_listing()
        self.submit()
        self.assertEqual([row['category'] for row in self.backend.reviews], ['front'])
        self.dismiss()
        same_file = self.page.evaluate('''()=>{
            const front=document.getElementById('photos-front'),rear=document.getElementById('photos-rear');
            const file=front.files[0],transfer=new DataTransfer();transfer.items.add(file);
            front.value='';front.dispatchEvent(new Event('change',{bubbles:true}));
            rear.files=transfer.files;rear.dispatchEvent(new Event('change',{bubbles:true}));
            return rear.files[0]===file&&caPhotoUploadCache.has(file);
        }''')
        self.assertTrue(same_file, 'Fixture must move the exact cached File object')
        self.backend.fail_save = False
        self.backend.error_code = 'category_mismatch'
        self.submit()
        self.assertEqual([row['category'] for row in self.backend.reviews], ['front', 'rear'])
        self.assertIn('Arxa görünüş', self.page.locator('#listingFeedbackText').inner_text())
        self.assertIn('bu bölməyə uyğun deyil', self.page.locator('#caPhotoReview-rear').inner_text())
        self.assertEqual(len(self.backend.saves), 1, 'The rejected category must not send a second listing write')
        self.assertFalse(self.backend.uploads)


    def blank_photo_form(self):
        self.sign_in()
        self.page.evaluate('openSellPage()')
        self.page.locator('#photos-front').set_input_files(dict(name='precheck.png', mimeType='image/png', buffer=fixtures.PNG))

    def wait_for_precheck(self):
        self.page.locator('#caPhotoPrecheck').wait_for(state='visible')
        self.page.wait_for_function('!document.getElementById("caPhotoPrecheck").disabled')

    def test_precheck_reviews_blank_form_without_listing_write_and_fits_small_screen(self):
        self.blank_photo_form()
        self.wait_for_precheck()
        self.assertFalse(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'))
        self.page.set_viewport_size({'width': 320, 'height': 812})
        self.assertTrue(self.page.locator('#caPhotoPrecheck').evaluate('''button=>{const r=button.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}'''))
        self.page.locator('#caPhotoPrecheck').click()
        self.page.wait_for_function('document.getElementById("caPhotoPrecheckResult").textContent.includes("Elanı göndərə bilərsən")')
        self.assertEqual(len(self.backend.reviews), 1)
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 1)
        self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '')
        self.assertTrue(self.page.locator('#photos-front').is_enabled())
        self.assertTrue(self.page.locator('#submitListingBtn').is_enabled())
        self.assertTrue(self.page.locator('#caPhotoPrecheck').is_enabled())

    def test_form_submit_after_precheck_reuses_category_verified_url(self):
        self.blank_photo_form()
        self.wait_for_precheck()
        self.page.locator('#caPhotoPrecheck').click()
        self.page.wait_for_function('document.getElementById("caPhotoPrecheckResult").textContent.includes("Elanı göndərə bilərsən")')
        fields = {key: value for key, value in owned_row()['ca_data'].items()
                  if key not in ('photos', 'photo', 'equipment', 'pack')}
        self.page.evaluate('''data=>{const form=document.getElementById('listingForm');for(const [key,value] of Object.entries(data)){const field=form.elements.namedItem(key);if(field&&'value' in field){field.disabled=false;field.value=String(value);}}form.elements.namedItem('package').selectedIndex=0;}''', fields)
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'))
        self.submit()
        self.assertEqual(len(self.backend.reviews), 1, 'Confirmed photo must not run through the model twice')
        self.assertEqual(len(self.backend.saves), 1)
        self.assertFalse(self.backend.uploads)
        self.assertIn(f'/{OWNER}/checked/', self.backend.saves[0]['sekiller'][0])

    def test_failed_precheck_preserves_blank_form_file_and_translates_quota_errors(self):
        self.blank_photo_form()
        self.wait_for_precheck()
        for code, text in (('category_mismatch', 'bu bölməyə uyğun deyil'),
                           ('provider_quota', 'xidmətinin limiti dolub'),
                           ('provider_denied', 'xidmətinə giriş təsdiqlənmədi')):
            with self.subTest(code=code):
                self.backend.error_code = code
                self.backend.error_status = 429 if code == 'provider_quota' else 422
                self.page.locator('#caPhotoPrecheck').click()
                self.page.locator('#listingFeedback').wait_for(state='visible')
                self.assertIn(text, self.page.locator('#listingFeedbackText').inner_text())
                self.assertIn(text, self.page.locator('#caPhotoPrecheckResult').inner_text())
                self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files[0].name'), 'precheck.png')
                self.assertTrue(self.page.locator('#photos-front').is_enabled())
                self.assertTrue(self.page.locator('#submitListingBtn').is_enabled())
                self.assertFalse(self.backend.saves)
                self.assertFalse(self.backend.uploads)
                self.dismiss()

    def test_manual_mode_hides_precheck_and_never_uploads_when_invoked(self):
        self.backend.enabled = False
        self.backend.configured = False
        self.blank_photo_form()
        self.page.wait_for_function('document.getElementById("caPhotoReviewNote").dataset.reviewMode==="manual"')
        self.assertTrue(self.page.locator('#caPhotoPrecheck').is_hidden())
        self.assertFalse(self.page.evaluate('caPrecheckPhotos()'))
        self.assertFalse(self.backend.reviews)
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)
        self.assertIn('admin tərəfindən yoxlanacaq', self.page.locator('#caPhotoPrecheckResult').inner_text())
        self.assertTrue(self.page.locator('#photos-front').is_enabled())

    def test_precheck_with_no_new_photo_warns_without_provider_call(self):
        self.sign_in()
        self.page.evaluate('openSellPage()')
        self.wait_for_precheck()
        self.page.locator('#caPhotoPrecheck').click()
        self.assertIn('ən azı bir yeni', self.page.locator('#caPhotoPrecheckResult').inner_text())
        self.assertFalse(self.backend.reviews)
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_pending_precheck_locks_controls_and_account_switch_keeps_new_draft(self):
        self.backend.hold_review = True
        self.blank_photo_form()
        self.wait_for_precheck()
        self.page.locator('#caPhotoPrecheck').click()
        for _ in range(100):
            if self.backend.pending_reviews:
                break
            self.page.wait_for_timeout(20)
        self.assertTrue(self.backend.pending_reviews)
        self.assertTrue(self.page.locator('#caPhotoPrecheck').is_disabled())
        self.assertTrue(self.page.locator('#photos-front').is_disabled())
        self.assertTrue(self.page.locator('#listingForm [name=price]').is_disabled())
        self.assertTrue(self.page.locator('#submitListingBtn').is_disabled())
        self.page.evaluate('''async id=>{await caPersistSession({access_token:'second-token',expires_at:4102444800,user:{id,email:'second@example.invalid',user_metadata:{telefon:'+994000000002'}}});openSellPage();document.querySelector('#listingForm [name=price]').value='55555';}''', OTHER_OWNER)
        route, response = self.backend.pending_reviews.pop()
        route.fulfill(content_type='application/json', body=json.dumps(response))
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '55555')
        self.assertTrue(self.page.locator('#listingForm [name=price]').is_enabled())
        self.assertTrue(self.page.locator('#listingFeedback').is_hidden())
        self.assertEqual(self.page.locator('#caPhotoPrecheckResult').inner_text(), '')
        self.assertEqual(self.page.locator('#caPhotoReview-front').inner_text(), '')
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)

    def batch_review(self, categories=('front', 'rear'), snapshot=False):
        return self.page.evaluate("""async({categories,snapshot})=>{
            const file=document.getElementById('photos-front').files[0];
            const items=await Promise.all(categories.map(async(category,index)=>({category,fileName:'sample-'+index+'.jpg',blob:await caPreparePhoto(file)})));
            try{
                const results=await caReviewPreparedPhotoBatch(items,{owner:currentUser.id,submission:caListingSubmissionSequence,token:caSession.access_token,...(snapshot?{reviewStatus:window.__batchStatus}:{})});
                return results.map(result=>({index:result.index,url:result.url,code:result.error?.code,message:result.error?.message}));
            }catch(error){return {code:error.code,message:error.message};}
        }""", dict(categories=list(categories),snapshot=snapshot))

    def test_batch_capability_is_optional_and_malformed_caps_fail_closed(self):
        self.new_listing()
        result = self.page.evaluate('''async()=>{const status=await caPhotoReviewBeforeBatch({owner:currentUser.id,submission:caListingSubmissionSequence,token:caSession.access_token});return {batchSupported:status.batchSupported,batchMax:status.batchMax};}''')
        self.assertEqual(result, dict(batchSupported=False, batchMax=0))
        for kind in ('boolean', 'size'):
            with self.subTest(kind=kind):
                self.backend.bad_batch_cap = kind == 'boolean'
                self.backend.batch_supported = True
                self.backend.batch_max = 7 if kind == 'size' else 6
                self.page.evaluate('''()=>{const before=Date.now;Date.now=()=>before()+11000;}''')
                result = self.page.evaluate('''async()=>{try{return await caPhotoReviewBeforeBatch({owner:currentUser.id,submission:caListingSubmissionSequence,token:caSession.access_token});}catch(error){return {code:error.code};}}''')
                self.assertEqual(result, dict(code='invalid_review_response'))
        self.assertFalse(self.backend.batch_calls)
        self.assertFalse(self.backend.uploads)

    def test_batch_reorders_results_to_original_positions_and_shares_prepared_status(self):
        self.backend.batch_supported = True
        self.backend.batch_reverse = True
        self.new_listing()
        self.page.evaluate('''async()=>{window.__batchStatus=await caPhotoReviewBeforeBatch({owner:currentUser.id,submission:caListingSubmissionSequence,token:caSession.access_token});const before=Date.now;Date.now=()=>before()+11000;}''')
        status_calls = len(self.backend.status_calls)
        result = self.batch_review(('front', 'rear', 'side'), snapshot=True)
        self.assertEqual([item['index'] for item in result], [0, 1, 2])
        self.assertTrue(all(f'/{OWNER}/checked/' in item['url'] for item in result))
        self.assertEqual(len({item['url'] for item in result}), 3)
        self.assertEqual(self.backend.batch_calls[0]['categories'], ['front', 'rear', 'side'])
        self.assertEqual(len(self.backend.status_calls), status_calls, 'Long batches must use the initial status snapshot')
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)
        self.assertIn('1 şəkil yoxlamadan keçdi', self.page.locator('#caPhotoReview-rear').inner_text())

    def test_batch_partial_rejection_keeps_verified_successes_and_per_group_warning(self):
        self.backend.batch_supported = True
        self.backend.batch_errors = {1: 'screenshot'}
        self.new_listing()
        result = self.batch_review()
        self.assertIn(f'/{OWNER}/checked/', result[0]['url'])
        self.assertEqual(result[1]['code'], 'screenshot')
        self.assertIsNone(result[1].get('url'))
        self.assertIn('Arxa görünüş', result[1]['message'])
        self.assertIn('sample-1.jpg', result[1]['message'])
        self.assertIn('Ekran görüntüsü', self.page.locator('#caPhotoReview-rear').inner_text())
        self.assertEqual(self.page.locator('#photos-rear').get_attribute('aria-invalid'), 'true')
        self.assertIsNone(self.page.locator('#photos-front').get_attribute('aria-invalid'))
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_batch_rejects_all_malformed_results_before_any_false_approval(self):
        self.backend.batch_supported = True
        self.new_listing()
        for kind in ('duplicate_index', 'missing_result', 'wrong_category', 'untrusted_url', 'failed_url', 'bad_ok'):
            with self.subTest(kind=kind):
                self.backend.batch_bad_kind = kind
                result = self.batch_review()
                self.assertEqual(result['code'], 'invalid_review_response')
                self.assertNotIn('yoxlamadan keçdi', self.page.locator('#caPhotoReview-front').inner_text())
                self.assertNotIn('yoxlamadan keçdi', self.page.locator('#caPhotoReview-rear').inner_text())
                self.assertFalse(self.backend.saves)
                self.assertFalse(self.backend.uploads)

    def test_batch_quota_error_preserves_files_and_cannot_fall_back_to_unchecked_upload(self):
        self.backend.batch_supported = True
        self.backend.error_code = 'provider_quota'
        self.backend.error_status = 429
        self.new_listing()
        result = self.batch_review()
        self.assertEqual(result['code'], 'provider_quota')
        self.assertIn('xidmətinin limiti dolub', result['message'])
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 1)
        self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '42000')
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)

    def test_batch_input_limits_are_enforced_before_review_http(self):
        self.backend.batch_supported = True
        self.new_listing()
        result = self.page.evaluate('''async()=>{
            const blob=new Blob([new Uint8Array(5*1024*1024)],{type:'image/jpeg'});
            const options={owner:currentUser.id,submission:caListingSubmissionSequence,token:caSession.access_token};
            const outcomes=[];
            for(const items of [Array(7).fill({category:'front',blob}),[{category:'front',blob},{category:'rear',blob}],[{category:'unknown',blob}]]){
                try{await caReviewPreparedPhotoBatch(items,options);outcomes.push('accepted');}catch(error){outcomes.push(error.code);}
            }
            return outcomes;
        }''')
        self.assertEqual(result, ['invalid_image']*3)
        self.assertFalse(self.backend.batch_calls)
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)

    def test_late_batch_response_cannot_mark_new_account_photos_approved(self):
        self.backend.batch_supported = True
        self.backend.hold_review = True
        self.new_listing()
        self.page.evaluate("""()=>{window.__batchOutcome=null;(async()=>{
            const file=document.getElementById('photos-front').files[0],blob=await caPreparePhoto(file);
            try{await caReviewPreparedPhotoBatch([{category:'front',blob},{category:'rear',blob}],{owner:currentUser.id,submission:caListingSubmissionSequence,token:caSession.access_token});window.__batchOutcome='accepted';}
            catch(error){window.__batchOutcome=error.code;}
        })();}""")
        for _ in range(100):
            if self.backend.pending_reviews:
                break
            self.page.wait_for_timeout(20)
        self.assertTrue(self.backend.pending_reviews)
        self.page.evaluate('''async id=>{await caPersistSession({access_token:'second-token',expires_at:4102444800,user:{id,email:'second@example.invalid',user_metadata:{telefon:'+994000000002'}}});openSellPage();document.querySelector('#listingForm [name=price]').value='55555';}''', OTHER_OWNER)
        route, response = self.backend.pending_reviews.pop()
        route.fulfill(content_type='application/json', body=json.dumps(response))
        self.page.wait_for_function('window.__batchOutcome!==null')
        self.assertEqual(self.page.evaluate('__batchOutcome'), 'photo_review_stale')
        self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '55555')
        self.assertEqual(self.page.locator('#caPhotoReview-front').inner_text(), '')
        self.assertEqual(self.page.locator('#caPhotoReview-rear').inner_text(), '')
        self.assertFalse(self.backend.saves)
        self.assertFalse(self.backend.uploads)
