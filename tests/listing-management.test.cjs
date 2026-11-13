const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('./source-loader.cjs').loadPageSource().source;

function productionFunction(context, name) {
  const start = source.search(new RegExp(`(?:async\\s+)?function ${name}\\s*\\(`));
  assert.notEqual(start, -1, `Production function ${name} must exist`);
  for (let end = source.indexOf('}', start); end !== -1; end = source.indexOf('}', end + 1)) {
    const candidate = source.slice(start, end + 1);
    try { new vm.Script(`(${candidate})`); } catch { continue; }
    vm.runInContext(candidate, context);
    return context[name];
  }
  throw new Error(`Cannot extract production function ${name}`);
}

function production(names, globals = {}) {
  const context = vm.createContext({
    console,
    currentUser: { id: 'fixture-owner', phone: '+994000000000' },
    photoCategoryNames: {
      front: 'Ön görünüş', rear: 'Arxa görünüş', side: 'Yan görünüş',
      interior: 'Salon', engine: 'Mühərrik', other: 'Digər şəkillər',
    },
    ...globals,
  });
  for (const name of names) productionFunction(context, name);
  return context;
}
const plain = value => JSON.parse(JSON.stringify(value));
const flatten = groups => Object.values(groups).flat();
const photoUrls = count => Array.from({ length: count }, (_, i) => `https://fixture.invalid/photo-${i + 1}.jpg`);
const payloadContext = () => production(['caValue', 'caNumber', 'caListingPayload']);

test('saving a blank mileage preserves null while an entered zero remains zero', () => {
  const { caListingPayload } = payloadContext();
  for (const mileage of [undefined, null, '', '   ']) {
    const payload = caListingPayload({ make: 'Toyota', model: 'Prius', mileage });
    assert.equal(payload.yurus, null, 'A missing mileage must not be persisted as a fabricated zero');
  }
  for (const mileage of [0, '0']) {
    assert.equal(caListingPayload({ mileage }).yurus, 0, 'A genuine zero mileage must survive');
  }
  assert.equal(caListingPayload({ mileage: '120 000 km' }).yurus, 120000);
});

test('seller payloads derive ownership from the current account and exclude protected package and sold columns', () => {
  const { caListingPayload } = payloadContext();
  const payload = caListingPayload({
    make: 'Toyota', ownerId: 'another-owner', satici_id: 'another-owner',
    pack: 'VIP', paket_adi: 'VIP', paket_baslayir: '2099-01-01', paket_bitir: '2099-12-31',
    is_sold: true, isSold: true, status: 'satilib',
  });
  assert.equal(payload.satici_id, 'fixture-owner');
  assert.equal(payload.veziyyet, 'gozlemede');
  for (const key of ['paket_adi', 'paket_baslayir', 'paket_bitir', 'tesdiq_tarixi', 'paket_tesdiq_qeydi', 'is_sold']) {
    assert.equal(Object.hasOwn(payload, key), false, `Seller payload must not set ${key}`);
  }
});

test('consistent stored photo categories survive authoritative URL mapping', () => {
  const { caStoredPhotoGroups } = production(['caStoredPhotoGroups']);
  const urls = photoUrls(12);
  const photos = { front: urls.slice(0, 4), rear: urls.slice(4, 8), interior: urls.slice(8) };
  const original = JSON.stringify(photos);
  const result = caStoredPhotoGroups({ sekiller: urls }, { photos, photo: urls[0] });
  assert.deepEqual(plain(result.photos), photos);
  assert.equal(result.photo, urls[0]);
  assert.equal(JSON.stringify(photos), original, 'Snapshot photo categories must not be mutated');
});

test('uncategorized legacy photo lists retain every original image without inventing viewing angles', () => {
  const { caStoredPhotoGroups } = production(['caStoredPhotoGroups']);
  for (const count of [9, 41]) {
    const urls = photoUrls(count);
    const result = caStoredPhotoGroups({ sekiller: urls }, {});
    assert.deepEqual(plain(result.photos.other), urls);
    assert.deepEqual(plain(flatten(result.photos)), urls);
    assert.equal(result.photo, urls[0]);
    assert.deepEqual(urls, photoUrls(count), 'Authoritative photo URLs must not be mutated');
  }
});

test('explicitly empty authoritative photos do not resurrect stale form images', () => {
  const { caStoredPhotoGroups } = production(['caStoredPhotoGroups']);
  const result = caStoredPhotoGroups({ sekiller: [] }, {
    photo: 'https://fixture.invalid/stale-cover.jpg',
    photos: { front: ['https://fixture.invalid/stale-front.jpg'] },
  });
  assert.equal(result.photo, null);
  assert.deepEqual(plain(flatten(result.photos)), []);
});

test('authoritative photos retain duplicates and matching categories while stale URLs disappear', () => {
  const { caStoredPhotoGroups } = production(['caStoredPhotoGroups']);
  const [a, b, c, removed, fresh] = photoUrls(5);
  const urls = [c, b, fresh, a, a];
  const snapshot = { photos: { front: [a, b], rear: [c], other: [removed] } };
  const original = JSON.stringify({ urls, snapshot });
  const result = caStoredPhotoGroups({ sekiller: urls }, snapshot);
  assert.deepEqual(plain(flatten(result.photos)).sort(), urls.slice().sort());
  assert.ok(result.photos.front.includes(a) && result.photos.front.includes(b));
  assert.ok(result.photos.rear.includes(c));
  assert.ok(result.photos.other.includes(fresh));
  assert.equal(flatten(result.photos).includes(removed), false);
  assert.equal(result.photo, c);
  assert.equal(JSON.stringify({ urls, snapshot }), original, 'Reconciliation must not mutate either source');
});

test('absent authoritative photo data preserves legacy categories and the existing cover', () => {
  const { caStoredPhotoGroups } = production(['caStoredPhotoGroups']);
  const urls = photoUrls(3);
  const snapshot = { photo: urls[1], photos: { front: [urls[0]], other: urls.slice(1) } };
  const result = caStoredPhotoGroups({}, snapshot);
  assert.deepEqual(plain(result.photos), snapshot.photos);
  assert.equal(result.photo, urls[1]);
});

test('editing restores equipment by checkbox value and clears selections absent from the record', () => {
  const { caRestoreEquipment } = production(['caRestoreEquipment']);
  const boxes = [
    { value: 'ABS', checked: false },
    { value: 'Kondisioner', checked: true },
    { value: 'Park radarı', checked: false },
  ];
  const form = { querySelectorAll: () => boxes };
  caRestoreEquipment(form, ['ABS', 'Park radarı']);
  assert.deepEqual(boxes.map(({ value, checked }) => [value, checked]), [
    ['ABS', true], ['Kondisioner', false], ['Park radarı', true],
  ]);
  caRestoreEquipment(form, []);
  assert.ok(boxes.every(box => box.checked === false));
});

test('a zero-row mutation response is an error rather than a successful save or delete', () => {
  const { caRequireAffectedRow } = production(['caRequireAffectedRow']);
  for (const result of [[], null, undefined]) {
    assert.throws(() => caRequireAffectedRow(result, 'fixture-listing', 'save'));
    assert.throws(() => caRequireAffectedRow(result, 'fixture-listing', 'delete'));
  }
});

test('mutation confirmation must identify exactly the requested listing', () => {
  const { caRequireAffectedRow } = production(['caRequireAffectedRow']);
  assert.doesNotThrow(() => caRequireAffectedRow([{ id: 'fixture-listing' }], 'fixture-listing', 'save'));
  assert.throws(() => caRequireAffectedRow([{ id: 'another-listing' }], 'fixture-listing', 'save'));
  assert.throws(() => caRequireAffectedRow([{ id: 'fixture-listing' }, { id: 'another-listing' }], 'fixture-listing', 'delete'));
});

test('photo count checks allow untouched legacy metadata edits and valid replacements without allowing added overflow', () => {
  const { caValidatePhotoCounts } = production(['caValidatePhotoCounts']);
  const original = { other: photoUrls(41) };
  assert.doesNotThrow(() => caValidatePhotoCounts(plain(original), original, []));
  assert.doesNotThrow(() => caValidatePhotoCounts({ other: photoUrls(6) }, original, [{ files: Array(6) }]));
  assert.throws(() => caValidatePhotoCounts({ other: photoUrls(9) }, null, [{ files: Array(9) }]));
  assert.throws(() => caValidatePhotoCounts({ other: photoUrls(42) }, original, []));
  assert.throws(() => caValidatePhotoCounts({ ...plain(original), front: ['https://fixture.invalid/new.jpg'] }, original, [{ files: [{}] }]));
});

test('engine descriptions persist their numeric capacity and blank engine values remain null', () => {
  const { caListingPayload } = payloadContext();
  for (const engine of [undefined, null, '', '  ']) {
    assert.equal(caListingPayload({ engine }).muherrik_hecmi, null);
  }
  assert.equal(caListingPayload({ engine: '2.0 L benzin' }).muherrik_hecmi, 2);
  assert.equal(caListingPayload({ engine: '1,6 L dizel' }).muherrik_hecmi, 1.6);
});

function mutationHarness(response, token = 'fixture-token') {
  const calls = [];
  const context = production([
    'caValue', 'caNumber', 'caListingPayload', 'caRequireAffectedRow',
    'caSaveRemoteCar', 'caDeleteRemoteCar',
  ], {
    editingCarId: 'fixture-listing',
    caToken: async () => token,
    caRequest: async (...args) => {
      calls.push(plain(args));
      return typeof response === 'function' ? response(...args) : response;
    },
  });
  return { context, calls };
}

test('editing requests the owned listing and confirms one affected row without trying to set ownership', async () => {
  const { context, calls } = mutationHarness([{ id: 'fixture-listing' }]);
  assert.equal(await context.caSaveRemoteCar({ make: 'Toyota', model: 'Prius', mileage: 0 }, true), 'fixture-listing');
  assert.equal(calls.length, 1);
  const [pathname, method, body] = calls[0];
  assert.equal(method, 'PATCH');
  assert.ok(pathname.includes('id=eq.fixture-listing'));
  assert.ok(pathname.includes('satici_id=eq.fixture-owner'));
  assert.ok(pathname.includes('select=id'));
  assert.equal(Object.hasOwn(body, 'satici_id'), false, 'Metadata edits must not update the protected owner column');
  assert.equal(body.veziyyet, 'gozlemede');
  assert.equal(body.yurus, 0);
  assert.ok(calls[0][4].Prefer.includes('return=representation'));
});

test('an edit that affects no listing is rejected before success can be reported', async () => {
  const { context, calls } = mutationHarness([]);
  await assert.rejects(() => context.caSaveRemoteCar({ make: 'Toyota' }, true));
  assert.equal(calls.length, 1);
});

test('deleting archives only the owned listing and requires server confirmation', async () => {
  const { context, calls } = mutationHarness([{ id: 'fixture-listing' }]);
  await context.caDeleteRemoteCar('fixture-listing');
  assert.equal(calls.length, 1);
  const [pathname, method, body] = calls[0];
  assert.equal(method, 'PATCH', 'Listings must be archived rather than physically removed');
  assert.ok(pathname.includes('id=eq.fixture-listing'));
  assert.ok(pathname.includes('satici_id=eq.fixture-owner'));
  assert.ok(pathname.includes('select=id'));
  assert.deepEqual(body, { veziyyet: 'silindi' });
  assert.ok(calls[0][4].Prefer.includes('return=representation'));
});

test('zero-row or mismatched archive confirmations cannot be reported as deletion', async () => {
  for (const response of [[], [{ id: 'another-listing' }]]) {
    const { context, calls } = mutationHarness(response);
    await assert.rejects(() => context.caDeleteRemoteCar('fixture-listing'));
    assert.equal(calls.length, 1);
  }
});

test('new listings require a returned server ID and do not issue a separate package RPC', async () => {
  const { context, calls } = mutationHarness([{ id: 'fixture-created' }]);
  assert.equal(await context.caSaveRemoteCar({ make: 'Toyota', requestedPackage: 'VIP' }, false), 'fixture-created');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1], 'POST');
  assert.equal(calls[0][2].satici_id, 'fixture-owner');
  assert.equal(calls[0][2].ca_data.requestedPackage, 'VIP');
  assert.ok(!calls.some(([pathname]) => pathname.includes('/rpc/')));
  const failed = mutationHarness([]);
  await assert.rejects(() => failed.context.caSaveRemoteCar({ make: 'Toyota' }, false));
});

test('unauthenticated mutation attempts fail before any request is issued', async () => {
  const { context, calls } = mutationHarness([{ id: 'fixture-listing' }], null);
  await assert.rejects(() => context.caSaveRemoteCar({}, true));
  await assert.rejects(() => context.caDeleteRemoteCar('fixture-listing'));
  assert.deepEqual(calls, []);
});

test('seller cabinet listings exclude archived rows and other owners', () => {
  const context = production(['myCars'], {
    caRemoteCars: [
      { _id: 'own-active', ownerId: 'fixture-owner', veziyyet: 'aktiv' },
      { _id: 'own-pending', ownerId: 'fixture-owner', veziyyet: 'gozlemede' },
      { _id: 'own-archived', ownerId: 'fixture-owner', veziyyet: 'silindi' },
      { _id: 'other-active', ownerId: 'another-owner', veziyyet: 'aktiv' },
    ],
  });
  assert.deepEqual(plain(context.myCars()).map(car => car._id), ['own-active', 'own-pending']);
});


test('equipment edits retain legacy values missing from the catalog while honoring known deselections', () => {
  const { caCollectEquipment } = production(['caCollectEquipment']);
  const boxes = [
    { value: 'ABS', checked: true },
    { value: 'Kondisioner', checked: false },
  ];
  const form = { querySelectorAll: () => boxes };
  const original = ['ABS', 'Legacy safety option'];
  assert.deepEqual(plain(caCollectEquipment(form, original)).sort(), original.slice().sort());
  boxes[0].checked = false;
  boxes[1].checked = true;
  assert.deepEqual(plain(caCollectEquipment(form, original)).sort(), ['Kondisioner', 'Legacy safety option'].sort());
  boxes[1].checked = false;
  assert.deepEqual(plain(caCollectEquipment(form, null)), []);
  assert.deepEqual(original, ['ABS', 'Legacy safety option'], 'Original equipment must not be mutated');
});

function fixtureId(index) {
  return `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
}
function listingRows(count, first = 0) {
  return Array.from({ length: count }, (_, index) => ({
    id: fixtureId(first + index), marka: 'Fixture', model: String(first + index),
    veziyyet: 'aktiv', satici_id: 'fixture-owner',
  }));
}
function browseReply({ items = listingRows(24), vip = [], total = 1001, page = 1, today = 0 } = {}) {
  return { items, vip_items: vip, total, page, page_size: 24,
    total_pages: Math.ceil(total / 24), today_approved: today };
}
function listingHarness({ respond = async () => browseReply(), filters = null, pack = 'all', sort = 'newest', globals = {} } = {}) {
  const calls = [];
  const elements = {
    sortListings: { value: sort },
    caTodayApproved: { textContent: '—' },
    elanlar: { scrollIntoView() {} },
  };
  const context = production([
    'listingKey', 'caRebuildListingCache', 'caRememberListings', 'caCurrentListings',
    'caInvalidatePrivateRequests', 'caClearPrivateListings', 'caUpdatePublicStats', 'caFetchListings',
    'caFetchScopedListings', 'caFetchMyListings', 'caFetchFavoriteListings', 'caChangePage',
  ], {
    AbortController,
    console: { warn() {} },
    document: { getElementById: id => elements[id] || null },
    caToken: async () => 'fixture-token',
    caRequest: async (pathname, method, body, token, headers, signal) => {
      const call = { pathname, method, body: body == null ? body : plain(body), token, headers, signal };
      calls.push(call);
      return respond(call, calls.length);
    },
    caRemoteToCar: row => ({ ...row, _id: row.id, status: row.veziyyet }),
    render() {}, renderCabinet() {}, renderBuyerFavorites() {},
    favoriteKeys: () => [],
    currentSearch: filters, currentFilter: pack,
    caRemoteCars: [], caPageCars: [], caVipCars: [], caOwnCars: [], caFavoriteCars: [],
    caListingCache: new Map(), caListingsError: false,
    caBrowseSequence: 0, caBrowseController: null, caOwnSequence: 0, caFavoritesSequence: 0,
    caBrowseState: { page: 1, pageSize: 24, total: 0, totalPages: 0, loaded: false,
      loading: false, error: false, todayApproved: null, requestedPage: 1 },
    caPrivateState: { ownLoaded: false, ownLoading: false, ownError: false,
      favoritesLoaded: false, favoritesLoading: false, favoritesError: false },
    ...globals,
  });
  const declaration = source.match(/const CA_LISTING_COLUMNS\s*=\s*(['"])[^'"\n]+\1;/);
  assert.ok(declaration);
  vm.runInContext(declaration[0], context);
  return { context, calls, elements };
}
function assertScopedRead(call) {
  assert.equal(call.method, 'GET');
  const url = new URL(call.pathname, 'https://fixture.invalid');
  assert.equal(url.pathname, '/rest/v1/elanlar');
  const columns = url.searchParams.get('select').split(',');
  assert.equal(columns.length, 30);
  assert.equal(new Set(columns).size, 30);
  assert.ok(columns.includes('is_sold'));
  assert.ok(columns.includes('tesdiq_tarixi'));
  assert.ok(!columns.includes('*') && !columns.includes('paket_tesdiq_qeydi'));
  assert.equal(url.searchParams.get('limit'), '100');
  assert.equal(url.searchParams.get('order'), 'yaradildi.desc,id.desc');
  assert.equal(call.token, 'fixture-token');
  return url.searchParams;
}
const nextTurn = () => new Promise(resolve => setImmediate(resolve));

test('server browsing forwards page, package, sorting and explicit zero bounds without fetching the full table', async () => {
  const filters = { make: 'Toyota', kmMin: 0, kmMax: 0, priceMin: 0,
    engineMin: 0, equipment: ['ABS'], city: 'Bakı' };
  const original = JSON.stringify(filters);
  const { context, calls, elements } = listingHarness({
    filters, pack: 'VIP', sort: 'priceAsc',
    respond: async () => browseReply({ page: 22, vip: listingRows(2, 9000), today: 73 }),
  });
  assert.equal(await context.caFetchListings(22), true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].pathname, '/rest/v1/rpc/ca_browse_listings');
  assert.equal(calls[0].method, 'POST');
  assert.deepEqual(calls[0].body, {
    p_filters: { ...filters, pack: 'VIP', sort: 'priceAsc' }, p_page: 22, p_page_size: 24,
  });
  assert.equal(JSON.stringify(filters), original, 'The form filters must not be mutated');
  assert.equal(context.caPageCars.length, 24);
  assert.equal(context.caVipCars.length, 2);
  assert.equal(context.caBrowseState.total, 1001);
  assert.equal(context.caBrowseState.totalPages, 42);
  assert.equal(context.caBrowseState.page, 22);
  assert.equal(elements.caTodayApproved.textContent, '73', 'The counter comes from the server, not the visible page');
});

test('the last page remains reachable beyond the former 500-row limit', async () => {
  const { context } = listingHarness({
    respond: async () => browseReply({ page: 26, total: 617, items: listingRows(17, 600) }),
  });
  assert.equal(await context.caFetchListings(26), true);
  assert.equal(context.caBrowseState.total, 617);
  assert.equal(context.caBrowseState.totalPages, 26);
  assert.equal(context.caPageCars.length, 17);
  assert.equal(context.caPageCars[0]._id, fixtureId(600));
  assert.equal(context.caPageCars.at(-1)._id, fixtureId(616));
});

test('today counts preserve a database zero and do not infer approvals from cached listing dates', () => {
  const { context, elements } = listingHarness();
  context.caRemoteCars = [{ _id: 'cached', veziyyet: 'aktiv',
    createdAt: new Date().toISOString(), approvedAt: new Date().toISOString() }];
  for (const [value, expected] of [[0, '0'], [89, '89'], [null, '—']]) {
    context.caBrowseState.todayApproved = value;
    context.caUpdatePublicStats();
    assert.equal(elements.caTodayApproved.textContent, expected);
  }
});

test('a late response from an older page cannot overwrite the newer page or its cache', async () => {
  const pending = [];
  const { context, calls } = listingHarness({
    respond: () => new Promise(resolve => pending.push(resolve)),
  });
  const first = context.caFetchListings(1);
  await nextTurn();
  const second = context.caFetchListings(2);
  await nextTurn();
  assert.equal(calls.length, 2);
  assert.equal(calls[0].signal.aborted, true);
  pending[1](browseReply({ page: 2, items: listingRows(1, 24), total: 25 }));
  assert.equal(await second, true);
  pending[0](browseReply({ page: 1, items: listingRows(24), total: 25 }));
  assert.equal(await first, false);
  assert.equal(context.caBrowseState.page, 2);
  assert.deepEqual(plain(context.caPageCars).map(row => row._id), [fixtureId(24)]);
  assert.equal(context.caListingCache.has(fixtureId(0)), false);
  assert.equal(context.caListingCache.has(fixtureId(24)), true);
});

test('failed or malformed page responses preserve the last successful records and total', async () => {
  let mode = 'success';
  const { context } = listingHarness({ respond: async () => {
    if (mode === 'error') throw new Error('Fixture network failure');
    if (mode === 'malformed') return { items: null, vip_items: [], total: 9999 };
    if (mode === 'null-total') return { items: [], vip_items: [], total: null, page: 1, page_size: 24, total_pages: 0, today_approved: 0 };
    if (mode === 'mapping-error') return browseReply({ page: 2, total: 37,
      items: listingRows(1, 24), vip: listingRows(1, 99999) });
    return browseReply({ total: 37, items: listingRows(24), vip: listingRows(1, 9000) });
  } });
  assert.equal(await context.caFetchListings(1), true);
  const previous = JSON.stringify(plain(context.caRemoteCars));
  const previousPage = JSON.stringify(plain(context.caPageCars));
  const previousVip = JSON.stringify(plain(context.caVipCars));
  const originalMapper = context.caRemoteToCar;
  context.caRemoteToCar = row => {
    if (row.id === fixtureId(99999)) throw new Error('Fixture VIP mapping failure');
    return originalMapper(row);
  };
  for (mode of ['error', 'malformed', 'null-total', 'mapping-error']) {
    assert.equal(await context.caFetchListings(2), false);
    assert.equal(context.caBrowseState.page, 1);
    assert.equal(context.caBrowseState.total, 37);
    assert.equal(context.caBrowseState.loading, false);
    assert.equal(context.caBrowseState.error, true);
    assert.equal(context.caListingsError, true);
    assert.equal(JSON.stringify(plain(context.caRemoteCars)), previous);
    assert.equal(JSON.stringify(plain(context.caPageCars)), previousPage);
    assert.equal(JSON.stringify(plain(context.caVipCars)), previousVip);
  }
});

test('pager controls respect the first page, last page and an active request', () => {
  const { context } = listingHarness();
  const requested = [];
  context.caFetchListings = page => requested.push(page);
  Object.assign(context.caBrowseState, { page: 1, totalPages: 42 });
  context.caChangePage(-1);
  assert.deepEqual(requested, []);
  context.caChangePage(1);
  assert.deepEqual(requested, [2]);
  Object.assign(context.caBrowseState, { page: 42 });
  context.caChangePage(1);
  assert.deepEqual(requested, [2]);
  Object.assign(context.caBrowseState, { page: 20, loading: true });
  context.caChangePage(1);
  assert.deepEqual(requested, [2]);
});

test('seller listings retrieve all owned records in stable 100-row batches beyond 500', async () => {
  const rows = listingRows(617).map(row => ({ ...row, veziyyet: 'gozlemede' }));
  const { context, calls } = listingHarness({ respond: async call => {
    const query = assertScopedRead(call);
    assert.equal(query.get('satici_id'), 'eq.fixture-owner');
    assert.equal(query.get('veziyyet'), 'neq.silindi');
    const offset = Number(query.get('offset'));
    return rows.slice(offset, offset + 100);
  } });
  assert.equal(await context.caFetchMyListings(), true);
  assert.equal(calls.length, 7);
  assert.deepEqual(calls.map(call => Number(new URL(call.pathname, 'https://fixture.invalid').searchParams.get('offset'))),
    [0, 100, 200, 300, 400, 500, 600]);
  assert.equal(context.caOwnCars.length, 617);
  assert.equal(context.caRemoteCars.length, 617);
  assert.equal(context.caPrivateState.ownLoaded, true);
  assert.equal(context.caPrivateState.ownLoading, false);
});

test('favorite listing retrieval batches valid unique IDs and excludes invalid stored keys', async () => {
  const rows = listingRows(205);
  const byId = new Map(rows.map(row => [row.id, row]));
  const ids = rows.map(row => row.id);
  const { context, calls } = listingHarness({
    globals: { favoriteKeys: () => [...ids, ids[0], 'invalid-id', 'id)or(veziyyet.eq.gozlemede'] },
    respond: async call => {
      const query = assertScopedRead(call);
      assert.equal(query.get('veziyyet'), 'eq.aktiv');
      const selected = query.get('id').slice(4, -1).split(',');
      assert.ok(selected.length <= 100);
      assert.ok(selected.every(id => byId.has(id)));
      const offset = Number(query.get('offset'));
      return selected.map(id => byId.get(id)).slice(offset, offset + 100);
    },
  });
  assert.equal(await context.caFetchFavoriteListings(), true);
  assert.equal(context.caFavoriteCars.length, 205);
  assert.equal(new Set(context.caFavoriteCars.map(row => row._id)).size, 205);
  assert.ok(calls.length >= 3);
  assert.equal(context.caPrivateState.favoritesLoaded, true);
  assert.equal(context.caPrivateState.favoritesLoading, false);
});

test('a later failed owner batch cannot replace cached listings with an incomplete first batch', async () => {
  const original = { id: fixtureId(9999), _id: fixtureId(9999), veziyyet: 'gozlemede' };
  const { context } = listingHarness({
    respond: async call => {
      const query = assertScopedRead(call);
      if (query.get('offset') === '0') return listingRows(100);
      throw new Error('Fixture second batch failure');
    },
    globals: { caOwnCars: [original] },
  });
  context.caRememberListings([original]);
  assert.equal(await context.caFetchMyListings(), false);
  assert.deepEqual(plain(context.caOwnCars).map(row => row._id), [original._id]);
  assert.deepEqual(plain(context.caRemoteCars).map(row => row._id), [original._id]);
  assert.equal(context.caPrivateState.ownError, true);
  assert.equal(context.caPrivateState.ownLoading, false);
});

test('private listing loaders do not request data without a signed-in user', async () => {
  const { context, calls } = listingHarness({ globals: { currentUser: null } });
  assert.equal(await context.caFetchMyListings(), false);
  assert.equal(await context.caFetchFavoriteListings(), false);
  assert.deepEqual(calls, []);
});

test('logging out prunes private cache entries and ignores a previously started private response', async () => {
  let resolveResponse;
  const publicCar = { id: fixtureId(1), _id: fixtureId(1), veziyyet: 'aktiv' };
  const ownCar = { id: fixtureId(2), _id: fixtureId(2), veziyyet: 'gozlemede' };
  const favoriteCar = { id: fixtureId(3), _id: fixtureId(3), veziyyet: 'aktiv' };
  const { context } = listingHarness({
    respond: () => new Promise(resolve => { resolveResponse = resolve; }),
    globals: { caPageCars: [publicCar], caOwnCars: [ownCar], caFavoriteCars: [favoriteCar] },
  });
  context.caRememberListings([publicCar, ownCar, favoriteCar]);
  const pending = context.caFetchMyListings();
  await nextTurn();
  context.currentUser = null;
  context.caClearPrivateListings();
  resolveResponse([ownCar]);
  assert.equal(await pending, false);
  assert.deepEqual(plain(context.caOwnCars), []);
  assert.deepEqual(plain(context.caFavoriteCars), []);
  assert.deepEqual(plain(context.caRemoteCars).map(row => row._id), [publicCar._id]);
  assert.equal(context.caListingCache.has(ownCar._id), false);
  assert.equal(context.caListingCache.has(favoriteCar._id), false);
  assert.equal(context.caPrivateState.ownLoading, false);
});

test('metadata payloads preserve the original authoritative image order without persisting the helper field', () => {
  const { caListingPayload } = payloadContext();
  const [front, rear, unknown] = photoUrls(3);
  const original = { photos: { front: [front], rear: [rear], other: [unknown, front] },
    _photoOrder: [rear, unknown, front, front], mileage: '' };
  const snapshot = JSON.stringify(original);
  const payload = caListingPayload(original);
  assert.deepEqual(plain(payload.sekiller), original._photoOrder);
  assert.notEqual(payload.sekiller, original._photoOrder);
  assert.equal(Object.hasOwn(payload.ca_data, '_photoOrder'), false);
  assert.deepEqual(plain(payload.ca_data.photos), original.photos);
  assert.equal(JSON.stringify(original), snapshot);
});

test('a late failure from an old request cannot turn a successfully loaded newer page into an error', async () => {
  const pending = [];
  const { context } = listingHarness({
    respond: () => new Promise((resolve, reject) => pending.push({ resolve, reject })),
  });
  const first = context.caFetchListings(1);
  await nextTurn();
  const second = context.caFetchListings(2);
  await nextTurn();
  pending[1].resolve(browseReply({ page: 2, total: 25, items: listingRows(1, 24) }));
  assert.equal(await second, true);
  pending[0].reject(new Error('Fixture late old request failure'));
  assert.equal(await first, false);
  assert.equal(context.caBrowseState.page, 2);
  assert.equal(context.caBrowseState.error, false);
  assert.equal(context.caBrowseState.loading, false);
  assert.equal(context.caListingsError, false);
  assert.deepEqual(plain(context.caPageCars).map(row => row._id), [fixtureId(24)]);
});

function deferred() {
  let resolve, reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}

test('mutations cannot change accounts while waiting for an authentication token', async () => {
  for (const operation of ['edit', 'insert', 'archive']) {
    const token = deferred();
    const { context, calls } = mutationHarness([{ id: 'fixture-listing' }], token.promise);
    const pending = operation === 'archive'
      ? context.caDeleteRemoteCar('fixture-listing')
      : context.caSaveRemoteCar({ make: 'Fixture' }, operation === 'edit');
    context.currentUser = { id: 'another-owner', phone: '+994000000001' };
    token.resolve('fixture-token');
    await assert.rejects(pending, undefined, `${operation} must reject an account switch`);
    assert.deepEqual(calls, [], 'No request may target the newly selected account');
  }
});

test('an edit target or submission epoch change during a token wait cannot mutate the new draft', async () => {
  for (const changed of ['target', 'submission']) {
    const token = deferred();
    const { context, calls } = mutationHarness([{ id: 'fixture-listing' }], token.promise);
    context.caListingSubmissionSequence = 4;
    const pending = context.caSaveRemoteCar({ make: 'Fixture' }, true, 'fixture-owner', 'fixture-listing', 4);
    if (changed === 'target') context.editingCarId = 'another-listing';
    else context.caListingSubmissionSequence = 5;
    token.resolve('fixture-token');
    await assert.rejects(pending);
    assert.deepEqual(calls, []);
    assert.equal(context.editingCarId, changed === 'target' ? 'another-listing' : 'fixture-listing');
    assert.equal(context.caListingSubmissionSequence, changed === 'submission' ? 5 : 4);
  }
});

test('confirmed archiving invalidates older owner and favorite reads so they cannot resurrect the listing', async () => {
  const ownerResponse = deferred(), favoriteResponse = deferred();
  const car = { id: fixtureId(70), _id: fixtureId(70), ownerId: 'fixture-owner', veziyyet: 'aktiv' };
  const alerts = [];
  const { context, calls } = listingHarness({
    globals: {
      caOwnCars: [car], caFavoriteCars: [car], userCars: [car],
      favoriteKeys: () => [car.id], confirm: () => true,
      saveUserCars() {}, alert: message => alerts.push(message),
    },
    respond: async call => {
      if (call.method === 'PATCH') {
        assert.deepEqual(call.body, { veziyyet: 'silindi' });
        return [{ id: car.id }];
      }
      if (call.method === 'POST') return browseReply({ total: 0, items: [], page: 1 });
      const query = new URL(call.pathname, 'https://fixture.invalid').searchParams;
      return query.has('satici_id') ? ownerResponse.promise : favoriteResponse.promise;
    },
  });
  for (const name of ['myCars', 'caRequireAffectedRow', 'caDeleteRemoteCar', 'deleteCar']) productionFunction(context, name);
  context.caRememberListings([car]);
  const ownerRead = context.caFetchMyListings();
  const favoriteRead = context.caFetchFavoriteListings();
  await nextTurn();
  assert.equal(context.caPrivateState.ownLoading, true);
  assert.equal(context.caPrivateState.favoritesLoading, true);
  await context.deleteCar(car.id);
  assert.equal(calls.filter(call => call.method === 'PATCH').length, 1);
  ownerResponse.resolve([car]);
  favoriteResponse.resolve([car]);
  assert.deepEqual(await Promise.all([ownerRead, favoriteRead]), [false, false]);
  assert.deepEqual(plain(context.caOwnCars), []);
  assert.deepEqual(plain(context.caFavoriteCars), []);
  assert.deepEqual(plain(context.caRemoteCars), []);
  assert.equal(context.caListingCache.has(car.id), false);
  assert.equal(context.caPrivateState.ownLoading, false);
  assert.equal(context.caPrivateState.favoritesLoading, false);
  assert.deepEqual(alerts, []);
});

function refreshHarness() {
  const requests = [], persisted = [], removed = [];
  let clears = 0, updates = 0;
  let context;
  context = production(['caRefresh'], {
    caSession: { refresh_token: 'refresh-A', user: { id: 'fixture-A' } },
    currentUser: { id: 'fixture-A' }, caRefreshPromise: null,
    CA_SESSION_KEY: 'fixture-session',
    caRequest: (pathname, method, body) => {
      const pending = deferred();
      requests.push({ pathname, method, body: plain(body), pending });
      return pending.promise;
    },
    caPersistSession: async session => {
      persisted.push(plain(session));
      context.caSession = session;
      context.currentUser = { id: session.user.id };
    },
    caClearPrivateListings: () => { clears++; },
    updateAccountUI: () => { updates++; },
    localStorage: { removeItem: key => removed.push(key) },
  });
  return { context, requests, persisted, removed, get clears() { return clears; }, get updates() { return updates; } };
}

test('concurrent refresh calls share one server request and persist the refreshed session once', async () => {
  const h = refreshHarness();
  const first = h.context.caRefresh(), second = h.context.caRefresh();
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].pathname, '/auth/v1/token?grant_type=refresh_token');
  assert.equal(h.requests[0].method, 'POST');
  assert.deepEqual(h.requests[0].body, { refresh_token: 'refresh-A' });
  h.requests[0].pending.resolve({ refresh_token: 'refresh-A2', user: { id: 'fixture-A' } });
  assert.deepEqual(await Promise.all([first, second]), [true, true]);
  assert.equal(h.persisted.length, 1);
  assert.equal(h.context.caSession.refresh_token, 'refresh-A2');
  assert.equal(h.context.caRefreshPromise, null);
  assert.equal(h.clears, 0);
  assert.deepEqual(h.removed, []);
});

test('a stale refresh success cannot restore the old account or clear the new account refresh in progress', async () => {
  const h = refreshHarness();
  const old = h.context.caRefresh();
  h.context.caSession = { refresh_token: 'refresh-B', user: { id: 'fixture-B' } };
  h.context.currentUser = { id: 'fixture-B' };
  const current = h.context.caRefresh();
  assert.equal(h.requests.length, 2);
  h.requests[0].pending.resolve({ refresh_token: 'refresh-A2', user: { id: 'fixture-A' } });
  assert.equal(await old, false);
  assert.equal(h.context.caSession.refresh_token, 'refresh-B');
  assert.equal(h.context.currentUser.id, 'fixture-B');
  assert.equal(h.context.caRefreshPromise.token, 'refresh-B');
  assert.deepEqual(h.persisted, []);
  h.requests[1].pending.resolve({ refresh_token: 'refresh-B2', user: { id: 'fixture-B' } });
  assert.equal(await current, true);
  assert.equal(h.context.caSession.refresh_token, 'refresh-B2');
  assert.equal(h.persisted.length, 1);
  assert.equal(h.persisted[0].user.id, 'fixture-B');
  assert.equal(h.clears, 0);
  assert.deepEqual(h.removed, []);
});

test('a stale refresh failure cannot sign out or remove the newer account session', async () => {
  const h = refreshHarness();
  const old = h.context.caRefresh();
  const currentSession = { refresh_token: 'refresh-B', user: { id: 'fixture-B' } };
  h.context.caSession = currentSession;
  h.context.currentUser = { id: 'fixture-B' };
  h.requests[0].pending.reject(new Error('Fixture expired old token'));
  assert.equal(await old, false);
  assert.equal(h.context.caSession, currentSession);
  assert.equal(h.context.currentUser.id, 'fixture-B');
  assert.deepEqual(h.persisted, []);
  assert.deepEqual(h.removed, []);
  assert.equal(h.clears, 0);
  assert.equal(h.updates, 0);
});
