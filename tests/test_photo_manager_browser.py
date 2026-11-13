"""Photo editing regressions in Chromium with every HTTP request intercepted.

Exercises the real form and POST/PATCH payloads, with synthetic local photos.
No cloud storage, database, email, or payment requests leave the test browser.
"""
import copy
import os
from pathlib import Path
import struct
import time
import unittest
import zlib
import json

from playwright.sync_api import sync_playwright
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, OWNED_ID, GROUPS, owned_row
from test_package_feedback_browser import PackageFeedbackBackend
from test_photo_review_browser import PhotoReviewBackend

ROOT = Path(__file__).resolve().parents[1]


def photo(name, rgb):
    """Small distinct valid PNGs, without external codecs or test assets."""
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    pixels = (b'\x00' + bytes(rgb) * 4) * 4
    image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 4, 4, 8, 2, 0, 0, 0))
    image += chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')
    return dict(name=name, mimeType='image/png', buffer=image)


class PhotoManagerBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={'width':1280, 'height':1000})
        self.context.set_default_timeout(5000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error:self.errors.append(str(error)))
        self.page.add_init_script('''window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true;
            window.__createdPhotoUrls=[];window.__revokedPhotoUrls=[];
            const originalCreate=URL.createObjectURL.bind(URL),originalRevoke=URL.revokeObjectURL.bind(URL);
            URL.createObjectURL=(...args)=>{const url=originalCreate(...args);__createdPhotoUrls.push(url);return url;};
            URL.revokeObjectURL=url=>{__revokedPhotoUrls.push(url);return originalRevoke(url);};''')
        self.backend = PackageFeedbackBackend()
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')
        # During development the module may precede its final index inclusion.
        if self.page.evaluate('typeof caPhotoManagerProject!=="function"'):
            self.page.add_script_tag(path=str(ROOT/'assets/js/19-photo-manager.js'))

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')

    def sign_in(self, owner=OWNER):
        self.page.evaluate('''async id=>await caPersistSession({access_token:'seller-token',expires_at:4102444800,
            user:{id,email:'offline@example.invalid',user_metadata:{telefon:'+994000000000'}}})''', owner)

    def open_edit(self, expected_count=9):
        self.sign_in()
        self.page.evaluate('async()=>await caFetchMyListings()')
        self.page.evaluate('id=>editCar(id)', OWNED_ID)
        self.assertEqual(self.page.locator('.ca-managed-photo').count(), expected_count)

    def new_listing(self):
        self.sign_in()
        self.page.evaluate('openSellPage()')
        fields = {key:value for key,value in owned_row()['ca_data'].items()
                  if key not in ('photos', 'photo', 'equipment', 'pack')}
        self.page.evaluate('''data=>{const form=document.getElementById('listingForm');
            for(const [key,value] of Object.entries(data)){
              const field=form.elements.namedItem(key);if(field&&'value' in field){field.disabled=false;field.value=String(value);}}
            form.elements.namedItem('package').selectedIndex=0;}''', fields)

    def cards(self, category):
        return self.page.locator('#preview-'+category+' .ca-managed-photo')

    def action(self, category, index, label):
        self.cards(category).nth(index).get_by_role('button', name=label, exact=True).click()

    def project(self):
        return self.page.evaluate('caPhotoManagerProject()')

    def submit(self):
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'))
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')

    def patch(self):
        writes = [call for call in self.backend.calls
                  if call['method']=='PATCH' and call['path']=='/rest/v1/elanlar']
        self.assertEqual(len(writes), 1)
        return writes[0]['body']

    def enable_review_fixture(self):
        self.page.unroute('**/*', self.backend.route)
        self.backend = PhotoReviewBackend()
        self.backend.batch_supported = True
        self.page.route('**/*', self.backend.route)

    def test_existing_authoritative_cover_survives_edit_without_photo_changes(self):
        existing = next(row for row in self.backend.rows if row['id'] == OWNED_ID)
        existing['sekiller'] = [GROUPS['rear'][1], *[url for url in existing['sekiller'] if url != GROUPS['rear'][1]]]
        existing['ca_data']['photo'] = GROUPS['front'][0]  # Stale metadata never overrides the gallery.
        self.open_edit()
        self.assertIn('★ Əsas şəkil', self.cards('rear').nth(1).inner_text())
        self.submit()
        payload = self.patch()
        self.assertEqual(payload['ca_data']['photo'], GROUPS['rear'][1])
        self.assertEqual(payload['sekiller'][0], GROUPS['rear'][1])
        self.assertEqual(payload['ca_data']['photos'], GROUPS)

    def test_original_photos_delete_reorder_and_rear_cover_reach_patch(self):
        self.open_edit()
        self.action('rear', 1, 'Əsas şəkil seç')
        self.action('front', 0, 'Şəkli sonraya keçir')
        self.action('side', 0, 'Şəkli sil')
        expected = copy.deepcopy(GROUPS)
        expected['front'].reverse()
        expected['side'] = expected['side'][1:]
        self.assertEqual(self.project(), expected)
        self.page.evaluate('caRenderPhotoManager()')
        self.assertEqual(self.project(), expected, 'A render must not resurrect deleted original photos')
        self.assertEqual(self.page.evaluate('editingOriginalPhotos'), GROUPS, 'Edit baseline stays immutable')
        self.submit()
        payload = self.patch()
        self.assertEqual(payload['ca_data']['photos'], expected)
        self.assertEqual(payload['sekiller'][0], GROUPS['rear'][1])
        self.assertEqual(payload['ca_data']['photo'], GROUPS['rear'][1])
        self.assertEqual(len(payload['sekiller']), 8)
        self.assertCountEqual(payload['sekiller'], [url for group in expected.values() for url in group])
        self.assertEqual(self.backend.uploads, [], 'Original URL edits need no image upload')

    def test_new_files_keep_identity_after_delete_reorder_and_cover(self):
        self.new_listing()
        self.page.locator('#photos-front').set_input_files([
            photo('first.png', (210, 40, 40)), photo('deleted.png', (40, 210, 40)), photo('third.png', (40, 40, 210))])
        self.page.locator('#photos-rear').set_input_files(photo('rear-cover.png', (210, 180, 40)))
        self.page.evaluate('window.__originalFiles=[...document.getElementById("photos-front").files]')
        self.action('front', 1, 'Şəkli sil')
        self.action('front', 1, 'Şəkli əvvələ keçir')
        self.action('rear', 0, 'Əsas şəkil seç')
        self.assertTrue(self.page.evaluate('''()=>{const files=document.getElementById('photos-front').files;
            return files.length===2&&files[0]===__originalFiles[2]&&files[1]===__originalFiles[0];}'''),
            'DataTransfer must preserve File identity for upload and review caches')
        self.assertEqual(self.project(), {'front':['new', 'new'], 'rear':['new']})
        self.submit()
        self.assertEqual(len(self.backend.uploads), 3)
        self.assertEqual(len(self.backend.saves), 1)
        payload = self.backend.saves[0]
        self.assertEqual(payload['sekiller'][0], payload['ca_data']['photos']['rear'][0])
        self.assertEqual(payload['ca_data']['photo'], payload['sekiller'][0])
        self.assertEqual(payload['sekiller'][1:], payload['ca_data']['photos']['front'])
        self.assertEqual(len(set(payload['sekiller'])), 3)
        self.assertTrue(all('/storage/v1/object/public/' in url for url in payload['sekiller']))
        self.assertFalse(self.page.locator('.ca-managed-photo').count(), 'A confirmed save clears the draft')

    def test_adding_one_new_file_retains_unremoved_originals_in_same_category(self):
        self.open_edit()
        self.action('front', 0, 'Şəkli sil')
        self.page.locator('#photos-front').set_input_files(photo('replacement.png', (40, 180, 180)))
        self.assertEqual(self.project()['front'], [GROUPS['front'][1], 'new'])
        self.submit()
        payload = self.patch()
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertEqual(payload['ca_data']['photos']['front'][0], GROUPS['front'][1])
        self.assertEqual(len(payload['ca_data']['photos']['front']), 2)
        for category in ('rear', 'side', 'interior', 'engine', 'other'):
            self.assertEqual(payload['ca_data']['photos'][category], GROUPS[category])
        self.assertNotIn(GROUPS['front'][0], payload['sekiller'])
        self.assertEqual(len(payload['sekiller']), 9)

    def test_failed_save_preserves_editor_and_reuses_uploaded_file_on_retry(self):
        self.open_edit()
        self.page.locator('#photos-front').set_input_files(photo('retry.png', (180, 40, 180)))
        self.action('front', 2, 'Şəkli əvvələ keçir')
        self.action('front', 1, 'Əsas şəkil seç')
        self.backend.fail_save = True
        self.submit()
        self.assertIn('Mock listing save unavailable', self.page.locator('#listingFeedbackText').inner_text())
        expected = self.project()
        self.assertEqual(len(self.backend.uploads), 1)
        self.page.evaluate('caDismissListingFeedback(false);caRenderPhotoManager()')
        self.assertEqual(self.project(), expected)
        self.assertEqual(self.cards('front').nth(1).locator('figcaption').inner_text(), '★ Əsas şəkil · 2')
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 1)
        self.backend.fail_save = False
        self.submit()
        self.assertEqual(len(self.backend.uploads), 1, 'Retry must reuse the previously uploaded File')
        payload = self.patch()
        self.assertEqual(payload['ca_data']['photos']['front'][0], GROUPS['front'][0])
        self.assertEqual(payload['ca_data']['photos']['front'][2], GROUPS['front'][1])
        self.assertEqual(payload['sekiller'][0], payload['ca_data']['photos']['front'][1])
        self.assertEqual(payload['ca_data']['photo'], payload['sekiller'][0])

    def test_removing_bad_new_file_prevents_it_from_being_decoded_or_uploaded(self):
        self.new_listing()
        self.page.locator('#photos-front').set_input_files([
            dict(name='broken.jpg', mimeType='image/jpeg', buffer=b'not-an-image'),
            photo('valid.png', (30, 100, 170))])
        self.action('front', 0, 'Şəkli sil')
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>[...input.files].map(f=>f.name)'), ['valid.png'])
        self.submit()
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertEqual(len(self.backend.saves), 1)
        self.assertEqual(len(self.backend.saves[0]['sekiller']), 1)
        self.assertEqual(self.page.evaluate('__alerts'), [])

    def test_reviewed_file_approval_survives_delete_reorder_and_cover(self):
        self.enable_review_fixture()
        self.new_listing()
        self.page.locator('#photos-front').set_input_files([
            photo('review-first.png', (180, 30, 50)), photo('review-deleted.png', (30, 180, 50)),
            photo('review-third.png', (30, 50, 180))])
        self.page.locator('#photos-rear').set_input_files(photo('review-rear.png', (190, 150, 30)))
        self.page.locator('#caPhotoPrecheck').click()
        self.page.wait_for_function('!document.getElementById("caPhotoPrecheck").disabled')
        self.assertEqual(len(self.backend.reviews), 4)
        approved = self.page.evaluate('''()=>Object.fromEntries(['front','rear'].map(cat=>[cat,
            [...document.getElementById('photos-'+cat).files].map(file=>caPhotoUploadCache.get(file).url)]))''')
        self.action('front', 1, 'Şəkli sil')
        self.action('front', 1, 'Şəkli əvvələ keçir')
        self.action('rear', 0, 'Əsas şəkil seç')
        self.submit()
        self.assertEqual(len(self.backend.reviews), 4, 'Editing must retain category-bound review approvals')
        self.assertEqual(self.backend.uploads, [], 'Verified server photo URLs need no direct upload')
        self.assertEqual(len(self.backend.saves), 1)
        payload = self.backend.saves[0]
        self.assertEqual(payload['ca_data']['photos']['front'], [approved['front'][2], approved['front'][0]])
        self.assertEqual(payload['ca_data']['photos']['rear'], approved['rear'])
        self.assertEqual(payload['sekiller'], [approved['rear'][0], approved['front'][2], approved['front'][0]])
        self.assertEqual(payload['ca_data']['photo'], approved['rear'][0])

    def test_saving_locks_photo_actions_until_confirmation(self):
        self.new_listing()
        self.page.locator('#photos-front').set_input_files(photo('pending.png', (90, 120, 160)))
        self.backend.delay_save = True
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        deadline = time.monotonic() + 5
        while not self.backend.pending_saves and time.monotonic() < deadline:
            self.page.wait_for_timeout(10)
        self.assertTrue(self.backend.pending_saves)
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.getAttribute("aria-busy")==="true"'))
        self.assertTrue(self.cards('front').get_by_role('button', name='Şəkli sil', exact=True).is_disabled())
        self.cards('front').get_by_role('button', name='Şəkli sil', exact=True).evaluate('button=>button.click()')
        self.assertEqual(self.project(), {'front':['new']}, 'Disabled action cannot change the in-flight payload')
        route, result = self.backend.pending_saves.pop()
        route.fulfill(content_type='application/json', body=json.dumps(result))
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')
        self.assertEqual(len(self.backend.saves), 1)
        self.assertEqual(len(self.backend.saves[0]['sekiller']), 1)

    def test_deleting_last_image_blocks_save_without_resurrecting_it(self):
        self.new_listing()
        self.page.locator('#photos-front').set_input_files(photo('remove-last.png', (150, 70, 30)))
        self.action('front', 0, 'Şəkli sil')
        self.submit()
        self.assertEqual(self.project(), {})
        self.assertEqual(self.backend.uploads, [])
        self.assertEqual(self.backend.saves, [])
        self.assertIn('ən azı 1', self.page.evaluate('__alerts.at(-1)'))

    def test_reset_and_owner_change_clear_private_previews_and_revoke_blob_urls(self):
        self.new_listing()
        self.page.locator('#photos-front').set_input_files([
            photo('first-reset.png', (150, 50, 70)), photo('second-reset.png', (50, 150, 70))])
        self.action('front', 1, 'Şəkli sil')
        self.page.evaluate('caClearListingDraft()')
        self.assertEqual(self.project(), {})
        self.assertEqual(self.page.locator('.ca-managed-photo').count(), 0)
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 0)
        self.assertTrue(self.page.evaluate('''__createdPhotoUrls.length>0&&
            __createdPhotoUrls.every(url=>__revokedPhotoUrls.includes(url))'''), 'Every local preview URL must be revoked')
        self.open_edit()
        self.assertGreater(self.page.locator('.ca-managed-photo img[src^="https://fixture.invalid/"]').count(), 0)
        self.sign_in(OTHER_OWNER)
        self.assertEqual(self.page.locator('.ca-managed-photo').count(), 0)
        self.assertEqual(self.project(), {})
        self.assertIsNone(self.page.evaluate('editingCarId'))

    def test_category_limit_counts_retained_and_new_images_together(self):
        self.open_edit()
        self.page.locator('#photos-front').set_input_files([
            photo(f'new-{n}.png', (30 + n * 20, 80, 140)) for n in range(5)])
        self.submit()
        self.assertIn('Maksimum 36 şəkil', self.page.evaluate('__alerts.at(-1)'))
        self.assertEqual(self.backend.uploads, [], 'Reject the combined seven-photo group before upload')
        self.assertEqual(len(self.cards('front').all()), 7)
        self.assertFalse([call for call in self.backend.calls
                          if call['method']=='PATCH' and call['path']=='/rest/v1/elanlar'])

    def test_legacy_oversized_category_can_remove_and_reorder_existing_urls(self):
        row = next(row for row in self.backend.rows if row['id']==OWNED_ID)
        old_front = [f'https://fixture.invalid/legacy-{n}.svg' for n in range(8)]
        row['ca_data']['photos']['front'] = old_front[:]
        row['ca_data']['photo'] = old_front[0]
        row['sekiller'] = [url for group in row['ca_data']['photos'].values() for url in group]
        self.open_edit(expected_count=15)
        self.action('front', 0, 'Şəkli sil')
        self.action('front', 0, 'Şəkli sonraya keçir')
        expected = [old_front[2], old_front[1], *old_front[3:]]
        self.assertEqual(self.project()['front'], expected)
        self.assertEqual(self.page.evaluate('editingOriginalPhotos.front'), old_front)
        self.submit()
        payload = self.patch()
        self.assertEqual(payload['ca_data']['photos']['front'], expected)
        self.assertEqual(len(payload['sekiller']), 14)
        self.assertEqual(self.backend.uploads, [])

    def test_photo_controls_fit_and_work_on_320px_mobile_screen(self):
        self.page.set_viewport_size({'width':320, 'height':780})
        self.new_listing()
        self.page.locator('#photos-front').set_input_files([
            photo('mobile-first.png', (60, 100, 160)), photo('mobile-second.png', (100, 160, 60))])
        self.cards('front').first.scroll_into_view_if_needed()
        bounds = self.cards('front').locator('button').evaluate_all('''buttons=>buttons.map(button=>{
            const rect=button.getBoundingClientRect();return {left:rect.left,right:rect.right,width:rect.width,height:rect.height};})''')
        self.assertEqual(len(bounds), 8)
        for box in bounds:
            self.assertGreaterEqual(box['left'], 0)
            self.assertLessEqual(box['right'], 320)
            self.assertGreaterEqual(box['width'], 24)
            self.assertGreaterEqual(box['height'], 32)
        self.action('front', 1, 'Əsas şəkil seç')
        self.assertIn('Əsas şəkil', self.cards('front').nth(1).locator('figcaption').inner_text())
        self.action('front', 0, 'Şəkli sil')
        self.assertEqual(self.cards('front').count(), 1)
        self.assertIn('Əsas şəkil', self.cards('front').first.locator('figcaption').inner_text())

    def test_accident_damaged_car_state_is_saved_with_photo_upload_flow(self):
        self.new_listing()
        self.page.locator('#listingForm [name=condition]').select_option(label='Qəzalı')
        self.page.locator('#listingForm [name=accident]').select_option(label='Qəza qeydi var')
        self.page.locator('#photos-front').set_input_files(photo('damaged-car.png', (25, 80, 120)))
        self.submit()
        saved = self.backend.saves[-1]
        self.assertEqual(saved['ca_data']['condition'], 'Qəzalı')
        self.assertEqual(saved['ca_data']['accident'], 'Qəza qeydi var')
        self.assertTrue(saved['sekiller'])

if __name__ == '__main__':
    unittest.main()
