"""Static SEO publishing contract; no network, credentials, or provider writes."""
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import unittest
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class Head(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.title_parts = []
        self.in_title = False
        self.metas = []
        self.links = []
        self.scripts = []
        self.current_script = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'head':
            self.in_head = True
        if not self.in_head:
            return
        if tag == 'title':
            self.in_title = True
        elif tag == 'meta':
            self.metas.append(attrs)
        elif tag == 'link':
            self.links.append(attrs)
        elif tag == 'script':
            self.current_script = {'attrs': attrs, 'text': ''}

    def handle_data(self, value):
        if self.in_title:
            self.title_parts.append(value)
        if self.current_script is not None:
            self.current_script['text'] += value

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        elif tag == 'script' and self.current_script is not None:
            self.scripts.append(self.current_script)
            self.current_script = None
        elif tag == 'head':
            self.in_head = False

    @property
    def title(self):
        return ''.join(self.title_parts).strip()

    def meta(self, key):
        return [item.get('content', '') for item in self.metas
                if item.get('name') == key or item.get('property') == key]

    @property
    def canonical(self):
        return [item.get('href', '') for item in self.links
                if 'canonical' in item.get('rel', '').split()]


class StaticSEOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / 'seo.config.json').read_text())
        cls.public = [page for page in cls.config['pages'] if page['indexable']]

    def test_generated_files_match_config_without_changing_files(self):
        result = subprocess.run(['node', 'tools/generate-seo.cjs', '--check'], cwd=ROOT,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_public_url(self, value):
        url = urlsplit(value)
        base = urlsplit(self.config['baseUrl'])
        self.assertEqual(url.scheme, 'https')
        self.assertEqual(url.netloc, base.netloc)
        self.assertTrue(url.path.startswith(base.path), value)
        self.assertFalse(url.query, value)
        self.assertFalse(url.fragment, value)

    def test_five_public_pages_have_unique_consistent_metadata(self):
        self.assertEqual({page['file'] for page in self.public},
                         {'index.html', 'about.html', 'support.html', 'terms.html', 'privacy.html'})
        titles = []
        descriptions = []
        for page in self.public:
            with self.subTest(page=page['file']):
                source = (ROOT / page['file']).read_text()
                head = Head(source)
                expected = urljoin(self.config['baseUrl'], page['path'])
                titles.append(head.title)
                descriptions.append(page['description'])
                self.assertEqual(head.title, page['title'])
                self.assertEqual(head.meta('description'), [page['description']])
                # The shared app document also serves ?ad= routes. Its canonical
                # is added at runtime after the public listing route is checked.
                self.assertEqual(head.canonical, [] if page['file'] == 'index.html' else [expected])
                self.assert_public_url(expected)
                for key, value in (('og:title', page['title']), ('og:description', page['description']),
                                   ('og:url', expected), ('og:site_name', self.config['name']),
                                   ('og:locale', self.config['locale']), ('twitter:card', 'summary_large_image'),
                                   ('twitter:title', page['title']), ('twitter:description', page['description'])):
                    self.assertEqual(head.meta(key), [value], key)
                image = urljoin(self.config['baseUrl'], self.config['logo']['path'])
                self.assertEqual(head.meta('og:image'), [image])
                self.assertEqual(head.meta('twitter:image'), [image])
                self.assertEqual(head.meta('og:image:alt'), [self.config['logo']['alt']])
                self.assertEqual(head.meta('og:image:width'), [str(self.config['logo']['width'])])
                self.assertEqual(head.meta('og:image:height'), [str(self.config['logo']['height'])])
                self.assertFalse(any('noindex' in value.lower() for value in head.meta('robots')))
                self.assertIn('<html lang="az">', source)
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(descriptions), len(set(descriptions)))
        self.assertTrue((ROOT / self.config['logo']['path']).is_file())

    def test_home_structured_data_contains_public_organization_and_website_only(self):
        head = Head((ROOT / 'index.html').read_text())
        scripts = [item for item in head.scripts
                   if item['attrs'].get('type') == 'application/ld+json']
        self.assertEqual(len(scripts), 1)
        data = json.loads(scripts[0]['text'])
        self.assertEqual(data['@context'], 'https://schema.org')
        graph = data['@graph']
        self.assertEqual({item['@type'] for item in graph}, {'Organization', 'WebSite'})
        for item in graph:
            self.assertEqual(item['name'], self.config['name'])
            self.assertEqual(item['url'], self.config['baseUrl'])
        organization = next(item for item in graph if item['@type'] == 'Organization')
        self.assertEqual(organization['email'], self.config['contact']['email'])
        self.assertEqual(organization['telephone'], self.config['contact']['telephone'])
        self.assertNotIn('Car', scripts[0]['text'])
        token = self.config['googleSiteVerification']
        self.assertEqual(head.meta('google-site-verification'), [token] if token else [])

    def test_reset_remains_noindex_and_has_no_canonical_or_social_token_targets(self):
        head = Head((ROOT / 'reset-password.html').read_text())
        robots = ','.join(head.meta('robots')).lower()
        self.assertIn('noindex', robots)
        self.assertIn('nofollow', robots)
        self.assertEqual(head.canonical, [])
        self.assertFalse([item for item in head.metas
                          if item.get('property', '').startswith('og:') or
                          item.get('name', '').startswith('twitter:')])

    def test_sitemap_is_valid_xml_and_contains_only_the_five_public_canonical_urls(self):
        root = ET.fromstring((ROOT / 'sitemap.xml').read_bytes())
        ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
        self.assertEqual(root.tag, ns + 'urlset')
        urls = [item.findtext(ns + 'loc') for item in root.findall(ns + 'url')]
        self.assertEqual(len(urls), 5)
        self.assertCountEqual(urls, [urljoin(self.config['baseUrl'], page['path']) for page in self.public])
        for url in urls:
            self.assert_public_url(url)
            self.assertNotIn('reset-password', url)
        robots = (ROOT / 'robots.txt').read_text()
        self.assertIn('User-agent: *', robots)
        self.assertIn('Sitemap: ' + urljoin(self.config['baseUrl'], 'sitemap.xml'), robots)
        self.assertNotIn('Disallow: /\n', robots)


if __name__ == '__main__':
    unittest.main()
