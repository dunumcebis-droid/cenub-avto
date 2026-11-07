"""Vehicle generation stays tied to the selected listing make/model.
All network requests use offline fixtures; no listing mutation is performed.
"""
import os
import unittest
from playwright.sync_api import sync_playwright
from test_listing_management_browser import OfflineBackend,ORIGIN,OWNER,OWNED_ID


class GenerationBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1280,'height':1000})
        self.page=self.context.new_page();self.errors=[];self.backend=OfflineBackend()
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true')
        self.page.route('**/*',self.backend.route);self.page.goto(ORIGIN,wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')
        self.page.evaluate('''async id=>{currentUser={id,phone:'+994000000000'};
            caSession={access_token:'offline-token',expires_at:4102444800,user:{id}};
            await caFetchMyListings();}''',OWNER)
        self.page.evaluate('id=>editCar(id)',OWNED_ID)
        self.assertEqual(self.page.locator('#generationInput').input_value(),'G30')

    def tearDown(self):
        self.context.close();self.assertFalse(self.errors)

    def test_changing_model_clears_old_generation_and_requires_a_new_choice(self):
        self.page.evaluate("openVehiclePicker('model',listingModelEl,'listingModelsList')")
        self.page.locator('#pickerSearch').fill('M3')
        self.page.locator('#pickerList button[data-picker-value="M3"]').click()
        self.page.wait_for_function('document.getElementById("generationPicker").classList.contains("open")')
        self.page.locator('#generationPicker .generation-close').click()
        self.assertEqual(self.page.locator('#listingForm [name="model"]').input_value(),'M3')
        self.assertEqual(self.page.locator('#generationInput').input_value(),'')
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('window.__alerts.some(message=>message.includes("nəslini seç"))')
        self.assertTrue(self.page.locator('#generationPicker').is_visible())
        self.assertFalse(any(c['method'] in ('PATCH','DELETE') for c in self.backend.calls))

    def test_changing_make_drops_generation_before_the_new_model_is_chosen(self):
        self.page.evaluate("openVehiclePicker('make',listingMakeEl,'listingMakesList')")
        self.page.locator('#pickerSearch').fill('Toyota')
        self.page.locator('#pickerList button[data-picker-value="Toyota"]').click()
        self.page.wait_for_function('activePicker.kind==="model"&&activePicker.make==="Toyota"&&document.getElementById("vehiclePicker").classList.contains("open")')
        self.assertEqual(self.page.locator('#generationInput').input_value(),'')
        self.page.locator('#pickerSearch').fill('Corolla')
        self.page.locator('#pickerList button[data-picker-value="Corolla"]').click()
        self.page.wait_for_function('document.getElementById("generationPicker").classList.contains("open")')
        self.page.locator('#generationPicker [data-generation="E210"]').click()
        self.assertEqual(self.page.locator('#generationInput').input_value(),'E210')

    def test_reselecting_same_model_preserves_existing_generation(self):
        self.page.evaluate("openVehiclePicker('model',listingModelEl,'listingModelsList')")
        self.page.locator('#pickerSearch').fill('530')
        option=self.page.locator('#pickerList button[data-picker-value="530"]')
        if option.count():option.click()
        else:self.page.locator('#pickerCustom').click()
        self.page.wait_for_function('document.getElementById("generationPicker").classList.contains("open")')
        self.page.locator('#generationPicker .generation-close').click()
        self.assertEqual(self.page.locator('#generationInput').input_value(),'G30')


if __name__=='__main__':unittest.main()
