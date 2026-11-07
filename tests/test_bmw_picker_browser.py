"""Offline BMW picker regressions; every network request is mocked."""
import os
import unittest

from playwright.sync_api import sync_playwright
from test_listing_management_browser import OfflineBackend, ORIGIN, OWNER


class BMWPickerBrowserTests(unittest.TestCase):
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
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.backend = OfflineBackend()
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caRemoteCars.length === 2')

    def tearDown(self):
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertFalse([call for call in self.backend.calls if call['method'] in ('PATCH', 'DELETE')
                          or call['method'] == 'POST' and call['path'] == '/rest/v1/elanlar'],
                         'Picker tests must never mutate listings')
        self.context.close()

    def open_bmw_models(self, listing=False):
        if listing:
            self.page.evaluate('''owner => {
                currentUser={id:owner,email:'offline@example.invalid',phone:'+994000000000'};
                caSession={access_token:'offline-token',expires_at:4102444800,user:{id:owner}};
                openSellPage();
            }''', OWNER)
        elif not self.page.locator('#searchMake').is_visible():
            self.page.locator('#caFilterLaunch').click()
        make = '#listingForm input[name="make"]' if listing else '#searchMake'
        self.page.locator(make).click()
        self.page.locator('#pickerSearch').fill('BMW')
        self.page.locator('#pickerList [data-picker-value="BMW"]').click()
        self.page.wait_for_function('pickerOverlay.classList.contains("open") && activePicker.kind === "model"')

    def select_exact_model(self, model, listing=False):
        self.open_bmw_models(listing=listing)
        self.page.locator('#pickerSearch').fill(model)
        option = self.page.locator(f'#pickerList [data-picker-value="{model}"]').first
        self.assertTrue(option.is_visible(), f'Existing BMW {model} must be selectable after exact search')
        self.assertFalse(self.page.locator('#pickerCustom').is_visible(), 'An exact visible result needs no duplicate custom action')
        option.click()
        field = '#listingForm input[name="model"]' if listing else '#searchModel'
        self.assertEqual(self.page.locator(field).input_value(), model)
        if listing:
            self.page.wait_for_function('generationOverlay.classList.contains("open")')
            self.page.locator('#generationPicker [onclick="closeGenerationPicker()"]',).click()

    def test_existing_nonseries_models_are_selectable_after_exact_search(self):
        for model in ('X5', 'X3', 'Z4', 'i3', 'iX'):
            with self.subTest(model=model):
                self.select_exact_model(model)

    def test_existing_nonseries_models_are_browsable_without_search(self):
        self.open_bmw_models()
        for model in ('X5', 'X3', 'Z4', 'i3', 'iX'):
            with self.subTest(model=model):
                self.assertGreater(self.page.locator(f'#pickerList [data-picker-value="{model}"]').count(), 0,
                                   f'Existing BMW {model} must appear without requiring a typed workaround')

    def test_listing_picker_selects_nonseries_models_and_opens_generation_step(self):
        for model in ('X5', 'X3', 'Z4', 'i3', 'iX'):
            with self.subTest(model=model):
                self.select_exact_model(model, listing=True)

    def test_530_and_m3_keep_the_existing_series_accordion(self):
        for series, model in ((5, '530i'), (3, 'M3')):
            with self.subTest(model=model):
                self.page.evaluate('cenubBMWOpenSeries.clear()')
                self.open_bmw_models()
                heading = self.page.locator(f'[data-bmw-series-toggle="{series}"]')
                self.assertEqual(heading.get_attribute('aria-expanded'), 'false')
                heading.click()
                self.assertEqual(heading.get_attribute('aria-expanded'), 'true')
                self.page.locator(f'#pickerList [data-picker-value="{model}"]').first.click()
                self.assertEqual(self.page.locator('#searchModel').input_value(), model)

    def test_typed_530_and_m3_results_keep_their_series_groups(self):
        for query, series, model in (('530', 5, '530i'), ('M3', 3, 'M3')):
            with self.subTest(query=query):
                self.open_bmw_models()
                self.page.locator('#pickerSearch').fill(query)
                self.assertEqual(self.page.locator(f'[data-bmw-series-toggle="{series}"]').get_attribute('aria-expanded'), 'true')
                self.page.locator(f'#pickerList [data-picker-value="{model}"]').first.click()
                self.assertEqual(self.page.locator('#searchModel').input_value(), model)

    def test_every_catalog_and_remote_model_has_an_option_after_opening_series(self):
        self.open_bmw_models()
        self.page.evaluate('''() => {
            remoteModelCache.BMW=['Remote electric fixture'];
            for(let n=1;n<=8;n++)cenubBMWOpenSeries.add(String(n));
            renderPickerItems();
        }''')
        missing = self.page.evaluate('''() => {
            const shown=new Set([...pickerList.querySelectorAll('[data-picker-value]')].map(option=>option.dataset.pickerValue));
            return pickerItems().filter(model=>!shown.has(model));
        }''')
        self.assertEqual(missing, [], 'Series, special, electric and remotely supplied models must all remain available')

    def test_unknown_model_keeps_the_custom_value_action(self):
        self.open_bmw_models()
        self.page.locator('#pickerSearch').fill('Offline special BMW model')
        self.assertEqual(self.page.locator('#pickerList [data-picker-value]').count(), 0)
        self.assertTrue(self.page.locator('#pickerCustom').is_visible())
        self.page.locator('#pickerCustom').click()
        self.assertEqual(self.page.locator('#searchModel').input_value(), 'Offline special BMW model')

    def test_mobile_exact_model_selection(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.select_exact_model('X5')


if __name__ == '__main__':
    unittest.main()
