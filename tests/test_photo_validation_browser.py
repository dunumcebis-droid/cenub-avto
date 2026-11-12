"""Actual image decoders and form rejection; all HTTP uses synthetic fixtures."""
import os
import unittest

from playwright.sync_api import sync_playwright

from test_package_feedback_browser import PackageFeedbackBackend
from test_listing_management_browser import ORIGIN, OWNER, owned_row


class PhotoValidationBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(
            executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'),
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 375, 'height': 812})
        self.page = self.context.new_page()
        self.page.set_default_timeout(6000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script('window.alert=()=>{};window.confirm=()=>true')
        self.backend = PackageFeedbackBackend()
        self.page.route('**/*', self.backend.route)
        self.page.goto(ORIGIN, wait_until='load')
        self.page.wait_for_function('caBrowseState.loaded')

    def tearDown(self):
        self.context.close()
        self.assertFalse(self.errors)

    def prepare_form(self):
        self.page.evaluate('''id=>{
            currentUser={id,email:'validation@example.invalid',phone:'+994000000000'};
            caSession={access_token:'seller-token',expires_at:4102444800,user:{id}};
            updateAccountUI();openSellPage();
        }''', OWNER)
        fields = {key: value for key, value in owned_row()['ca_data'].items()
                  if key not in ('photos', 'photo', 'equipment', 'pack')}
        self.page.evaluate('''data=>{
            const f=document.getElementById('listingForm');
            for(const [key,value] of Object.entries(data)){
                const field=f.elements.namedItem(key);
                if(field&&'value' in field){field.disabled=false;field.value=String(value);}
            }
            f.elements.namedItem('package').selectedIndex=0;
        }''', fields)

    def test_spoofed_jpeg_cannot_upload_or_save_a_listing(self):
        self.prepare_form()
        self.page.locator('#photos-front').set_input_files({
            'name': 'broken.jpg', 'mimeType': 'image/jpeg',
            'buffer': b'This is not a JPEG or any other decodable image.'})
        self.assertTrue(self.page.locator('#listingForm').evaluate('form=>form.checkValidity()'))
        self.page.locator('#listingForm').evaluate('form=>form.requestSubmit()')
        self.page.wait_for_function('!document.getElementById("submitListingBtn").disabled')
        self.assertTrue(self.page.locator('#listingFeedback').is_visible())
        self.assertIn('Şəkil açıla bilmədi', self.page.locator('#listingFeedbackText').inner_text())
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)
        self.assertTrue(self.page.evaluate('document.body.classList.contains("sell-open")'))
        self.assertEqual(self.page.locator('#listingForm [name="price"]').input_value(), '42000')
        self.assertEqual(self.page.locator('#photos-front').evaluate('input=>input.files[0].name'), 'broken.jpg')

    def test_valid_browser_image_fallback_stamps_and_resizes_supported_formats(self):
        for mime, mode, width, height, expected in (
            ('image/png', 'missing', 640, 480, (640, 480)),
            ('image/png', 'reject', 2400, 1600, (1440, 960)),
            ('image/jpeg', 'reject', 720, 540, (720, 540)),
            ('image/webp', 'missing', 720, 540, (720, 540)),
        ):
            with self.subTest(mime=mime, mode=mode):
                result = self.page.evaluate('''async({mime,mode,width,height})=>{
                    const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
                    const context=canvas.getContext('2d');context.fillStyle='rgb(36,70,90)';context.fillRect(0,0,width,height);
                    const input=await new Promise(resolve=>canvas.toBlob(resolve,mime));
                    const original=window.createImageBitmap,create=URL.createObjectURL,revoke=URL.revokeObjectURL;
                    const made=[],released=[];
                    URL.createObjectURL=function(blob){const url=create.call(URL,blob);made.push(url);return url;};
                    URL.revokeObjectURL=function(url){released.push(url);return revoke.call(URL,url);};
                    window.createImageBitmap=mode==='missing'?undefined:()=>Promise.reject(Error('synthetic decoder limitation'));
                    let prepared;
                    try{prepared=await caPreparePhoto(new File([input],'real-image',{type:mime}));}
                    finally{window.createImageBitmap=original;URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
                    const bitmap=await original(prepared),output=document.createElement('canvas');
                    output.width=bitmap.width;output.height=bitmap.height;
                    const ctx=output.getContext('2d');ctx.drawImage(bitmap,0,0);bitmap.close();
                    const rgba=ctx.getImageData(0,0,output.width,output.height).data;
                    let changed=0;
                    for(let y=Math.floor(output.height*.3);y<output.height*.7;y++)
                        for(let x=Math.floor(output.width*.1);x<output.width*.9;x++){
                            const index=(y*output.width+x)*4;
                            if(Math.max(Math.abs(rgba[index]-36),Math.abs(rgba[index+1]-70),Math.abs(rgba[index+2]-90))>15)changed++;
                        }
                    return {type:prepared.type,width:output.width,height:output.height,changed,made,released};
                }''', dict(mime=mime, mode=mode, width=width, height=height))
                self.assertEqual(result['type'], 'image/jpeg')
                self.assertEqual((result['width'], result['height']), expected)
                self.assertGreater(result['changed'], 150)
                self.assertEqual(result['released'], result['made'])
                self.assertEqual(len(result['made']), 1)
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_invalid_or_unsupported_image_fallback_releases_its_object_url(self):
        result = self.page.evaluate('''async()=>{
            const original=window.createImageBitmap,create=URL.createObjectURL,revoke=URL.revokeObjectURL;
            const made=[],released=[],failures=[];
            window.createImageBitmap=()=>Promise.reject(Error('synthetic decoder limitation'));
            URL.createObjectURL=function(blob){const url=create.call(URL,blob);made.push(url);return url;};
            URL.revokeObjectURL=function(url){released.push(url);return revoke.call(URL,url);};
            try{
                for(const type of ['image/jpeg','image/avif']){
                    try{await caPreparePhoto(new File(['unsupported image bytes'],'broken-image',{type}));failures.push('accepted');}
                    catch(error){failures.push(error.message);}
                }
            }finally{window.createImageBitmap=original;URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
            return {made,released,failures};
        }''')
        self.assertEqual(len(result['made']), 2)
        self.assertEqual(result['released'], result['made'])
        self.assertTrue(all('Şəkil açıla bilmədi' in message for message in result['failures']))
        self.assertFalse(self.backend.uploads)
        self.assertFalse(self.backend.saves)

    def test_encoding_failure_also_releases_fallback_image_resources(self):
        result = self.page.evaluate('''async()=>{
            const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;
            canvas.getContext('2d').fillRect(0,0,640,480);
            const input=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
            const bitmap=window.createImageBitmap,encode=HTMLCanvasElement.prototype.toBlob,create=URL.createObjectURL,revoke=URL.revokeObjectURL;
            const made=[],released=[];let failure='';
            window.createImageBitmap=undefined;
            HTMLCanvasElement.prototype.toBlob=function(callback){callback(null);};
            URL.createObjectURL=function(blob){const url=create.call(URL,blob);made.push(url);return url;};
            URL.revokeObjectURL=function(url){released.push(url);return revoke.call(URL,url);};
            try{await caPreparePhoto(new File([input],'valid.png',{type:'image/png'}));}
            catch(error){failure=error.message;}
            finally{window.createImageBitmap=bitmap;HTMLCanvasElement.prototype.toBlob=encode;URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
            return {failure,made,released};
        }''')
        self.assertEqual(result['failure'], 'Şəkil hazırlanmadı.')
        self.assertEqual(len(result['made']), 1)
        self.assertEqual(result['released'], result['made'])
