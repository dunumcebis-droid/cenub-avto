'use strict';
// Offline fixtures only. Every client call injects fetch; no provider is contacted.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const load = import('../supabase/functions/_shared/epoint-protocol.mjs');
const KEY = 'offline-fixture-key', PUBLIC = 'i_fixture_merchant';
const BANK = 'https://bank.fixture.invalid';
const EXPECTED = Object.freeze({orderId:'order-fixture-1',transaction:'te_fixture_1',amountMinor:100,currency:'AZN'});
const PAYMENT = Object.freeze({orderId:EXPECTED.orderId,amountMinor:100,currency:'AZN',language:'az',
  successUrl:'https://merchant.fixture.invalid/payment.html?result=success',
  errorUrl:'https://merchant.fixture.invalid/payment.html?result=error',description:'AvtoUnvan — Təcili'});
const CALLBACK = Object.freeze({order_id:EXPECTED.orderId,transaction:EXPECTED.transaction,status:'success',
  operation_code:'100',amount:'1.00',code:'000',card_name:'fixture-private-cardholder',
  card_mask:'111111******1234',bank_response:'fixture-private-bank-response',other_attr:{private:'fixture-private-attribute'}});
const encode = value => Buffer.from(typeof value === 'string' ? value : JSON.stringify(value),'utf8').toString('base64');
const sign = (data, key = KEY) => createHash('sha1').update(key + data + key,'utf8').digest('base64');
const reply = value => new Response(JSON.stringify(value), {headers:{'content-type':'application/json'}});
const success = () => reply({status:'success',transaction:EXPECTED.transaction,redirect_url:BANK+'/pay?session=fixture'});
async function fixture(fetchImpl = async () => success(), config = {}) {
  const calls=[], api=await load;
  const client=api.createEpointClient({publicKey:PUBLIC,privateKey:KEY,allowedRedirectOrigins:[BANK],
    fetchImpl:async (url, options) => { calls.push({url,options}); return fetchImpl(url, options); },...config});
  return {api,client,calls};
}
function safeError(error) {
  assert.equal(error.name,'EpointProtocolError');
  assert.doesNotMatch(String(error)+JSON.stringify(error),/offline-fixture-key|fixture-private|111111\*{6}1234/);
  return true;
}
async function rejection(promise, code, ambiguous) {
  await assert.rejects(promise, error => {
    safeError(error); if(code)assert.equal(error.code,code);
    if(ambiguous!==undefined)assert.equal(error.ambiguousCreate,ambiguous);
    return true;
  });
}

test('construction and import perform no fetch; no implicit bank origins are supplied',async () => {
  const f=await fixture();assert.deepEqual(f.calls,[]);
  const empty=await fixture(undefined,{allowedRedirectOrigins:[]});
  await rejection(empty.client.createPayment(PAYMENT),'epoint_redirect_origins_required',false);
  assert.equal(empty.calls.length,0);
});

test('raw SHA1/Base64 signature matches an independent pinned vector and Unicode bytes',async () => {
  const {signEpointData}=await load;
  const data='eyJvcmRlcl9pZCI6Im9yZGVyLWZpeHR1cmUtMSIsInN0YXR1cyI6InN1Y2Nlc3MiLCJ0cmFuc2FjdGlvbiI6InRlX2ZpeHR1cmVfMSIsIm9wZXJhdGlvbl9jb2RlIjoiMTAwIiwiYW1vdW50IjoiMS4wMCJ9';
  assert.equal(await signEpointData(data,KEY),'XHL84tQAJ4fSy8QoHTCOH2yyc5A=');
  const unicode=encode({...CALLBACK,note:'AvtoÜnvan — Azərbaycan 🚘'});
  assert.equal(await signEpointData(unicode,KEY),sign(unicode));
  assert.notEqual(await signEpointData(unicode,KEY),createHash('sha1').update(KEY+unicode+KEY).digest('hex'));
});

test('checkout uses fixed endpoint, numeric exact amount, URL-encoded signature and no browser credentials',async () => {
  const f=await fixture();const result=await f.client.createPayment(PAYMENT);
  assert.deepEqual(result,{transaction:EXPECTED.transaction,redirectUrl:BANK+'/pay?session=fixture'});
  assert.ok(Object.isFrozen(result));assert.equal(f.calls.length,1);
  const {url,options}=f.calls[0], form=new URLSearchParams(options.body);
  assert.equal(url,'https://epoint.az/api/1/request');assert.equal(options.method,'POST');
  assert.equal(options.redirect,'error');assert.equal(options.credentials,'omit');
  assert.equal(options.referrerPolicy,'no-referrer');
  assert.equal(options.headers['Content-Type'],'application/x-www-form-urlencoded');
  assert.deepEqual([...form.keys()],['data','signature']);assert.equal(form.get('signature'),sign(form.get('data')));
  const payload=JSON.parse(Buffer.from(form.get('data'),'base64').toString('utf8'));
  assert.equal(payload.amount,1);assert.equal(typeof payload.amount,'number');
  assert.equal(payload.public_key,PUBLIC);assert.equal(payload.currency,'AZN');assert.equal(payload.is_installment,0);
  assert.equal(payload.order_id,PAYMENT.orderId);assert.equal(payload.description,PAYMENT.description);
  assert.equal(payload.success_redirect_url,PAYMENT.successUrl);assert.equal(payload.error_redirect_url,PAYMENT.errorUrl);
  assert.doesNotMatch(options.body,/offline-fixture-key/);
});

test('qepik validation rejects invalid/unrepresentable amounts before any request and preserves 0.29 exactly',async () => {
  for(const amountMinor of [0,-1,0.1,1.5,'100',NaN,Infinity,Number.MAX_SAFE_INTEGER+1,Number.MAX_SAFE_INTEGER]) {
    const f=await fixture();await rejection(f.client.createPayment({...PAYMENT,amountMinor}),'epoint_invalid_amount',false);
    assert.equal(f.calls.length,0);
  }
  const f=await fixture();await f.client.createPayment({...PAYMENT,amountMinor:29});
  const p=JSON.parse(Buffer.from(new URLSearchParams(f.calls[0].options.body).get('data'),'base64').toString());
  assert.equal(p.amount,0.29);
});

test('input/currency/return origin checks and unsafe configured origins fail before network',async () => {
  for(const patch of [{currency:'USD'},{language:'xx'},{description:'x'.repeat(1001)},{orderId:'bad\norder'},
    {successUrl:'http://merchant.fixture.invalid/success'},{successUrl:PAYMENT.successUrl+'#'},
    {successUrl:'https://@merchant.fixture.invalid/success'},{errorUrl:'https://different.fixture.invalid/error'}]) {
    const f=await fixture();await rejection(f.client.createPayment({...PAYMENT,...patch}),undefined,false);assert.equal(f.calls.length,0);
  }
  const {createEpointClient}=await load;
  for(const origin of ['http://bank.fixture.invalid','https://127.0.0.1','https://[::1]',
    'https://localhost','https://bank.local','https://bank.internal','https://bank.fixture.invalid/#',
    'https://bank.fixture.invalid/?','https://@bank.fixture.invalid','https://bank.fixture.invalid/path','https://*.fixture.invalid']) {
    assert.throws(()=>createEpointClient({publicKey:PUBLIC,privateKey:KEY,allowedRedirectOrigins:[origin],fetchImpl:()=>assert.fail('network')}),safeError);
  }
});

test('only exact configured public HTTPS redirect origins pass; denial remains an ambiguous creation',async () => {
  for(const url of ['http://bank.fixture.invalid/pay','https://bank.fixture.invalid.evil.invalid/pay',
    'https://user:password@bank.fixture.invalid/pay','https://@bank.fixture.invalid/pay',
    BANK+'/pay#',BANK+'/pay#fragment','https://127.0.0.1/pay','https://2130706433/pay','https://[::1]/pay',
    'https://host.local/pay','https://another.fixture.invalid/pay',BANK+':8443/pay']) {
    const f=await fixture(async()=>reply({status:'success',transaction:EXPECTED.transaction,redirect_url:url}));
    await assert.rejects(f.client.createPayment(PAYMENT),error=>{
      safeError(error);assert.equal(error.code,'epoint_create_ambiguous');assert.equal(error.ambiguousCreate,true);
      assert.equal(error.safeTransaction,EXPECTED.transaction);return true;
    });
    assert.equal(f.calls.length,1);
  }
});

test('transport, HTTP, malformed and oversized create responses remain ambiguous and are never retried',async () => {
  const cases=[async()=>{throw Error('fixture-private-network-detail')},
    async()=>new Response('fixture-private-http-detail',{status:503}),
    async()=>new Response('fixture-private-redirect-detail',{status:302,headers:{location:'https://private.invalid'}}),
    async()=>new Response('fixture-private-malformed-json'),
    async()=>new Response('x'.repeat(16385)),
    async()=>reply({status:'unexpected',message:'fixture-private-api-detail'}),
    async()=>new Response('{"status":"success","status":"error"}'),
    async()=>new Response(new Uint8Array([255])),
  ];
  for(const fetchImpl of cases) {
    const f=await fixture(fetchImpl);await rejection(f.client.createPayment(PAYMENT),'epoint_create_ambiguous',true);assert.equal(f.calls.length,1);
  }
  const explicit=await fixture(async()=>reply({status:'error',message:'fixture-private-rejection'}));
  await rejection(explicit.client.createPayment(PAYMENT),'epoint_create_rejected',false);assert.equal(explicit.calls.length,1);
});

test('creation timeout bounds even a stalled injected fetch without an automatic retry',async () => {
  const f=await fixture(async()=>new Promise(()=>{}),{timeoutMs:10});
  await rejection(f.client.createPayment(PAYMENT),'epoint_create_ambiguous',true);assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].options.signal.aborted,true);
});

test('callback verifies original noncanonical JSON whitespace/order before decoding and returns no card data',async () => {
  const {decodeVerifiedEpointCallback,verifyEpointCallback}=await load;
  const text=' { "amount" : "1.00", "operation_code":"100", "transaction":"te_fixture_1", "order_id":"order-fixture-1", "status":"success", "note":"Ünvan 🚘", "card_name":"fixture-private-cardholder", "card_mask":"111111******1234" } ';
  const data=encode(text), signature=sign(data), observed=await decodeVerifiedEpointCallback(data,signature,KEY);
  assert.deepEqual(observed,{status:'success',transaction:EXPECTED.transaction,operation_code:'100',amount:'1.00',order_id:EXPECTED.orderId});
  assert.equal(Object.hasOwn(observed,'paid'),false);assert.ok(Object.isFrozen(observed));
  const bound=await verifyEpointCallback(data,signature,KEY,EXPECTED);
  assert.deepEqual(bound,{...EXPECTED,status:'success',state:'paid',paid:true,currencyReported:false});assert.ok(Object.isFrozen(bound));
  assert.doesNotMatch(JSON.stringify({observed,bound}),/fixture-private|card_name|card_mask|bank_response|other_attr/);
});

test('tamper, wrong key and malformed signatures fail before parsing a signed JSON body',async () => {
  const {decodeVerifiedEpointCallback}=await load;
  const data=encode('fixture-private-not-json');
  await rejection(decodeVerifiedEpointCallback(data,sign(data,'wrong-key'),KEY),'epoint_signature_mismatch');
  const good=encode(CALLBACK);await rejection(decodeVerifiedEpointCallback(good,sign(good),KEY+'-changed'),'epoint_signature_mismatch');
  await rejection(decodeVerifiedEpointCallback(good.slice(0,-2)+'AA',sign(good),KEY),'epoint_signature_mismatch');
  for(const signature of ['','not-base64',sign(good)+'\n',Buffer.alloc(19).toString('base64'),Buffer.alloc(21).toString('base64')]) {
    await rejection(decodeVerifiedEpointCallback(good,signature,KEY));
  }
});

test('authenticated malformed JSON/Base64/UTF8, duplicate keys and excessive depth or size are rejected',async () => {
  const {decodeVerifiedEpointCallback}=await load;
  const textCases=['{','[]','null','true','{"status":"success","status":"failed"}',
    '{"status":"success","sta\\u0074us":"failed"}',
    JSON.stringify({...CALLBACK,other_attr:{nested:1}}).replace('"nested":1','"nested":1,"nested":2'),
    JSON.stringify({...CALLBACK,other_attr:JSON.parse('['.repeat(33)+'0'+']'.repeat(33))})];
  for(const text of textCases){const data=encode(text);await rejection(decodeVerifiedEpointCallback(data,sign(data),KEY));}
  for(const data of [Buffer.from([255]).toString('base64'),'YWJjZA=','YWJjZA===','YWJjZA==\n','Zh==']) {
    // Sign only after forming the malformed sample, so validation reaches decoding.
    await rejection(decodeVerifiedEpointCallback(data,sign(data),KEY));
  }
  const large=encode(' '.repeat(16385));await rejection(decodeVerifiedEpointCallback(large,sign(large),KEY));
  const huge='A'.repeat(22000);await rejection(decodeVerifiedEpointCallback(huge,sign(huge),KEY),'epoint_invalid_data');
});

test('callback saved-order/transaction/amount/currency/operation mismatches never become paid',async () => {
  const {verifyEpointCallback}=await load;
  const patches=[{order_id:'different-order'},{transaction:'te_other'},{amount:'0.99'},{amount:'1.01'},
    {amount:'-1.00'},{amount:'1.001'},{amount:'1e0'},{amount:null},{currency:'USD'},
    {currency:null},{operation_code:'001'},{operation_code:100},{status:'SUCCESS'}];
  for(const patch of patches){const data=encode({...CALLBACK,...patch});await rejection(verifyEpointCallback(data,sign(data),KEY,EXPECTED));}
  const missing={...CALLBACK};delete missing.order_id;const data=encode(missing);
  await rejection(verifyEpointCallback(data,sign(data),KEY,EXPECTED),'epoint_missing_order');
});

test('pending, failed, refund and unknown are explicit nonpaid observations; repeated signed receipts do not imply settlement',async () => {
  const {verifyEpointCallback}=await load;
  for(const [status,state] of [['new','pending'],['failed','failed'],['error','failed'],['returned','refunded'],['server_error','unknown']]) {
    const data=encode({...CALLBACK,status,currency:'AZN'}), result=await verifyEpointCallback(data,sign(data),KEY,EXPECTED);
    assert.equal(result.state,state);assert.equal(result.paid,false);assert.equal(result.currencyReported,true);
  }
  const data=encode(CALLBACK), a=await verifyEpointCallback(data,sign(data),KEY,EXPECTED), b=await verifyEpointCallback(data,sign(data),KEY,EXPECTED);
  assert.deepEqual(a,b); // A future atomic ledger, not this stateless adapter, prevents duplicate grants.
});

test('status uses signed transaction-only lookup and returns no paid flag, PII, or undocumented order/currency claim',async () => {
  const f=await fixture(async()=>reply(CALLBACK));const observed=await f.client.getStatus(EXPECTED.transaction);
  const call=f.calls[0],form=new URLSearchParams(call.options.body);
  assert.equal(call.url,'https://epoint.az/api/1/get-status');assert.equal(f.calls.length,1);
  assert.deepEqual(JSON.parse(Buffer.from(form.get('data'),'base64').toString()),{public_key:PUBLIC,transaction:EXPECTED.transaction});
  assert.equal(form.get('signature'),sign(form.get('data')));assert.equal(Object.hasOwn(observed,'paid'),false);
  assert.doesNotMatch(JSON.stringify(observed),/fixture-private|card_name|card_mask|other_attr|bank_response/);
  const bound=f.api.validateEpointObservation(observed,EXPECTED,{source:'status'});assert.equal(bound.paid,true);
  assert.equal(bound.currencyReported,false);
});

test('status snapshots can omit order ID/currency but contradicting fields and amounts are rejected',async () => {
  const {validateEpointObservation}=await load;
  const raw={...CALLBACK};delete raw.order_id;
  assert.equal(validateEpointObservation(raw,EXPECTED,{source:'status'}).paid,true);
  for(const patch of [{order_id:'other-order'},{transaction:'te_other'},{amount:0.99},{currency:'EUR'},{operation_code:'001'}]) {
    assert.throws(()=>validateEpointObservation({...raw,...patch},EXPECTED,{source:'status'}),safeError);
  }
  const f=await fixture(async()=>reply({...raw,transaction:'te_other'}));
  await rejection(f.client.getStatus(EXPECTED.transaction),'epoint_transaction_mismatch',false);assert.equal(f.calls.length,1);
});

test('status transport/parse/timeouts are safe failures and never classify a lookup error as paid or retry',async () => {
  for(const fetchImpl of [async()=>{throw Error('fixture-private-network')},async()=>new Response('fixture-private-invalid-json'),async()=>new Response('',{status:503})]) {
    const f=await fixture(fetchImpl);await rejection(f.client.getStatus(EXPECTED.transaction),undefined,false);assert.equal(f.calls.length,1);
  }
  const f=await fixture(async()=>new Promise(()=>{}),{timeoutMs:10});
  await rejection(f.client.getStatus(EXPECTED.transaction),'epoint_timeout',false);assert.equal(f.calls.length,1);
});

test('response streaming is bounded and cancellation happens before reading unbounded provider data',async () => {
  let cancelled=false;
  const f=await fixture(async()=>new Response(new ReadableStream({
    start(controller){controller.enqueue(new Uint8Array(16385));},cancel(){cancelled=true;},
  })));
  await rejection(f.client.createPayment(PAYMENT),'epoint_create_ambiguous',true);assert.equal(cancelled,true);assert.equal(f.calls.length,1);
  const length=await fixture(async()=>new Response('fixture-private-length',{headers:{'content-length':'999999'}}));
  await rejection(length.client.getStatus(EXPECTED.transaction),'epoint_response_too_large',false);assert.equal(length.calls.length,1);
});
