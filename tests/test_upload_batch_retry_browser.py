"""Failed upload batches drain active workers before retries; all HTTP is mocked."""
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

import test_package_feedback_browser as fixtures
from test_listing_management_browser import ORIGIN


class DelayedUploadBackend(fixtures.PackageFeedbackBackend):
    def __init__(self):
        super().__init__()
        self.delayed = None
        self.reject_one = True

    def route(self, route):
        request = route.request
        if (request.method == 'POST'
                and urlsplit(request.url).path.startswith('/storage/v1/object/')):
            self.uploads.append(urlsplit(request.url).path)
            if len(self.uploads) == 1:
                self.delayed = route
                return
            if len(self.uploads) == 2 and self.reject_one:
                route.fulfill(status=503, content_type='application/json',
                              body='{"message":"Synthetic upload failure"}')
                return
            route.fulfill(content_type='application/json', body='{}')
            return
        super().route(route)


class UploadBatchRetryBrowserTests(unittest.TestCase):
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

    def test_failure_waits_for_active_upload_and_retry_reuses_successes(self):
        context = self.browser.new_context(viewport={'width': 375, 'height': 812})
        self.page = context.new_page()
        self.page.set_default_timeout(6000)
        self.backend = DelayedUploadBackend()
        errors = []
        self.page.on('pageerror', lambda error: errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.page.route('**/*', self.backend.route)
        try:
            self.page.goto(ORIGIN, wait_until='load')
            self.page.wait_for_function('caBrowseState.loaded')
            fixtures.PackageFeedbackBrowserTests.new_listing(self)
            self.page.locator('#photos-front').set_input_files([
                dict(name=f'synthetic-{i}.png', mimeType='image/png', buffer=fixtures.PNG)
                for i in range(6)])
            self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
            for _ in range(150):
                if self.backend.delayed and len(self.backend.uploads) >= 4:
                    break
                self.page.wait_for_timeout(20)
            self.assertIsNotNone(self.backend.delayed)
            self.assertEqual(len(self.backend.uploads), 4)
            self.page.wait_for_timeout(100)
            self.assertTrue(self.page.locator('#submitListingBtn').is_disabled())
            self.assertTrue(self.page.locator('#listingForm [name=price]').is_disabled())
            self.assertTrue(self.page.locator('#listingFeedback').is_hidden())
            self.assertFalse(self.backend.saves)
            route = self.backend.delayed
            self.backend.delayed = None
            route.fulfill(content_type='application/json', body='{}')
            self.page.locator('#listingFeedback').wait_for(state='visible')
            self.assertIn('Synthetic upload failure',
                          self.page.locator('#listingFeedbackText').inner_text())
            self.assertEqual(self.page.evaluate('''[...document.getElementById('photos-front').files]
                .filter(file=>caPhotoUploadCache.has(file)).length'''), 3)
            self.assertTrue(self.page.locator('#listingForm [name=price]').is_enabled())
            self.page.locator('#listingFeedbackClose').click()
            self.backend.reject_one = False
            self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
            self.page.locator('#listingFeedback').wait_for(state='visible')
            self.assertIn('qəbul edildi', self.page.locator('#listingFeedbackText').inner_text())
            self.assertEqual(len(self.backend.uploads), 7)
            self.assertEqual(len(self.backend.saves), 1)
            self.assertEqual(len(self.backend.saves[0]['sekiller']), 6)
            self.assertFalse(errors)
        finally:
            if self.backend.delayed:
                self.backend.delayed.abort()
            context.close()

    def sign_in(self, admin=False):
        fixtures.PackageFeedbackBrowserTests.sign_in(self, admin)
