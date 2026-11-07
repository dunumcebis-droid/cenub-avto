"""Offline Chromium regressions; every network request is mocked.

Run: python3 -m unittest discover -s tests -p 'test_*_browser.py' -v
Requires Python Playwright and Chromium (CHROMIUM_PATH may override its path).
"""
import json
import mimetypes
import os
import re
from pathlib import Path
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:8765/'
PHOTO = 'https://fixture.invalid/portrait.svg'
FIXTURE_IDS = {key:f'00000000-0000-4000-8000-{index:012d}' for index,key in enumerate(('vip','premium','standard','free-expensive','free-cheap','missing','pending'),1)}
# Public response contract: excludes the internal package approval note.
PUBLIC_COLUMNS = frozenset((
    'id', 'satici_id', 'marka', 'model', 'il', 'qiymet', 'yurus', 'seher',
    'tesvir', 'veziyyet', 'yaradildi', 'neqliyyat_novu', 'nesil', 'ban_novu',
    'yanacaq', 'suretler_qutusu', 'muherrik_hecmi', 'at_gucu', 'reng',
    'bazar_ucun', 'oturacaq_sayi', 'techizat', 'sekiller', 'telefon', 'ca_data',
    'paket_adi', 'paket_baslayir', 'paket_bitir', 'tesdiq_tarixi',
))


def fixtures():
    def row(id, make, model, year, price, mileage, package='Pulsuz', **extra):
        return dict(id=FIXTURE_IDS[id], marka=make, model=model, il=year, qiymet=price,
                    yurus=mileage, seher='Bakı', yanacaq='Benzin',
                    suretler_qutusu='Avtomat', veziyyet='aktiv',
                    paket_adi=package, paket_bitir='2099-01-01T00:00:00Z',
                    yaradildi='2026-01-01T00:00:00Z', satici_id='test-owner',
                    sekiller=[PHOTO], **extra)
    return [
        row('vip', 'BMW', '530', 2017, 42000, 132000, 'VIP'),
        row('premium', 'Toyota', 'Corolla', 2026, 33500, 0, 'Premium'),
        row('standard', 'Hyundai', 'Santa Fe', 2019, 25800, None, 'Standart',
            ca_data={'mileage': '94 000 km', 'fuel': 'Dizel'}),
        row('free-expensive', 'Kia', 'Sportage', 2020, 30000, 76543,
            ca_data={'description': 'Sınaq avtomobili', 'engine': '2.0 L benzin'}),
        row('free-cheap', 'LADA', 'Niva', 2015, 12500, 88000),
        {'id': FIXTURE_IDS['missing'], 'veziyyet': 'aktiv', 'paket_adi': 'Pulsuz', 'sekiller': []},
        {'id': FIXTURE_IDS['pending'], 'marka': 'Hidden', 'model': 'Pending', 'veziyyet': 'gozlemede',
         'paket_adi': 'VIP', 'paket_bitir': '2099-01-01T00:00:00Z', 'sekiller': []},
    ]


def browse_fixture_response(rows, payload, today_approved=3):
    """Emulate the reviewed read-only browse RPC; this is not a SQL/RLS proof."""
    assert set(payload) == {'p_filters','p_page','p_page_size'}
    assert payload['p_page_size'] == 24 and int(payload['p_page']) >= 1
    filters = payload['p_filters']
    active = [row for row in rows if row.get('veziyyet') == 'aktiv']
    rank = {'VIP':0,'Premium':1,'Standart':2,'Pulsuz':3}

    def field(row, key, fallback):
        value = row.get(key)
        return value if value is not None and str(value).strip() else (row.get('ca_data') or {}).get(fallback)

    def number(value):
        if value is None or str(value).strip() == '':
            return None
        match = re.search(r'[0-9][0-9 ,.]*', str(value))
        return float(re.sub(r'[ ,]', '', match.group())) if match else None

    def matches(row):
        for key, remote in (('make','marka'),('model','model'),('city','seher')):
            if filters.get(key) and str(filters[key]).casefold() not in str(field(row,remote,key) or '').casefold():
                return False
        if filters.get('pack','all') != 'all' and row.get('paket_adi','Pulsuz') != filters['pack']:
            return False
        for key, remote, fallback, direction in (
            ('price','qiymet','price','max'),('priceMin','qiymet','price','min'),
            ('priceMax','qiymet','price','max'),('yearMin','il','year','min'),
            ('yearMax','il','year','max'),('kmMin','yurus','mileage','min'),
            ('kmMax','yurus','mileage','max')):
            bound = filters.get(key)
            if bound is not None and str(bound).strip() != '':
                value = number(field(row,remote,fallback))
                if value is None or (direction=='min' and value<float(bound)) or (direction=='max' and value>float(bound)):
                    return False
        return True

    selected = [row for row in active if matches(row)]
    def sort_key(row):
        package = rank.get(row.get('paket_adi','Pulsuz'),3)
        price = number(field(row,'qiymet','price'))
        if filters.get('sort') in ('priceAsc','priceDesc'):
            return (package, price is None, (price or 0) * (-1 if filters['sort']=='priceDesc' else 1))
        return (package,)
    selected.sort(key=sort_key)
    size, page = 24, int(payload['p_page'])
    project = lambda row: {key:value for key,value in row.items() if key in PUBLIC_COLUMNS}
    return {'items':[project(row) for row in selected[(page-1)*size:page*size]],
            'total':len(selected),'page':page,'page_size':size,
            'total_pages':max(1,(len(selected)+size-1)//size),
            'vip_items':[project(row) for row in active if row.get('paket_adi')=='VIP'][:6],
            'today_approved':today_approved}


class CardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
            headless=True, args=['--no-sandbox'])
        cls.html = (ROOT / 'index.html').read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.page = self.context.new_page()
        self.errors = []
        self.requests = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

        def route(request):
            req = request.request
            self.requests.append((req.method, req.url))
            if req.url == ORIGIN:
                request.fulfill(content_type='text/html', body=self.html)
            elif req.url.startswith(ORIGIN):
                target = (ROOT / unquote(urlsplit(req.url).path).lstrip('/')).resolve()
                allowed = target.is_relative_to(ROOT.resolve()) and (target == ROOT/'index.html' or target.is_relative_to(ROOT/'assets'))
                if allowed and target.is_file():
                    request.fulfill(content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream',
                                    body=target.read_bytes())
                else:
                    request.abort()
            elif req.url.startswith(PHOTO):
                request.fulfill(content_type='image/svg+xml', body=(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="1800">'
                    '<rect width="300" height="1800" fill="#96b2c3"/></svg>'))
            elif urlsplit(req.url).path == '/rest/v1/rpc/ca_browse_listings':
                self.assertEqual(req.method,'POST')
                response = browse_fixture_response(fixtures(), req.post_data_json)
                request.fulfill(content_type='application/json',body=json.dumps(response))
            elif '/rest/v1/elanlar?' in req.url:
                self.assertEqual(req.method, 'GET', 'Production mutations are forbidden in tests')
                columns = self.assert_public_select(req.url)
                query=parse_qs(urlsplit(req.url).query)
                selected=fixtures()
                if 'satici_id' in query:
                    selected=[row for row in selected if 'eq.'+str(row.get('satici_id',''))==query['satici_id'][0]]
                if 'id' in query and query['id'][0].startswith('in.('):
                    ids=query['id'][0][4:-1].split(',')
                    selected=[row for row in selected if row.get('id') in ids and row.get('veziyyet')=='aktiv']
                offset=int(query.get('offset',['0'])[0]);limit=int(query.get('limit',['100'])[0])
                rows = [{key: value for key, value in row.items() if key in columns}
                        for row in selected[offset:offset+limit]]
                request.fulfill(content_type='application/json', body=json.dumps(rows))
            else:
                request.abort()

        self.page.route('**/*', route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caRemoteCars.length === 6')
        self.page.wait_for_function('document.querySelectorAll("#allGrid .car-card").length === 6')

    def tearDown(self):
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertFalse([item for item in self.requests if item[0] not in ('GET','HEAD') and
                          not (item[0]=='POST' and urlsplit(item[1]).path=='/rest/v1/rpc/ca_browse_listings')],
                         'Only the mocked read-only browse RPC may use POST')
        self.assertTrue(any(method=='POST' and urlsplit(url).path=='/rest/v1/rpc/ca_browse_listings' for method,url in self.requests))
        reads = [(method, url) for method, url in self.requests if '/rest/v1/elanlar?' in url]
        for method, url in reads:
            self.assertEqual(method, 'GET')
            self.assert_public_select(url)
        self.context.close()

    def assert_public_select(self, url):
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(len(query.get('select', [])), 1)
        columns = query['select'][0].split(',')
        self.assertNotIn('*', columns, 'The public request must not read every column')
        self.assertNotIn('paket_tesdiq_qeydi', columns, 'Internal approval notes stay private')
        self.assertEqual(len(columns), len(PUBLIC_COLUMNS), 'No duplicate or extra public columns')
        self.assertEqual(set(columns), PUBLIC_COLUMNS)
        self.assertEqual(query.get('limit'), ['100'])
        return set(columns)

    def text(self, selector):
        return self.page.locator(selector).inner_text()

    def test_every_card_metadata_and_geometry_desktop_and_mobile(self):
        expected = [
            ('BMW 530', '2017', '42,000', '132,000 km'),
            ('Toyota Corolla', '2026', '33,500', '0 km'),
            ('Hyundai Santa Fe', '2019', '25,800', '94,000 km'),
            ('Kia Sportage', '2020', '30,000', '76,543 km'),
            ('LADA Niva', '2015', '12,500', '88,000 km'),
        ]
        for width in (1440, 768, 375, 320):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 1000})
                cards = self.page.locator('#allGrid .car-card')
                for name, year, price, mileage in expected:
                    card = cards.filter(has_text=name)
                    self.assertEqual(card.count(), 1)
                    content = card.inner_text()
                    for value in (name, year, price, mileage):
                        self.assertIn(value, content)
                    self.assertTrue(card.locator('.details').is_visible())
                missing = cards.filter(has_text='Marka və model qeyd edilməyib')
                self.assertIn('Qiymət qeyd edilməyib', missing.inner_text())
                self.assertIn('İl qeyd edilməyib', missing.inner_text())
                self.assertIn('Yürüş qeyd edilməyib', missing.inner_text())
                self.assertNotIn('NaN', cards.all_text_contents().__str__())
                geometry = cards.evaluate_all('''els => els.map(e => {
                    const p=e.querySelector('.photo').getBoundingClientRect();
                    const d=e.querySelector('.details').getBoundingClientRect();
                    const img=e.querySelector('.photo img');
                    const i=img ? img.getBoundingClientRect() : null;
                    const flag=e.querySelector('.flag');
                    const f=flag ? flag.getBoundingClientRect() : null;
                    return {photo:p.toJSON(),details:d.toJSON(),image:i&&i.toJSON(),flag:f&&f.toJSON()};
                })''')
                for bounds in geometry:
                    photo, details, image, flag = [bounds[k] for k in ('photo','details','image','flag')]
                    self.assertGreaterEqual(details['top'], photo['bottom']-1)
                    if image:
                        self.assertLessEqual(image['height'], photo['height']+1)
                        self.assertLessEqual(image['width'], photo['width']+1)
                    if flag:
                        self.assertLess(flag['width'], photo['width']*.9, 'VIP badge must not fill photo')
                        self.assertLess(flag['height'], 60)
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)

    def test_packages_sorting_and_public_visibility(self):
        self.assertEqual(self.page.locator('#vipGrid .car-card').count(), 1)
        self.assertIn('BMW 530', self.text('#vipGrid'))
        self.assertNotIn('Hidden Pending', self.text('#allGrid'))
        self.page.evaluate("async()=>{document.getElementById('sortListings').value='priceAsc';await caFetchListings(1)}")
        names = self.page.locator('#allGrid .ca-visible-car-name').all_text_contents()
        self.assertIn('BMW 530', names[0])
        self.assertIn('Toyota Corolla', names[1])
        self.assertIn('Hyundai Santa Fe', names[2])
        self.assertLess(next(i for i,n in enumerate(names) if 'LADA' in n),
                        next(i for i,n in enumerate(names) if 'Kia' in n))
        self.assertIn('Marka və model qeyd edilməyib', names[-1])
        self.page.evaluate("async()=>await setFilter('VIP',document.querySelector('.pill'))")
        self.assertEqual(self.page.locator('#allGrid .car-card').count(), 1)
        self.assertIn('BMW 530', self.text('#allGrid'))

    def test_details_match_selected_card_and_zero_mileage(self):
        card = self.page.locator('#allGrid .car-card').filter(has_text='Toyota Corolla')
        card.locator('.ca-visible-car-name').click()
        self.assertEqual(self.text('#detailTitle'), 'Toyota Corolla')
        self.assertEqual(self.text('#detailPrice'), card.locator('.price').inner_text())
        self.assertIn('0 km', self.text('#detailSpecs'))
        self.assertIn('2026', self.text('#detailSpecs'))
        self.assertEqual(self.page.locator('#galleryStage img').get_attribute('src'), PHOTO)
        self.page.keyboard.press('Escape')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        bmw = self.page.locator('#allGrid .car-card').filter(has_text='BMW 530')
        bmw.focus()
        self.page.keyboard.press('Enter')
        self.assertEqual(self.text('#detailTitle'), 'BMW 530')

    def test_favorites_comparison_and_nested_keyboard(self):
        self.page.evaluate("currentUser={id:'test-owner',phone:'+994000000000'};caSession={access_token:'offline-token',expires_at:4102444800,user:{id:'test-owner'}}")
        card = self.page.locator('#allGrid .car-card').filter(has_text='Toyota Corolla')
        card.locator('.favorite-btn').focus()
        self.page.keyboard.press('Enter')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible(),
                         'Favorite keyboard activation must not open details')
        self.assertTrue(card.locator('.favorite-btn').evaluate("e=>e.classList.contains('is-favorite')"))
        self.page.evaluate('async()=>{await caFetchFavoriteListings();renderBuyerFavorites()}')
        self.assertEqual(self.page.locator('#buyerFavoritesList .car-card').count(), 1)
        self.assertIn('Toyota Corolla', self.page.locator('#buyerFavoritesList').text_content())
        card.locator('.ca-compare').focus()
        self.page.keyboard.press('Enter')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible(),
                         'Comparison keyboard activation must not open details')
        self.assertEqual(self.text('#caCompareCount'), '1')
        self.page.evaluate('caShowCompare()')
        self.assertIn('Toyota Corolla', self.text('#caDialogBody'))
        self.assertIn('0 km', self.text('#caDialogBody'))

    def test_formatted_mileage_filter_and_search(self):
        self.page.evaluate('''async() => {
            document.getElementById('caKmMin').value='90000';
            document.getElementById('caKmMax').value='95000';
            await searchCars();
        }''')
        self.assertEqual(self.page.locator('#allGrid .car-card').count(), 1)
        self.assertIn('Hyundai Santa Fe', self.text('#allGrid'))
        self.page.evaluate('async()=>await clearCarSearch()')
        self.assertEqual(self.page.locator('#allGrid .car-card').count(), 6)
        self.page.evaluate("async()=>{document.getElementById('caKmMax').value='0';await searchCars()}")
        self.assertEqual(self.page.locator('#allGrid .car-card').count(), 1)
        self.assertIn('Toyota Corolla', self.text('#allGrid'))
        self.page.evaluate('async()=>await clearCarSearch()')
        self.page.evaluate("async()=>{document.getElementById('searchMake').value='Toyota';await searchCars()}")
        self.assertEqual(self.page.locator('#allGrid .car-card').count(), 1)
        self.assertIn('Toyota Corolla', self.text('#allGrid'))


    def test_public_read_failure_and_retry_recovery(self):
        fail = [True]

        def temporarily_denied(route):
            if fail[0]:
                req = route.request
                self.requests.append((req.method, req.url))
                self.assertEqual(req.method, 'POST')
                route.fulfill(status=401, content_type='application/json', body=json.dumps({
                    'code': '42501', 'message': 'permission denied for table elanlar'}))
            else:
                route.fallback()

        self.page.route(re.compile(r'/rest/v1/rpc/ca_browse_listings'), temporarily_denied)
        self.page.evaluate('''async()=>{caRemoteCars=[];caPageCars=[];caVipCars=[];Object.assign(caBrowseState,{loaded:false,total:0,totalPages:0,page:1,requestedPage:1,error:false,todayApproved:null});await caFetchListings(1)}''')
        self.assertEqual(self.text('#countLabel'), 'Elanlar yüklənmədi')
        self.assertIn('Elanları yükləmək mümkün olmadı', self.text('#allGrid'))
        self.assertEqual(self.page.locator('#allGrid .car-card').count(), 0)
        fail[0] = False
        self.page.locator('#allGrid button').click()
        self.page.wait_for_function('document.querySelectorAll("#allGrid .car-card").length === 6')
        self.assertIn('6 elan', self.text('#countLabel'))
        self.assertEqual(self.page.locator('#vipGrid .car-card').count(), 1)

    def test_seller_cabinet_keeps_metadata_status_and_cover(self):
        self.page.evaluate("""async() => {
            currentUser={id:'test-owner',phone:'+994000000000'};
            caSession={access_token:'offline-token',expires_at:4102444800,user:{id:'test-owner'}};
            document.body.classList.add('cabinet-open');
            await caFetchMyListings();renderCabinet();
        }""")
        self.assertEqual(self.text('#cabTotal'), '5')
        self.assertEqual(self.text('#cabVip'), '1')
        cards = self.page.locator('#cabinetList .cabinet-card')
        self.assertEqual(cards.count(), 5)
        toyota = cards.filter(has_text='Toyota Corolla')
        for value in ('33,500', '2026', '0 km', 'Təsdiqlənib'):
            self.assertIn(value, toyota.inner_text())
        self.assertEqual(toyota.locator('img').get_attribute('src'), PHOTO)
        self.assertTrue(toyota.locator('button').first.is_visible())
        self.assertIn('94,000 km', cards.filter(has_text='Hyundai Santa Fe').inner_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
