"""Offline comparison regressions; every HTTP request uses synthetic fixtures."""
import os
import unittest

from playwright.sync_api import sync_playwright
from test_listing_management_browser import OfflineBackend, ORIGIN, OWNER, OTHER_OWNER, OWNED_ID, OTHER_ID, owned_row


class ComparisonBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1280,'height':1000})
        self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.page.add_init_script('window.__alerts=[];window.alert=m=>window.__alerts.push(String(m));window.confirm=()=>true')
        self.backend=OfflineBackend();self.page.route('**/*',self.backend.route)
        self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        self.context.close();self.assertFalse(self.errors)

    def sign_in(self,owner=OWNER):
        self.page.evaluate('''async id=>await caPersistSession({access_token:'offline-token',expires_at:4102444800,
            user:{id,email:'fixture@example.invalid',user_metadata:{telefon:'+994000000000'}}})''',owner)

    def select(self,key=OWNED_ID):
        self.page.evaluate('key=>caToggleCompare(key)',key)

    def comparison_values(self,label):
        return self.page.locator('#caDialogBody tr').filter(has=self.page.locator('th',has_text=label)).locator('td').all_text_contents()

    def test_comparison_resolves_new_price_and_mileage_after_public_refresh(self):
        self.select();self.page.evaluate('caShowCompare()')
        self.assertEqual(self.comparison_values('Qiymət'),[self.page.evaluate('caFormatPrice(42000)')])
        row=next(row for row in self.backend.rows if row['id']==OWNED_ID)
        row.update(qiymet=43000,yurus=0)
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'1')
        self.assertEqual(self.comparison_values('Qiymət'),[self.page.evaluate('caFormatPrice(43000)')])
        self.assertEqual(self.comparison_values('Yürüş'),['0 km'])
        self.page.evaluate('caCloseDialog();caShowCompare()')
        self.assertEqual(self.comparison_values('Qiymət'),[self.page.evaluate('caFormatPrice(43000)')])

    def test_offscreen_selection_survives_cache_eviction_and_refreshes_when_seen_again(self):
        rows=[]
        for n in range(25):
            row=owned_row();row.update(id=f'66666666-6666-4666-8666-{n:012d}',model=f'Page-{n:02d}',paket_adi='Pulsuz',qiymet=20000+n)
            rows.append(row)
        self.backend.rows=rows
        self.page.evaluate('async()=>await caFetchListings(1)')
        first=rows[0]['id'];last=rows[-1]['id']
        self.select(first)
        self.page.evaluate('async()=>await caFetchListings(2)')
        self.assertFalse(self.page.evaluate('key=>caListingCache.has(key)||caRemoteCars.some(car=>listingKey(car)===key)',first))
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'1')
        self.select(last);self.page.evaluate('caShowCompare()')
        self.assertEqual(self.comparison_values('Marka / model'),['BMW Page-00','BMW Page-24'])
        rows[0]['qiymet']=21000
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'2')
        self.assertEqual(self.comparison_values('Qiymət'),self.page.evaluate('[caFormatPrice(21000),caFormatPrice(20024)]'))

    def test_verified_archive_removes_only_its_comparison_column(self):
        self.sign_in();self.page.evaluate('async()=>await caFetchMyListings()')
        self.select();self.select(OTHER_ID);self.page.evaluate('caShowCompare()')
        self.page.evaluate('async id=>await deleteCar(id)',OWNED_ID)
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'1')
        self.assertEqual(self.comparison_values('Marka / model'),['Toyota Corolla'])
        self.assertTrue(self.page.locator('#caOverlay').is_visible())
        self.assertEqual(next(row for row in self.backend.rows if row['id']==OWNED_ID)['veziyyet'],'silindi')

    def test_unconfirmed_archive_keeps_comparison_selection(self):
        self.sign_in();self.page.evaluate('async()=>await caFetchMyListings()')
        self.select();self.page.evaluate('caShowCompare()');self.backend.empty_delete=True
        self.page.evaluate('async id=>await deleteCar(id)',OWNED_ID)
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'1')
        self.assertEqual(self.comparison_values('Marka / model'),['BMW 530'])
        self.assertTrue(self.page.evaluate('__alerts.some(message=>message.startsWith("Silinmədi:"))'))

    def test_known_private_owner_row_disappears_without_public_page_refresh(self):
        self.sign_in();self.page.evaluate('async()=>await caFetchMyListings()')
        row=next(row for row in self.backend.rows if row['id']==OWNED_ID)
        for status in ('gozlemede','reddedildi'):
            with self.subTest(status=status):
                row.update(veziyyet='aktiv',model='530')
                self.page.evaluate('async()=>await caFetchListings(1)')
                self.select();self.page.evaluate('caShowCompare()')
                row.update(veziyyet=status,model='Private owner revision',qiymet=91919)
                self.page.evaluate('async()=>await caFetchMyListings()')
                self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'0')
                self.assertEqual(self.page.locator('#caDialogBody table').count(),0)
                self.assertNotIn('Private owner revision',self.page.locator('#caDialogBody').inner_text())

    def test_confirmed_edit_and_admin_rejection_remove_selection_even_without_refresh(self):
        self.sign_in();self.page.evaluate('async()=>await caFetchMyListings()')
        self.select();self.page.evaluate('caShowCompare()')
        self.page.evaluate('''async id=>{editCar(id);const source=myCars().find(car=>car._id===id);
            await caSaveRemoteCar({...source,price:43000},true,currentUser.id,id);}''',OWNED_ID)
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'0')
        self.assertEqual(self.page.locator('#caDialogBody table').count(),0)
        self.select()
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'0','An old active cache row must not restore a confirmed private edit')
        self.select(OTHER_ID);self.page.evaluate('caShowCompare()')
        next(row for row in self.backend.rows if row['id']==OTHER_ID)['veziyyet']='reddedildi'
        self.page.evaluate("async id=>await caRequest('/rest/v1/rpc/ca_admin_status','POST',{p_id:id,p_status:'reddedildi'},'offline-admin-token')",OTHER_ID)
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'0')
        self.assertEqual(self.page.locator('#caDialogBody table').count(),0)
        self.select(OTHER_ID)
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'0','A rejected listing cannot be restored from a stale cache row')
        next(row for row in self.backend.rows if row['id']==OWNED_ID)['veziyyet']='aktiv'
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.select();self.page.evaluate('caShowCompare()')
        self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'1')
        self.assertEqual(self.comparison_values('Qiymət'),[self.page.evaluate('caFormatPrice(43000)')])

    def test_logout_and_direct_account_switch_clear_comparison_and_old_dialog_content(self):
        self.sign_in()
        for action in ('switch','logout'):
            with self.subTest(action=action):
                self.select();self.page.evaluate('caShowCompare()')
                self.assertIn('BMW 530',self.page.locator('#caDialogBody').inner_text())
                if action=='switch':
                    self.sign_in(OTHER_OWNER)
                else:
                    self.page.evaluate('async()=>await logout()')
                self.assertEqual(self.page.locator('#caCompareCount').inner_text(),'0')
                self.assertFalse(self.page.locator('#caOverlay').is_visible())
                self.assertNotIn('BMW 530',self.page.locator('#caDialogBody').inner_text())
                self.page.evaluate('render();caShowCompare()')
                self.assertEqual(self.page.locator('#caDialogBody table').count(),0)
                self.page.evaluate('caCloseDialog()')

    def test_refresh_does_not_reopen_comparison_or_replace_another_dialog(self):
        self.select();self.page.evaluate('caShowCompare();caCloseDialog()')
        row=next(row for row in self.backend.rows if row['id']==OWNED_ID);row['qiymet']=43000
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.assertFalse(self.page.locator('#caOverlay').is_visible())
        self.page.evaluate('caShowPolicy()')
        title=self.page.locator('#caDialogTitle').inner_text();body=self.page.locator('#caDialogBody').inner_text()
        row['qiymet']=44000
        self.page.evaluate('async()=>await caFetchListings(1)')
        self.assertTrue(self.page.locator('#caOverlay').is_visible())
        self.assertEqual(self.page.locator('#caDialogTitle').inner_text(),title)
        self.assertEqual(self.page.locator('#caDialogBody').inner_text(),body)
        self.page.evaluate('caShowCompare()')
        self.assertEqual(self.comparison_values('Qiymət'),[self.page.evaluate('caFormatPrice(44000)')])


if __name__=='__main__':unittest.main(verbosity=2)
