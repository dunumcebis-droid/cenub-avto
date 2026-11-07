const fs = require('node:fs');
const path = require('node:path');

// Read classic page scripts in document order without executing the application.
function loadPageSource(root = path.resolve(__dirname, '..')) {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const scripts = [];
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const src = match[1].match(/\bsrc\s*=\s*["']([^"']+)["']/i);
    if (!src) {
      scripts.push({ path: null, source: match[2], attributes: match[1] });
      continue;
    }
    if (/^(?:[a-z]+:)?\/\//i.test(src[1])) continue;
    const relative = decodeURIComponent(src[1].split(/[?#]/)[0]);
    const filename = path.resolve(root, relative);
    if (!filename.startsWith(path.resolve(root) + path.sep)) {
      throw new Error(`Script path leaves repository: ${relative}`);
    }
    scripts.push({ path: relative, source: fs.readFileSync(filename, 'utf8'), attributes: match[1] });
  }
  return { html, scripts, source: scripts.map(script => script.source).join('\n;\n') };
}

module.exports = { loadPageSource };
