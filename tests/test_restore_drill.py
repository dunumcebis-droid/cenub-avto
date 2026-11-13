"""Strict ZIP restoration gates; synthetic bytes only, no HTTP or cloud writes."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

spec=importlib.util.spec_from_file_location('restore_drill',Path(__file__).resolve().parents[1]/'tools/restore_drill.py')
drill=importlib.util.module_from_spec(spec);spec.loader.exec_module(drill)
PHOTO_ID='22222222-2222-4222-8222-222222222222'
PHOTO_DATA=b'synthetic-original-image-bytes'

def content():
    resources=[dict(name=name,count=0,sha256=drill.sha(''),pages=[]) for name in drill.RESOURCES]
    data={}
    for name,row in [
      ('elanlar',{'id':'11111111-1111-4111-8111-111111111111','ca_data':'{"legacy":"scalar JSON string"}','marka':'Cənub'}),
      ('storage_objects',{'id':PHOTO_ID,'bucket_id':'elan-sekilleri','name':'owner/original.jpg','metadata':{'size':len(PHOTO_DATA),'mimetype':'image/jpeg'}})]:
        item=next(r for r in resources if r['name']==name)
        page_path=f'data/{name}/000001.json';h=drill.sha('synthetic canonical '+name)
        data[page_path]=json.dumps({'resource':name,'items':[row],'hashes':[h]},ensure_ascii=False).encode()
        item.update(count=1,sha256=drill.sha(h),pages=[page_path])
    photo_path='photos/'+PHOTO_ID+'.jpg';data[photo_path]=PHOTO_DATA
    files=[{'path':name,'bytes':len(value),'sha256':drill.sha(value)} for name,value in data.items()]
    manifest={'format':'cenub-avto-server-data-backup','version':1,'resources':resources,'files':files,
      'photos':[{'path':photo_path,'id':PHOTO_ID,'originalName':'owner/original.jpg','bytes':len(PHOTO_DATA),'sha256':drill.sha(PHOTO_DATA)}]}
    return manifest,data

def archive(manifest=None,files=None,compression=zipfile.ZIP_STORED,extra=None):
    if manifest is None:manifest,files=content()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=compression) as z:
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
        for name,value in files.items():z.writestr(name,value)
        if extra:
            for name,value in extra:z.writestr(name,value)
    buffer.seek(0);return buffer

class RestoreArchiveTests(unittest.TestCase):
    def test_complete_archive_keeps_original_bytes_and_json_scalar_types(self):
        manifest,_=content();value=drill.validate_archive(archive(),manifest)
        self.assertEqual(value['photos'][0]['bytes'],PHOTO_DATA)
        self.assertIsInstance(value['rows']['elanlar'][0]['ca_data'],str)
        self.assertEqual(value['rows']['elanlar'][0]['marka'],'Cənub')
        self.assertEqual(len(value['manifest']['resources']),12)

    def test_empty_resources_are_valid_without_fake_data_pages(self):
        manifest,files=content();manifest['resources']=[dict(name=n,count=0,sha256=drill.sha(''),pages=[]) for n in drill.RESOURCES]
        manifest.update(files=[],photos=[])
        value=drill.validate_archive(archive(manifest,{}));self.assertFalse(any(value['rows'].values()))

    def test_captured_server_manifest_must_match(self):
        manifest,_=content();expected=copy.deepcopy(manifest);expected['resources'][0]['count']+=1
        with self.assertRaisesRegex(ValueError,'captured server manifest'):drill.validate_archive(archive(),expected)

    def test_duplicate_resource_is_rejected(self):
        manifest,files=content();manifest['resources'][-1]=copy.deepcopy(manifest['resources'][0])
        with self.assertRaises(ValueError):drill.validate_archive(archive(manifest,files))

    def test_duplicate_zip_entry_is_rejected(self):
        manifest,files=content()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            value=archive(manifest,files,extra=[('manifest.json',b'{}')])
        with self.assertRaisesRegex(ValueError,'Duplicate archive entry'):drill.validate_archive(value)

    def test_unreferenced_or_missing_files_are_rejected(self):
        manifest,files=content()
        for changed in [dict(files,**{'data/elanlar/000002.json':b'{}'}),{k:v for k,v in files.items() if not k.startswith('photos/')}]:
            with self.subTest(files=len(changed)),self.assertRaises(ValueError):drill.validate_archive(archive(manifest,changed))

    def test_archive_traversal_path_is_rejected_before_extraction(self):
        manifest,files=content()
        with self.assertRaisesRegex(ValueError,'Invalid archive path'):
            drill.validate_archive(archive(manifest,files,extra=[('../outside.txt',b'never extract')]))

    def test_symlinks_are_rejected(self):
        manifest,files=content();link=zipfile.ZipInfo('photos/link');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaisesRegex(ValueError,'symlink'):
            drill.validate_archive(archive(manifest,files,extra=[(link,b'/outside')]))

    def test_photo_original_path_cannot_escape_local_recovery_directory(self):
        manifest,files=content();manifest['photos'][0]['originalName']='../outside'
        with self.assertRaisesRegex(ValueError,'Invalid archive path'):drill.validate_archive(archive(manifest,files))

    def test_storage_photo_membership_must_match_exactly(self):
        manifest,files=content();manifest['photos'][0]['originalName']='owner/wrong.jpg'
        with self.assertRaisesRegex(ValueError,'membership'):drill.validate_archive(archive(manifest,files))

    def test_crc_corruption_is_rejected(self):
        raw=bytearray(archive().getvalue());offset=raw.index(PHOTO_DATA);raw[offset]^=1
        with self.assertRaises((ValueError,zipfile.BadZipFile)):drill.validate_archive(io.BytesIO(raw))

    def test_valid_crc_with_changed_file_content_still_fails_sha256(self):
        manifest,files=content();files[next(k for k in files if k.startswith('photos/'))]=b'tampered-but-valid-zip-crc'
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):drill.validate_archive(archive(manifest,files))

    def test_resource_page_cannot_claim_another_table(self):
        manifest,files=content();path='data/elanlar/000001.json';page=json.loads(files[path]);page['resource']='adminler';files[path]=json.dumps(page).encode()
        entry=next(f for f in manifest['files'] if f['path']==path);entry.update(bytes=len(files[path]),sha256=drill.sha(files[path]))
        with self.assertRaisesRegex(ValueError,'page content'):drill.validate_archive(archive(manifest,files))

    def test_resource_hash_count_and_page_order_are_checked(self):
        for mode in ['hash','count','order']:
            manifest,files=content()
            if mode=='hash':manifest['resources'][0]['sha256']='0'*64
            if mode=='count':manifest['resources'][0]['count']+=1
            if mode=='order':manifest['resources'][0]['pages']=['data/elanlar/000002.json']
            with self.subTest(mode=mode),self.assertRaises(ValueError):drill.validate_archive(archive(manifest,files))

    def test_compressed_or_oversized_archives_are_rejected_before_reading(self):
        with self.assertRaisesRegex(ValueError,'STORE-only'):drill.validate_archive(archive(compression=zipfile.ZIP_DEFLATED))
        original=drill.MAX_ARCHIVE_BYTES
        try:
            drill.MAX_ARCHIVE_BYTES=10
            with self.assertRaisesRegex(ValueError,'memory bound'):drill.validate_archive(archive())
        finally:drill.MAX_ARCHIVE_BYTES=original

    def test_invalid_storage_names_never_reach_http(self):
        for name in ['../escape','/absolute','a\\b','a//b','a/./b','a/../b','a\x00b']:
            with self.subTest(name=name),self.assertRaises(ValueError):
                drill.photo_url({'id':PHOTO_ID,'bucket_id':'elan-sekilleri','name':name})
        with self.assertRaises(ValueError):drill.photo_url({'id':PHOTO_ID,'bucket_id':'private-other','name':'safe.jpg'})

    def test_snapshot_count_hash_pairing_is_required(self):
        manifest,_=content();snapshot={'manifest':manifest,'resources':{n:{'pages':[]} for n in drill.RESOURCES}}
        with self.assertRaisesRegex(ValueError,'Snapshot does not match'):drill.snapshot_rows(snapshot,'elanlar')

    def test_private_artifacts_cannot_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'private.json';drill.private_write(target,b'private fixture')
            self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
            with self.assertRaises(FileExistsError):drill.private_write(target,b'replace')
            self.assertEqual(target.read_bytes(),b'private fixture')

if __name__=='__main__':unittest.main()
