"""Offline marketplace regressions; every HTTP request is intercepted.

These fixtures test browser behavior and account-change races, not SQL/RLS.
No real listing, report, notification, account, or email is changed.
"""
import copy
import json
import os
import re
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_cards_browser import browse_fixture_response
from test_listing_management_browser import ORIGIN, OWNER, OTHER_OWNER, OWNED_ID, OTHER_ID, ROOT, owned_row

SEARCH_ID = '66666666-6666-4666-8666-666666666666'
OTHER_SEARCH_ID = '66666666-6666-4666-8666-777777777777'
REPORT_ID = '77777777-7777-4777-8777-777777777777'
NOTICE_ID = '88888888-8888-4888-8888-888888888888'
OTHER_NOTICE_ID = '88888888-8888-4888-8888-999999999999'
CREATED = '2026-11-13T10:00:00Z'


class MarketplaceBackend(AdminAuthBackend):
    """Synthetic RPC contract, with deliberate failures and held responses."""
    MARKET_RPCS = {
        'ca_mark_listing_sold', 'ca_record_listing_event', 'ca_my_listing_stats',
        'ca_report_listing', 'ca_admin_browse_reports', 'ca_admin_resolve_report',
        'ca_save_search', 'ca_list_saved_searches', 'ca_delete_saved_search',
        'ca_list_notifications', 'ca_mark_notification_read',
    }

    def __init__(self):
        super().__init__()
        self.rows = [row for row in self.rows if row['id'] in (OWNED_ID, OTHER_ID)]
        for row in self.rows:
            row['is_sold'] = False
        self.market_calls = []
        self.fail = set()
        self.hold = set()
        self.pending = []
        self.saved = {
            OWNER: [dict(id=SEARCH_ID, name='BMW axtarışım', filters={'make': 'BMW', 'pack': 'all', 'sort': 'newest'}, created_at=CREATED)],
            OTHER_OWNER: [dict(id=OTHER_SEARCH_ID, name='Digər şəxsin axtarışı', filters={'make': 'Toyota', 'pack': 'all', 'sort': 'newest'}, created_at=CREATED)],
        }
        self.notifications = {
            OWNER: [dict(id=NOTICE_ID, search_id=SEARCH_ID, search_name='BMW axtarışım', elan_id=OTHER_ID,
                         marka='Toyota', model='Corolla', il=2017, qiymet=42000, seher='Bakı', created_at=CREATED, is_read=False)],
            OTHER_OWNER: [dict(id=OTHER_NOTICE_ID, search_id=OTHER_SEARCH_ID, search_name='Digər şəxsin axtarışı', elan_id=OWNED_ID,
                               marka='BMW', model='530', il=2017, qiymet=42000, seher='Bakı', created_at=CREATED, is_read=False)],
        }
        self.reports = [dict(id=REPORT_ID, elan_id=OTHER_ID, marka='Toyota', model='Corolla', reason='fraud',
                             details='<img src=x onerror="window.__reportXss=1"> Şikayət mətni', status='open', created_at=CREATED, admin_note='')]
        self.processing_responses = 0

    def calls_for(self, name):
        return [call for call in self.market_calls if call['name'] == name]

    @staticmethod
    def owner_for(request):
        return {'Bearer seller-token': OWNER, 'Bearer admin-token': OWNER,
                'Bearer other-token': OTHER_OWNER}.get(request.headers.get('authorization'))

    def release(self, name):
        held = [item for item in self.pending if item[0] == name]
        self.pending = [item for item in self.pending if item[0] != name]
        for _, route, data in held:
            route.fulfill(content_type='application/json', body=json.dumps(data))

    def route(self, route):
        req = route.request
        parsed = urlsplit(req.url)
        body = req.post_data_json if req.post_data else None
        name = parsed.path.rsplit('/', 1)[-1]

        def send(data, status=200):
            if status == 200 and name in self.hold:
                self.pending.append((name, route, copy.deepcopy(data)))
                return
            route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

        if parsed.path == '/auth/v1/settings':
            send({'external': {'phone': False}})
            return
        if parsed.path == '/auth/v1/user' and req.method == 'GET':
            send(dict(id=self.owner_for(req), email='offline@example.invalid', user_metadata={'telefon': '+994000000000'}))
            return
        if parsed.path == '/rest/v1/rpc/ca_browse_listings':
            self.calls.append(dict(method=req.method, path=parsed.path, query=parse_qs(parsed.query), headers=dict(req.headers), body=body))
            # Sold listings disappear from all public browse surfaces.
            data = browse_fixture_response([r for r in self.rows if not r.get('is_sold', False)], body, self.today_approved)
            data['total_pages'] = (data['total'] + 23) // 24
            send(data)
            return
        if parsed.path.startswith('/rest/v1/rpc/') and name in self.MARKET_RPCS:
            owner = self.owner_for(req)
            self.market_calls.append(dict(name=name, body=copy.deepcopy(body), owner=owner,
                                          authorization=req.headers.get('authorization')))
            if name in self.fail:
                send({'message': 'Offline fixture unavailable'}, 503)
                return
            if name != 'ca_record_listing_event' and not owner:
                send({'message': 'Login required'}, 403)
                return
            if name == 'ca_mark_listing_sold':
                row = next((r for r in self.rows if r['id'] == body['p_id'] and r['satici_id'] == owner), None)
                if row is None:
                    send({'message': 'Not owned'}, 403)
                    return
                row['is_sold'] = True
                send(row['id'])
            elif name == 'ca_record_listing_event':
                assert set(body) == {'p_id', 'p_kind', 'p_visitor'}
                assert body['p_kind'] in ('view', 'contact')
                assert re.fullmatch(r'[0-9a-f-]{36}', body['p_visitor'], re.I)
                send(True)
            elif name == 'ca_my_listing_stats':
                assert set(body) == {'p_ids'} and 0 < len(body['p_ids']) <= 100
                send([dict(id=r['id'], views=41, contact_clicks=7) for r in self.rows
                      if r['satici_id'] == owner and r['id'] in body['p_ids']])
            elif name == 'ca_report_listing':
                assert set(body) == {'p_id', 'p_reason', 'p_details'}
                assert body['p_reason'] in ('fraud', 'wrong_info', 'duplicate', 'inappropriate', 'other')
                assert len(body['p_details']) <= 1000
                send(REPORT_ID)
            elif name == 'ca_admin_browse_reports':
                if req.headers.get('authorization') != 'Bearer admin-token':
                    send({'message': 'Admin denied'}, 403)
                    return
                assert set(body) == {'p_status', 'p_page', 'p_page_size'} and body['p_page_size'] == 24
                rows = [r for r in self.reports if body['p_status'] == 'all' or r['status'] == body['p_status']]
                total = len(rows)
                page = max(1, min(body['p_page'], max(1, (total + 23) // 24)))
                send(dict(items=rows[(page-1)*24:page*24], total=total, page=page, total_pages=(total+23)//24))
            elif name == 'ca_admin_resolve_report':
                if req.headers.get('authorization') != 'Bearer admin-token':
                    send({'message': 'Admin denied'}, 403)
                    return
                assert set(body) == {'p_report_id', 'p_status', 'p_note'}
                assert body['p_status'] in ('resolved', 'dismissed')
                next(r for r in self.reports if r['id'] == body['p_report_id']).update(status=body['p_status'], admin_note=body['p_note'])
                send(True)
            elif name == 'ca_save_search':
                assert set(body) == {'p_name', 'p_filters'} and 1 <= len(body['p_name']) <= 80
                self.saved[owner] = [dict(id=SEARCH_ID, name=body['p_name'], filters=body['p_filters'], created_at=CREATED)]
                send(SEARCH_ID)
            elif name == 'ca_list_saved_searches':
                assert body == {}
                send(self.saved.get(owner, []))
            elif name == 'ca_delete_saved_search':
                assert set(body) == {'p_id'}
                self.saved[owner] = [r for r in self.saved.get(owner, []) if r['id'] != body['p_id']]
                send(True)
            elif name == 'ca_list_notifications':
                assert set(body) == {'p_page', 'p_page_size'} and body['p_page_size'] == 24
                rows = self.notifications.get(owner, [])
                total = len(rows)
                page = max(1, min(body['p_page'], max(1, (total+23)//24)))
                processing = self.processing_responses > 0
                self.processing_responses = max(0, self.processing_responses-1)
                send(dict(items=rows[(page-1)*24:page*24], total=total, page=page, total_pages=(total+23)//24,
                          unread_count=sum(not r['is_read'] for r in rows), processing=processing))
            elif name == 'ca_mark_notification_read':
                assert set(body) == {'p_id'}
                for row in self.notifications.get(owner, []):
                    if body['p_id'] is None or row['id'] == body['p_id']:
                        row['is_read'] = True
                send(True)
            return
        super().route(route)


class MarketplaceBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
                                             headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 1000})
        self.context.set_default_timeout(5000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('''window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true;
            // Keep real tel-click events, while preventing OS/app navigation in headless Chromium.
            document.addEventListener('click',e=>{if(e.target.closest('a[href^="tel:"]'))e.preventDefault()},true);''')
        self.backend = MarketplaceBackend()
        self.page.route('**/*', self.backend.route)

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')

    def go(self):
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')
        if not self.page.evaluate('typeof caMarketSessionChanged === "function"'):
            self.page.add_script_tag(url=ORIGIN+'assets/js/20-marketplace.js')
        self.page.wait_for_function('typeof caMarketSessionChanged === "function"')

    def sign_in(self, owner=OWNER, admin=False):
        self.page.evaluate('''async ({id,token})=>await caPersistSession({access_token:token,expires_at:4102444800,
            user:{id,email:'offline@example.invalid',user_metadata:{telefon:'+994000000000'}}})''',
                           dict(id=owner, token='admin-token' if admin else 'seller-token' if owner == OWNER else 'other-token'))

    def cabinet(self):
        self.page.evaluate('async()=>{openCabinet();await caFetchMyListings();renderCabinet()}')

    def detail(self, listing=OTHER_ID, private=False):
        self.page.evaluate('''({id,privatePreview})=>{
            const car=allCars().find(c=>(c._id||c.id)===id);
            if(!car)throw Error('Missing fixture car');
            caOpenCarRecord(car,privatePreview?{adminPreview:true}:{});
        }''', dict(id=listing, privatePreview=private))

    def wait_calls(self, name, minimum=1):
        for _ in range(200):
            if len(self.backend.calls_for(name)) >= minimum:
                return self.backend.calls_for(name)
            self.page.wait_for_timeout(10)
        self.fail('Expected mocked RPC '+name)

    def click_sold(self, listing=OWNED_ID):
        self.page.locator('[data-ca-sold="'+listing+'"]').click()
        # The shared confirmation dialog may ask for an explicit second click.
        if self.page.locator('#caMarketSubmit').is_visible() and not self.backend.calls_for('ca_mark_listing_sold'):
            self.page.locator('#caMarketSubmit').click()

    def test_sold_listing_remains_private_preserves_photos_and_package(self):
        self.go(); self.sign_in(); self.cabinet()
        original = copy.deepcopy(next(r for r in self.backend.rows if r['id'] == OWNED_ID))
        self.click_sold()
        self.wait_calls('ca_mark_listing_sold')
        card = self.page.locator('#cabinetList [data-listing-id="'+OWNED_ID+'"]')
        expect(card.locator('.ca-cab-status')).to_contain_text('Satılıb')
        self.assertEqual(card.locator('button', has_text='Redaktə et').count(), 0)
        self.assertEqual(card.locator('[data-ca-sold]').count(), 0)
        self.assertNotIn(OWNED_ID, self.page.evaluate('caPageCars.map(c=>c._id)'))
        updated = next(r for r in self.backend.rows if r['id'] == OWNED_ID)
        self.assertTrue(updated['is_sold'])
        self.assertEqual(updated['sekiller'], original['sekiller'])
        self.assertEqual(updated['ca_data'], original['ca_data'])
        self.assertEqual(updated['paket_adi'], 'VIP')
        self.assertFalse(any(c['method'] == 'DELETE' for c in self.backend.calls))

    def test_failed_sold_request_keeps_owned_and_public_listing(self):
        self.backend.fail.add('ca_mark_listing_sold')
        self.go(); self.sign_in(); self.cabinet(); self.click_sold()
        self.wait_calls('ca_mark_listing_sold')
        expect(self.page.locator('[data-ca-sold="'+OWNED_ID+'"]')).to_be_enabled()
        expect(self.page.locator('#cabinetList [data-listing-id="'+OWNED_ID+'"] .ca-cab-status')).to_have_text('Təsdiqlənib')
        self.assertIn(OWNED_ID, self.page.evaluate('caPageCars.map(c=>c._id)'))
        self.assertFalse(self.backend.rows[0]['is_sold'])

    def test_stats_are_owner_only_and_requests_are_batched(self):
        base = owned_row()
        self.backend.rows.extend(dict(copy.deepcopy(base), id=f'99999999-9999-4999-8999-{n:012d}') for n in range(104))
        self.go()
        self.assertFalse(self.backend.calls_for('ca_my_listing_stats'))
        self.sign_in(); self.cabinet()
        expect(self.page.locator('[data-ca-stats="'+OWNED_ID+'"]')).to_contain_text('41')
        self.page.wait_for_function('document.querySelectorAll("[data-ca-stats]").length>=105')
        expect(self.page.locator('[data-ca-stats="99999999-9999-4999-8999-000000000103"]')).to_contain_text('41')
        calls = self.wait_calls('ca_my_listing_stats', 2)
        requested = {id for call in calls for id in call['body']['p_ids']}
        self.assertEqual(requested, {r['id'] for r in self.backend.rows if r['satici_id'] == OWNER})
        self.assertTrue(all(call['owner'] == OWNER and 0 < len(call['body']['p_ids']) <= 100 for call in calls))
        expect(self.page.locator('[data-ca-stats="'+OWNED_ID+'"]')).to_contain_text('7')
        self.assertEqual(self.page.locator('[data-ca-stats="'+OTHER_ID+'"]').count(), 0)

    def test_public_views_and_tel_clicks_dedupe_and_exclude_owner_and_preview(self):
        preview_id = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
        preview = copy.deepcopy(self.backend.rows[1]); preview['id'] = preview_id
        self.backend.rows.append(preview)
        self.go(); self.detail()
        self.wait_calls('ca_record_listing_event')
        self.page.locator('#detailContact a[href^="tel:"]').evaluate('link=>link.click()')
        self.wait_calls('ca_record_listing_event', 2)
        self.page.evaluate('closeCarDetail()'); self.detail()
        self.page.locator('#detailContact a[href^="tel:"]').evaluate('link=>link.click()')
        self.page.wait_for_timeout(100)
        events = self.backend.calls_for('ca_record_listing_event')
        self.assertEqual([(c['body']['p_id'], c['body']['p_kind']) for c in events], [(OTHER_ID, 'view'), (OTHER_ID, 'contact')])
        self.assertEqual(events[0]['body']['p_visitor'], events[1]['body']['p_visitor'])
        self.page.evaluate('closeCarDetail()'); self.sign_in(); self.detail(OWNED_ID)
        self.page.locator('#detailContact a[href^="tel:"]').evaluate('link=>link.click()')
        self.page.evaluate('closeCarDetail()')
        self.detail(preview_id, private=True)
        self.page.locator('#detailContact a[href^="tel:"]').evaluate('link=>link.click()')
        self.page.wait_for_timeout(100)
        self.assertEqual(len(self.backend.calls_for('ca_record_listing_event')), 2)

    def test_reports_require_login_and_failed_submit_retains_form(self):
        self.go(); self.detail()
        self.page.locator('#caReportListingBtn').click()
        expect(self.page.locator('#authOverlay')).to_have_class(re.compile(r'open'))
        self.assertFalse(self.backend.calls_for('ca_report_listing'))
        self.page.evaluate('closeAuth();closeCarDetail()'); self.sign_in(); self.detail(OWNED_ID)
        self.assertFalse(self.page.locator('#caReportListingBtn').is_visible())
        self.page.evaluate('closeCarDetail()'); self.detail()
        self.page.locator('#caReportListingBtn').click()
        self.page.locator('#caReportReason').select_option('wrong_info')
        self.page.locator('#caReportDetails').fill('Elanın qiyməti düzgün deyil.')
        self.backend.fail.add('ca_report_listing')
        self.page.locator('#caMarketSubmit').click(); self.wait_calls('ca_report_listing')
        expect(self.page.locator('#caMarketSubmit')).to_be_enabled()
        expect(self.page.locator('#caReportDetails')).to_have_value('Elanın qiyməti düzgün deyil.')
        self.backend.fail.remove('ca_report_listing')
        self.page.locator('#caMarketSubmit').click(); self.wait_calls('ca_report_listing', 2)
        body = self.backend.calls_for('ca_report_listing')[-1]['body']
        self.assertEqual(body, dict(p_id=OTHER_ID, p_reason='wrong_info', p_details='Elanın qiyməti düzgün deyil.'))
        self.assertTrue(all(r['veziyyet'] == 'aktiv' for r in self.backend.rows))

    def test_admin_report_queue_renders_plain_text_and_saves_review(self):
        # SQL keeps the moderation status active and uses an independent sold flag.
        self.backend.admin_rows[0]['is_sold'] = True
        self.go(); self.sign_in(admin=True)
        self.page.evaluate('async()=>await caAdminOpen()')
        sold = self.page.locator('[data-ad-row-id="'+self.backend.admin_rows[0]['id']+'"]')
        expect(sold.locator('.ca-status-sold')).to_contain_text('Satılıb')
        self.assertEqual(sold.locator('[data-status]').count(), 0, 'Sold listings must not expose moderation actions that republish them')
        row = self.page.locator('[data-report-id="'+REPORT_ID+'"]')
        expect(row).to_contain_text('<img src=x onerror="window.__reportXss=1">')
        self.assertEqual(row.locator('img').count(), 0)
        self.assertIsNone(self.page.evaluate('window.__reportXss'))
        row.locator('[data-ca-report-note]').fill('Məlumat yoxlanıldı.')
        row.locator('[data-ca-report-status="resolved"]').click()
        call = self.wait_calls('ca_admin_resolve_report')[-1]
        self.assertEqual(call['body'], dict(p_report_id=REPORT_ID, p_status='resolved', p_note='Məlumat yoxlanıldı.'))
        self.assertEqual(self.backend.reports[0]['status'], 'resolved')
        self.assertFalse(any(c['name'] == 'ca_admin_status' for c in self.backend.admin_calls))
        self.page.locator('#caReportsFilter').select_option('resolved')
        expect(self.page.locator('[data-report-id="'+REPORT_ID+'"]')).to_be_visible()

    def test_nonadmin_cannot_open_report_queue(self):
        self.go(); self.sign_in()
        self.page.evaluate('async()=>await caAdminOpen()')
        self.assertFalse(self.page.locator('#caReportsAdmin').is_visible())
        self.assertFalse(self.backend.calls_for('ca_admin_browse_reports'))

    def test_delayed_admin_reports_cannot_leak_after_account_change(self):
        self.backend.hold.add('ca_admin_browse_reports')
        self.go(); self.sign_in(admin=True)
        self.page.evaluate('void caAdminOpen()')
        self.wait_calls('ca_admin_browse_reports')
        self.backend.hold.clear()
        self.sign_in(OTHER_OWNER)
        self.backend.release('ca_admin_browse_reports')
        self.page.wait_for_timeout(100)
        self.assertFalse(self.page.locator('#caReportsAdmin').is_visible())
        self.assertEqual(self.page.locator('[data-report-id="'+REPORT_ID+'"]').count(), 0)
        self.assertNotIn('Şikayət mətni', self.page.locator('body').inner_text())

    def test_saved_search_preserves_full_filter_and_restores_page_one(self):
        self.go(); self.sign_in()
        filters = dict(make='BMW', model='530', city='Bakı', price=60000, priceMin=20000, priceMax=50000,
                       yearMin=2010, yearMax=2026, kmMin=1000, kmMax=100000, engineMin=1.5, engineMax=3,
                       hpMin=100, hpMax=400, vehicle='Minik avtomobili', state='Sürülmüş', body='Sedan',
                       color='Qara', market='Avropa', seats='5', equipment=['ABS', 'Bluetooth'])
        self.page.evaluate('''async filters=>{
            const fields={make:'searchMake',model:'searchModel',city:'searchCity',price:'searchPrice',
              priceMin:'caPriceMin',priceMax:'caPriceMax',yearMin:'caYearMin',yearMax:'caYearMax',kmMin:'caKmMin',kmMax:'caKmMax',
              engineMin:'caEngineMin',engineMax:'caEngineMax',hpMin:'caHpMin',hpMax:'caHpMax',vehicle:'caVehicle',state:'caState',
              body:'caBody',color:'caColor',market:'caMarket',seats:'caSeats'};
            for(const [name,id] of Object.entries(fields))document.getElementById(id).value=String(filters[name]);
            document.getElementById('searchModel').disabled=false;
            document.querySelectorAll('input[name="caEquipment"]').forEach(n=>n.checked=filters.equipment.includes(n.value));
            currentFilter='VIP';document.getElementById('sortListings').value='priceAsc';await searchCars();
        }''', filters)
        # The filter launcher exposes the search action on narrow screens too.
        self.page.evaluate('if(!document.getElementById("caFilterContent").hidden){}else caToggleFilters()')
        self.page.locator('#caSaveSearchLaunch').click()
        self.page.locator('#caSearchName').fill('Öz BMW axtarışım')
        self.page.locator('#caMarketSubmit').click()
        call = self.wait_calls('ca_save_search')[-1]
        self.assertEqual(call['body'], dict(p_name='Öz BMW axtarışım', p_filters=dict(filters, pack='VIP', sort='priceAsc')))
        if self.page.locator('#caMarketClose').is_visible():
            self.page.locator('#caMarketClose').click()
        self.cabinet()
        row = self.page.locator('[data-search-id="'+SEARCH_ID+'"]')
        expect(row).to_contain_text('Öz BMW axtarışım')
        self.page.evaluate('async()=>{currentSearch=null;currentFilter="all";document.getElementById("sortListings").value="newest";await caFetchListings(1)}')
        row.locator('[data-ca-search-apply]').click()
        self.page.wait_for_function('currentSearch?.make==="BMW"&&currentFilter==="VIP"&&caBrowseState.page===1&&!caBrowseState.loading')
        self.assertEqual(self.page.locator('#searchMake').input_value(), 'BMW')
        self.assertEqual(self.page.locator('#searchModel').input_value(), '530')
        self.assertEqual(self.page.locator('#caPriceMin').input_value(), '20000')
        self.assertEqual(self.page.locator('#sortListings').input_value(), 'priceAsc')
        browse = [c for c in self.backend.calls if c['path'].endswith('/ca_browse_listings')][-1]
        self.assertEqual(browse['body']['p_page'], 1)
        self.assertEqual(browse['body']['p_filters'], dict(filters, pack='VIP', sort='priceAsc'))

    def test_failed_saved_search_deletion_keeps_row_and_success_removes_it(self):
        self.go(); self.sign_in(); self.cabinet()
        row = self.page.locator('[data-search-id="'+SEARCH_ID+'"]')
        expect(row).to_be_visible()
        self.backend.fail.add('ca_delete_saved_search')
        row.locator('[data-ca-search-delete]').click(); self.wait_calls('ca_delete_saved_search')
        expect(row.locator('[data-ca-search-delete]')).to_be_enabled()
        self.assertEqual(len(self.backend.saved[OWNER]), 1)
        self.backend.fail.remove('ca_delete_saved_search')
        row.locator('[data-ca-search-delete]').click(); self.wait_calls('ca_delete_saved_search', 2)
        expect(row).to_have_count(0)

    def test_notification_read_actions_and_open_use_the_public_listing(self):
        second = copy.deepcopy(self.backend.notifications[OWNER][0])
        second['id'] = OTHER_NOTICE_ID
        self.backend.notifications[OWNER].append(second)
        self.go(); self.sign_in()
        self.page.locator('#caNotificationsLaunch').click()
        row = self.page.locator('[data-notification-id="'+NOTICE_ID+'"]')
        expect(row).to_contain_text('Corolla')
        row.locator('[data-ca-notification-read]').click()
        self.wait_calls('ca_mark_notification_read')
        self.assertTrue(self.backend.notifications[OWNER][0]['is_read'])
        row.locator('[data-ca-notification-open]').click()
        expect(self.page.locator('#detailOverlay')).to_have_class(re.compile(r'open'))
        expect(self.page.locator('#detailTitle')).to_have_text('Toyota Corolla')
        self.assertEqual(self.page.evaluate('activeDetailCar._id'), OTHER_ID)
        self.assertNotEqual(self.page.locator('#detailOverlay').get_attribute('data-private-preview'), 'true')
        self.page.evaluate('closeCarDetail()'); self.page.locator('#caNotificationsLaunch').click()
        previous = len(self.backend.calls_for('ca_mark_notification_read'))
        self.page.locator('#caNotificationReadAll').click()
        calls = self.wait_calls('ca_mark_notification_read', previous+1)
        self.assertTrue(any(c['body']['p_id'] is None for c in calls))
        self.assertFalse(self.backend.auth_calls)

    def test_private_responses_cannot_repopulate_a_new_accounts_interface(self):
        self.backend.hold.update(('ca_list_saved_searches', 'ca_list_notifications', 'ca_my_listing_stats'))
        self.go(); self.sign_in(); self.cabinet()
        self.wait_calls('ca_list_saved_searches'); self.wait_calls('ca_list_notifications'); self.wait_calls('ca_my_listing_stats')
        self.backend.hold.clear()
        self.sign_in(OTHER_OWNER); self.cabinet()
        expect(self.page.locator('#caSavedSearchList')).to_contain_text('Digər şəxsin axtarışı')
        for name in ('ca_list_saved_searches', 'ca_list_notifications', 'ca_my_listing_stats'):
            self.backend.release(name)
        self.page.wait_for_timeout(100)
        expect(self.page.locator('#caSavedSearchList')).not_to_contain_text('BMW axtarışım')
        self.assertEqual(self.page.locator('[data-search-id="'+SEARCH_ID+'"]').count(), 0)
        self.assertEqual(self.page.locator('[data-ca-stats="'+OWNED_ID+'"]').count(), 0)
        self.page.locator('#caNotificationsLaunch').click()
        expect(self.page.locator('#caNotificationList')).to_contain_text('Digər şəxsin axtarışı')
        self.assertEqual(self.page.locator('[data-notification-id="'+NOTICE_ID+'"]').count(), 0)
        self.page.evaluate('async()=>await logout()')
        self.assertFalse(self.page.locator('#caMarketOverlay').is_visible())
        self.assertNotIn('Digər şəxsin axtarışı', self.page.locator('body').inner_text())

    def test_notification_rechecks_public_status_before_opening_cached_listing(self):
        self.go(); self.sign_in()
        # The initial browse cache still contains an active copy of this listing.
        next(r for r in self.backend.rows if r['id'] == OTHER_ID)['is_sold'] = True
        self.page.locator('#caNotificationsLaunch').click()
        row = self.page.locator('[data-notification-id="'+NOTICE_ID+'"]')
        row.locator('[data-ca-notification-open]').click()
        expect(self.page.locator('#caMarketMessage')).to_contain_text('aktiv deyil')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        self.assertFalse(self.backend.calls_for('ca_mark_notification_read'))
        reads = [c for c in self.backend.calls if c['path'] == '/rest/v1/elanlar' and c['query'].get('id') == ['eq.'+OTHER_ID]]
        self.assertTrue(reads)
        self.assertEqual(reads[-1]['query']['veziyyet'], ['eq.aktiv'])

    def test_notification_queue_drains_and_pages_without_email_or_sms(self):
        base = copy.deepcopy(self.backend.notifications[OWNER][0])
        self.backend.notifications[OWNER] = [dict(base, id=f'88888888-8888-4888-8888-{n:012d}') for n in range(25)]
        self.backend.processing_responses = 2
        self.go(); self.sign_in()
        self.page.locator('#caNotificationsLaunch').click()
        self.wait_calls('ca_list_notifications', 3)
        expect(self.page.locator('#caNotificationList [data-notification-id]')).to_have_count(24)
        self.page.locator('[data-ca-notification-page="next"]').click()
        expect(self.page.locator('#caNotificationList [data-notification-id]')).to_have_count(1)
        self.assertEqual(self.page.locator('[data-notification-id]').get_attribute('data-notification-id'), '88888888-8888-4888-8888-000000000024')
        self.page.locator('#caNotificationReadAll').click()
        self.wait_calls('ca_mark_notification_read')
        self.assertTrue(all(r['is_read'] for r in self.backend.notifications[OWNER]))
        expect(self.page.locator('#caNotificationBadge')).to_be_hidden()
        self.assertFalse(self.backend.auth_calls)

    def test_report_modal_mobile_keyboard_and_maxlength(self):
        self.page.set_viewport_size({'width': 320, 'height': 640})
        self.go(); self.sign_in(); self.detail()
        self.page.locator('#caReportListingBtn').click()
        overlay = self.page.locator('#caMarketOverlay')
        expect(overlay).to_have_attribute('role', 'dialog')
        expect(overlay).to_have_attribute('aria-modal', 'true')
        self.page.wait_for_function('document.getElementById("caToolsBar").hidden&&document.getElementById("caToolsBar").inert')
        self.assertFalse(self.page.locator('#caToolsBar').is_visible())
        self.assertEqual(self.page.locator('#caReportDetails').get_attribute('maxlength'), '1000')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 320)
        self.page.locator('#caMarketClose').focus()
        self.page.keyboard.press('Shift+Tab')
        self.assertTrue(self.page.evaluate('document.getElementById("caMarketOverlay").contains(document.activeElement)'))
        self.page.keyboard.press('Escape')
        self.assertFalse(overlay.is_visible())
        self.assertTrue(self.page.locator('#detailOverlay').is_visible())
        self.assertFalse(self.backend.calls_for('ca_report_listing'))


if __name__ == '__main__':
    unittest.main()
