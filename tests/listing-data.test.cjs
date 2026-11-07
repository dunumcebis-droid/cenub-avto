const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');

const source = require('./source-loader.cjs').loadPageSource().source;
const context = vm.createContext({ console });

// Execute the actual production functions, without the page's network requests,
// authentication setup, browser storage or DOM initialization.
function productionFunction(name) {
  const start = source.search(new RegExp(`(?:async\\s+)?function ${name}\\s*\\(`));
  assert.notEqual(start, -1, `Production function ${name} must exist`);
  for (let end = source.indexOf('}', start); end !== -1; end = source.indexOf('}', end + 1)) {
    const candidate = source.slice(start, end + 1);
    try {
      new vm.Script(`(${candidate})`);
    } catch {
      continue;
    }
    vm.runInContext(candidate, context);
    return context[name];
  }
  throw new Error(`Cannot extract production function ${name}`);
}

const helperNames = [
  'caValue', 'caNumber', 'caFormatNumber', 'caFormatPrice',
  'caFormatMileage', 'caCarName', 'caEffectivePackage', 'caStoredPhotoGroups', 'caRemoteToCar',
  'caComparePackages', 'caComparePrices', 'caNum',
];
const rankDeclaration = source.match(/const caPackageRank\s*=\s*\{[^;]+\};/);
assert.ok(rankDeclaration, 'Production package ranking must exist');
vm.runInContext(rankDeclaration[0], context);
const helpers = Object.fromEntries(helperNames.map(name => [name, productionFunction(name)]));
const { caValue, caNumber, caFormatPrice, caFormatMileage, caCarName, caRemoteToCar, caEffectivePackage, caComparePrices, caNum } = helpers;
const plain = value => JSON.parse(JSON.stringify(value));
const grouped = value => Number(value).toLocaleString('az-AZ');

test('missing values are distinct from a legitimate numeric zero', () => {
  assert.equal(caValue(undefined, null, '', '  ', 0, 19), 0);
  assert.equal(caValue(undefined, '', 'Toyota'), 'Toyota');
  for (const value of [undefined, null, '', '  ', 'naməlum', NaN, Infinity, -1, '-15']) {
    assert.equal(caNumber(value), null, `Invalid numeric value: ${String(value)}`);
  }
  assert.equal(caNumber(0), 0);
  assert.equal(caNumber('0'), 0);
});

test('numeric data supports stored grouped amounts and engine descriptions', () => {
  for (const [input, expected] of [
    [25500, 25500], [1.598, 1.598], ['25 500', 25500], ['25\u00a0500', 25500],
    ['25.500', 25500], ['25.500,50', 25500.5],
    ['120 000 km', 120000], ['2,0 L benzin', 2], ['2.0 L benzin', 2],
  ]) assert.equal(caNumber(input), expected, input);
});

test('price and mileage formatting never invent zero or lose zero mileage', () => {
  for (const empty of [undefined, null, '', 'naməlum']) {
    assert.equal(caFormatPrice(empty), 'Qiymət qeyd edilməyib');
    assert.equal(caFormatMileage(empty), 'Yürüş qeyd edilməyib');
  }
  assert.equal(caFormatPrice(0), '0 ₼');
  assert.equal(caFormatPrice('25 500'), `${grouped(25500)} ₼`);
  assert.equal(caFormatMileage(0), '0 km');
  assert.equal(caFormatMileage('0'), '0 km');
  assert.equal(caFormatMileage(120000), `${grouped(120000)} km`);
  assert.equal(caFormatMileage('120 000 km'), `${grouped(120000)} km`);
});

test('price sorting puts missing values last in both directions while keeping package priority', () => {
  const cars = [
    { _id: 'unknown', pack: 'Pulsuz', price: null },
    { _id: 'expensive', pack: 'Pulsuz', price: 25000 },
    { _id: 'zero', pack: 'Pulsuz', price: 0 },
    { _id: 'vip', pack: 'VIP', price: 50000 },
    { _id: 'cheap', pack: 'Pulsuz', price: 5000 },
  ];
  assert.deepEqual(cars.slice().sort((a, b) => caComparePrices(a, b, 1)).map(c => c._id),
    ['vip', 'zero', 'cheap', 'expensive', 'unknown']);
  assert.deepEqual(cars.slice().sort((a, b) => caComparePrices(a, b, -1)).map(c => c._id),
    ['vip', 'expensive', 'cheap', 'zero', 'unknown']);
});

test('numeric search input distinguishes an empty bound from an explicit zero bound', () => {
  for (const [input, expected] of [['', null], ['  ', null], ['0', 0], ['120000', 120000], ['2,0', 2]]) {
    context.caVal = () => input;
    assert.equal(caNum('test-field'), expected, `Search input ${JSON.stringify(input)}`);
  }
});

test('listing names use supplied make/model and explicit missing-name text', () => {
  assert.equal(caCarName({ make: 'Toyota', model: 'Camry' }), 'Toyota Camry');
  assert.equal(caCarName({ make: '  Toyota ', model: ' Camry ' }), 'Toyota Camry');
  assert.equal(caCarName({}), 'Marka və model qeyd edilməyib');
});

test('database columns take priority over the seller form snapshot', () => {
  const car = caRemoteToCar({
    id: 'db-1', marka: 'Toyota', model: 'Camry', il: 2020, qiymet: 25500,
    yurus: 0, seher: 'Bakı', yanacaq: 'Hibrid', suretler_qutusu: 'Avtomat',
    ban_novu: 'Sedan', muherrik_hecmi: 2.5, at_gucu: 218, reng: 'Ağ',
    bazar_ucun: 'Avropa', neqliyyat_novu: 'Minik', nesil: 'XV70',
    oturacaq_sayi: 5, techizat: ['ABS', 'Kondisioner'],
    tesvir: 'Database description', telefon: '+994501234567',
    satici_id: 'seller-1', veziyyet: 'aktiv',
    ca_data: { make: 'BMW', model: '530', year: 2017, price: 42000, mileage: 99000, city: 'Masallı' },
  });
  assert.equal(car._id, 'db-1');
  assert.equal(car.make, 'Toyota');
  assert.equal(car.model, 'Camry');
  assert.equal(car.year, 2020);
  assert.equal(car.price, 25500);
  assert.equal(car.mileage, 0);
  assert.equal(car.city, 'Bakı');
  assert.equal(car.fuel, 'Hibrid');
  assert.equal(car.gear, 'Avtomat');
  assert.equal(car.body, 'Sedan');
  assert.equal(car.engine, 2.5);
  assert.equal(Number(car.horsepower), 218);
  assert.equal(car.color, 'Ağ');
  assert.equal(car.market, 'Avropa');
  assert.equal(car.vehicleType, 'Minik');
  assert.equal(car.generation, 'XV70');
  assert.equal(Number(car.seats), 5);
  assert.deepEqual(plain(car.equipment), ['ABS', 'Kondisioner']);
  assert.equal(car.description, 'Database description');
  assert.equal(car.phone, '+994501234567');
  assert.equal(car.ownerId, 'seller-1');
  assert.equal(car.veziyyet, 'aktiv');
});

test('an explicitly empty database equipment list does not resurrect old form selections', () => {
  const car = caRemoteToCar({ techizat: [], ca_data: { equipment: ['ABS'] } });
  assert.deepEqual(plain(car.equipment), []);
});

test('English form snapshots work both as objects and serialized JSON', () => {
  const data = {
    make: 'Hyundai', model: 'Elantra', year: '2019', price: '25 500',
    mileage: '94 000 km', city: 'Masallı', fuel: 'Benzin', gear: 'Avtomat',
    engine: '2,0 L benzin', generation: 'AD', vehicleType: 'Minik',
    seats: '5', equipment: ['ABS'],
  };
  for (const ca_data of [data, JSON.stringify(data)]) {
    const car = caRemoteToCar({ id: 'legacy-en', ca_data, veziyyet: 'aktiv' });
    assert.equal(car.make, 'Hyundai');
    assert.equal(car.model, 'Elantra');
    assert.equal(car.year, 2019);
    assert.equal(car.price, 25500);
    assert.equal(car.mileage, 94000);
    assert.equal(car.city, 'Masallı');
    assert.equal(car.generation, 'AD');
    assert.equal(car.vehicleType, 'Minik');
    assert.equal(Number(car.seats), 5);
    assert.deepEqual(plain(car.equipment), ['ABS']);
  }
});

test('Azerbaijani legacy snapshots retain listing and technical fields', () => {
  const car = caRemoteToCar({
    id: 'legacy-az', veziyyet: 'aktiv',
    ca_data: {
      marka: 'Kia', model: 'Rio', il: 2019, qiymet: '24.000', yurus: '60 000 km',
      seher: 'Lənkəran', yanacaq: 'Benzin', suretler_qutusu: 'Avtomat',
      ban_novu: 'Sedan', muherrik_hecmi: 1.6, at_gucu: 123,
      reng: 'Qara', bazar_ucun: 'Avropa', neqliyyat_novu: 'Minik',
      nesil: 'FB', oturacaq_sayi: 5, techizat: ['ABS'],
      tesvir: 'Saxlanılan açıqlama', telefon: '+994551234567',
    },
  });
  assert.equal(car.make, 'Kia');
  assert.equal(car.model, 'Rio');
  assert.equal(car.year, 2019);
  assert.equal(car.price, 24000);
  assert.equal(car.mileage, 60000);
  assert.equal(car.city, 'Lənkəran');
  assert.equal(car.fuel, 'Benzin');
  assert.equal(car.gear, 'Avtomat');
  assert.equal(car.body, 'Sedan');
  assert.equal(car.engine, 1.6);
  assert.equal(Number(car.horsepower), 123);
  assert.equal(car.color, 'Qara');
  assert.equal(car.market, 'Avropa');
  assert.equal(car.vehicleType, 'Minik');
  assert.equal(car.generation, 'FB');
  assert.equal(Number(car.seats), 5);
  assert.deepEqual(plain(car.equipment), ['ABS']);
  assert.equal(car.description, 'Saxlanılan açıqlama');
  assert.equal(car.phone, '+994551234567');
});

test('incomplete or malformed snapshots have null numeric values instead of invented data', () => {
  for (const ca_data of [undefined, null, '', '{broken JSON', [], 'null']) {
    const car = caRemoteToCar({ id: 'empty', ca_data, veziyyet: 'aktiv' });
    assert.equal(car.year, null);
    assert.equal(car.price, null);
    assert.equal(car.mileage, null);
    assert.equal(caCarName(car), 'Marka və model qeyd edilməyib');
  }
});

test('mapping preserves uploaded photo URLs and category lists', () => {
  const photos = {
    front: ['https://photos.example/front-1.jpg', 'https://photos.example/front-2.jpg'],
    interior: ['https://photos.example/interior.jpg'],
  };
  const original = JSON.stringify(photos);
  const car = caRemoteToCar({ id: 'photos', ca_data: { photos, photo: photos.front[0] } });
  assert.equal(JSON.stringify(photos), original, 'Source photos must not be mutated');
  assert.deepEqual(plain(car.photos), photos);
  assert.equal(car.photo, photos.front[0]);
  const urls = ['https://photos.example/a.jpg', 'https://photos.example/b.jpg'];
  const dbCar = caRemoteToCar({ id: 'db-photos', sekiller: urls });
  assert.equal(dbCar.photo, urls[0]);
  assert.deepEqual(plain(Object.values(dbCar.photos).flat()), urls);
  assert.deepEqual(plain(dbCar._photoOrder), urls);
  assert.notEqual(dbCar._photoOrder, urls, 'Original photo order must be copied, not mutated through the mapper');
});

test('VIP eligibility remains tied to approved, unexpired database packages', () => {
  const now = Date.now();
  const future = new Date(now + 86400000).toISOString();
  const past = new Date(now - 86400000).toISOString();
  const base = { paket_adi: 'VIP', veziyyet: 'aktiv', paket_bitir: future };
  assert.equal(caEffectivePackage(base), 'VIP');
  assert.equal(caEffectivePackage({ ...base, veziyyet: 'gozlemede' }), 'Pulsuz');
  assert.equal(caEffectivePackage({ ...base, paket_bitir: past }), 'Pulsuz');
  assert.equal(caEffectivePackage({ ...base, paket_adi: 'unknown' }), 'Pulsuz');
  assert.equal(caEffectivePackage({ veziyyet: 'aktiv', ca_data: { pack: 'VIP' } }), 'Pulsuz');
  assert.equal(caRemoteToCar({ ...base, ca_data: { pack: 'Pulsuz' } }).pack, 'VIP');
  assert.equal(caRemoteToCar({ veziyyet: 'aktiv', ca_data: { pack: 'VIP' } }).pack, 'Pulsuz');
  for (const [name, ageDays, expected] of [['Premium', 6, 'Pulsuz'], ['Standart', 4, 'Pulsuz'], ['VIP', 14, 'VIP']]) {
    const approved = new Date(now - ageDays * 86400000).toISOString();
    assert.equal(caEffectivePackage({ paket_adi: name, veziyyet: 'aktiv', paket_bitir: null, tesdiq_tarixi: approved }),
      expected, `${name} uses the canonical fallback term when no end date exists`);
  }
  for (const name of ['VIP', 'Premium', 'Standart']) {
    assert.equal(caEffectivePackage({ paket_adi: name, veziyyet: 'aktiv', paket_bitir: future,
      tesdiq_tarixi: new Date(now - 365 * 86400000).toISOString() }), name,
      'An explicit future database end date remains authoritative');
    assert.equal(caEffectivePackage({ paket_adi: name, veziyyet: 'aktiv', paket_bitir: past,
      tesdiq_tarixi: new Date(now - 86400000).toISOString() }), 'Pulsuz',
      'An explicit expired database end date remains authoritative');
  }
});

test('the reviewed listing projection includes the approval timestamp and excludes the internal note', () => {
  const declaration = source.match(/const CA_LISTING_COLUMNS\s*=\s*(['"])[^'"\n]+\1;/);
  assert.ok(declaration, 'The listing projection must be explicitly declared');
  const expected = [
    'id', 'satici_id', 'marka', 'model', 'il', 'qiymet', 'yurus', 'seher',
    'tesvir', 'veziyyet', 'yaradildi', 'neqliyyat_novu', 'nesil', 'ban_novu',
    'yanacaq', 'suretler_qutusu', 'muherrik_hecmi', 'at_gucu', 'reng',
    'bazar_ucun', 'oturacaq_sayi', 'techizat', 'sekiller', 'telefon', 'ca_data',
    'paket_adi', 'paket_baslayir', 'paket_bitir', 'tesdiq_tarixi',
  ];
  const requestContext = vm.createContext({});
  vm.runInContext(declaration[0], requestContext);
  const declared = vm.runInContext('CA_LISTING_COLUMNS', requestContext).split(',');
  assert.equal(new Set(declared).size, 29);
  assert.deepEqual(declared.slice().sort(), expected.slice().sort());
  assert.ok(!declared.includes('paket_tesdiq_qeydi'));
  assert.ok(!declared.includes('*'));
});
