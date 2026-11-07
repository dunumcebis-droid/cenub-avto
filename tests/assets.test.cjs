const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { loadPageSource } = require('./source-loader.cjs');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'assets/manifest.json'), 'utf8'));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

test('all original embedded image bytes and 56 reference identities are preserved', () => {
  assert.equal(manifest.source_html_sha256, '78ae01e5d4e895b3f2aed6f59436a819692e35667ac79e688d45793eba817078');
  assert.equal(manifest.original_data_uri_list_sha256, '731611a07c211e10ff4fef10b080b5c9ea5975462cca0717059cb9c53d641295');
  assert.equal(manifest.references.length, 56);
  assert.equal(manifest.images.length, 46);
  assert.equal(digest(manifest.references.map(reference => reference.data_uri_sha256).join('\n')),
    '0be0053616ad72171ff87409ef7b16da303f42554086944b691a780b609cea27');
  const images = new Map(manifest.images.map(image => [image.path, image]));
  for (const image of manifest.images) {
    const bytes = fs.readFileSync(path.join(root, image.path));
    assert.equal(bytes.length, image.bytes, image.path);
    assert.equal(digest(bytes), image.decoded_sha256, image.path);
  }
  for (const reference of manifest.references) {
    const image = images.get(reference.path);
    assert.equal(image?.decoded_sha256, reference.decoded_sha256);
    const bytes = fs.readFileSync(path.join(root, reference.path));
    const originalUri = `data:${image.mime_type};base64,${bytes.toString('base64')}`;
    assert.equal(digest(originalUri), reference.data_uri_sha256, `Original data URI: ${reference.path}`);
  }
});

test('the initial HTML stays small and classic script execution order is preserved', () => {
  const page = loadPageSource(root);
  assert.ok(Buffer.byteLength(page.html) < 100 * 1024, 'Static image bytes must not inflate the HTML response');
  assert.equal(page.scripts.length, 10);
  assert.deepEqual(page.scripts.map(script => script.path), [
    'assets/js/00-auth-callback.js', 'assets/js/01-main.js', 'assets/js/02-mileage-input.js', 'assets/js/03-bmw-series.js',
    'assets/js/04-bmw-picker.js', 'assets/js/05-filters-toggle.js', 'assets/js/06-extra-tools.js',
    'assets/js/07-admin.js', 'assets/js/08-equipment-toggle.js', 'assets/js/09-auth.js',
  ]);
  for (const script of page.scripts) {
    if (script.path === 'assets/js/00-auth-callback.js') assert.doesNotMatch(script.attributes, /\bdefer\b/);
    else assert.match(script.attributes, /\bdefer\b/);
    assert.doesNotMatch(script.attributes, /\b(?:async|type\s*=\s*["']module["'])\b/);
  }
  assert.doesNotMatch(page.html + page.source, /data:image\/(?:jpeg|png);base64,/);
  assert.match(page.html, /<link[^>]+href="assets\/site\.css(?:\?[^"<>]*)?"/);
  assert.ok(page.html.indexOf('00-auth-callback.js') < page.html.indexOf('assets/site.css'));
  assert.match(page.html, /<meta name="referrer" content="no-referrer"/);
  const hero = page.html.match(/<img\b[^>]*alt="Premium idman avtomobili"[^>]*>/)?.[0];
  assert.ok(hero);
  assert.match(hero, /loading="eager"/);
  assert.match(hero, /fetchpriority="high"/);
});
