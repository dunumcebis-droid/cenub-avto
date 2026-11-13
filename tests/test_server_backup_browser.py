"""Admin application export: mock APIs, parse produced ZIPs, no real records/files."""
import copy,hashlib,io,json,os,tempfile,unittest,uuid,zipfile
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from test_admin_auth_browser import AdminAuthBackend
from test_listing_management_browser import ORIGIN,OWNER,OTHER_OWNER
RESOURCES=['elanlar','paket_sorgulari','profiller','adminler','storage_objects',
 'listing_stats','listing_events','listing_reports','saved_searches',
 'approved_listing_events','notification_progress','search_notifications']
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
  listing=self.resources['elanlar'][0]['id'];search='33333333-3333-4333-8333-333333333333'
  self.resources['listing_stats']=[{'elan_id':listing,'views':41,'contact_clicks':7}]
  self.resources['listing_events']=[{'elan_id':listing,'kind':'view','day':'2026-11-13','visitor_hash':sha(str(i))[:32]} for i in range(105)]
  self.resources['listing_reports']=[{'id':'44444444-4444-4444-8444-444444444444','elan_id':listing,'reporter_id':OTHER_OWNER,'reason':'fraud','details':'Synthetic report','status':'open','admin_note':'Private review note','created_at':'2026-11-13T10:00:00Z','resolved_at':None}]
  self.resources['saved_searches']=[{'id':search,'owner_id':OWNER,'name':'BMW axtarışım','filters':{'make':'BMW','pack':'VIP'},'filter_hash':sha('BMW'),'start_seq':3,'created_at':'2026-11-13T10:00:00Z'}]
  self.resources['approved_listing_events']=[{'seq':i,'elan_id':listing,'created_at':'2026-11-13T10:00:00Z'} for i in range(1,106)]
  self.resources['notification_progress']=[{'owner_id':OWNER,'cursor_seq':105}]
  self.resources['search_notifications']=[{'id':'55555555-5555-4555-8555-555555555555','owner_id':OWNER,'search_id':search,'elan_id':listing,'created_at':'2026-11-13T10:00:00Z','is_read':False}]
 def key(self,name,row):
  # Public cursors remain opaque UUIDs even for non-UUID/composite table keys.
  if name=='approved_listing_events':return str(uuid.UUID(int=row['seq']))
  if name=='listing_events':return str(uuid.UUID(hex=sha(json.dumps([row[k] for k in ('elan_id','kind','day','visitor_hash')]))[:32]))
  return row.get('id') or row.get('istifadeci_id') or row.get('elan_id') or row['owner_id']
 def ordered(self,name):return sorted(self.resources[name],key=lambda row:self.key(name,row))
 def manifest(self):
  return {'version':1,'resources':[{'name':name,'count':len(self.resources[name]),'sha256':sha(''.join(rowhash(row) for row in self.ordered(name)))} for name in RESOURCES]}
 def route(self,route):
  req=route.request;p=urlsplit(req.url);path=p.path
  if path.startswith('/rest/v1/rpc/ca_admin_export_'):
   self.reads.append(path);body=req.post_data_json
   if req.headers.get('authorization')!='Bearer backup-token':route.fulfill(status=403,content_type='application/json',body='{"message":"Admin only"}');return
   if path.endswith('_manifest'):
    self.manifests+=1;data=self.manifest()
    if self.mode=='changed' and self.manifests>=3:data['resources'][0]['sha256']='f'*64
    if self.mode=='missing_resource':data['resources'].pop()
    if self.mode=='duplicate_resource':data['resources'][-1]=copy.deepcopy(data['resources'][0])
    if self.mode=='unexpected_resource':data['resources'][-1]['name']='auth_users'
    if self.mode=='hold_manifest':self.held.append(route);return
   else:
    name=body['p_resource'];assert name in RESOURCES;assert body['p_page_size']==100
    rows=self.ordered(name);cursor=body.get('p_cursor')
    if self.mode=='page_failure' and name=='listing_events':route.fulfill(status=503,content_type='application/json',body='{"message":"Offline page unavailable"}');return
    if self.mode=='truncated_private' and name=='listing_events':rows=rows[:-1]
    size=101 if self.mode=='oversized_page' and name=='listing_events' else 100
    selected=[row for row in rows if not cursor or self.key(name,row)>cursor][:size]
    data={'items':selected,'hashes':[rowhash(row) for row in selected],'next_cursor':self.key(name,selected[-1]) if len(selected)==size else None}
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
   self.assertIsNone(archive.testzip());manifest=json.loads(archive.read('manifest.json'))
   self.assertEqual([resource['name'] for resource in manifest['resources']],RESOURCES)
   actual={name:[] for name in RESOURCES}
   for name in archive.namelist():
    self.assertNotIn('..',name.split('/'))
    if name.startswith('data/'):
     page=json.loads(archive.read(name));self.assertEqual(page['resource'],name.split('/')[1])
     actual[page['resource']].extend(page['items'])
   for resource in RESOURCES:self.assertEqual(actual[resource],self.backend.ordered(resource),resource)
   self.assertEqual(len([name for name in archive.namelist() if name.startswith('data/listing_events/')]),2)
   self.assertEqual(len([name for name in archive.namelist() if name.startswith('data/approved_listing_events/')]),2)
   self.assertEqual([archive.read(item['path']) for item in manifest['photos']],PHOTO_BYTES)
   for file in manifest['files']:self.assertEqual(sha(archive.read(file['path'])),file['sha256'])
   self.assertNotIn(b'backup-token',b''.join(archive.read(name) for name in archive.namelist()))
 def test_guest_and_ordinary_account_cannot_export_or_download(self):
  self.page.evaluate('caShowBackup()');self.assertTrue(self.page.locator('#caServerBackupStart').is_disabled());self.assertFalse(self.backend.reads)
  self.login(OTHER_OWNER,'ordinary-token');self.page.evaluate('caShowBackup()');self.page.wait_for_function("document.getElementById('caServerBackupStatus').getAttribute('role')==='alert'")
  self.assertTrue(self.page.locator('#caServerBackupStart').is_disabled());self.assertFalse(self.downloads)
 def test_missing_duplicate_or_unexpected_resource_manifest_is_rejected_before_export(self):
  self.login()
  for mode in ('missing_resource','duplicate_resource','unexpected_resource'):
   with self.subTest(mode=mode):
    self.backend.mode=mode;self.page.evaluate('caShowBackup()')
    self.page.wait_for_function("document.getElementById('caServerBackupStatus').getAttribute('role')==='alert'")
    self.assertTrue(self.page.locator('#caServerBackupStart').is_disabled());self.assertFalse(self.downloads)
    self.assertFalse(any(path.endswith('_page') for path in self.backend.reads))
 def test_missing_photo_changed_manifest_or_hash_never_produces_success_or_partial_download(self):
  self.login()
  for mode in ('missing','changed','bad_hash','page_failure','truncated_private','oversized_page'):
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
