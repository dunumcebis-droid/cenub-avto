"""Current purchase choices and protected legacy package edits, with all HTTP mocked.

The database suite covers real request canonicalization and payment authorization.
These cases check seller UI, submission feedback, and retained recorded history.
"""
import copy
from datetime import datetime, timedelta, timezone
import os
import unittest

from playwright.sync_api import expect, sync_playwright
from test_listing_management_browser import OWNED_ID, GROUPS
import test_package_feedback_browser as package_fixture


class PackagePricingBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    setUp=package_fixture.PackageFeedbackBrowserTests.setUp
    sign_in=package_fixture.PackageFeedbackBrowserTests.sign_in
    new_listing=package_fixture.PackageFeedbackBrowserTests.new_listing
    submit=package_fixture.PackageFeedbackBrowserTests.submit
    feedback=package_fixture.PackageFeedbackBrowserTests.feedback

    def tearDown(self):
        self.context.close();self.assertFalse(self.errors)
        self.assertFalse([c for c in self.backend.calls if '/checkout' in c['path'] or '/bank' in c['path']])

    def select_package(self,label):
        option=self.page.locator('#listingForm [name=package] option').filter(has_text=label)
        self.assertEqual(option.count(),1)
        value=option.evaluate('option=>option.value')
        self.page.locator('#listingForm [name=package]').select_option(value)
        return option.inner_text()

    def edited_legacy(self,package):
        row=next(r for r in self.backend.rows if r['id']==OWNED_ID)
        now=datetime.now(timezone.utc)
        row.update(paket_adi=package,paket_baslayir=(now-timedelta(days=3)).isoformat(),
            paket_bitir=(now+timedelta(days=2)).isoformat())
        row['ca_data'].update(pack=package,requestedPackage='Üstün — 5 AZN / 5 gün' if package=='Premium' else 'Sərfəli seçim — 3 AZN / 3 gün')
        original=copy.deepcopy(row)
        self.sign_in();self.page.evaluate('async()=>await caFetchMyListings()')
        self.page.evaluate('id=>editCar(id)',OWNED_ID)
        expect(self.page.locator('#listingForm [name=package]')).to_have_value('')
        expect(self.page.locator('#listingForm option[data-keep-package]')).to_have_text('Cari paketi saxla — yeni paket sifariş etmə')
        expect(self.page.locator('#listingForm .photo-preview img')).to_have_count(9)
        return row,original

    def assert_protected_history(self,row,original):
        for key in ('paket_adi','paket_baslayir','paket_bitir','sekiller'):
            self.assertEqual(row[key],original[key],key+' must retain recorded history')
        updates=[c for c in self.backend.calls if c['method']=='PATCH' and c['path']=='/rest/v1/elanlar']
        self.assertEqual(len(updates),1)
        payload=updates[0]['body']
        for key in ('paket_adi','paket_baslayir','paket_bitir'):
            self.assertNotIn(key,payload)
        self.assertEqual(payload['ca_data']['photos'],GROUPS)
        self.assertEqual(self.backend.uploads,[],'Existing photos do not need uploading again')
        return payload

    def test_new_purchase_catalog_has_four_choices_and_no_discontinued_standard(self):
        self.new_listing()
        labels=self.page.locator('#listingForm [name=package] option').all_text_contents()
        self.assertEqual(len(labels),4)
        self.assertEqual(sum('10 AZN' in s and '15 gün' in s for s in labels),1)
        self.assertEqual(sum('5 AZN' in s and '10 gün' in s for s in labels),1)
        self.assertEqual(sum('1 AZN' in s and 'satılanadək' in s for s in labels),1)
        self.assertEqual(sum('Pulsuz' in s for s in labels),1)
        self.assertFalse(any('Sərfəli' in s or 'Standart' in s or '3 AZN' in s for s in labels))

    def test_ten_azn_vip_submission_is_vip_not_one_azn_urgent(self):
        self.new_listing(paid=True)
        selected=self.page.locator('#listingForm [name=package] option:checked').inner_text()
        self.assertIn('10 AZN',selected);self.assertIn('15 gün',selected)
        self.submit()
        message=self.feedback()
        self.assertIn('VIP paket müraciətiniz qəbul edildi',message)
        self.assertNotIn('Təcili',message)
        payload=self.backend.saves[0]
        self.assertEqual(payload['ca_data']['requestedPackage'],selected)
        self.assertEqual(payload['ca_data']['pack'],'Pulsuz')
        self.assertEqual(payload['veziyyet'],'gozlemede')
        self.assertNotIn('paket_adi',payload)
        self.assertFalse(any(c['path'].endswith('/ca_paket_sorgusu_yarat') for c in self.backend.calls))

    def test_five_azn_premium_purchase_shows_ten_days_and_preserves_pending_flow(self):
        self.new_listing();selected=self.select_package('5 AZN')
        self.assertIn('Üstün',selected);self.assertIn('10 gün',selected)
        self.submit();self.assertIn('Premium paket müraciətiniz qəbul edildi',self.feedback())
        self.assertEqual(self.backend.saves[0]['ca_data']['requestedPackage'],selected)
        self.assertEqual(self.backend.saves[0]['veziyyet'],'gozlemede')
        self.assertNotIn('paket_bitir',self.backend.saves[0])

    def test_urgent_stays_one_azn_until_sold(self):
        self.new_listing();selected=self.select_package('1 AZN')
        self.assertIn('Təcili',selected);self.assertIn('satılanadək',selected)
        self.submit();self.assertIn('Təcili paket müraciətiniz qəbul edildi',self.feedback())
        self.assertEqual(self.backend.saves[0]['ca_data']['requestedPackage'],selected)
        self.assertNotIn('paket_bitir',self.backend.saves[0])

    def test_existing_standard_edit_keeps_paid_history_and_all_photos(self):
        row,original=self.edited_legacy('Standart')
        self.page.locator('#listingForm [name=price]').fill('43000')
        self.submit();self.assertIn('Dəyişikliklər saxlanıldı',self.feedback())
        payload=self.assert_protected_history(row,original)
        self.assertEqual(payload['ca_data']['requestedPackage'],'')

    def test_existing_five_day_premium_edit_does_not_extend_recorded_end(self):
        row,original=self.edited_legacy('Premium')
        self.page.locator('#listingForm [name=price]').fill('44000')
        self.submit();self.feedback()
        payload=self.assert_protected_history(row,original)
        self.assertEqual(payload['ca_data']['requestedPackage'],'')

    def test_legacy_standard_can_request_new_vip_without_replacing_existing_history(self):
        row,original=self.edited_legacy('Standart')
        selected=self.select_package('10 AZN');self.submit()
        self.assertIn('VIP paket müraciətiniz qəbul edildi',self.feedback())
        payload=self.assert_protected_history(row,original)
        self.assertEqual(payload['ca_data']['requestedPackage'],selected)
        self.assertEqual(row['paket_adi'],'Standart')


if __name__=='__main__':
    unittest.main()
