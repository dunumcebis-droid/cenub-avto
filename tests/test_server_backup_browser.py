"""Admin application export: mock APIs, parse produced ZIPs, no real records/files."""
import copy,hashlib,io,json,os,tempfile,unittest,zipfile
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN,OWNER,OTHER_OWNER
RESOURCES=['elanlar','paket_sorgulari','profiller','adminler','storage_objects']
PHOTO_BYTES=[b'first-original-photo-bytes',b'second-original-photo-bytes']
def sha(value):return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()
def rowhash(row):return sha(json.dumps(row,sort_keys=True,separators=(',',':')))
class BackupBackend(AdminAuthBackend):
 def __init__(self):
  super().__init__();self.reads=[];self.manifests=0;self.mode='ok';self.held=[]
  self.resources={name:[] for name in RESOURCES}
  self.resources['elanlar']=[{'id':f'11111111-2222-4333-8444-{i:012d}','model':'Server-only '+str(i),'telefon':'+994000000000'} for i in range(105)]
  self.resources['profiller']=[{'id':OWNER,'telefon':'+994000000000'}]
  self.resources['adminler']=[{'istifadeci_id':OWNER}]
  self.resources['storage_objects']=[{'id':f'22222222-3333-4444-8555-{i:012d}','bucket_id':'elan-sekilleri','name':OWNER+'/photo-'+str(i)+'.jpg','metadata':{'size':len(data),'mimetype':'image/jpeg'}} for i,data in enumerate(PHOTO_BYTES)]
 def manifest(self):
  return {'version':1,'resources':[{'name':name,'count':len(rows),'sha256':sha(''.join(rowhash(row) for row in rows))} for name,rows in self.resources.items()]}
 def route(self,route):
  req=route.request;p=urlsplit(req.url);path=p.path
  if path.startswith('/rest/v1/rpc/ca_admin_export_'):
   self.reads.append(path);body=req.post_data_json
   if req.headers.get('authorization')!='Bearer backup-token':route.fulfill(status=403,content_type='application/json',body='{"message":"Admin only"}');return
   if path.endswith('_manifest'):
    self.manifests+=1;data=self.manifest()
    if self.mode=='changed' and self.manifests>=3:data['resources'][0]['sha256']='f'*64
    if self.mode=='hold_manifest':self.held.append(route);return
   else:
    rows=self.resources[body['p_resource']];cursor=body.get('p_cursor')
    key=lambda row:row.get('id') or row['istifadeci_id']
    selected=[row for row in rows if not cursor or key(row)>cursor][:100]
    data={'items':selected,'hashes':[rowhash(row) for row in selected],'next_cursor':key(selected[-1]) if len(selected)==100 else None}
    if self.mode=='bad_hash' and selected:data['hashes'][0]='0'*64
   route.fulfill(content_type='application/json',body=json.dumps(data));return
  if path.startswith('/storage/v1/object/public/elan-sekilleri/'):
   if self.mode=='hold_photo':self.held.append(route);return
   if self.mode=='missing':route.fulfill(status=404,body='missing');return
   number=int(path.rsplit('photo-',1)[-1].split('.')[0]);route.fulfill(content_type='image/jpeg',body=PHOTO_BYTES[number]);return
  super().route(route)
class ServerBackupBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  self.context=self.browser.new_context(accept_downloads=True,viewport={'width':375,'height':812});self.page=self.context.new_page();self.page.set_default_timeout(6000);self.errors=[];self.downloads=[]
  self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.on('download',lambda d:self.downloads.append(d));self.backend=BackupBackend();self.page.route('**/*',self.backend.route)
  self.page.add_init_script('window.showSaveFilePicker=undefined;window.alert=()=>{};window.confirm=()=>true')
  self.page.goto(ORIGIN,wait_until='load');self.page.wait_for_function('caBrowseState.loaded')
 def tearDown(self):
  for route in self.backend.held:
   try:route.abort()
   except Exception:pass
  self.page.wait_for_timeout(20)
  self.context.close();self.assertFalse(self.errors)
 def login(self,owner=OWNER,token='backup-token'):
  self.page.evaluate('''({id,token})=>{currentUser={id,email:'backup@example.invalid',phone:'+994000000000'};caSession={access_token:token,expires_at:4102444800,user:{id}};updateAccountUI()}''',{'id':owner,'token':token})
 def open(self):
  self.page.evaluate('caShowBackup()');self.page.wait_for_function("document.getElementById('caServerBackupStart')&&!document.getElementById('caServerBackupStart').disabled")
 def archive(self):
  with self.page.expect_download() as event:self.page.locator('#caServerBackupStart').click()
  return Path(event.value.path()).read_bytes()
 def test_explicit_admin_export_contains_all_server_pages_and_original_photo_bytes(self):
  self.login();self.open();self.assertEqual(len(self.backend.reads),1);self.assertFalse(self.downloads)
  data=self.archive();self.assertIn('Tam nüsxə hazırdır',self.page.locator('#caServerBackupStatus').inner_text())
  with zipfile.ZipFile(io.BytesIO(data)) as archive:
   self.assertIsNone(archive.testzip());manifest=json.loads(archive.read('manifest.json'));self.assertEqual(len(manifest['resources']),5)
   actual=[]
   for name in archive.namelist():
    self.assertNotIn('..',name.split('/'))
    if name.startswith('data/elanlar/'):actual.extend(json.loads(archive.read(name))['items'])
   self.assertEqual(actual,self.backend.resources['elanlar'])
   self.assertEqual([archive.read(item['path']) for item in manifest['photos']],PHOTO_BYTES)
   for file in manifest['files']:self.assertEqual(sha(archive.read(file['path'])),file['sha256'])
   self.assertNotIn(b'backup-token',b''.join(archive.read(name) for name in archive.namelist()))
 def test_guest_and_ordinary_account_cannot_export_or_download(self):
  self.page.evaluate('caShowBackup()');self.assertTrue(self.page.locator('#caServerBackupStart').is_disabled());self.assertFalse(self.backend.reads)
  self.login(OTHER_OWNER,'ordinary-token');self.page.evaluate('caShowBackup()');self.page.wait_for_function("document.getElementById('caServerBackupStatus').getAttribute('role')==='alert'")
  self.assertTrue(self.page.locator('#caServerBackupStart').is_disabled());self.assertFalse(self.downloads)
 def test_missing_photo_changed_manifest_or_hash_never_produces_success_or_partial_download(self):
  self.login()
  for mode in ('missing','changed','bad_hash'):
   with self.subTest(mode=mode):
    self.backend.mode='ok';self.backend.manifests=0;self.open();self.backend.mode=mode;self.page.locator('#caServerBackupStart').click()
    self.page.wait_for_function("document.getElementById('caServerBackupStatus').getAttribute('role')==='alert'")
    self.assertNotIn('Tam nüsxə hazırdır',self.page.locator('#caServerBackupStatus').inner_text());self.assertFalse(self.downloads)
 def test_logout_aborts_inflight_photo_download_and_clears_export(self):
  self.login();self.open();self.backend.mode='hold_photo';self.page.locator('#caServerBackupStart').click()
  for _ in range(100):
   if self.backend.held:break
   self.page.wait_for_timeout(20)
  self.assertTrue(self.backend.held)
  self.page.evaluate('currentUser=null;caSession=null;updateAccountUI()');self.page.wait_for_timeout(100)
  self.assertTrue(self.page.locator('#caServerBackupStart').is_disabled());self.assertFalse(self.downloads)
 def test_traversal_photo_name_is_rejected_before_fetch_or_download(self):
  self.backend.resources['storage_objects'][0]['name']='../outside.jpg';self.login();self.open();self.page.locator('#caServerBackupStart').click()
  self.page.wait_for_function("document.getElementById('caServerBackupStatus').getAttribute('role')==='alert'")
  self.assertFalse(self.downloads)
 def test_streaming_path_commits_only_verified_zip(self):
  self.page.evaluate('''()=>{window.__stream=[];window.__streamClosed=false;window.showSaveFilePicker=async()=>({createWritable:async()=>({write:async bytes=>window.__stream.push(Array.from(bytes)),close:async()=>window.__streamClosed=true,abort:async()=>{window.__stream=[]}})})}''')
  self.login();self.open();self.page.locator('#caServerBackupStart').click();self.page.wait_for_function('window.__streamClosed')
  data=bytes(self.page.evaluate('window.__stream.flat()'))
  with zipfile.ZipFile(io.BytesIO(data)) as archive:self.assertIsNone(archive.testzip());self.assertIn('manifest.json',archive.namelist())
  self.assertFalse(self.downloads)
