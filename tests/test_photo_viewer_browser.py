"""Touch-first photo viewer regressions; every network request is mocked.

Exercises actual tap/pointer gestures and rendered geometry, rather than only
calling the viewer API. No Storage uploads, account changes or emails are sent.
"""
import copy
import os
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from test_listing_management_browser import OfflineBackend, ORIGIN, owned_row

PHOTO_BASE = 'https://fixture.invalid/viewer-'
BROKEN = PHOTO_BASE + 'broken.svg'
SINGLE = PHOTO_BASE + 'single.svg'
PHOTOS = [PHOTO_BASE + str(i) + '.svg' for i in range(36)]


def viewer_rows():
    groups = {name: PHOTOS[i * 6:(i + 1) * 6]
              for i, name in enumerate(('front', 'rear', 'side', 'interior', 'engine', 'other'))}
    rows = []
    for i, (model, photos) in enumerate((
        ('Gallery36', groups), ('Single', {'front': [SINGLE]}),
        ('Empty', {}), ('Broken', {'front': [BROKEN, SINGLE]}),
    ), 1):
        row = owned_row()
        urls = [url for values in photos.values() for url in values]
        row.update(id=f'98989898-9898-4989-8989-{i:012d}', model=model,
                   sekiller=urls, paket_adi='Pulsuz')
        row['ca_data'].update(model=model, photos=photos,
                              photo=urls[0] if urls else None, pack='Pulsuz')
        rows.append(row)
    return rows


class ViewerBackend(OfflineBackend):
    def __init__(self):
        super().__init__(viewer_rows())

    def route(self, route):
        request = route.request
        if request.url.startswith(PHOTO_BASE):
            assert request.method == 'GET'
            if request.url == BROKEN:
                route.fulfill(status=404, content_type='text/plain', body='Missing synthetic photo')
                return
            width, height = ((600, 1200) if request.url == PHOTOS[0]
                             else (1600, 800) if request.url == PHOTOS[1]
                             else (1200, 800))
            route.fulfill(content_type='image/svg+xml', body=(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
                '<rect width="100%" height="100%" fill="#365a70"/>'
                '<circle cx="50%" cy="50%" r="100" fill="#91c3db"/>'
                '</svg>'))
            return
        super().route(route)


class PhotoViewerBrowserTests(unittest.TestCase):
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
        self.context = self.browser.new_context(
            viewport={'width': 375, 'height': 812}, has_touch=True, is_mobile=True)
        self.context.set_default_timeout(6000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.backend = ViewerBackend()
        self.original_rows = copy.deepcopy(self.backend.rows)
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded&&caPageCars.length===4')

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors, 'Uncaught browser errors')
        self.assertEqual(self.backend.rows, self.original_rows)
        self.assertFalse([call for call in self.backend.calls
                          if call['method'] != 'GET' and
                          call['path'] != '/rest/v1/rpc/ca_browse_listings'])

    def card(self, model):
        return self.page.locator('#allGrid .car-card').filter(has_text='BMW ' + model)

    def open_detail(self, model='Gallery36'):
        self.card(model).locator('.car-cover').tap()
        self.page.locator('#detailOverlay').wait_for(state='visible')

    def open_viewer(self, model='Gallery36'):
        self.open_detail(model)
        self.page.locator('#galleryStage .ca-gallery-open').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='visible')
        if model != 'Broken':
            self.page.locator('#caPhotoViewerCanvas img').evaluate('img=>img.decode()')
            self.page.locator('[data-ca-viewer="plus"]').wait_for(state='visible')
            self.page.wait_for_function('!document.querySelector("[data-ca-viewer=plus]").disabled')

    def close_viewer(self):
        self.page.locator('[data-ca-viewer="close"]').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='hidden')

    def photo_src(self):
        return self.page.locator('#caPhotoViewerCanvas img').get_attribute('src')

    def zoom(self):
        return self.page.locator('#caPhotoViewerCanvas').evaluate('e=>new DOMMatrixReadOnly(getComputedStyle(e).transform).a')

    def gesture(self, paths):
        """CDP touch produces real pointer events in Chromium's touch context."""
        client = self.context.new_cdp_session(self.page)
        def points(frame):
            return [dict(id=i + 1, x=x, y=y, radiusX=2, radiusY=2, force=1)
                    for i, (x, y) in enumerate(frame)]
        client.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=points(paths[0])))
        for frame in paths[1:]:
            client.send('Input.dispatchTouchEvent', dict(type='touchMove', touchPoints=points(frame)))
            self.page.wait_for_timeout(30)
        client.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
        client.detach()
        self.page.wait_for_timeout(60)

    def stage_center(self):
        r = self.page.locator('#caPhotoViewerStage').bounding_box()
        return r['x'] + r['width'] / 2, r['y'] + r['height'] / 2

    def assert_tools_absent(self):
        tools = self.page.locator('#caToolsBar')
        self.assertFalse(tools.is_visible())
        self.assertTrue(tools.evaluate('e=>e.inert'))
        self.assertFalse(self.page.evaluate('''()=>{
            const e=document.getElementById('caToolsBar'),r=e.getBoundingClientRect();
            return r.width>0&&r.height>0&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('#caToolsBar')===e;
        }'''))

    def test_touch_photo_opens_full_view_and_toolbar_cannot_cover_detail_or_viewer(self):
        for width in (320, 375, 430):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 812})
                self.page.locator('#caAdminLaunch').evaluate('e=>{e.hidden=false;e.style.display="block"}')
                self.open_detail()
                self.assert_tools_absent()
                small = self.page.locator('#galleryStage img').bounding_box()
                self.page.locator('#galleryStage .ca-gallery-open').tap()
                self.page.locator('#caPhotoViewer').wait_for(state='visible')
                self.page.wait_for_function('document.querySelector("#caPhotoViewerCanvas img")?.naturalWidth>0')
                self.assert_tools_absent()
                bounds = self.page.locator('#caPhotoViewer').bounding_box()
                self.assertAlmostEqual(bounds['x'], 0, delta=1)
                self.assertAlmostEqual(bounds['y'], 0, delta=1)
                self.assertAlmostEqual(bounds['width'], width, delta=1)
                self.assertAlmostEqual(bounds['height'], 812, delta=1)
                self.assertEqual(self.photo_src(), PHOTOS[0])
                self.assertTrue(self.page.locator('#caPhotoViewer .ca-photo-watermark').is_visible())
                self.assertGreater(self.page.locator('#caPhotoViewerCanvas img').bounding_box()['height'], small['height'])
                self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                self.close_viewer()
                self.assertTrue(self.page.locator('#detailOverlay').is_visible())
                self.assertEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')
                self.page.keyboard.press('Escape')
                self.assertFalse(self.page.locator('#detailOverlay').is_visible())
                self.assertTrue(self.page.locator('#caToolsBar').is_visible())

    def test_all_36_photos_navigation_and_close_keep_selected_detail_photo(self):
        self.open_viewer()
        self.assertIn('1 / 36', self.page.locator('#caPhotoViewerCaption').inner_text())
        self.page.locator('.ca-photo-viewer-next').tap()
        self.page.wait_for_function('source=>document.querySelector("#caPhotoViewerCanvas img").getAttribute("src")===source', arg=PHOTOS[1])
        self.assertIn('2 / 36', self.page.locator('#caPhotoViewerCaption').inner_text())
        self.page.keyboard.press('ArrowLeft')
        self.assertEqual(self.photo_src(), PHOTOS[0])
        self.page.keyboard.press('ArrowLeft')
        self.assertEqual(self.photo_src(), PHOTOS[-1])
        self.assertIn('36 / 36', self.page.locator('#caPhotoViewerCaption').inner_text())
        self.close_viewer()
        self.assertEqual(self.page.locator('#galleryStage img').get_attribute('src'), PHOTOS[-1])
        self.assertIn('36 / 36', self.page.locator('#galleryStage .gallery-counter').inner_text())
        self.assertEqual(self.page.locator('#galleryThumbs button.active img').get_attribute('src'), PHOTOS[-1])
        self.page.locator('#galleryThumbs button').nth(1).tap()
        self.page.locator('#galleryStage .ca-gallery-open').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='visible')
        self.assertEqual(self.photo_src(), PHOTOS[1])
        self.assertIn('2 / 36', self.page.locator('#caPhotoViewerCaption').inner_text())

    def test_real_touch_pinch_pan_and_swipe_change_geometry_and_photos(self):
        self.open_viewer()
        x, y = self.stage_center()
        initial = self.page.locator('#caPhotoViewerCanvas img').bounding_box()
        self.gesture([[(x-30,y),(x+30,y)], [(x-50,y),(x+50,y)], [(x-85,y),(x+85,y)]])
        self.assertGreater(self.zoom(), 1.5)
        self.assertGreater(self.page.locator('#caPhotoViewerCanvas img').bounding_box()['height'], initial['height']*1.5)
        before = self.page.locator('#caPhotoViewerCanvas').bounding_box()
        self.gesture([[(x,y)], [(x+25,y+30)], [(x+55,y+60)]])
        after = self.page.locator('#caPhotoViewerCanvas').bounding_box()
        self.assertGreater(abs(after['x']-before['x'])+abs(after['y']-before['y']), 10)
        self.assertEqual(self.photo_src(), PHOTOS[0], 'Panning a zoomed image must not advance the gallery')
        self.page.locator('[data-ca-viewer="reset"]').tap()
        self.assertAlmostEqual(self.zoom(), 1, delta=.01)
        x, y = self.stage_center()
        self.gesture([[(x+80,y)], [(x+25,y)], [(x-45,y)], [(x-85,y)]])
        self.assertEqual(self.photo_src(), PHOTOS[1])
        self.gesture([[(x-80,y)], [(x-10,y)], [(x+85,y)]])
        self.assertEqual(self.photo_src(), PHOTOS[0])
        self.gesture([[(x,y-50)], [(x,y+10)], [(x,y+80)]])
        self.assertEqual(self.photo_src(), PHOTOS[0], 'A vertical gesture is not a gallery page change')

    def test_zoom_controls_double_tap_and_keyboard_are_usable(self):
        self.open_viewer()
        self.assertTrue(self.page.locator('[data-ca-viewer="minus"]').is_disabled())
        original = self.page.locator('#caPhotoViewerCanvas img').bounding_box()
        self.page.locator('[data-ca-viewer="plus"]').tap()
        self.assertGreater(self.zoom(), 1)
        self.assertGreater(self.page.locator('#caPhotoViewerCanvas img').bounding_box()['width'], original['width'])
        for _ in range(5):
            self.page.locator('[data-ca-viewer="plus"]').tap()
        self.assertAlmostEqual(self.zoom(), 4, delta=.01)
        self.assertTrue(self.page.locator('[data-ca-viewer="plus"]').is_disabled())
        self.page.locator('[data-ca-viewer="minus"]').tap()
        self.assertLess(self.zoom(), 4)
        self.page.locator('[data-ca-viewer="reset"]').tap()
        self.page.locator('#caPhotoViewerStage').dblclick()
        self.assertGreater(self.zoom(), 2, 'A genuine mouse double-click must still zoom')
        self.page.keyboard.press('0')
        self.assertAlmostEqual(self.zoom(), 1, delta=.01)
        x, y = self.stage_center()
        self.page.touchscreen.tap(x, y)
        self.page.touchscreen.tap(x, y)
        self.assertGreater(self.zoom(), 2)
        self.page.locator('[data-ca-viewer="reset"]').tap()
        self.assertAlmostEqual(self.zoom(), 1, delta=.01)

    def test_escape_focus_trap_and_browser_back_close_only_top_photo_view(self):
        self.open_viewer()
        for _ in range(12):
            self.page.keyboard.press('Tab')
            self.assertTrue(self.page.evaluate('document.getElementById("caPhotoViewer").contains(document.activeElement)'))
        self.page.keyboard.press('Escape')
        self.page.locator('#caPhotoViewer').wait_for(state='hidden')
        self.assertTrue(self.page.locator('#detailOverlay').is_visible())
        self.assertTrue(self.page.locator('#galleryStage .ca-gallery-open').evaluate('e=>e===document.activeElement'))
        self.page.locator('#galleryStage .ca-gallery-open').tap()
        self.page.locator('#caPhotoViewer').wait_for(state='visible')
        self.page.go_back(wait_until='domcontentloaded')
        self.page.locator('#caPhotoViewer').wait_for(state='hidden')
        self.assertTrue(self.page.locator('#detailOverlay').is_visible())
        self.assertEqual(self.page.url, ORIGIN)
        self.assertEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')
        self.page.keyboard.press('Escape')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        self.assertNotEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')

    def test_single_empty_and_failed_images_have_safe_controls_and_recovery(self):
        self.open_detail('Empty')
        self.assertEqual(self.page.locator('#galleryStage .ca-gallery-open').count(), 0)
        self.assertFalse(self.page.evaluate('caOpenPhotoViewer()'))
        self.assertFalse(self.page.locator('#caPhotoViewer').is_visible())
        self.page.keyboard.press('Escape')
        self.open_viewer('Single')
        self.assertIn('1 / 1', self.page.locator('#caPhotoViewerCaption').inner_text())
        self.assertFalse(self.page.locator('.ca-photo-viewer-prev').is_visible())
        self.assertFalse(self.page.locator('.ca-photo-viewer-next').is_visible())
        self.close_viewer()
        self.page.keyboard.press('Escape')
        self.open_viewer('Broken')
        self.page.wait_for_function('document.querySelector("#caPhotoViewerCanvas .ca-watermark-frame")?.dataset.caPhotoState==="error"')
        self.assertTrue(self.page.locator('[data-ca-viewer="plus"]').is_disabled())
        self.assertFalse(self.page.locator('#caPhotoViewer .ca-photo-watermark').is_visible())
        self.assertTrue(self.page.locator('#caPhotoViewerMessage').is_visible())
        self.page.locator('.ca-photo-viewer-next').tap()
        self.page.wait_for_function('!document.querySelector("[data-ca-viewer=plus]").disabled')
        self.assertEqual(self.photo_src(), SINGLE)

    def test_resizing_and_landscape_keep_photo_controls_inside_viewport(self):
        self.open_viewer()
        for width, height in ((320,812),(812,375),(1440,900),(375,812)):
            with self.subTest(width=width, height=height):
                self.page.set_viewport_size({'width': width, 'height': height})
                self.page.wait_for_timeout(70)
                self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                for selector in ('[data-ca-viewer="close"]','[data-ca-viewer="plus"]','[data-ca-viewer="minus"]',
                                 '.ca-photo-viewer-prev','.ca-photo-viewer-next'):
                    r = self.page.locator(selector).bounding_box()
                    self.assertIsNotNone(r)
                    self.assertGreaterEqual(r['x'], -1)
                    self.assertGreaterEqual(r['y'], -1)
                    self.assertLessEqual(r['x']+r['width'], width+1)
                    self.assertLessEqual(r['y']+r['height'], height+1)
                self.assertEqual(self.photo_src(), PHOTOS[0])
                self.assertTrue(self.page.locator('#caPhotoViewer .ca-photo-watermark').is_visible())

    def test_parent_detail_close_cleans_viewer_without_reopening_or_page_lock(self):
        self.open_viewer()
        self.page.evaluate('closeCarDetail()')
        self.page.locator('#caPhotoViewer').wait_for(state='hidden')
        self.assertFalse(self.page.locator('#detailOverlay').is_visible())
        self.assertNotEqual(self.page.evaluate('document.body.style.overflow'), 'hidden')
        self.assertTrue(self.page.locator('#caToolsBar').is_visible())
        self.open_viewer('Single')
        self.assertEqual(self.photo_src(), SINGLE)
        self.close_viewer()
        self.assertTrue(self.page.locator('#detailOverlay').is_visible())
