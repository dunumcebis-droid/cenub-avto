"""Offline listing-management regressions; every HTTP request is intercepted.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_listing_management_browser.py' -v
Requires Python Playwright and Chromium. No real database/storage writes occur.
Mocked denials verify client behavior; database RLS is checked separately in a
rolled-back SQL transaction, not inferred from these mocks.
"""
import copy
import json
import mimetypes
import os
from pathlib import Path
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

from playwright.sync_api import sync_playwright
from test_cards_browser import browse_fixture_response, market_read_fixture_response, MARKET_READ_RPC_NAMES

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:8766/'
OWNER = '11111111-1111-4111-8111-111111111111'
OTHER_OWNER = '22222222-2222-4222-8222-222222222222'
OWNED_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
OTHER_ID = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
PHOTO_ORIGIN = 'https://fixture.invalid/'
GROUPS = {
    'front': [PHOTO_ORIGIN+'front-1.svg', PHOTO_ORIGIN+'front-2.svg'],
    'rear': [PHOTO_ORIGIN+'rear-1.svg', PHOTO_ORIGIN+'rear-2.svg'],
    'side': [PHOTO_ORIGIN+'side-1.svg', PHOTO_ORIGIN+'side-2.svg'],
    'interior': [PHOTO_ORIGIN+'interior.svg'],
    'engine': [PHOTO_ORIGIN+'engine.svg'],
    'other': [PHOTO_ORIGIN+'other.svg'],
}
EQUIPMENT = ['ABS', 'Bluetooth', 'Arxa kamera']


def safe_local_asset(url):
    """Permit only this local origin's index and resolved assets inside ROOT."""
    parsed = urlsplit(url)
    if (parsed.scheme, parsed.netloc) != ('http', '127.0.0.1:8766'):
        return None
    path = unquote(parsed.path)
    if '\x00' in path or '\\' in path:
        return None
    candidate = (ROOT / (path.lstrip('/') or 'index.html')).resolve()
    try:
        relative = candidate.relative_to(ROOT)
    except ValueError:
        return None
    if relative == Path('index.html'):
        return candidate
    if not relative.parts or relative.parts[0] != 'assets':
        return None
    if candidate.suffix.lower() not in {'.js','.css','.jpg','.jpeg','.png','.webp','.svg','.gif','.avif','.ico','.woff','.woff2','.ttf'}:
        return None
    return candidate


def owned_row():
    groups = copy.deepcopy(GROUPS)
    snapshot = dict(make='BMW', model='530', generation='G30', year=2017,
                    price=42000, city='Bakı', mileage='50000', fuel='Benzin',
                    gear='Avtomat', engine='2.0 L benzin', body='Sedan', color='Qara',
                    drive='Arxa ötürücü', condition='Yaxşı', owners='Birinci',
                    accident='Qəzasız', phone='+994000000000', vehicleType='Minik avtomobili',
                    horsepower='252', market='Avropa', seats='5', vehicleState='Sürülmüş',
                    equipment=EQUIPMENT[:], description='Offline synthetic test listing',
                    photos=groups, photo=groups['front'][0], pack='VIP')
    return dict(id=OWNED_ID, satici_id=OWNER, marka='BMW', model='530', il=2017,
                qiymet=42000, yurus=50000, seher='Bakı', tesvir=snapshot['description'],
                veziyyet='aktiv', yaradildi='2026-01-01T00:00:00Z',
                neqliyyat_novu='Minik avtomobili', nesil='G30', ban_novu='Sedan',
                yanacaq='Benzin', suretler_qutusu='Avtomat', muherrik_hecmi=2,
                at_gucu=252, reng='Qara', bazar_ucun='Avropa', oturacaq_sayi=5,
                techizat=EQUIPMENT[:], sekiller=[url for group in groups.values() for url in group],
                telefon='+994000000000', ca_data=snapshot, paket_adi='VIP',
                paket_baslayir='2026-01-01T00:00:00Z', paket_bitir='2099-01-01T00:00:00Z')


def default_rows():
    owned = owned_row()
    other = copy.deepcopy(owned)
    other.update(id=OTHER_ID, satici_id=OTHER_OWNER, marka='Toyota', model='Corolla', paket_adi='Pulsuz')
    other['ca_data'].update(make='Toyota', model='Corolla', pack='Pulsuz')
    return [owned, other]


class OfflineBackend:
    def __init__(self, rows=None):
        self.rows = copy.deepcopy(default_rows() if rows is None else rows)
        self.calls = []
        self.empty_update = False
        self.empty_delete = False
        self.today_approved = 1
        self.delay_owner_reads = 0
        self.pending_owner_reads = []
        self.delay_update_responses = 0
        self.pending_updates = []

    @property
    def writes(self):
        return [call for call in self.calls if call['method'] in ('POST','PATCH','DELETE') and
                call['path'] not in {'/rest/v1/rpc/'+name for name in MARKET_READ_RPC_NAMES}]

    def route(self, route):
        if urlsplit(route.request.url).path == '/functions/v1/ca-photo-review/status':
            route.fulfill(content_type='application/json', body='{"enabled":false,"configured":false}')
            return
        req = route.request
        local = safe_local_asset(req.url)
        if local is not None:
            if req.method != 'GET' or not local.is_file():
                route.fulfill(status=404, body='')
            else:
                route.fulfill(content_type=mimetypes.guess_type(local.name)[0] or 'application/octet-stream', body=local.read_bytes())
            return
        if req.url.startswith(PHOTO_ORIGIN):
            route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="600" height="400" fill="#87a9b0"/></svg>')
            return
        parsed = urlsplit(req.url)
        if parsed.path == '/auth/v1/logout' and req.method == 'POST':
            route.fulfill(status=204,body='')
            return
        if not parsed.path.startswith('/rest/v1/'):
            route.abort()
            return
        query = parse_qs(parsed.query)
        body = req.post_data_json if req.post_data else None
        call = dict(method=req.method, path=parsed.path, query=query,
                    headers=dict(req.headers), body=body)
        self.calls.append(call)

        def send(payload, status=200, headers=None):
            route.fulfill(status=status, content_type='application/json',
                          body=json.dumps(payload), headers=headers or {})

        if parsed.path.startswith('/rest/v1/rpc/') and parsed.path.rsplit('/',1)[-1] in MARKET_READ_RPC_NAMES:
            assert req.method == 'POST'
            send(market_read_fixture_response(parsed.path.rsplit('/',1)[-1], body, req.headers.get('authorization')))
            return

        if parsed.path == '/rest/v1/rpc/ca_browse_listings' and req.method == 'POST':
            send(browse_fixture_response(self.rows, body, today_approved=self.today_approved))
            return
        if parsed.path == '/rest/v1/elanlar' and req.method == 'GET':
            columns = query.get('select', [''])[0].split(',')
            assert '*' not in columns, 'Public listing reads must remain scoped'
            assert 'paket_tesdiq_qeydi' not in columns, 'Internal approval notes stay private'
            rows = self.rows
            for key in ('id','satici_id','veziyyet'):
                if key in query and query[key][0].startswith('eq.'):
                    rows = [row for row in rows if str(row.get(key)) == query[key][0][3:]]
            offset = int(query.get('offset', ['0'])[0])
            limit = int(query.get('limit', ['500'])[0])
            if 'range' in req.headers:
                left, right = req.headers['range'].split('-')
                offset, limit = int(left), int(right)-int(left)+1
            page = rows[offset:offset+limit]
            projected = [{key: value for key,value in row.items() if key in columns} for row in page]
            content_range = f'{offset}-{offset+len(page)-1}/{len(rows)}' if page else f'*/{len(rows)}'
            if self.delay_owner_reads and 'satici_id' in query:
                self.delay_owner_reads -= 1
                self.pending_owner_reads.append((route,copy.deepcopy(projected),{'Content-Range':content_range}))
                return
            send(projected, headers={'Content-Range':content_range})
            return
        if parsed.path == '/rest/v1/elanlar' and req.method in ('PATCH','DELETE'):
            id_filter = query.get('id', [''])[0]
            owner_filter = query.get('satici_id', [''])[0]
            row = next((item for item in self.rows if 'eq.'+item['id']==id_filter and
                        'eq.'+item['satici_id']==owner_filter and item['satici_id']==OWNER), None)
            archiving = req.method=='PATCH' and body=={'veziyyet':'silindi'}
            empty = self.empty_delete if archiving or req.method=='DELETE' else self.empty_update
            if row is None or empty:
                send([])
                return
            if req.method == 'PATCH':
                row.update(body)
            else:
                self.rows.remove(row)
            if self.delay_update_responses and req.method=='PATCH' and not archiving:
                self.delay_update_responses -= 1
                self.pending_updates.append((route,[{'id':row['id']}]))
                return
            if 'return=representation' in req.headers.get('prefer', ''):
                send([{'id':row['id']}])
            else:
                route.fulfill(status=204, body='')
            return
        if parsed.path.startswith('/rest/v1/rpc/'):
            # Tests may inspect these calls but no real function is invoked.
            send(None)
            return
        route.abort()


class AssetPathTests(unittest.TestCase):
    def test_local_assets_cannot_escape_repository(self):
        for path in ('../README.md', '%2e%2e/README.md',
                     'assets/%2e%2e/%2e%2e/etc/passwd', '.git/config',
                     'assets/js/%2e%2e/%2e%2e/%2e%2e/.env', 'assets/js/%00main.js'):
            self.assertIsNone(safe_local_asset(ORIGIN+path), path)
        self.assertIsNone(safe_local_asset('https://external.invalid/assets/js/01-main.js'))
        self.assertEqual(safe_local_asset(ORIGIN+'assets/js/01-main.js'), ROOT/'assets/js/01-main.js')


class ListingManagementBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'), headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1280,'height':1000})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error:self.errors.append(str(error)))
        self.page.add_init_script("window.__alerts=[];window.alert=message=>window.__alerts.push(String(message));window.confirm=()=>true")
        self.backend = OfflineBackend()
        self.page.route('**/*',self.backend.route)
        self.page.goto(ORIGIN,wait_until='load')
        self.page.wait_for_function('typeof caFetchListings === "function" && caRemoteCars.length===2')
        self.page.evaluate('''async owner=>{
            currentUser={id:owner,email:'offline@example.invalid',phone:'+994000000000'};
            caSession={access_token:'offline-token',expires_at:4102444800,user:{id:owner}};
            await caFetchMyListings();renderCabinet();
        }''',OWNER)

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors,'Uncaught browser errors')

    def open_edit(self):
        self.page.evaluate('id=>editCar(id)',OWNED_ID)
        self.assertTrue(self.page.locator('#listingForm').is_visible())

    def submit(self):
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'),'Restored edit form must remain valid')
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('document.getElementById("submitListingBtn").disabled===false')

    def test_edit_restores_equipment_and_nine_photo_categories(self):
        self.open_edit()
        checked = self.page.locator('#listingForm input[name="equipment"]:checked').evaluate_all('els=>els.map(e=>e.value)')
        self.assertEqual(set(checked),set(EQUIPMENT))
        groups = self.page.evaluate('editingOriginalPhotos')
        self.assertEqual(groups,GROUPS,'Editing must retain the original nine photos and known categories')
        self.assertEqual(self.page.locator('#listingForm .photo-preview img').count(),9)

    def test_metadata_save_preserves_photos_equipment_and_blank_mileage(self):
        self.open_edit()
        self.page.locator('#listingForm [name="price"]').fill('43000')
        self.page.locator('#listingForm [name="mileage"]').fill('')
        self.submit()
        writes = [call for call in self.backend.writes if call['path']=='/rest/v1/elanlar']
        self.assertEqual(len(writes),1,'A metadata edit must make exactly one verified PATCH')
        write = writes[0]
        self.assertEqual(write['method'],'PATCH')
        self.assertEqual(write['query'].get('id'),['eq.'+OWNED_ID])
        self.assertEqual(write['query'].get('satici_id'),['eq.'+OWNER])
        self.assertIn('return=representation',write['headers'].get('prefer',''))
        self.assertIsNone(write['body']['yurus'],'Blank mileage is unknown, not zero')
        self.assertEqual(set(write['body']['techizat']),set(EQUIPMENT))
        self.assertCountEqual(write['body']['sekiller'],[url for group in GROUPS.values() for url in group])
        self.assertEqual(write['body']['ca_data']['photos'],GROUPS)
        self.assertFalse([call for call in self.backend.writes if '/rpc/ca_paket_sorgusu_yarat' in call['path']],
                         'An unchanged paid package must not create another request')
        self.assertIn(write['body']['ca_data'].get('requestedPackage'),(None,''))
        self.assertIsNone(self.page.evaluate('editingCarId'))
        self.assertEqual(self.page.evaluate('myCars()[0].price'),43000)

    def test_zero_row_update_keeps_edit_draft_and_reports_failure(self):
        self.backend.empty_update = True
        self.open_edit()
        self.page.locator('#listingForm [name="price"]').fill('43000')
        self.submit()
        self.assertEqual(len([call for call in self.backend.writes if call['method']=='PATCH']),1)
        self.assertEqual(self.page.evaluate('editingCarId'),OWNED_ID)
        self.assertEqual(self.page.locator('#listingForm [name="price"]').input_value(),'43000')
        self.assertEqual(self.page.evaluate('myCars()[0].price'),42000)
        self.assertTrue(self.page.locator('#listingFeedback').is_visible(),'An update affecting zero rows must be reported')
        self.assertEqual(self.page.locator('#listingFeedback').get_attribute('data-kind'),'error')
        self.assertIn('göndərmək mümkün olmadı',self.page.locator('#listingFeedbackText').inner_text())
        self.assertFalse(self.page.evaluate('__alerts'),'Seller outcomes use site feedback rather than a native alert')

    def test_zero_row_archive_keeps_card_and_reports_failure(self):
        self.backend.empty_delete = True
        self.page.evaluate('id=>deleteCar(id)',OWNED_ID)
        self.page.wait_for_function('__alerts.length>0',timeout=5000)
        self.assertTrue(self.page.evaluate('id=>myCars().some(c=>c._id===id)',OWNED_ID))
        self.assertEqual(self.page.locator('#cabinetList .cabinet-card').count(),1)
        calls = [call for call in self.backend.writes if call['method']=='PATCH' and call['body']=={'veziyyet':'silindi'}]
        self.assertEqual(len(calls),1)
        self.assertFalse([call for call in self.backend.writes if call['method']=='DELETE'])

    def test_verified_archive_hides_only_owned_card_and_preserves_row_assets(self):
        self.page.evaluate('id=>deleteCar(id)',OWNED_ID)
        self.page.wait_for_function('id=>!myCars().some(c=>c._id===id)',arg=OWNED_ID)
        calls = [call for call in self.backend.writes if call['method']=='PATCH' and call['body']=={'veziyyet':'silindi'}]
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['query'].get('id'),['eq.'+OWNED_ID])
        self.assertEqual(calls[0]['query'].get('satici_id'),['eq.'+OWNER])
        self.assertIn('return=representation',calls[0]['headers'].get('prefer',''))
        self.assertTrue(any(row['id']==OTHER_ID for row in self.backend.rows))
        archived = next(row for row in self.backend.rows if row['id']==OWNED_ID)
        self.assertEqual(archived['veziyyet'],'silindi')
        self.assertEqual(archived['sekiller'],[url for group in GROUPS.values() for url in group])
        self.assertEqual(archived['paket_adi'],'VIP')
        self.assertFalse([call for call in self.backend.writes if call['method']=='DELETE'])

    def test_server_paging_reaches_listing_501_without_loading_all_rows(self):
        template = owned_row()
        self.backend.rows = []
        for i in range(501):
            row = copy.deepcopy(template)
            row.update(id=f'33333333-3333-4333-8333-{i:012d}',satici_id=OTHER_OWNER,model='Model'+str(i),paket_adi='Pulsuz',sekiller=[])
            row['ca_data'].update(model='Model'+str(i),photos={},photo=None,pack='Pulsuz')
            self.backend.rows.append(row)
        self.backend.calls.clear()
        self.page.evaluate('async ()=>await caFetchListings(1)')
        self.assertEqual(self.page.evaluate('caBrowseState.total'),501)
        self.assertEqual(self.page.evaluate('caBrowseState.totalPages'),21)
        self.assertEqual(self.page.locator('#allGrid .car-card').count(),24)
        self.page.locator('#caPageNext').click()
        self.page.wait_for_function('caBrowseState.page===2&&!caBrowseState.loading')
        self.assertEqual(self.page.locator('#allGrid .car-card').count(),24)
        self.page.evaluate('async ()=>await caFetchListings(21)')
        self.assertEqual(self.page.locator('#allGrid .car-card').count(),21)
        self.assertIn('Model500',self.page.locator('#allGrid').inner_text())
        self.assertTrue(self.page.locator('#caPageNext').is_disabled())
        self.assertFalse(self.page.locator('#caPagePrev').is_disabled())
        reads = [call for call in self.backend.calls if call['path']=='/rest/v1/rpc/ca_browse_listings']
        self.assertEqual([call['body']['p_page'] for call in reads],[1,2,21])
        self.assertTrue(all(call['body']['p_page_size']==24 for call in reads))
        self.assertLess(self.page.evaluate('caRemoteCars.length'),501,'The browser must not fetch every listing to show a later page')
        self.page.evaluate("""async()=>{
            document.getElementById('searchMake').value='BMW';
            document.getElementById('searchModel').value='Model500';
            await searchCars();
        }""")
        self.assertEqual(self.page.evaluate('caBrowseState.page'),1)
        self.assertEqual(self.page.evaluate('caBrowseState.total'),1)
        self.assertEqual(self.page.locator('#allGrid .car-card').count(),1)
        self.assertIn('Model500',self.page.locator('#allGrid').inner_text())

    def wait_for_pending(self, pending):
        for _ in range(100):
            if pending:
                return
            self.page.wait_for_timeout(10)
        self.fail('The deliberately delayed offline request did not start')

    def switch_to_second_account(self):
        self.page.evaluate("""async owner=>{
            await caPersistSession({access_token:'offline-b-token',expires_at:4102444800,
                user:{id:owner,email:'second@example.invalid',user_metadata:{telefon:'+994000000001'}}});
            openSellPage();
        }""",OTHER_OWNER)

    def release_update(self):
        route,payload=self.backend.pending_updates.pop(0)
        with self.page.expect_response(lambda response:response.request.method=='PATCH' and urlsplit(response.url).path=='/rest/v1/elanlar') as response:
            route.fulfill(status=200,content_type='application/json',body=json.dumps(payload))
        response.value.body()
        self.page.evaluate('async()=>await new Promise(requestAnimationFrame)')

    def test_old_owner_read_cannot_resurrect_confirmed_archive(self):
        self.backend.delay_owner_reads=1
        self.page.evaluate('()=>{window.__oldOwnerRead=caFetchMyListings()}')
        self.wait_for_pending(self.backend.pending_owner_reads)
        self.page.evaluate('async id=>await deleteCar(id)',OWNED_ID)
        self.assertFalse(self.page.evaluate('id=>myCars().some(car=>car._id===id)',OWNED_ID))
        route,payload,headers=self.backend.pending_owner_reads.pop(0)
        route.fulfill(status=200,content_type='application/json',body=json.dumps(payload),headers=headers)
        self.page.evaluate('async()=>await window.__oldOwnerRead')
        self.assertFalse(self.page.evaluate('id=>myCars().some(car=>car._id===id)',OWNED_ID))
        self.assertFalse(self.page.evaluate('id=>caOwnCars.some(car=>car._id===id)',OWNED_ID))
        self.assertEqual(self.page.locator('#cabinetList .cabinet-card').count(),0)
        self.assertEqual(next(row for row in self.backend.rows if row['id']==OWNED_ID)['veziyyet'],'silindi')

    def test_logout_then_second_account_has_no_previous_draft_or_photos(self):
        self.open_edit()
        self.assertEqual(self.page.locator('#listingForm .photo-preview img').count(),9)
        self.page.locator('#sellerDescription').fill('Private draft belonging to first offline account')
        self.page.evaluate('async()=>await logout()')
        self.switch_to_second_account()
        for name in ('make','model','generation','year','price','mileage','description'):
            self.assertEqual(self.page.locator('#listingForm [name="'+name+'"]').input_value(),'')
        self.assertIsNone(self.page.evaluate('editingCarId'))
        self.assertIsNone(self.page.evaluate('editingOriginalPhotos'))
        self.assertEqual(self.page.locator('#listingForm .photo-preview img').count(),0)
        self.assertEqual(self.page.locator('#listingForm input[name="equipment"]:checked').count(),0)
        self.assertEqual(self.page.locator('#listingForm [name="phone"]').input_value(),'+994000000001')
        self.assertEqual(self.page.evaluate('caDraftOwner'),OTHER_OWNER)

    def test_inflight_first_account_save_cannot_reset_second_account_draft(self):
        self.open_edit()
        self.page.locator('#listingForm [name="price"]').fill('43000')
        self.backend.delay_update_responses=1
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.wait_for_pending(self.backend.pending_updates)
        self.switch_to_second_account()
        self.page.locator('#listingForm [name="price"]').fill('47000')
        self.page.locator('#sellerDescription').fill('Second account draft must survive')
        self.release_update()
        self.assertEqual(self.page.evaluate('currentUser.id'),OTHER_OWNER)
        self.assertEqual(self.page.locator('#listingForm [name="price"]').input_value(),'47000')
        self.assertEqual(self.page.locator('#sellerDescription').input_value(),'Second account draft must survive')
        self.assertIsNone(self.page.evaluate('editingCarId'))
        self.assertEqual(self.page.locator('#listingForm .photo-preview img').count(),0)
        self.assertFalse(self.page.locator('#submitListingBtn').is_disabled())
        mutations=[call for call in self.backend.writes if call['path']=='/rest/v1/elanlar']
        self.assertEqual(len(mutations),1)
        self.assertEqual(mutations[0]['query'].get('satici_id'),['eq.'+OWNER])
        self.assertNotIn('satici_id',mutations[0]['body'])

    def test_confirmed_old_save_refreshes_cache_without_resetting_new_edit(self):
        second_id='cccccccc-cccc-4ccc-8ccc-cccccccccccc'
        second=owned_row();second.update(id=second_id,marka='Audi',model='A4',qiymet=28000,paket_adi='Pulsuz')
        second['ca_data'].update(make='Audi',model='A4',price=28000,pack='Pulsuz')
        self.backend.rows.append(second)
        self.page.evaluate('async()=>await caFetchMyListings()')
        self.open_edit()
        self.page.locator('#listingForm [name="price"]').fill('43000')
        self.backend.delay_update_responses=1
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.wait_for_pending(self.backend.pending_updates)
        self.page.evaluate('id=>editCar(id)',second_id)
        self.page.locator('#listingForm [name="price"]').fill('29000')
        self.release_update()
        self.page.wait_for_function('id=>myCars().some(car=>car._id===id&&car.price===43000)',arg=OWNED_ID)
        self.assertEqual(self.page.evaluate('editingCarId'),second_id)
        self.assertEqual(self.page.locator('#listingForm [name="price"]').input_value(),'29000')
        self.assertEqual(self.page.locator('#listingForm [name="make"]').input_value(),'Audi')
        self.assertEqual(self.page.locator('#listingForm .photo-preview img').count(),9)
        self.assertFalse(self.page.locator('#submitListingBtn').is_disabled())

    def test_today_counter_uses_server_value_including_zero(self):
        self.assertEqual(self.page.locator('#caTodayApproved').inner_text(),'1')
        self.backend.today_approved=0
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.assertEqual(self.page.locator('#caTodayApproved').inner_text(),'0')
        self.assertEqual(self.page.evaluate('caBrowseState.todayApproved'),0)


if __name__=='__main__':
    unittest.main(verbosity=2)
