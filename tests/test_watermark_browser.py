"""Watermark regressions with real browser image encoding and mocked HTTP.

No test uploads to Storage, sends mail, or changes a real listing. Pixel checks
exercise the generated JPEG rather than trusting a filename or canvas spy.
"""
import base64
import copy
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from test_listing_management_browser import OfflineBackend, ORIGIN, OWNER, owned_row


STORAGE = 'https://iqdtehqxusfiwokrzceo.supabase.co/storage/v1/object/public/elan-sekilleri/'
STAMPED = STORAGE + OWNER + '/99999999-9999-4999-8999-999999999999-ca-wm1.jpg'
PORTRAIT = 'https://fixture.invalid/watermark-portrait.svg'
LANDSCAPE = 'https://fixture.invalid/watermark-landscape.svg'
PANORAMA = 'https://fixture.invalid/watermark-panorama.svg'
LOOKALIKE = 'https://fixture.invalid/' + OWNER + '/99999999-9999-4999-8999-999999999999-ca-wm1.jpg'
BROKEN = 'https://fixture.invalid/watermark-broken.jpg'
QUOTED = 'https://fixture.invalid/watermark-quoted.svg?label=" onerror="window.__watermarkInjected=1'


def watermark_rows():
    rows = []
    for number, (model, photos) in enumerate((
        ('OldPortrait', [PORTRAIT, LANDSCAPE, PANORAMA]),
        ('Stamped', [STAMPED]),
        ('Lookalike', [LOOKALIKE]),
        ('Missing', []),
        ('Broken', [BROKEN]),
        ('Quoted', [QUOTED]),
    ), 1):
        row = owned_row()
        row.update(id=f'77777777-7777-4777-8777-{number:012d}', model=model,
                   paket_adi='Pulsuz', sekiller=photos)
        row['ca_data'].update(model=model, photos={'front': photos},
                              photo=photos[0] if photos else None, pack='Pulsuz')
        rows.append(row)
    return rows


class WatermarkBackend(OfflineBackend):
    def __init__(self):
        super().__init__(watermark_rows())
        self.uploads = []

    def route(self, route):
        request = route.request
        parsed = urlsplit(request.url)
        if parsed.path.startswith('/storage/v1/object/elan-sekilleri/'):
            assert request.method == 'POST'
            self.uploads.append(dict(url=request.url, body=request.post_data_buffer,
                                     headers=dict(request.headers)))
            route.fulfill(content_type='application/json', body='{}')
            return
        if request.url.startswith('https://fixture.invalid/') or request.url.startswith(STORAGE):
            assert request.method == 'GET'
            if request.url == BROKEN:
                route.fulfill(status=404, content_type='text/plain', body='not a photo')
                return
            width, height = ((300, 1200) if request.url == PORTRAIT else
                             (4000, 100) if request.url == PANORAMA else (1200, 300))
            route.fulfill(content_type='image/svg+xml', body=(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
                f'<rect width="{width}" height="{height}" fill="#467790"/></svg>'))
            return
        super().route(route)


class WatermarkBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.context.set_default_timeout(5000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.backend = WatermarkBackend()
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded && caRemoteCars.length===6')

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertFalse([call for call in self.backend.calls
                          if call['method'] in ('PATCH', 'DELETE')])

    def card(self, model):
        return self.page.locator('#allGrid .car-card').filter(has_text='BMW ' + model)

    def sign_in(self):
        self.page.evaluate('''async owner=>{
            currentUser={id:owner,email:'watermark@example.invalid',phone:'+994000000000'};
            caSession={access_token:'watermark-token',expires_at:4102444800,user:{id:owner}};
            await caFetchMyListings();renderCabinet();
        }''', OWNER)

    def pixel_summary(self, encoded):
        return self.page.evaluate('''async encoded=>{
            const bytes=Uint8Array.from(atob(encoded),ch=>ch.charCodeAt(0));
            const bitmap=await createImageBitmap(new Blob([bytes]));
            const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
            const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0);bitmap.close();
            const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
            let centerChanged=0,edgeMaxDifference=0;
            const difference=(x,y)=>{
                const offset=(y*canvas.width+x)*4;
                return Math.max(Math.abs(pixels[offset]-36),Math.abs(pixels[offset+1]-70),Math.abs(pixels[offset+2]-90));
            };
            for(let y=Math.floor(canvas.height*.25);y<canvas.height*.75;y++)
                for(let x=Math.floor(canvas.width*.1);x<canvas.width*.9;x++)
                    if(difference(x,y)>15)centerChanged++;
            for(const [fx,fy] of [[.05,.05],[.95,.05],[.05,.95],[.95,.95]])
                edgeMaxDifference=Math.max(edgeMaxDifference,difference(Math.floor(canvas.width*fx),Math.floor(canvas.height*fy)));
            return {width:canvas.width,height:canvas.height,centerChanged,edgeMaxDifference};
        }''', encoded)

    def test_prepared_jpeg_contains_watermark_without_upscaling_or_recoloring_edges(self):
        for width, height, expected in ((640, 480, (640, 480)),
                                        (2400, 1600, (1440, 960)),
                                        (1200, 2400, (720, 1440))):
            with self.subTest(width=width, height=height):
                result = self.page.evaluate('''async({width,height})=>{
                    const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
                    const ctx=canvas.getContext('2d');ctx.fillStyle='rgb(36,70,90)';ctx.fillRect(0,0,width,height);
                    const input=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
                    const result=await caPreparePhoto(new File([input],'synthetic.png',{type:'image/png'}));
                    const data=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.readAsDataURL(result)});
                    return {type:result.type,data};
                }''', dict(width=width, height=height))
                self.assertEqual(result['type'], 'image/jpeg')
                pixels = self.pixel_summary(result['data'])
                self.assertEqual((pixels['width'], pixels['height']), expected)
                self.assertGreater(pixels['centerChanged'], 150)
                self.assertLessEqual(pixels['edgeMaxDifference'], 5)
        self.assertFalse(self.backend.uploads)

    def test_upload_bytes_are_stamped_but_decode_fallback_is_not_falsely_labelled(self):
        self.sign_in()
        urls = self.page.evaluate('''async()=>{
            const canvas=document.createElement('canvas');canvas.width=800;canvas.height=600;
            const ctx=canvas.getContext('2d');ctx.fillStyle='rgb(36,70,90)';ctx.fillRect(0,0,800,600);
            const input=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
            const file=new File([input],'synthetic.png',{type:'image/png'});
            const stamped=await caUploadPhoto(file,'watermark-token',()=>{});
            const decode=window.createImageBitmap;
            window.createImageBitmap=()=>Promise.reject(Error('unsupported synthetic decoder'));
            try{return [stamped,await caUploadPhoto(file,'watermark-token',()=>{})];}
            finally{window.createImageBitmap=decode;}
        }''')
        self.assertEqual(len(self.backend.uploads), 2)
        stamped, fallback = self.backend.uploads
        self.assertRegex(urls[0], r'/[0-9a-f-]+-ca-wm1\.jpg$')
        self.assertNotIn('-ca-wm1', urls[1])
        self.assertEqual(stamped['body'][:2], b'\xff\xd8')
        self.assertEqual(fallback['body'][:8], b'\x89PNG\r\n\x1a\n')
        pixels = self.pixel_summary(base64.b64encode(stamped['body']).decode())
        self.assertGreater(pixels['centerChanged'], 150)
        for upload in self.backend.uploads:
            self.assertEqual(upload['headers'].get('authorization'), 'Bearer watermark-token')
            self.assertEqual(upload['headers'].get('x-upsert'), 'false')

    def test_old_photos_keep_sources_and_only_verified_embedded_stamps_skip_overlay(self):
        for model, source in (('OldPortrait', PORTRAIT), ('Lookalike', LOOKALIKE), ('Quoted', QUOTED)):
            card = self.card(model)
            card.scroll_into_view_if_needed()
            card.locator('.car-cover img').evaluate('img=>img.decode()')
            self.assertEqual(card.locator('.car-cover img').get_attribute('src'), source)
            mark = card.locator('.ca-photo-watermark')
            self.assertEqual(mark.count(), 1)
            self.assertTrue(mark.is_visible())
            self.assertEqual(mark.inner_text(), 'CƏNUB AVTO')
        stamped = self.card('Stamped')
        self.assertEqual(stamped.locator('.car-cover img').get_attribute('src'), STAMPED)
        self.assertEqual(stamped.locator('.ca-photo-watermark').count(), 0)
        self.assertEqual(self.card('Missing').locator('.ca-photo-watermark').count(), 0)
        broken = self.card('Broken');broken.scroll_into_view_if_needed()
        self.page.wait_for_function('()=>{const image=[...document.querySelectorAll("#allGrid .car-card")].find(e=>e.textContent.includes("BMW Broken")).querySelector("img");return image.complete}')
        self.assertFalse(broken.locator('.ca-photo-watermark').is_visible())
        self.assertEqual(self.page.locator('.hero .ca-photo-watermark,header .ca-photo-watermark').count(), 0)
        self.assertIsNone(self.page.evaluate('window.__watermarkInjected'))

    def test_portrait_and_landscape_gallery_marks_fit_photos_and_controls_work(self):
        for width in (320, 375, 1440):
            with self.subTest(width=width):
                self.page.evaluate('closeCarDetail()')
                self.page.set_viewport_size({'width': width, 'height': 1000})
                self.card('OldPortrait').locator('.car-cover').click()
                for source in (PORTRAIT, LANDSCAPE, PANORAMA):
                    self.page.wait_for_function('source=>{const img=document.querySelector("#galleryStage img");return img&&img.getAttribute("src")===source&&img.complete&&img.naturalWidth>0}',arg=source)
                    mark = self.page.locator('#galleryStage .ca-photo-watermark')
                    mark.wait_for(state='visible')
                    geometry = self.page.locator('#galleryStage').evaluate('''stage=>{
                        const img=stage.querySelector('img'),r=img.getBoundingClientRect(),m=stage.querySelector('.ca-photo-watermark').getBoundingClientRect();
                        const scale=Math.min(r.width/img.naturalWidth,r.height/img.naturalHeight);
                        const width=img.naturalWidth*scale,height=img.naturalHeight*scale;
                        return {left:r.x+(r.width-width)/2,right:r.x+(r.width+width)/2,
                            top:r.y+(r.height-height)/2,bottom:r.y+(r.height+height)/2,
                            frameHeight:img.closest('.ca-watermark-frame').getBoundingClientRect().height,
                            mark:{left:m.left,right:m.right,top:m.top,bottom:m.bottom}};
                    }''')
                    if width <= 500:
                        self.assertAlmostEqual(geometry['frameHeight'], 480, delta=1)
                    for start, end in (('left', 'right'), ('top', 'bottom')):
                        self.assertGreaterEqual(geometry['mark'][start], geometry[start]-1)
                        self.assertLessEqual(geometry['mark'][end], geometry[end]+1)
                    if source != PANORAMA:
                        self.page.locator('.gallery-next').click()
                self.page.locator('.gallery-prev').click()
                self.assertEqual(self.page.locator('#galleryStage img').get_attribute('src'), LANDSCAPE)
                self.page.locator('.gallery-prev').click()
                self.assertEqual(self.page.locator('#galleryStage img').get_attribute('src'), PORTRAIT)
                self.page.keyboard.press('Escape')
                self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        self.page.evaluate('closeCarDetail()')
        self.sign_in()
        card = self.card('OldPortrait')
        card.locator('.favorite-btn').click()
        self.assertIn('is-favorite', self.card('OldPortrait').locator('.favorite-btn').get_attribute('class'))

    def test_cabinet_and_thumbnails_reuse_original_photos_without_double_marking(self):
        original = copy.deepcopy(self.backend.rows)
        self.sign_in()
        self.page.evaluate('openCabinet()')
        cabinet = self.page.locator('#cabinetList .cabinet-card').filter(has_text='BMW OldPortrait')
        cabinet.scroll_into_view_if_needed()
        self.assertEqual(cabinet.locator('img').get_attribute('src'), PORTRAIT)
        self.assertTrue(cabinet.locator('.ca-photo-watermark').is_visible())
        self.assertEqual(self.page.locator('#cabinetList .cabinet-card').filter(has_text='BMW Stamped').locator('.ca-photo-watermark').count(), 0)
        self.page.evaluate('closeCabinet()')
        self.card('OldPortrait').locator('.car-cover').click()
        thumbs = self.page.locator('#galleryThumbs button')
        self.assertEqual(thumbs.count(), 3)
        self.assertEqual(thumbs.locator('img').evaluate_all('els=>els.map(e=>e.getAttribute("src"))'), [PORTRAIT, LANDSCAPE, PANORAMA])
        thumbs.nth(1).click()
        self.assertEqual(self.page.locator('#galleryStage img').get_attribute('src'), LANDSCAPE)
        self.assertEqual(self.backend.rows, original)
        self.assertFalse(self.backend.uploads)

