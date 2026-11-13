"""Cash/credit/barter form, browse and saved-search regressions.

Every HTTP request is intercepted. These are client contract tests; live SQL,
RLS and search matching are verified separately. No real listing or bank call.
"""
import copy
import json
import os
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright
from test_cards_browser import browse_fixture_response
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, OWNED_ID, OTHER_ID, owned_row
from test_marketplace_browser import MarketplaceBackend, SEARCH_ID, CREATED
from test_package_feedback_browser import PackageFeedbackBackend, PNG

LEGACY_ID = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
BOTH_ID = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
BARTER_ID = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'


def options(row):
    data = row.get('ca_data') or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            data = {}
    raw = data.get('saleOptions') if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return ['cash']
    valid = [key for key in ('cash', 'credit', 'barter') if key in raw]
    return valid or ['cash']


class SaleOptionsBackend(MarketplaceBackend, PackageFeedbackBackend):
    def __init__(self):
        super().__init__()
        self.sale_browse_calls = []
        self.rows[0]['ca_data']['saleOptions'] = ['cash', 'barter']
        self.rows[1]['ca_data']['saleOptions'] = ['credit']
        for id, model, sale in (
            (LEGACY_ID, 'Legacy-cash', None),
            (BOTH_ID, 'Credit-barter', ['credit', 'barter']),
            (BARTER_ID, 'Barter-only', ['barter']),
        ):
            row = copy.deepcopy(self.rows[1])
            row.update(id=id, model=model)
            row['ca_data'].update(model=model)
            row['ca_data'].pop('saleOptions', None)
            if sale is not None:
                row['ca_data']['saleOptions'] = sale
            self.rows.append(row)

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        if parsed.path.startswith('/storage/v1/object/'):
            # Route JPEG bytes before the JSON-only marketplace mixin.
            return PackageFeedbackBackend.route(self, route)
        if parsed.path == '/rest/v1/rpc/ca_browse_listings':
            assert req.method == 'POST'
            body = req.post_data_json
            self.sale_browse_calls.append(copy.deepcopy(body))
            self.calls.append(dict(method=req.method, path=parsed.path, query=parse_qs(parsed.query),
                                   headers=dict(req.headers), body=copy.deepcopy(body)))
            sale = body['p_filters'].get('saleType', '')
            assert sale in ('', 'cash', 'credit', 'barter')
            rows = [r for r in self.rows if not r.get('is_sold') and (not sale or sale in options(r))]
            data = browse_fixture_response(rows, body, self.today_approved)
            data['total_pages'] = (data['total'] + 23) // 24
            route.fulfill(content_type='application/json', body=json.dumps(data))
            return
        super().route(route)


class SaleOptionsBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(viewport={'width':1280, 'height':1000}, has_touch=True)
        self.context.set_default_timeout(5000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error:self.errors.append(str(error)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>__alerts.push(String(m));window.confirm=()=>true')
        self.backend = SaleOptionsBackend()
        self.page.route('**/*', self.backend.route)

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertFalse([call for call in self.backend.admin_calls if call['name'] in
                          ('ca_admin_status', 'ca_admin_paket_tesdiq', 'ca_admin_paket_reddet')],
                         'Sale choices cannot approve a payment or publish an ad')

    def go(self):
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def sign_in(self, owner=OWNER):
        self.page.evaluate('''async id=>await caPersistSession({access_token:id===%s?'seller-token':'other-token',
            expires_at:4102444800,user:{id,email:'offline@example.invalid',user_metadata:{telefon:'+994000000000'}}})''' % json.dumps(OWNER), owner)

    def selected(self):
        return self.page.locator('#caSaleOptions input:checked').evaluate_all('items=>items.map(n=>n.value)')

    def choose(self, values):
        for value in ('cash', 'credit', 'barter'):
            self.page.locator('#caSaleOptions input[value="'+value+'"]').set_checked(value in values)

    def new_listing(self):
        self.sign_in()
        self.page.evaluate('openSellPage()')
        fields = {key:value for key,value in owned_row()['ca_data'].items()
                  if key not in ('photos', 'photo', 'equipment', 'pack', 'saleOptions')}
        self.page.evaluate('''data=>{const form=document.getElementById('listingForm');
            for(const [key,value] of Object.entries(data)){
                const input=form.elements.namedItem(key);if(input&&'value' in input){input.disabled=false;input.value=String(value);}}
            form.elements.namedItem('package').selectedIndex=0;}''', fields)
        self.page.locator('#photos-front').set_input_files(dict(name='synthetic.png', mimeType='image/png', buffer=PNG))

    def edit(self, id=OWNED_ID):
        self.sign_in()
        self.page.evaluate('async()=>await caFetchMyListings()')
        self.page.evaluate('id=>editCar(id)', id)

    def submit(self):
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'))
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')

    def wait_browse(self, minimum, sale=None):
        for _ in range(250):
            calls = self.backend.sale_browse_calls
            if len(calls) >= minimum and (sale is None or calls[-1]['p_filters'].get('saleType', '') == sale):
                self.page.wait_for_function('!caBrowseState.loading')
                return calls[-1]
            self.page.wait_for_timeout(10)
        self.fail('Expected browse request for sale type '+str(sale))

    def public_ids(self):
        return self.page.evaluate('caPageCars.map(car=>car._id)')

    def tab(self, sale):
        return self.page.locator('#caSaleTypeTabs button[data-sale-type="'+sale+'"]')

    def test_new_listing_defaults_to_cash_and_persists_explicit_array(self):
        self.go(); self.new_listing()
        self.assertEqual(self.selected(), ['cash'])
        self.submit()
        self.assertEqual(len(self.backend.saves), 1)
        self.assertEqual(self.backend.saves[0]['ca_data']['saleOptions'], ['cash'])
        self.assertEqual(self.selected(), ['cash'], 'A confirmed save resets the next draft')

    def test_credit_and_barter_save_together_without_cash_or_bank_payment(self):
        self.go(); self.new_listing(); self.choose(['credit', 'barter']); self.submit()
        self.assertEqual(self.backend.saves[0]['ca_data']['saleOptions'], ['credit', 'barter'])
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertFalse([c for c in self.backend.calls if 'payment' in c['path'] or 'checkout' in c['path']])
        self.assertFalse([c for c in self.backend.admin_calls if c['name'] == 'ca_admin_paket_tesdiq'])

    def test_edit_restores_multiple_options_and_patch_keeps_photos_and_vip(self):
        original = copy.deepcopy(self.backend.rows[0])
        self.go(); self.edit()
        self.assertEqual(self.selected(), ['cash', 'barter'])
        self.choose(['credit', 'barter']); self.submit()
        patches = [c for c in self.backend.calls if c['method']=='PATCH' and c['path']=='/rest/v1/elanlar']
        self.assertEqual(len(patches), 1)
        body = patches[0]['body']
        self.assertEqual(body['ca_data']['saleOptions'], ['credit', 'barter'])
        self.assertEqual(body['sekiller'], original['sekiller'])
        self.assertEqual(self.backend.rows[0]['paket_adi'], original['paket_adi'])
        self.assertEqual(self.backend.uploads, [])

    def test_empty_seller_choice_warns_before_upload_or_write(self):
        self.go(); self.new_listing(); self.choose([])
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('__alerts.some(text=>text.includes("Ən azı bir satış şərti"))')
        self.assertEqual(self.backend.saves, [])
        self.assertEqual(self.backend.uploads, [])
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 1)
        self.assertFalse(self.page.locator('#submitListingBtn').is_disabled())

    def test_cancel_edit_resets_sale_choices_to_cash(self):
        self.go(); self.edit(); self.choose(['credit'])
        self.page.locator('#cancelEditBtn').click()
        self.assertEqual(self.selected(), ['cash'])
        self.assertIsNone(self.page.evaluate('editingCarId'))

    def test_account_change_discards_previous_sellers_sale_choices(self):
        self.go(); self.edit(); self.choose(['credit', 'barter'])
        self.sign_in(OTHER_OWNER)
        self.assertEqual(self.selected(), ['cash'])
        self.assertIsNone(self.page.evaluate('editingCarId'))
        self.assertEqual(self.page.locator('#listingForm [name=price]').input_value(), '')
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files.length'), 0)

    def test_home_credit_tab_synchronizes_filter_and_filters_featured_ads(self):
        self.go(); before = len(self.backend.sale_browse_calls)
        self.tab('credit').click(); call = self.wait_browse(before+1, 'credit')
        self.assertEqual(call['p_page'], 1)
        self.assertEqual(self.public_ids(), [OTHER_ID, BOTH_ID])
        expect(self.page.locator('#caSaleType')).to_have_value('credit')
        expect(self.tab('credit')).to_have_attribute('aria-pressed', 'true')
        self.assertNotIn(OWNED_ID, self.page.evaluate('caVipCars.map(car=>car._id)'))

    def test_filter_barter_synchronizes_home_tab_and_search_results(self):
        self.go(); before = len(self.backend.sale_browse_calls)
        self.page.evaluate('caToggleFilters(true)')
        self.page.locator('#caSaleType').select_option('barter')
        self.page.evaluate('searchCars()'); self.wait_browse(before+1, 'barter')
        self.assertEqual(set(self.public_ids()), {OWNED_ID, BOTH_ID, BARTER_ID})
        expect(self.tab('barter')).to_have_attribute('aria-pressed', 'true')
        expect(self.tab('credit')).to_have_attribute('aria-pressed', 'false')

    def test_sale_tab_preserves_package_sort_and_applied_search(self):
        self.go()
        self.page.evaluate('''async()=>{document.getElementById('searchMake').value='BMW';
            document.getElementById('sortListings').value='priceAsc';currentFilter='VIP';await searchCars()}''')
        before = len(self.backend.sale_browse_calls)
        self.tab('barter').click(); call = self.wait_browse(before+1, 'barter')
        self.assertEqual(call['p_filters']['make'], 'BMW')
        self.assertEqual(call['p_filters']['pack'], 'VIP')
        self.assertEqual(call['p_filters']['sort'], 'priceAsc')
        self.assertEqual(self.public_ids(), [OWNED_ID])
        self.assertTrue(self.page.evaluate('currentFilter==="VIP"'))

    def test_sale_tab_resets_server_pagination_to_first_page(self):
        for n in range(26):
            row = copy.deepcopy(self.backend.rows[2]); row['id']=f'99999999-9999-4999-8999-{n:012d}'
            self.backend.rows.append(row)
        self.go(); self.page.evaluate('async()=>await caFetchListings(2)')
        self.page.wait_for_function('caBrowseState.page===2&&!caBrowseState.loading')
        before = len(self.backend.sale_browse_calls)
        self.tab('credit').click(); call = self.wait_browse(before+1, 'credit')
        self.assertEqual(call['p_page'], 1)
        self.assertEqual(self.page.evaluate('caBrowseState.page'), 1)
        self.assertEqual(self.public_ids(), [OTHER_ID, BOTH_ID])

    def test_clear_search_resets_sale_filter_and_home_selection(self):
        self.go(); self.tab('credit').click(); self.wait_browse(2, 'credit')
        before = len(self.backend.sale_browse_calls)
        self.page.evaluate('clearCarSearch()'); call = self.wait_browse(before+1, '')
        self.assertFalse(call['p_filters'].get('saleType'))
        expect(self.page.locator('#caSaleType')).to_have_value('')
        expect(self.tab('')).to_have_attribute('aria-pressed', 'true')
        self.assertEqual(len(self.public_ids()), 5)

    def test_legacy_ads_are_cash_only_and_display_no_unoffered_credit(self):
        self.go()
        legacy = self.page.evaluate('id=>caPageCars.find(car=>car._id===id)', LEGACY_ID)
        self.assertEqual(legacy['saleOptions'], ['cash'])
        self.tab('cash').click(); self.wait_browse(2, 'cash')
        self.assertEqual(set(self.public_ids()), {OWNED_ID, LEGACY_ID})
        self.assertEqual(self.page.locator('#allGrid .ca-sale-badges [data-sale-option="credit"]').count(), 0)

    def test_card_and_detail_show_the_sellers_credit_barter_options(self):
        self.go()
        card = self.page.locator('#allGrid .car-card').filter(has_text='Credit-barter')
        expect(card.locator('.ca-sale-badges [data-sale-option="credit"]')).to_have_text('Kredit')
        expect(card.locator('.ca-sale-badges [data-sale-option="barter"]')).to_have_text('Barter')
        self.assertEqual(card.locator('.ca-sale-badges [data-sale-option="cash"]').count(), 0)
        self.page.evaluate('id=>caOpenCarRecord(caPageCars.find(car=>car._id===id))', BOTH_ID)
        expect(self.page.locator('#detailOverlay')).to_contain_text('Satış şərti')
        expect(self.page.locator('#detailOverlay')).to_contain_text('Kredit · Barter')

    def test_saved_search_stores_and_restores_sale_type_to_home_and_filter(self):
        self.go(); self.sign_in()
        self.tab('barter').click(); self.wait_browse(2, 'barter')
        self.page.evaluate('caToggleFilters(true)')
        self.page.locator('#caSaveSearchLaunch').click()
        self.page.locator('#caSearchName').fill('Barter axtarışım')
        self.page.locator('#caMarketSubmit').click()
        for _ in range(200):
            if self.backend.calls_for('ca_save_search'):
                break
            self.page.wait_for_timeout(10)
        call = self.backend.calls_for('ca_save_search')[-1]
        self.assertEqual(call['body']['p_filters']['saleType'], 'barter')
        self.page.locator('#caMarketClose').click()
        self.page.evaluate('async()=>{openCabinet();await caFetchMyListings();renderCabinet()}')
        search = self.page.locator('[data-search-id="'+SEARCH_ID+'"]')
        expect(search).to_be_visible()
        self.page.evaluate('clearCarSearch()'); self.wait_browse(3, '')
        search.locator('[data-ca-search-apply]').click()
        self.page.wait_for_function('currentSearch?.saleType==="barter"&&!caBrowseState.loading')
        expect(self.page.locator('#caSaleType')).to_have_value('barter')
        expect(self.tab('barter')).to_have_attribute('aria-pressed', 'true')
        self.assertEqual(self.backend.sale_browse_calls[-1]['p_page'], 1)

    def test_failed_save_keeps_sale_choices_and_reuses_uploaded_photo_on_retry(self):
        self.backend.fail_save = True
        self.go(); self.new_listing(); self.choose(['credit', 'barter']); self.submit()
        self.assertEqual(self.selected(), ['credit', 'barter'])
        self.assertEqual(len(self.backend.uploads), 1)
        expect(self.page.locator('#listingFeedback')).to_be_visible()
        self.page.locator('#listingFeedbackClose').click()
        self.backend.fail_save = False
        self.submit()
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertEqual([row['ca_data']['saleOptions'] for row in self.backend.saves],
                         [['credit', 'barter'], ['credit', 'barter']])
        self.assertEqual(len({row['ca_data']['_submission_id'] for row in self.backend.saves}), 1)

    def test_uncertain_create_resumes_edit_without_losing_new_sale_choices(self):
        from test_submission_retry_browser import RetryBackend
        self.page.unroute('**/*', self.backend.route)
        self.backend = RetryBackend()
        self.page.route('**/*', self.backend.route)
        self.backend.abort_response = True
        self.backend.fail_lookup = True
        self.go(); self.new_listing(); self.submit()
        expect(self.page.locator('#listingFeedback')).to_be_visible()
        self.assertEqual(len(self.backend.created), 1)
        self.assertEqual(self.backend.created[0]['ca_data']['saleOptions'], ['cash'])
        self.page.locator('#listingFeedbackClose').click()
        self.choose(['credit', 'barter'])
        self.backend.fail_lookup = False
        self.submit()
        expect(self.page.locator('#listingFeedbackText')).to_contain_text('Yeni dəyişikliklərin formadadır')
        self.assertEqual(self.selected(), ['credit', 'barter'])
        self.assertEqual(self.page.evaluate('editingCarId'), self.backend.created[0]['id'])
        self.page.locator('#listingFeedbackClose').click()
        self.backend.abort_response = False
        self.submit()
        self.assertEqual(len(self.backend.created), 1)
        self.assertEqual(self.backend.created[0]['ca_data']['saleOptions'], ['credit', 'barter'])
        self.assertEqual(len(self.backend.uploads), 1)
        self.assertEqual(self.backend.package_creates, [])

    def test_320px_sale_controls_fit_without_horizontal_overflow(self):
        self.page.set_viewport_size({'width':320, 'height':780})
        self.go()
        self.page.locator('#caSaleTypeTabs').scroll_into_view_if_needed()
        bounds = self.page.locator('#caSaleTypeTabs button').evaluate_all('''buttons=>buttons.map(n=>{
            const b=n.getBoundingClientRect();return {left:b.left,right:b.right,width:b.width,height:b.height};})''')
        self.assertEqual(len(bounds), 4)
        for rect in bounds:
            self.assertGreaterEqual(rect['left'], 0)
            self.assertLessEqual(rect['right'], 321)
            self.assertGreaterEqual(rect['height'], 40)
        self.tab('credit').click(); self.wait_browse(2, 'credit')
        self.new_listing()
        self.page.locator('#caSaleOptions').scroll_into_view_if_needed()
        rect = self.page.locator('#caSaleOptions').bounding_box()
        self.assertGreaterEqual(rect['x'], 0)
        self.assertLessEqual(rect['x']+rect['width'], 321)
        self.choose(['credit', 'barter'])
        self.assertEqual(self.selected(), ['credit', 'barter'])
        self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth+1'))


if __name__ == '__main__':
    unittest.main()
