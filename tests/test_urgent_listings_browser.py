"""Urgent package and two-column regressions with all HTTP intercepted.

These fixtures exercise the browser contract, not a bank or live publication.
The SQL authorization/lifecycle suite verifies the backend independently.
"""
import copy
from datetime import datetime, timezone
import json
import math
import os
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright
from test_cards_browser import PUBLIC_COLUMNS
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, OWNED_ID, owned_row
from test_sale_options_browser import SaleOptionsBackend, options
from test_package_feedback_browser import PAID_ID, REQUEST_ID, NEW_ID, PNG
from test_marketplace_browser import SEARCH_ID

URGENT_ID = '90909090-9090-4090-8090-000000000001'
OLD_URGENT_ID = '90909090-9090-4090-8090-000000000002'
SPOOF_ID = '90909090-9090-4090-8090-000000000003'
NEW_REQUEST_ID = '90909090-9090-4090-8090-000000000004'


def package(row):
    if row.get('veziyyet') != 'aktiv' or row.get('is_sold'):
        return 'Pulsuz'
    value = row.get('paket_adi', 'Pulsuz')
    if value == 'Tecili':
        return value
    if value in ('VIP', 'Premium', 'Standart') and str(row.get('paket_bitir', '')) > datetime.now(timezone.utc).isoformat():
        return value
    return 'Pulsuz'


class UrgentBackend(SaleOptionsBackend):
    def __init__(self):
        super().__init__()
        self.urgent_browse_calls = []
        self.created_requests = []
        for id, name, end, sale in (
            (URGENT_ID, 'Urgent-current', None, ['cash', 'barter']),
            (OLD_URGENT_ID, 'Urgent-stale-date', '2000-01-01T00:00:00Z', ['credit']),
        ):
            row = owned_row()
            row.update(id=id, satici_id=OTHER_OWNER, model=name, paket_adi='Tecili', paket_bitir=end,
                       paket_baslayir='2000-01-01T00:00:00Z', tesdiq_tarixi='2000-01-01T00:00:00Z')
            row['ca_data'].update(model=name, saleOptions=sale, pack='Pulsuz', requestedPackage='')
            self.rows.append(row)
        spoof = owned_row()
        spoof.update(id=SPOOF_ID, satici_id=OTHER_OWNER, model='Spoof-urgent', paket_adi='Pulsuz')
        spoof['ca_data'].update(model='Spoof-urgent', pack='Tecili', requestedPackage='Təcili — 1 AZN / satılanadək')
        self.rows.append(spoof)
        pending = owned_row()
        pending.update(id=PAID_ID, marka='LADA', model='Urgent-pending', veziyyet='gozlemede', paket_adi='Pulsuz', paket_bitir=None)
        pending['ca_data'].update(make='LADA', model='Urgent-pending', pack='Pulsuz', requestedPackage='Təcili — 1 AZN / satılanadək')
        self.rows.append(pending)
        self.admin_rows[0].update(requested_package='Tecili', approved_package='Pulsuz', package_status='pending')
        next(r for r in self.payments if r['id'] == REQUEST_ID)['paket_adi'] = 'Tecili'

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        if parsed.path.startswith('/storage/v1/object/'):
            return super().route(route)
        body = req.post_data_json if req.post_data else None
        name = parsed.path.rsplit('/', 1)[-1]
        def send(data, status=200):
            route.fulfill(status=status, content_type='application/json', body=json.dumps(data))
        if parsed.path == '/rest/v1/rpc/ca_browse_listings':
            assert req.method == 'POST'
            filters = body['p_filters']
            assert type(filters.get('urgent', False)) is bool
            self.urgent_browse_calls.append(copy.deepcopy(body))
            self.sale_browse_calls.append(copy.deepcopy(body))
            self.calls.append(dict(method=req.method, path=parsed.path, query=parse_qs(parsed.query),
                                   headers=dict(req.headers), body=copy.deepcopy(body)))
            active = [r for r in self.rows if r['veziyyet'] == 'aktiv' and not r.get('is_sold')]
            sale = filters.get('saleType', '')
            sale_rows = [r for r in active if not sale or sale in options(r)]
            selected = [r for r in sale_rows if not filters.get('urgent') or package(r) == 'Tecili']
            for key, field in [('make', 'marka'), ('model', 'model'), ('city', 'seher')]:
                if filters.get(key):
                    selected = [r for r in selected if str(filters[key]).casefold() in str(r.get(field, '')).casefold()]
            if filters.get('priceMax') is not None:
                selected = [r for r in selected if r['qiymet'] <= filters['priceMax']]
            if filters.get('pack', 'all') not in ('', 'all'):
                selected = [r for r in selected if package(r) == filters['pack']]
            rank = {'VIP':0, 'Premium':1, 'Standart':2, 'Tecili':3, 'Pulsuz':4}
            selected.sort(key=lambda r:(rank[package(r)], -r['qiymet'] if filters.get('sort')=='priceDesc' else r['qiymet'] if filters.get('sort')=='priceAsc' else 0))
            page, size = body['p_page'], body['p_page_size']
            project = lambda r:{k:v for k,v in r.items() if k in PUBLIC_COLUMNS}
            send(dict(items=[project(r) for r in selected[(page-1)*size:page*size]], total=len(selected), page=page,
                      page_size=size, total_pages=math.ceil(len(selected)/size),
                      vip_items=[] if filters.get('urgent') else [project(r) for r in sale_rows if package(r)=='VIP'][:6],
                      today_approved=self.today_approved))
            return
        if parsed.path == '/rest/v1/elanlar' and req.method == 'POST':
            assert req.headers.get('authorization') == 'Bearer seller-token'
            assert body['satici_id'] == OWNER and 'paket_adi' not in body
            self.saves.append(copy.deepcopy(body))
            if self.fail_save:
                send({'message':'Synthetic save failure'}, 503); return
            row = dict(body, id=NEW_ID, paket_adi='Pulsuz', yaradildi='2026-11-19T00:00:00Z')
            self.rows.append(row)
            if '1 AZN' in body['ca_data'].get('requestedPackage', ''):
                self.created_requests.append(dict(id=NEW_REQUEST_ID, elan_id=NEW_ID, paket_adi='Tecili', odenis_veziyyeti='gozlemede'))
            send([{'id':NEW_ID}]); return
        if parsed.path == '/rest/v1/elanlar' and req.method == 'PATCH' and body != {'veziyyet':'silindi'}:
            if '1 AZN' in body.get('ca_data', {}).get('requestedPackage', ''):
                self.created_requests.append(dict(id=NEW_REQUEST_ID, paket_adi='Tecili', odenis_veziyyeti='gozlemede'))
        if name == 'ca_admin_paket_tesdiq':
            assert req.headers.get('authorization') == 'Bearer admin-token'
            assert body == {'p_sorgu_id':REQUEST_ID}
            self.admin_calls.append(dict(name=name, body=copy.deepcopy(body), admin=True))
            payment = next(r for r in self.payments if r['id'] == REQUEST_ID)
            payment['odenis_veziyyeti'] = 'tesdiqlendi'
            target = next(r for r in self.admin_rows if r['id'] == PAID_ID)
            target.update(package_status='confirmed', approved_package='Tecili')
            # Payment approval is independent of publication and start dates.
            send(None); return
        if name == 'ca_admin_status' and body['p_id'] == PAID_ID:
            assert req.headers.get('authorization') == 'Bearer admin-token'
            self.admin_calls.append(dict(name=name, body=copy.deepcopy(body), admin=True))
            info = next(r for r in self.admin_rows if r['id'] == PAID_ID)
            if body['p_status']=='aktiv' and info['package_status'] != 'confirmed':
                send({'message':'Paket təsdiqlənməyib'}, 409); return
            info['veziyyet'] = body['p_status']
            row = next(r for r in self.rows if r['id'] == PAID_ID)
            row['veziyyet'] = body['p_status']
            if body['p_status']=='aktiv':
                row.update(paket_adi='Tecili', paket_baslayir='2026-11-19T00:00:00Z', paket_bitir=None)
            send(None); return
        super().route(route)


class UrgentListingsBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'), headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1280,'height':1000}, has_touch=True)
        self.context.set_default_timeout(5000)
        self.page = self.context.new_page(); self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>__alerts.push(String(m));window.confirm=()=>true')
        self.backend=UrgentBackend(); self.page.route('**/*',self.backend.route)

    def tearDown(self):
        self.context.close(); self.assertFalse(self.errors,'Uncaught browser error')
        self.assertFalse([r for r in self.backend.calls if '/checkout' in r['path'] or '/bank' in r['path']])

    def go(self):
        self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')

    def sign_in(self, admin=False):
        self.page.evaluate('''async token=>await caPersistSession({access_token:token,expires_at:4102444800,
            user:{id:%s,email:'offline@example.invalid',user_metadata:{telefon:'+994000000000'}}})''' % json.dumps(OWNER), 'admin-token' if admin else 'seller-token')

    def select_urgent(self):
        value=self.page.locator('#listingForm [name=package] option').filter(has_text='1 AZN').evaluate('option=>option.value')
        self.page.locator('#listingForm [name=package]').select_option(value)

    def new_listing(self):
        self.sign_in();self.page.evaluate('openSellPage()')
        fields={k:v for k,v in owned_row()['ca_data'].items() if k not in ('photos','photo','equipment','pack','saleOptions')}
        self.page.evaluate('''data=>{const f=document.getElementById('listingForm');for(const[k,v]of Object.entries(data)){
            const n=f.elements.namedItem(k);if(n&&'value'in n){n.disabled=false;n.value=String(v)}}}''',fields)
        self.select_urgent()
        self.page.locator('#photos-front').set_input_files(dict(name='synthetic.png',mimeType='image/png',buffer=PNG))

    def submit(self):
        self.assertTrue(self.page.locator('#listingForm').evaluate('f=>f.checkValidity()'))
        self.page.locator('#listingForm').evaluate('f=>f.requestSubmit()')
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')

    def wait_browse(self,n):
        for _ in range(250):
            if len(self.backend.urgent_browse_calls)>=n:
                self.page.wait_for_function('!caBrowseState.loading');return self.backend.urgent_browse_calls[-1]
            self.page.wait_for_timeout(10)
        self.fail('Expected urgent browse request')

    def urgent(self):
        return self.page.locator('#caUrgentTabs button[data-urgent="true"]')

    def card(self,id=URGENT_ID):
        model=next(r for r in self.backend.rows if r['id']==id)['model']
        return self.page.locator('#allGrid .car-card').filter(has_text=model)

    def open_admin(self):
        self.sign_in(True);self.page.evaluate('async()=>await caAdminOpen()')
        expect(self.page.locator('#caAdminList [data-ad-row-id="'+PAID_ID+'"]')).to_be_visible()

    def pending_admin(self):
        return self.page.locator('#caAdminList [data-ad-row-id="'+PAID_ID+'"]')

    def payment(self):
        self.pending_admin().locator('[data-package-request-id="'+REQUEST_ID+'"]').click()
        target=self.page.locator('#caPayList [data-pay-row-id="'+REQUEST_ID+'"]');expect(target).to_be_visible();return target

    def test_selector_price_and_duration_are_explicit(self):
        self.go();option=self.page.locator('#listingForm [name=package] option').filter(has_text='1 AZN')
        expect(option).to_have_count(1);self.assertIn('Təcili',option.inner_text());self.assertIn('satılanadək',option.inner_text())

    def test_new_urgent_submission_requests_package_without_publishing_or_charging(self):
        self.go();self.new_listing();self.submit()
        self.assertEqual(len(self.backend.saves),1);self.assertEqual(len(self.backend.created_requests),1)
        self.assertIn('1 AZN',self.backend.saves[0]['ca_data']['requestedPackage'])
        self.assertNotIn('paket_adi',self.backend.saves[0]);self.assertEqual(self.backend.rows[-1]['paket_adi'],'Pulsuz')
        self.assertEqual(self.backend.rows[-1]['veziyyet'],'gozlemede')
        expect(self.page.locator('#listingFeedbackText')).to_contain_text('Təcili')
        self.assertFalse(self.backend.admin_calls)

    def test_edit_urgent_request_preserves_current_vip_and_photos_until_admin_decision(self):
        before=copy.deepcopy(self.backend.rows[0]);self.go();self.sign_in()
        self.page.evaluate('async()=>await caFetchMyListings()');self.page.evaluate('id=>editCar(id)',OWNED_ID)
        self.select_urgent();self.submit()
        row=next(r for r in self.backend.rows if r['id']==OWNED_ID)
        self.assertEqual(row['paket_adi'],'VIP');self.assertEqual(row['paket_bitir'],before['paket_bitir'])
        self.assertEqual(row['sekiller'],before['sekiller']);self.assertEqual(self.backend.uploads,[])
        self.assertEqual(len(self.backend.created_requests),1)

    def test_pending_urgent_admin_badge_and_exact_payment_jump(self):
        self.go();self.open_admin();card=self.pending_admin()
        expect(card.locator('.ca-package-badge')).to_contain_text('Təcili')
        expect(card.locator('button[data-status="aktiv"]')).to_be_disabled()
        target=self.payment();expect(target).to_contain_text('Təcili')
        self.assertEqual(self.page.locator('#caPaySearch').input_value(),REQUEST_ID)
        self.assertEqual(self.page.locator('#caPayList article').count(),1)

    def test_payment_approval_alone_does_not_publish_or_show_urgent_badge(self):
        self.go();self.open_admin();self.payment().locator('[data-pay-action=approve]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Dəyişiklik saxlanıldı")')
        self.assertFalse([c for c in self.backend.admin_calls if c['name']=='ca_admin_status'])
        self.assertEqual(next(r for r in self.backend.rows if r['id']==PAID_ID)['veziyyet'],'gozlemede')
        self.assertNotIn(PAID_ID,self.page.evaluate('caPageCars.map(r=>r._id)'))

    def test_approved_then_published_urgent_gets_green_badge_and_null_end_date(self):
        self.go();self.open_admin();self.payment().locator('[data-pay-action=approve]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Dəyişiklik saxlanıldı")')
        self.pending_admin().locator('button[data-status=aktiv]').click()
        self.page.wait_for_function('document.getElementById("caAdminActionMsg").textContent.includes("Dəyişiklik saxlanıldı")')
        row=next(r for r in self.backend.rows if r['id']==PAID_ID)
        self.assertEqual(row['paket_adi'],'Tecili');self.assertIsNone(row['paket_bitir'])
        self.page.evaluate('caAdminClose()')
        card=self.page.locator('#allGrid .car-card').filter(has_text='Urgent-pending')
        expect(card.locator('.ca-urgent-badge')).to_have_text('TƏCİLİ')

    def test_until_sold_package_does_not_expire_with_calendar_or_stale_end_date(self):
        self.go();car=self.page.evaluate('id=>caPageCars.find(c=>c._id===id)',OLD_URGENT_ID)
        self.assertEqual(car['pack'],'Tecili');expect(self.card(OLD_URGENT_ID).locator('.ca-urgent-badge')).to_be_visible()

    def test_requested_or_form_package_cannot_forge_public_urgent_badge(self):
        self.go();expect(self.card(SPOOF_ID).locator('.ca-urgent-badge')).to_have_count(0)
        self.assertNotIn(PAID_ID,self.page.evaluate('caPageCars.map(c=>c._id)'))

    def test_sold_urgent_ad_disappears_from_public_cards(self):
        self.backend.rows[0].update(paket_adi='Tecili',paket_bitir=None)
        self.go();self.sign_in();self.page.evaluate('openCabinet()')
        self.page.wait_for_function('caPrivateState.ownLoaded')
        self.page.locator('#cabinetList [data-ca-sold="'+OWNED_ID+'"]').click()
        self.page.locator('#caMarketSubmit').click()
        self.page.wait_for_function('id=>caOwnCars.some(c=>c.isSold)&&!caBrowseState.loading&&!caPageCars.some(c=>c._id===id)',arg=OWNED_ID)
        self.assertNotIn(OWNED_ID,self.page.evaluate('caPageCars.map(c=>c._id)'))

    def test_main_urgent_tab_resets_package_and_shows_only_urgent(self):
        self.go();self.page.evaluate('currentFilter="VIP"');before=len(self.backend.urgent_browse_calls)
        self.urgent().click();call=self.wait_browse(before+1)
        self.assertEqual(call['p_filters']['urgent'],True);self.assertEqual(call['p_filters']['pack'],'all')
        self.assertEqual(set(self.page.evaluate('caPageCars.map(c=>c._id)')),{URGENT_ID,OLD_URGENT_ID})
        expect(self.page.locator('#caUrgentFilter')).to_have_value('true');expect(self.urgent()).to_have_attribute('aria-pressed','true')
        self.assertEqual(self.page.locator('#vipGrid .car-card').count(),0)

    def test_advanced_urgent_filter_and_clear_keep_home_selection_in_sync(self):
        self.go();self.page.evaluate('caToggleFilters(true)');before=len(self.backend.urgent_browse_calls)
        self.page.locator('#caUrgentFilter').select_option('true');self.wait_browse(before+1)
        expect(self.urgent()).to_have_attribute('aria-pressed','true')
        self.page.evaluate('clearCarSearch()');self.wait_browse(before+2)
        expect(self.page.locator('#caUrgentFilter')).to_have_value('');expect(self.urgent()).to_have_attribute('aria-pressed','false')

    def test_other_package_selection_clears_urgent_filter(self):
        self.go();self.urgent().click();self.wait_browse(2)
        self.page.locator('.pill').filter(has_text='Önə çıxarılan').click();call=self.wait_browse(3)
        self.assertFalse(call['p_filters'].get('urgent',False));self.assertEqual(call['p_filters']['pack'],'VIP')
        expect(self.urgent()).to_have_attribute('aria-pressed','false')

    def test_urgent_combines_with_sale_type_city_price_and_sort(self):
        self.go();self.page.evaluate('''async()=>{document.getElementById('caSaleType').value='credit';
          document.getElementById('searchCity').value='Bakı';document.getElementById('caPriceMax').value='50000';
          document.getElementById('sortListings').value='priceDesc';await searchCars()}''')
        self.urgent().click();call=self.wait_browse(3)
        self.assertTrue(call['p_filters']['urgent']);self.assertEqual(call['p_filters']['saleType'],'credit')
        self.assertEqual(call['p_filters']['city'],'Bakı');self.assertEqual(call['p_filters']['priceMax'],50000)
        self.assertEqual(call['p_filters']['sort'],'priceDesc')
        self.assertEqual(self.page.evaluate('caPageCars.map(c=>c._id)'),[OLD_URGENT_ID])

    def test_saved_search_keeps_boolean_urgent_and_restores_both_controls(self):
        self.go();self.sign_in();self.urgent().click();self.wait_browse(2)
        self.page.evaluate('caToggleFilters(true)');self.page.locator('#caSaveSearchLaunch').click()
        self.page.locator('#caSearchName').fill('Təcili avtomobil');self.page.locator('#caMarketSubmit').click()
        self.page.wait_for_function('document.getElementById("caMarketMessage").textContent.includes("saxlanıldı")')
        self.assertIs(self.backend.calls_for('ca_save_search')[-1]['body']['p_filters']['urgent'],True)
        self.page.locator('#caMarketClose').click();self.page.evaluate('openCabinet()')
        search=self.page.locator('[data-search-id="'+SEARCH_ID+'"]');expect(search).to_be_visible()
        self.page.evaluate('clearCarSearch()');self.wait_browse(3)
        search.locator('[data-ca-search-apply]').click();self.page.wait_for_function('currentSearch?.urgent===true&&!caBrowseState.loading')
        expect(self.urgent()).to_have_attribute('aria-pressed','true');expect(self.page.locator('#caUrgentFilter')).to_have_value('true')

    def test_browse_starts_at_page_one_when_urgent_selected(self):
        for n in range(26):
            row=copy.deepcopy(self.backend.rows[0]);row['id']=f'98989898-9898-4989-8989-{n:012d}';self.backend.rows.append(row)
        self.go();self.page.evaluate('async()=>await caFetchListings(2)');before=len(self.backend.urgent_browse_calls)
        self.assertEqual(self.page.evaluate('caBrowseState.page'),2)
        self.urgent().click();call=self.wait_browse(before+1)
        self.assertEqual(call['p_page'],1);self.assertEqual(self.page.evaluate('caBrowseState.page'),1)

    def test_two_columns_fit_at_all_sizes_with_full_metadata_and_usable_controls(self):
        row=next(r for r in self.backend.rows if r['id']==URGENT_ID)
        row.update(marka='Mercedes-Benz',model='Sprinter Long-Long-Long-Version',qiymet=9999999.99)
        row['ca_data'].update(make=row['marka'],model=row['model'],saleOptions=['cash','credit','barter'])
        self.go()
        for width in (320,375,768,1440):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width':width,'height':900})
                self.page.locator('#allGrid').scroll_into_view_if_needed()
                geometry=self.page.locator('#allGrid').evaluate('''grid=>{const g=grid.getBoundingClientRect();
                  return {columns:getComputedStyle(grid).gridTemplateColumns.split(' ').length,left:g.left,right:g.right,
                  cards:[...grid.querySelectorAll('.car-card')].map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,
                    overflow:n.scrollWidth>n.clientWidth+1,buttons:[...n.querySelectorAll('button')].map(b=>{const x=b.getBoundingClientRect();return {left:x.left,right:x.right,height:x.height}})}})}}''')
                self.assertEqual(geometry['columns'],2)
                self.assertGreaterEqual(geometry['left'],0);self.assertLessEqual(geometry['right'],width+1)
                for card in geometry['cards']:
                    self.assertFalse(card['overflow'])
                    for button in card['buttons']:
                        self.assertGreaterEqual(button['left'],card['left']-1);self.assertLessEqual(button['right'],card['right']+1)
                        self.assertGreaterEqual(button['height'],32)
                self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth+1'))
                card=self.card(URGENT_ID)
                self.assertIn(row['model'],card.inner_text());self.assertIn('Nağd',card.inner_text());self.assertIn('Kredit',card.inner_text());self.assertIn('Barter',card.inner_text())

    def test_mobile_favorite_compare_and_details_work_in_two_columns(self):
        self.page.set_viewport_size({'width':320,'height':850});self.go();self.sign_in();card=self.card()
        card.locator('.favorite-btn').click();expect(card.locator('.favorite-btn')).to_have_class('favorite-btn is-favorite')
        card.locator('.ca-compare').click();expect(self.page.locator('#caCompareCount')).to_have_text('1')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        card.locator('.ca-visible-car-name').click();expect(self.page.locator('#detailOverlay')).to_be_visible()
        expect(self.page.locator('#detailSpecs')).to_contain_text('Təcili')
        self.page.locator('#detailOverlay .detail-close').click();expect(self.page.locator('#detailOverlay')).not_to_be_visible()

    def test_failed_urgent_submission_does_not_show_false_success_or_lose_request(self):
        self.backend.fail_save=True;self.go();self.new_listing();self.submit()
        self.assertEqual(self.backend.created_requests,[])
        expect(self.page.locator('#listingFeedbackText')).to_have_attribute('role','alert')
        self.assertIn('1 AZN',self.page.locator('#listingForm [name=package]').input_value())
        expect(self.page.locator('#submitListingBtn')).to_be_enabled()


if __name__=='__main__':
    unittest.main()
