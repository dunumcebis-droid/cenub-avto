const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Execute both complete production scripts and submit their registered forms.
// The VM has no network or storage access; every Auth response is a fixture.
const sources = Object.fromEntries(['09-auth', '10-password-reset'].map(name => [
  name, fs.readFileSync(path.join(__dirname, '../assets/js', name + '.js'), 'utf8'),
]));
const api = 'https://iqdtehqxusfiwokrzceo.supabase.co';
const github = 'https://dunumcebis-droid.github.io/cenub-avto/';
const vip = 'https://avtounvan.vip/';
const sensitive = '?access_token=query-private-token&token_hash=query-private-hash&redirect_to=https%3A%2F%2Fother.invalid%2F#refresh_token=fragment-private-token';
const plain = value => JSON.parse(JSON.stringify(value));

function harness(name, href) {
  const elements = new Map(), requests = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', disabled: false, hidden: false, textContent: '', style: {}, attributes: {}, listeners: {},
      setAttribute(key, value) { this.attributes[key] = value; },
      addEventListener(type, listener) { this.listeners[type] = listener; },
      checkValidity() { return true; },
      focus() {},
    });
    return elements.get(id);
  };
  const existingSession = { access_token: 'existing-login-fixture' };
  const context = vm.createContext({
    URL, URLSearchParams,
    window: { ...(href === undefined ? {} : { location: { href } }), addEventListener() {} },
    document: { getElementById: element, addEventListener() {} },
    authMode: 'recover', currentUser: null, caSession: existingSession,
    normalizePhone: value => value,
    caRequest: async (...args) => {
      requests.push({ url: new URL(args[0], api).href, method: args[1], body: plain(args[2]), token: args[3] });
      return {};
    },
    fetch: async (url, options) => {
      requests.push({ url, method: options.method, body: JSON.parse(options.body),
        authorization: options.headers.Authorization, credentials: options.credentials,
        referrerPolicy: options.referrerPolicy });
      return { ok: true, status: 200, json: async () => ({}) };
    },
    localStorage: new Proxy({}, { get() { throw new Error('Recovery must not access stored sessions'); } }),
  });
  vm.runInContext(sources[name], context, { filename: name + '.js' });
  async function submit() {
    const modal = name === '09-auth';
    element(modal ? 'authEmail' : 'recoveryEmail').value = '  Customer@Example.invalid  ';
    let prevented = false;
    await element(modal ? 'authForm' : 'recoveryRequestForm').listeners.submit({
      preventDefault() { prevented = true; },
    });
    assert.equal(prevented, true);
    assert.equal(element(modal ? 'authSubmit' : 'recoverySubmit').disabled, false);
    assert.strictEqual(context.caSession, existingSession);
    return requests;
  }
  return { submit };
}

function checkRecovery(requests, expected) {
  assert.equal(requests.length, 1, 'Submitting recovery makes exactly one mocked Auth request');
  const [request] = requests;
  const url = new URL(request.url);
  assert.equal(url.origin, api);
  assert.equal(url.pathname, '/auth/v1/recover');
  assert.equal(request.method, 'POST');
  assert.deepEqual(request.body, { email: 'customer@example.invalid' });
  assert.equal(request.token, undefined, 'Recovery must not reuse the existing login token');
  assert.equal(request.authorization, undefined);
  assert.deepEqual([...url.searchParams.keys()], ['redirect_to']);
  assert.equal(url.searchParams.get('redirect_to'), expected);
  const redirect = new URL(url.searchParams.get('redirect_to'));
  assert.equal(redirect.search, '');
  assert.equal(redirect.hash, '');
}

for (const name of ['09-auth', '10-password-reset']) {
  test(name + ' submits recovery to the current host and site directory without query or fragment credentials', async t => {
    const pages = name === '09-auth' ? ['', 'index.html'] : ['reset-password.html'];
    for (const base of [github, vip]) {
      for (const page of pages) {
        for (const suffix of ['', sensitive]) {
          await t.test(base + page + (suffix ? ' with private query and fragment' : ''), async () => {
            checkRecovery(await harness(name, base + page + suffix).submit(), base + 'reset-password.html');
          });
        }
      }
    }
  });
  test(name + ' preserves the GitHub fallback for nonbrowser stubs without location.href', async () => {
    checkRecovery(await harness(name).submit(), github + 'reset-password.html');
  });
}
