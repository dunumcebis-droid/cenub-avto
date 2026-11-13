#!/usr/bin/env python3
"""Verify an application ZIP and restore it only into an isolated local drill.

No database URL or production target is accepted. The optional capture harness
feeds a read-only snapshot to the real browser ZIP writer; it never signs in.
Private snapshots, archives and recovered files stay in a 0700 workspace.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import urllib.request
import urllib.error
import time
from urllib.parse import quote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ['elanlar', 'paket_sorgulari', 'profiller', 'adminler', 'storage_objects',
             'listing_stats', 'listing_events', 'listing_reports', 'saved_searches',
             'approved_listing_events', 'notification_progress', 'search_notifications']
PHOTO_BASE = 'https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/'
HEX = re.compile(r'^[0-9a-f]{64}$')
UUID = re.compile(r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$', re.I)
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_PHOTO_BYTES = 50 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def private_write(path, data):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data.encode() if isinstance(data, str) else data)


def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('Invalid archive path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Invalid archive path')
    return value


def resources_from_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('version') != 1:
        raise ValueError('Unsupported manifest')
    rows = manifest.get('resources')
    if not isinstance(rows, list) or [r.get('name') for r in rows if isinstance(r, dict)] != RESOURCES:
        raise ValueError('Expected exactly twelve ordered resources')
    for item in rows:
        if type(item.get('count')) is not int or item['count'] < 0 or not HEX.fullmatch(str(item.get('sha256', ''))):
            raise ValueError('Invalid resource count/hash')
    return rows


def photo_url(item):
    name = safe_path(item.get('name'))
    if item.get('bucket_id') != 'elan-sekilleri' or not UUID.fullmatch(str(item.get('id', ''))):
        raise ValueError('Unexpected photo bucket or identifier')
    return PHOTO_BASE + '/'.join(quote(part, safe='') for part in name.split('/'))


class LocalPhotoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        base = urlsplit(PHOTO_BASE)
        if parsed.scheme != 'https' or parsed.netloc != base.netloc or not parsed.path.startswith(base.path):
            raise ValueError('Photo redirect outside the fixed storage origin')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def snapshot_rows(snapshot, name):
    resources_from_manifest(snapshot['manifest'])
    pages = snapshot['resources'][name]['pages']
    rows, hashes = [], []
    for page in pages:
        if not isinstance(page.get('items'), list) or len(page['items']) != len(page.get('hashes', [])):
            raise ValueError('Invalid snapshot page')
        rows.extend(page['items']); hashes.extend(page['hashes'])
    expected = next(r for r in snapshot['manifest']['resources'] if r['name'] == name)
    if len(rows) != expected['count'] or sha(''.join(hashes)) != expected['sha256']:
        raise ValueError('Snapshot does not match its manifest')
    return rows


def download_photos(snapshot, directory):
    directory.mkdir(mode=0o700, parents=False, exist_ok=True)
    if directory.stat().st_mode & 0o077:
        raise ValueError('Photo cache must be private')
    def one(item):
        url = photo_url(item)
        target = directory / (item['id'] + '.bin')
        expected = item.get('metadata', {}).get('size', item.get('metadata', {}).get('contentLength'))
        http_gets = 0
        cached = target.exists()
        if cached:
            data = target.read_bytes()
        else:
            opener = urllib.request.build_opener(LocalPhotoRedirects())
            for attempt in range(3):
                try:
                    request = urllib.request.Request(url, method='GET', headers={'Cache-Control': 'no-cache'})
                    http_gets += 1
                    with opener.open(request, timeout=45) as response:
                        if response.status != 200:
                            raise ValueError('Photo GET failed')
                        data = response.read(MAX_PHOTO_BYTES + 1)
                    break
                except urllib.error.HTTPError as error:
                    if error.code not in (429, 502, 503, 504) or attempt == 2:
                        raise
                    retry = error.headers.get('Retry-After', '')
                    if retry and not retry.isdigit():
                        raise ValueError('Deferred Retry-After requires a later rerun')
                    seconds = int(retry) if retry else 2 ** attempt
                    if seconds > 60:
                        raise ValueError('Retry-After exceeds this bounded drill window')
                    time.sleep(seconds)
            if not data or len(data) > MAX_PHOTO_BYTES:
                raise ValueError('Photo is empty or above the drill limit')
            if expected is not None and int(expected) != len(data):
                raise ValueError('Photo length does not match storage metadata')
            private_write(target, data)
        if not data or len(data) > MAX_PHOTO_BYTES or expected is not None and int(expected) != len(data):
            raise ValueError('Cached photo differs from the snapshot metadata')
        return url, {'path':target, 'bytes':len(data), 'sha256':sha(data), 'httpGets':http_gets, 'cached':cached}
    objects = snapshot_rows(snapshot, 'storage_objects')
    if sum(int(o.get('metadata', {}).get('size', 0)) for o in objects) > MAX_ARCHIVE_BYTES:
        raise ValueError('Photo dataset exceeds the isolated drill memory bound')
    with ThreadPoolExecutor(max_workers=4) as pool:
        photos = dict(pool.map(one, objects))
    if len(photos) != len(objects) or sum(p['bytes'] for p in photos.values()) > MAX_ARCHIVE_BYTES:
        raise ValueError('Photo dataset membership or size mismatch')
    return photos


def browser_zip(snapshot, photos, destination):
    """Run the actual 14-server-backup.js, with all browser network intercepted."""
    from playwright.sync_api import sync_playwright
    origin = 'http://127.0.0.1:8766/'
    html = '''<!doctype html><html><body><h1 id="caDialogTitle"></h1>
    <div id="caOverlay"><div id="caDialogBody"></div></div></body></html>'''
    pages = snapshot['resources']
    served = set()
    calls = {'manifest': 0, 'pages': 0, 'photos': 0}
    blocked = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True, args=['--no-sandbox'])
        context = browser.new_context(accept_downloads=True, service_workers='block')
        page = context.new_page(); page.set_default_timeout(120000)
        errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
        def route(request_route):
            req = request_route.request
            if req.method == 'GET' and req.url == origin:
                request_route.fulfill(content_type='text/html', body=html); return
            if req.method == 'GET' and req.url in photos:
                entry = photos[req.url]; calls['photos'] += 1; served.add(req.url)
                request_route.fulfill(content_type='application/octet-stream', body=entry['path'].read_bytes()); return
            blocked.append(req.method + ' ' + urlsplit(req.url).path)
            request_route.abort('blockedbyclient')
        page.route('**/*', route); page.goto(origin)
        page.evaluate('''({snapshot,base})=>{
          window.CA_URL=base;window.currentUser={id:'11111111-1111-4111-8111-111111111111'};
          window.caToken=async()=> 'isolated-restore-drill';
          window.__restoreCalls={manifest:0,pages:0};window.__restoreSnapshot=snapshot;
          window.caRequest=async(path,method,args)=>{
            if(method!=='POST')throw Error('Only captured read RPCs are allowed');
            if(path==='/rest/v1/rpc/ca_admin_export_manifest'){__restoreCalls.manifest++;return structuredClone(snapshot.manifest);}
            if(path!=='/rest/v1/rpc/ca_admin_export_page'||args.p_page_size!==100)throw Error('Unknown captured read RPC');
            const pages=snapshot.resources[args.p_resource]?.pages;if(!pages)throw Error('Unknown resource');
            let index=0;if(args.p_cursor){index=pages.findIndex(p=>p.next_cursor===args.p_cursor)+1;if(index===0)throw Error('Unknown cursor');}
            if(!pages[index])throw Error('Missing snapshot page');__restoreCalls.pages++;return structuredClone(pages[index]);
          };window.showSaveFilePicker=undefined;
        }''', {'snapshot': snapshot, 'base': PHOTO_BASE.split('/storage/')[0]})
        page.add_script_tag(path=str(ROOT / 'assets/js/14-server-backup.js'))
        page.evaluate('caShowServerBackup()')
        page.wait_for_function("document.getElementById('caServerBackupStart')&&!document.getElementById('caServerBackupStart').disabled")
        with page.expect_download(timeout=120000) as event:
            page.locator('#caServerBackupStart').click()
        event.value.save_as(str(destination)); os.chmod(destination, 0o600)
        assert 'Tam nüsxə hazırdır' in page.locator('#caServerBackupStatus').inner_text()
        rpc_calls = page.evaluate('__restoreCalls')
        assert not errors and not blocked and served == set(photos), 'Browser export did not finish safely'
        assert rpc_calls['manifest'] == 3
        calls.update(rpc_calls); browser.close()
    return calls


def validate_archive(path, expected_manifest=None):
    """Validate before any extraction, then return rows and verified photo bytes."""
    rows = {name: [] for name in RESOURCES}
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist(); names = [i.filename for i in infos]
        if len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValueError('Duplicate archive entry or missing manifest')
        if sum(i.file_size for i in infos) > MAX_ARCHIVE_BYTES or any(i.compress_type != zipfile.ZIP_STORED for i in infos):
            raise ValueError('Archive exceeds the STORE-only memory bound')
        for item in infos:
            safe_path(item.filename)
            if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Directory/symlink entries are not accepted')
            if item.filename != 'manifest.json' and not (item.filename.startswith('data/') or item.filename.startswith('photos/')):
                raise ValueError('Unexpected archive entry')
        if archive.testzip() is not None:
            raise ValueError('Archive CRC failure')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 'cenub-avto-server-data-backup':
            raise ValueError('Unknown application archive format')
        resources = resources_from_manifest(manifest)
        if expected_manifest is not None:
            expected = [{k:r[k] for k in ('name','count','sha256')} for r in resources_from_manifest(expected_manifest)]
            actual = [{k:r[k] for k in ('name','count','sha256')} for r in resources]
            if expected != actual:
                raise ValueError('Archive does not match the captured server manifest')
        files = manifest.get('files')
        if not isinstance(files, list):
            raise ValueError('Missing file manifest')
        file_paths = [f.get('path') for f in files if isinstance(f, dict)]
        if len(file_paths) != len(files) or len(set(file_paths)) != len(file_paths) or set(file_paths) != set(names)-{'manifest.json'}:
            raise ValueError('Archive file manifest is incomplete or duplicated')
        for item in files:
            safe_path(item['path']); data = archive.read(item['path'])
            if type(item.get('bytes')) is not int or item['bytes'] != len(data) or sha(data) != item.get('sha256'):
                raise ValueError('Archive file length or SHA-256 mismatch')
        referenced = []
        for resource in resources:
            name = resource['name']; pages = resource.get('pages')
            if not isinstance(pages, list) or len(pages) != len(set(pages)):
                raise ValueError('Invalid resource page list')
            hashes = []
            for i, page_path in enumerate(pages, 1):
                if page_path != f'data/{name}/{i:06d}.json':
                    raise ValueError('Resource page order/path is invalid')
                page = json.loads(archive.read(page_path)); referenced.append(page_path)
                if page.get('resource') != name or not isinstance(page.get('items'), list) or not isinstance(page.get('hashes'), list):
                    raise ValueError('Invalid resource page content')
                if len(page['items']) != len(page['hashes']) or not 1 <= len(page['items']) <= 100:
                    raise ValueError('Resource item/hash pairing or page size is invalid')
                if any(not isinstance(r, dict) for r in page['items']) or any(not HEX.fullmatch(str(h)) for h in page['hashes']):
                    raise ValueError('Invalid resource row or row hash')
                rows[name].extend(page['items']); hashes.extend(page['hashes'])
            if len(rows[name]) != resource['count'] or len(set(hashes)) != len(hashes) or sha(''.join(hashes)) != resource['sha256']:
                raise ValueError('Resource count or aggregate row hash mismatch')
        photos, original_names = [], set()
        for item in manifest.get('photos', []):
            photo_id = item.get('id'); original = safe_path(item.get('originalName'))
            if not UUID.fullmatch(str(photo_id)) or original in original_names or not re.fullmatch(r'photos/'+re.escape(photo_id)+r'\.[a-z0-9]+', str(item.get('path', ''))):
                raise ValueError('Invalid photo path/identifier or duplicate original name')
            original_names.add(original); referenced.append(item['path'])
            data = archive.read(item['path'])
            if len(data) != item.get('bytes') or sha(data) != item.get('sha256'):
                raise ValueError('Photo SHA-256 mismatch')
            photos.append({'id':photo_id, 'originalName':original, 'sha256':sha(data), 'bytes':data})
        objects = rows['storage_objects']
        if {(p['id'], p['originalName']) for p in photos} != {(o.get('id'), o.get('name')) for o in objects} or len(photos) != len(objects):
            raise ValueError('Storage object/photo membership mismatch')
        if len(referenced) != len(set(referenced)) or set(referenced) != set(file_paths):
            raise ValueError('Unreferenced or repeated archive file')
        return {'manifest':manifest, 'rows':rows, 'photos':photos}


def restore_local(verified, schema, directory, pglite_module):
    directory.mkdir(mode=0o700)
    data_file = directory / 'verified-data.json'
    private_write(data_file, json.dumps({'manifest':verified['manifest'], 'rows':verified['rows']}, ensure_ascii=False))
    photo_dir = directory / 'photos'; photo_dir.mkdir(mode=0o700)
    for item in verified['photos']:
        target = photo_dir.joinpath(*PurePosixPath(item['originalName']).parts)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_write(target, item['bytes'])
        if sha(target.read_bytes()) != item['sha256']:
            raise ValueError('Recovered photo mismatch')
    command = ['node', str(ROOT/'tools/restore-drill-pg.cjs'), str(data_file), str(schema), str(directory/'database'), str(pglite_module)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    report.update({'restoredPhotos':len(verified['photos']), 'restoredPhotoBytes':sum(len(p['bytes']) for p in verified['photos']),
                   'allPhotoHashesMatch':True, 'productionWrites':0, 'authCredentialsRestored':False, 'fullSupabaseRecovery':False})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Optional captured server manifest/pages; required when creating a ZIP')
    parser.add_argument('--archive', type=Path, help='Existing application ZIP; skips downloads and browser export')
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True, help='Existing private directory containing the capture; output names must not exist')
    parser.add_argument('--pglite-module', type=Path, required=True, help='Installed pinned @electric-sql/pglite module; no package/network installation is performed')
    args = parser.parse_args()
    os.umask(0o077)
    work = args.work_dir.resolve()
    if not work.is_dir() or work.stat().st_mode & 0o077:
        raise ValueError('Work directory must exist with mode0700')
    snapshot = json.loads(args.snapshot.read_text()) if args.snapshot else None
    if (work/'restored').exists() or (work/'report.json').exists():
        raise ValueError('Drill output already exists; choose a fresh private workspace')
    photos = {}; browser_calls = None
    if args.archive:
        archive_path = args.archive.resolve()
    else:
        if snapshot is None:
            raise ValueError('Creating an archive requires a read-only snapshot')
        archive_path = work/'application-backup.zip'
        if archive_path.exists():
            raise ValueError('Archive already exists; use --archive in a fresh workspace')
        photos = download_photos(snapshot, work/'source-photos')
        browser_calls = browser_zip(snapshot, photos, archive_path)
        private_write(work/'browser-export-report.json', json.dumps(browser_calls, indent=2)+'\n')
    verified = validate_archive(archive_path, snapshot['manifest'] if snapshot else None)
    report = restore_local(verified, args.schema.resolve(), work/'restored', args.pglite_module.resolve())
    report.update({'source':'real read-only application export' if snapshot else 'existing application archive',
                   'archiveSha256':sha(archive_path.read_bytes()),
                   'zipWriter':'assets/js/14-server-backup.js' if browser_calls else 'existing archive',
                   'interceptedBrowserReads':browser_calls,
                   'realHttpMethods':{'GET':sum(p['httpGets'] for p in photos.values())},
                   'cachedSourcePhotos':sum(p['cached'] for p in photos.values()),
                   'applicationRows':sum(len(r) for r in verified['rows'].values())})
    private_write(work/'report.json', json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print exception objects that could include private rows/URLs.
        print('Restore drill failed: '+type(error).__name__+'. Private details stay in the local workspace.', file=sys.stderr)
        raise SystemExit(1)
