"""Saved cars remain isolated by account UUID, including device-list migration.
All HTTP is mocked; login clicks never reach a real Auth or database endpoint.
"""
import json,os,unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN,OWNER,OTHER_OWNER,OWNED_ID,OTHER_ID
PHONE='+994501234567';CHANGED_PHONE='+994701234567'
class FavoritesBackend(AdminAuthBackend):
 def route(self,route):
  req=route.request;p=urlsplit(req.url)
  if p.path=='/auth/v1/token':
   body=req.post_data_json;name='a' if body['email'].startswith('a@') else 'b';uid=OWNER if name=='a' else OTHER_OWNER
   route.fulfill(content_type='application/json',body=json.dumps({'access_token':'token-'+name,'refresh_token':'refresh-'+name,'expires_at':4102444800,'user':{'id':uid,'email':body['email'],'user_metadata':{'telefon':PHONE}}}));return
  if p.path=='/auth/v1/settings':route.fulfill(content_type='application/json',body='{"external":{"phone":false,"email":true}}');return
  if p.path=='/auth/v1/user' and req.method=='GET':
   uid=OWNER if req.headers.get('authorization')=='Bearer token-a' else OTHER_OWNER
   route.fulfill(content_type='application/json',body=json.dumps({'id':uid,'phone':None,'phone_confirmed_at':None}));return
  super().route(route)
class AccountFavoritesBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.context=self.browser.new_context(viewport={'width':375,'height':812},has_touch=True);self.page=self.context.new_page();self.page.set_default_timeout(6000);self.errors=[]
  self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true');self.backend=FavoritesBackend();self.page.route('**/*',self.backend.route)
  self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')
 def tearDown(self):self.context.close();self.assertFalse(self.errors)
 def login(self,name='a'):
  self.page.locator('header .back-btn').tap();self.page.locator('#authModeSwitch').tap();self.page.locator('#authEmail').fill(name+'@example.invalid');self.page.locator('#authPassword').fill('sample-password');self.page.locator('#authSubmit').tap()
  self.page.wait_for_function('currentUser!==null&&document.body.classList.contains("cabinet-open")');self.page.wait_for_function('!caPrivateState.ownLoading');self.page.locator('[onclick="closeCabinet()"]').tap()
 def logout(self):
  self.page.locator('header .back-btn').tap();self.page.locator('[onclick="logout()"]').tap();self.page.wait_for_function('currentUser===null')
 def show_favorites(self):
  self.page.locator('header .back-btn').tap();self.page.locator('[onclick="showBuyerFavorites()"]').tap();self.page.wait_for_function('caPrivateState.favoritesLoaded&&!caPrivateState.favoritesLoading')
 def heart(self,key=OWNED_ID):
  return self.page.locator('#allGrid .car-card').filter(has=self.page.locator(f'.favorite-btn[onclick*="{key}"]')).locator('.favorite-btn')
 def test_accounts_with_the_same_phone_do_not_share_saved_cars(self):
  self.login('a');self.heart().tap();a_key=self.page.evaluate('caFavoriteStorageKey()');self.assertEqual(self.page.evaluate('favoriteKeys()'),[OWNED_ID]);self.logout();self.assertEqual(self.page.locator('#buyerFavoritesList .car-card').count(),0)
  self.login('b');b_key=self.page.evaluate('caFavoriteStorageKey()');self.assertNotEqual(a_key,b_key);self.assertEqual(self.page.evaluate('favoriteKeys()'),[]);self.assertFalse(self.heart().evaluate('e=>e.classList.contains("is-favorite")'))
  self.show_favorites();self.assertEqual(self.page.locator('#buyerFavoritesList .car-card').count(),0)
  self.logout();self.login('a');self.assertEqual(self.page.evaluate('favoriteKeys()'),[OWNED_ID]);self.assertTrue(self.heart().evaluate('e=>e.classList.contains("is-favorite")'))
 def test_phone_change_and_reload_keep_the_same_account_list(self):
  self.login();self.heart().tap();key=self.page.evaluate('caFavoriteStorageKey()')
  self.page.evaluate('''phone=>caPersistSession({...caSession,user:{...caSession.user,user_metadata:{telefon:phone}}})''',CHANGED_PHONE)
  self.assertEqual(self.page.evaluate('caFavoriteStorageKey()'),key);self.assertEqual(self.page.evaluate('favoriteKeys()'),[OWNED_ID])
  self.page.reload(wait_until='load');self.page.wait_for_function('caBrowseState.loaded');self.assertEqual(self.page.evaluate('caFavoriteStorageKey()'),key);self.assertTrue(self.heart().evaluate('e=>e.classList.contains("is-favorite")'))
  self.assertIsNone(self.page.evaluate('phone=>localStorage.getItem("cenubFavorites_"+phone)',CHANGED_PHONE))
 def test_unknown_legacy_device_list_is_never_automatically_imported(self):
  self.page.evaluate('''({phone,key})=>localStorage.setItem('cenubFavorites_'+phone,JSON.stringify([key]))''',{'phone':PHONE,'key':OWNED_ID})
  self.login('b');self.assertEqual(self.page.evaluate('favoriteKeys()'),[]);self.show_favorites();self.assertEqual(self.page.locator('#buyerFavoritesList .car-card').count(),0);self.assertTrue(self.page.locator('#caImportLegacyFavorites').is_visible())
  self.assertEqual(self.page.evaluate('phone=>JSON.parse(localStorage.getItem("cenubFavorites_"+phone))',PHONE),[OWNED_ID])
 def test_explicit_import_merges_preserves_old_data_and_binds_it_once(self):
  self.page.evaluate('''({phone,key})=>localStorage.setItem('cenubFavorites_'+phone,JSON.stringify([key]))''',{'phone':PHONE,'key':OWNED_ID});self.login('a');self.heart(OTHER_ID).tap();self.show_favorites();self.page.locator('#caImportLegacyFavorites').tap()
  self.page.wait_for_function('favoriteKeys().length===2');self.assertEqual(set(self.page.evaluate('favoriteKeys()')),{OWNED_ID,OTHER_ID});self.assertTrue(self.page.locator('#caImportLegacyFavorites').is_hidden())
  self.assertEqual(self.page.evaluate('phone=>JSON.parse(localStorage.getItem("cenubFavorites_"+phone))',PHONE),[OWNED_ID])
  self.page.evaluate('key=>toggleFavorite(key,null)',OWNED_ID);self.page.evaluate('caImportLegacyFavorites()');self.assertEqual(self.page.evaluate('favoriteKeys()'),[OTHER_ID])
  self.logout();self.login('b');self.show_favorites();self.assertTrue(self.page.locator('#caLegacyFavoritesNotice').is_hidden());self.assertFalse(self.page.evaluate('caImportLegacyFavorites()'));self.assertEqual(self.page.evaluate('favoriteKeys()'),[])
 def test_invalid_phone_metadata_cannot_address_another_uuid_storage_key(self):
  self.login('a');self.heart().tap();self.logout();self.login('b')
  self.page.evaluate('''phone=>caPersistSession({...caSession,user:{...caSession.user,user_metadata:{telefon:phone}}})''','user_'+OWNER)
  self.show_favorites();self.assertEqual(self.page.evaluate('favoriteKeys()'),[]);self.assertTrue(self.page.locator('#caLegacyFavoritesNotice').is_hidden());self.assertFalse(self.page.evaluate('caImportLegacyFavorites()'))
 def test_failed_import_keeps_existing_list_and_does_not_claim_legacy_owner(self):
  self.page.evaluate('''({phone,key})=>localStorage.setItem('cenubFavorites_'+phone,JSON.stringify([key]))''',{'phone':PHONE,'key':OWNED_ID});self.login();self.heart(OTHER_ID).tap();self.show_favorites()
  self.page.evaluate('''()=>{window.__setItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key===caFavoriteStorageKey())throw new DOMException('Full','QuotaExceededError');return window.__setItem.call(this,key,value)}}''')
  self.page.locator('#caImportLegacyFavorites').tap();self.assertIn('gətirilmədi',self.page.locator('#caLegacyFavoritesStatus').inner_text());self.assertEqual(self.page.evaluate('favoriteKeys()'),[OTHER_ID]);self.assertTrue(self.page.locator('#caImportLegacyFavorites').is_visible())
  self.assertIsNone(self.page.evaluate('phone=>localStorage.getItem("cenubFavorites_legacy_owner_"+encodeURIComponent("cenubFavorites_"+phone))',PHONE));self.page.evaluate('()=>{Storage.prototype.setItem=window.__setItem}')
 def test_another_tab_updates_only_the_current_uuid_list(self):
  self.login();self.heart().tap();second=self.context.new_page();second.route('**/*',self.backend.route);second.goto(ORIGIN,wait_until='load');second.wait_for_function('caBrowseState.loaded')
  second.locator('#allGrid .car-card').filter(has=second.locator(f'.favorite-btn[onclick*="{OTHER_ID}"]')).locator('.favorite-btn').tap()
  self.page.wait_for_function('favoriteKeys().length===2&&document.querySelectorAll("#allGrid .favorite-btn.is-favorite").length===2');self.assertEqual(set(self.page.evaluate('favoriteKeys()')),{OWNED_ID,OTHER_ID});second.close()
