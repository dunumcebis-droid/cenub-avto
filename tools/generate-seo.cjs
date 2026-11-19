#!/usr/bin/env node
'use strict';

// Offline only: no database access, listing export, packages or network requests.
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const begin = '<!-- SEO:BEGIN -->';
const end = '<!-- SEO:END -->';
const args = process.argv.slice(2);
if (args.some(arg => arg !== '--check')) {
  console.error('Usage: node tools/generate-seo.cjs [--check]');
  process.exit(1);
}
const check = args.includes('--check');
const config = JSON.parse(fs.readFileSync(path.join(root, 'seo.config.json'), 'utf8'));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function relativePath(value) {
  return typeof value === 'string' && !/^(?:[a-z]+:|\/)/i.test(value)
    && !value.includes('\\') && !value.split('/').includes('..')
    && !/[?#\s]/.test(value);
}

const base = new URL(config.baseUrl);
assert(base.protocol === 'https:' && !base.username && !base.password
  && !base.search && !base.hash && base.href === config.baseUrl
  && config.baseUrl.endsWith('/'), 'baseUrl must be a canonical HTTPS URL ending in /.');
for (const key of ['name', 'slogan', 'language', 'locale', 'description']) {
  assert(typeof config[key] === 'string' && config[key].trim(), `Missing ${key}.`);
}
assert(relativePath(config.logo.path) && fs.existsSync(path.join(root, config.logo.path)), 'Logo path must name an existing local image.');
assert(Number.isInteger(config.logo.width) && config.logo.width > 0
  && Number.isInteger(config.logo.height) && config.logo.height > 0, 'Logo dimensions must be positive integers.');
assert(typeof config.logo.alt === 'string' && config.logo.alt.trim(), 'Logo alt text is required.');
assert(typeof config.contact.email === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.contact.email), 'A real public support email is required.');
assert(typeof config.contact.telephone === 'string' && /^\+[0-9]{8,15}$/.test(config.contact.telephone), 'Support phone must use international format.');
assert(typeof config.googleSiteVerification === 'string'
  && /^(?:[A-Za-z0-9_-]+)?$/.test(config.googleSiteVerification), 'Use only the public verification token, or leave it empty.');
assert(Array.isArray(config.pages) && config.pages.length > 0, 'Pages are required.');
const pageFiles = new Set();
const pagePaths = new Set();
for (const page of config.pages) {
  assert(typeof page.file === 'string' && /^[a-z0-9-]+\.html$/.test(page.file), 'Each page must be a root HTML file.');
  assert(relativePath(page.path), `Invalid page path: ${page.file}.`);
  assert(!pageFiles.has(page.file) && !pagePaths.has(page.path), 'Page files and canonical paths must be unique.');
  assert(typeof page.title === 'string' && page.title.trim()
    && typeof page.description === 'string' && page.description.trim(), `Missing title or description: ${page.file}.`);
  assert(typeof page.indexable === 'boolean', `Set indexable explicitly: ${page.file}.`);
  assert(page.path === (page.file === 'index.html' ? '' : page.file), `Canonical path must match its HTML page: ${page.file}.`);
  pageFiles.add(page.file);
  pagePaths.add(page.path);
}
assert(config.pages.some(page => page.file === 'index.html' && page.indexable), 'An indexable home page is required.');
assert(config.pages.some(page => page.file === 'reset-password.html' && !page.indexable), 'Password recovery must stay noindex.');

const escape = value => String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
  .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;');
const json = value => JSON.stringify(value, null, 2).replace(/</g, '\\u003c')
  .replace(/>/g, '\\u003e').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
const url = resource => new URL(resource, base).href;
const meta = (attribute, key, value) => `<meta ${attribute}="${key}" content="${escape(value)}"/>`;

function homeStructuredData() {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebSite',
        '@id': url('#website'),
        url: config.baseUrl,
        name: config.name,
        description: config.description,
        inLanguage: config.language,
        publisher: { '@id': url('#organization') }
      },
      {
        '@type': 'Organization',
        '@id': url('#organization'),
        name: config.name,
        url: config.baseUrl,
        description: config.description,
        slogan: config.slogan,
        logo: {
          '@type': 'ImageObject',
          url: url(config.logo.path),
          width: config.logo.width,
          height: config.logo.height
        },
        email: config.contact.email,
        telephone: config.contact.telephone
      }
    ]
  };
}

function metadata(page) {
  const lines = [
    begin,
    '<!-- Generated from seo.config.json; run node tools/generate-seo.cjs after changes. -->',
    `<title>${escape(page.title)}</title>`,
    meta('name', 'description', page.description),
    meta('name', 'robots', page.indexable ? 'index, follow, max-image-preview:large' : 'noindex, nofollow')
  ];
  if (page.indexable) {
    // index.html also serves ?ad=... routes. Its canonical is created by 21-seo.js
    // after route validation, so initial HTML cannot canonicalize every ad to home.
    if (page.file !== 'index.html') {
      lines.push(`<link id="canonical-url" rel="canonical" href="${escape(url(page.path))}"/>`);
    }
    lines.push(
      meta('property', 'og:type', 'website'),
      meta('property', 'og:site_name', config.name),
      meta('property', 'og:locale', config.locale),
      meta('property', 'og:url', url(page.path)),
      meta('property', 'og:title', page.title),
      meta('property', 'og:description', page.description),
      meta('property', 'og:image', url(config.logo.path)),
      meta('property', 'og:image:type', 'image/png'),
      meta('property', 'og:image:width', config.logo.width),
      meta('property', 'og:image:height', config.logo.height),
      meta('property', 'og:image:alt', config.logo.alt),
      meta('name', 'twitter:card', 'summary_large_image'),
      meta('name', 'twitter:title', page.title),
      meta('name', 'twitter:description', page.description),
      meta('name', 'twitter:image', url(config.logo.path)),
      meta('name', 'twitter:image:alt', config.logo.alt)
    );
  }
  if (page.file === 'index.html') {
    if (config.googleSiteVerification) lines.push(meta('name', 'google-site-verification', config.googleSiteVerification));
    lines.push(`<script id="seo-structured-data" type="application/ld+json">\n${json(homeStructuredData())}\n</script>`);
  }
  lines.push(end);
  return lines.join('\n');
}

function attribute(tag, name) {
  const match = tag.match(new RegExp(`\\b${name}\\s*=\\s*["']([^"']*)["']`, 'i'));
  return match ? match[1].toLowerCase() : '';
}

function updateHead(html, page) {
  let count = 0;
  const result = html.replace(/<head\b[^>]*>([\s\S]*?)<\/head>/i, (head, contents) => {
    count += 1;
    const block = metadata(page);
    const start = contents.indexOf(begin);
    const finish = contents.indexOf(end);
    if (start !== -1 || finish !== -1) {
      assert(start !== -1 && finish > start
        && contents.indexOf(begin, start + begin.length) === -1
        && contents.indexOf(end, finish + end.length) === -1, `Malformed SEO markers: ${page.file}.`);
      return head.replace(contents.slice(start, finish + end.length), block);
    }
    // First run migrates existing metadata once. Subsequent runs only replace markers.
    const kept = contents.replace(/<title\b[^>]*>[\s\S]*?<\/title>/gi, '')
      .replace(/<meta\b[^>]*>/gi, tag => {
        const name = attribute(tag, 'name');
        const property = attribute(tag, 'property');
        return ['description', 'robots', 'google-site-verification'].includes(name)
          || name.startsWith('twitter:') || property.startsWith('og:') ? '' : tag;
      })
      .replace(/<link\b[^>]*>/gi, tag => attribute(tag, 'rel') === 'canonical' ? '' : tag)
      .trim().replace(/>\s*</g, '>\n<');
    return `<head>\n${kept}\n${block}\n</head>`;
  });
  assert(count === 1, `Missing head: ${page.file}.`);
  return result;
}

function sitemap() {
  return '<?xml version="1.0" encoding="UTF-8"?>\n'
    + '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + config.pages.filter(page => page.indexable)
      .map(page => `  <url><loc>${escape(url(page.path))}</loc></url>`).join('\n')
    + '\n</urlset>\n';
}

function robots() {
  const projectPath = base.pathname !== '/';
  return '# Generated by tools/generate-seo.cjs.\n'
    + (projectPath
      ? '# This project-path file is not the host-root /robots.txt and is not crawler policy.\n# Submit the sitemap directly in Search Console. See SEO_SETUP.md.\n'
      : '# Crawling stays allowed so search engines can read page-level noindex directives.\n')
    + 'User-agent: *\nAllow: /\n\n'
    + `Sitemap: ${url('sitemap.xml')}\n`;
}

// Prepare every output before writing, so an invalid config/HTML does not partly regenerate.
const outputs = config.pages.map(page => {
  const file = path.join(root, page.file);
  return [page.file, updateHead(fs.readFileSync(file, 'utf8'), page)];
});
outputs.push(['sitemap.xml', sitemap()], ['robots.txt', robots()]);
let changed = 0;
for (const [relative, content] of outputs) {
  const file = path.join(root, relative);
  const old = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
  if (old === content) continue;
  changed += 1;
  if (check) console.error(`SEO output needs regeneration: ${relative}`);
  else fs.writeFileSync(file, content);
}
if (check && changed) process.exitCode = 1;
else console.log(check ? 'SEO outputs are current.' : `SEO outputs generated (${changed} changed).`);
