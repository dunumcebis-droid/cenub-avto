/**
 * OFFLINE-PREPARED server-only Epoint protocol adapter. Importing performs no I/O.
 * Before calling createPayment, the caller MUST persist an owned, immutable price
 * snapshot and unique attempt/order ID, serialize competing creates, and retain
 * ambiguous attempts for reconciliation. This module is not a payment ledger,
 * settlement handler, browser endpoint, idempotency guarantee or activation flag.
 * Sources: Epoint API v1.0.3 and developer.epoint.az/{az/checkout/request,
 * az/status/get-status,en/callbacks}. Provider acknowledgement/retry behavior and
 * real bank redirect origins still require merchant confirmation before use.
 */
const LIMIT = 16 * 1024;
const ENCODED_LIMIT = Math.ceil(LIMIT / 3) * 4;
const encoder = new TextEncoder();
const decoder = () => new TextDecoder('utf-8', {fatal: true});
const has = (object, key) => Object.hasOwn(object, key);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

export class EpointProtocolError extends Error {
  constructor(code, {ambiguousCreate = false, safeTransaction} = {}) {
    super(code); this.name = 'EpointProtocolError'; this.code = code;
    this.ambiguousCreate = ambiguousCreate;
    if (safeTransaction) this.safeTransaction = safeTransaction;
  }
}
const fail = code => { throw new EpointProtocolError(code); };
function identifier(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}$/.test(value)) fail('epoint_invalid_identifier');
  return value;
}
function secret(value) {
  if (typeof value !== 'string' || !value.length || encoder.encode(value).length > 4096) fail('epoint_invalid_key');
  return value;
}
function minor(value, allowZero = false) {
  if (!Number.isSafeInteger(value) || value < (allowZero ? 0 : 1)) fail('epoint_invalid_amount');
  return value;
}
const decimal = value => `${BigInt(value) / 100n}.${String(BigInt(value) % 100n).padStart(2, '0')}`;
function readAmount(value) {
  if (!['string', 'number'].includes(typeof value) || !/^\d+(?:\.\d{1,2})?$/.test(String(value))) fail('epoint_invalid_amount');
  const [whole, fraction = ''] = String(value).split('.');
  const amount = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (amount > BigInt(Number.MAX_SAFE_INTEGER)) fail('epoint_invalid_amount');
  return minor(Number(amount), true);
}
function numericAmount(amountMinor) {
  const value = Number(decimal(amountMinor));
  if (readAmount(value) !== amountMinor) fail('epoint_invalid_amount');
  return value;
}
function base64(bytes) {
  let binary = ''; for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
function unbase64(value, maximum) {
  if (typeof value !== 'string' || !value.length || value.length > Math.ceil(maximum / 3) * 4 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) fail('epoint_invalid_base64');
  let binary; try { binary = atob(value); } catch { fail('epoint_invalid_base64'); }
  if (binary.length > maximum || btoa(binary) !== value) fail('epoint_invalid_base64');
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}
function encodedData(value) {
  if (typeof value !== 'string' || !value.length || value.length > ENCODED_LIMIT ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) fail('epoint_invalid_data');
  return value; // Never trim/re-encode the signed data.
}
export async function signEpointData(data, privateKey) {
  encodedData(data); secret(privateKey);
  const bytes = encoder.encode(privateKey + data + privateKey);
  try { return base64(new Uint8Array(await crypto.subtle.digest('SHA-1', bytes))); }
  catch { fail('epoint_crypto_failed'); }
}
function equalSignature(a, b) {
  let difference = 0; for (let i = 0; i < 20; i++) difference |= a[i] ^ b[i];
  return difference === 0;
}
function uniqueJson(text) {
  if (encoder.encode(text).length > LIMIT) fail('epoint_payload_too_large');
  let parsed; try { parsed = JSON.parse(text); } catch { fail('epoint_invalid_json'); }
  // JSON.parse otherwise accepts duplicate keys. Scan valid JSON strings and
  // decode keys so that "status" and "sta\u0074us" also count as duplicates.
  const stack = [];
  for (let i = 0; i < text.length; i++) {
    const character = text[i];
    if (character === '{' || character === '[') {
      stack.push(character === '{' ? new Set() : null);
      if (stack.length > 32) fail('epoint_json_too_deep');
    } else if (character === '}' || character === ']') stack.pop();
    else if (character === '"') {
      let end = i + 1;
      while (end < text.length) { if (text[end] === '\\') end += 2; else if (text[end] === '"') break; else end++; }
      let next = end + 1; while (/\s/.test(text[next] || '') && next < text.length) next++;
      if (text[next] === ':') {
        const keys = stack[stack.length - 1], key = JSON.parse(text.slice(i, end + 1));
        if (keys.has(key)) fail('epoint_duplicate_json_key');
        keys.add(key);
      }
      i = end;
    }
  }
  if (!object(parsed)) fail('epoint_invalid_payload');
  return parsed;
}
function parseBytes(bytes) {
  let text; try { text = decoder().decode(bytes); } catch { fail('epoint_invalid_utf8'); }
  return uniqueJson(text);
}
function normalize(raw, source) {
  if (!object(raw) || !['callback', 'status'].includes(source)) fail('epoint_invalid_payload');
  for (const key of ['status', 'transaction', 'amount', 'operation_code']) if (!has(raw, key)) fail('epoint_missing_field');
  if (!['new', 'success', 'failed', 'error', 'returned', 'server_error'].includes(raw.status)) fail('epoint_invalid_status');
  if (typeof raw.operation_code !== 'string' || !/^\d{3}$/.test(raw.operation_code)) fail('epoint_invalid_operation');
  if (has(raw, 'currency') && raw.currency !== 'AZN') fail('epoint_currency_mismatch');
  if (source === 'callback' && !has(raw, 'order_id')) fail('epoint_missing_order');
  const result = {status: raw.status, transaction: identifier(raw.transaction),
    operation_code: raw.operation_code, amount: decimal(readAmount(raw.amount))};
  if (has(raw, 'order_id')) result.order_id = identifier(raw.order_id);
  if (has(raw, 'currency')) result.currency = 'AZN';
  return result; // Never include card names/masks, bank responses or other_attr.
}

/** Structure/binding validation only, NOT authentication of a caller's payload.
 * Accept raw data only after verifyEpointCallback or a trusted server getStatus.
 * Never pass browser query/return parameters as a trusted provider observation.
 */
export function validateEpointObservation(raw, expected, {source = 'callback'} = {}) {
  if (!object(expected) || expected.currency !== 'AZN') fail('epoint_invalid_expectation');
  identifier(expected.orderId); identifier(expected.transaction); minor(expected.amountMinor);
  const observed = normalize(raw, source);
  if (observed.transaction !== expected.transaction) fail('epoint_transaction_mismatch');
  if (has(observed, 'order_id') && observed.order_id !== expected.orderId) fail('epoint_order_mismatch');
  if (readAmount(observed.amount) !== expected.amountMinor) fail('epoint_amount_mismatch');
  if (['success', 'returned'].includes(observed.status) && observed.operation_code !== '100') fail('epoint_operation_mismatch');
  const state = ({success:'paid', new:'pending', failed:'failed', error:'failed', returned:'refunded', server_error:'unknown'})[observed.status];
  return Object.freeze({orderId:expected.orderId, transaction:observed.transaction,
    amountMinor:expected.amountMinor, currency:'AZN', status:observed.status, state,
    paid:state === 'paid', currencyReported:has(observed, 'currency')});
}

/** Authenticate and decode only; output contains NO paid/settlement authority.
 * This allows a future ledger to correlate a genuine callback arriving before
 * createPayment returns its transaction ID. The ledger must still resolve the
 * saved attempt, bind amount/order/transaction and apply atomically exactly once.
 */
export async function decodeVerifiedEpointCallback(data, signature, privateKey) {
  encodedData(data);
  const supplied = unbase64(signature, 20);
  if (supplied.length !== 20) fail('epoint_invalid_signature');
  const generated = unbase64(await signEpointData(data, privateKey), 20);
  if (!equalSignature(supplied, generated)) fail('epoint_signature_mismatch');
  return Object.freeze(normalize(parseBytes(unbase64(data, LIMIT)), 'callback'));
}
/** Authenticate then bind to a known saved attempt. Replays remain possible:
 * callers MUST apply through their own atomic ledger, never grant from redirects.
 */
export async function verifyEpointCallback(data, signature, privateKey, expected) {
  const observed = await decodeVerifiedEpointCallback(data, signature, privateKey);
  return validateEpointObservation(observed, expected, {source:'callback'});
}

function publicHttps(value, originOnly = false) {
  if (typeof value !== 'string' || value !== value.trim() || /[\x00-\x20\x7f\\#]/.test(value)) fail('epoint_invalid_url');
  let url; try { url = new URL(value); } catch { fail('epoint_invalid_url'); }
  const hostname = url.hostname.toLowerCase();
  if (url.protocol !== 'https:' || url.username || url.password || /^https:\/\/[^/?#]*@/i.test(value) ||
      !/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z][a-z0-9-]*$/.test(hostname) ||
      /(?:^|\.)(?:localhost|local|internal|lan|home)$/.test(hostname) ||
      (originOnly && (url.pathname !== '/' || value.includes('?')))) fail('epoint_invalid_url');
  return url;
}
async function readResponse(response) {
  if (!response?.body?.getReader) fail('epoint_invalid_response');
  const length = response.headers.get('content-length');
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > LIMIT)) {
    await response.body.cancel().catch(() => {}); fail('epoint_response_too_large');
  }
  const reader = response.body.getReader(), chunks = []; let size = 0;
  try {
    while (true) {
      const chunk = await reader.read(); if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > LIMIT) { await reader.cancel().catch(() => {}); fail('epoint_response_too_large'); }
      chunks.push(chunk.value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return parseBytes(bytes);
}

/** Calls only fixed official HTTPS endpoints. No automatic retries are made.
 * getStatus(transaction) returns a sanitized observation, never paid authority;
 * bind it using validateEpointObservation(..., savedAttempt, {source:'status'}).
 */
export function createEpointClient({publicKey, privateKey, allowedRedirectOrigins = [], fetchImpl = globalThis.fetch, timeoutMs = 8000} = {}) {
  identifier(publicKey); secret(privateKey);
  if (typeof fetchImpl !== 'function' || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000 ||
      !Array.isArray(allowedRedirectOrigins) || allowedRedirectOrigins.length > 16) fail('epoint_invalid_config');
  const origins = new Set(allowedRedirectOrigins.map(value => publicHttps(value, true).origin));
  async function post(endpoint, payload, creation) {
    const data = base64(encoder.encode(JSON.stringify(payload))), signature = await signEpointData(data, privateKey);
    const controller = new AbortController(); let timer;
    // Promise.race bounds injected/noncompliant fetch implementations as well as
    // real fetch + streamed body reads; do not retry if creation might have run.
    const timeout = new Promise((_, reject) => { timer = setTimeout(() => {
      controller.abort(); reject(new EpointProtocolError('epoint_timeout'));
    }, timeoutMs); });
    let safeTransaction;
    try {
      return await Promise.race([(async () => {
        const response = await fetchImpl(`https://epoint.az/api/1/${endpoint}`, {
          method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded', Accept:'application/json'},
          body:new URLSearchParams({data, signature}).toString(), redirect:'error',
          credentials:'omit', referrerPolicy:'no-referrer', signal:controller.signal,
        });
        if (!response?.ok || response.redirected) fail('epoint_http_error');
        const raw = await readResponse(response);
        if (!creation) {
          const observed = normalize(raw, 'status');
          if (observed.transaction !== payload.transaction) fail('epoint_transaction_mismatch');
          return Object.freeze(observed);
        }
        if (raw.status === 'error') throw new EpointProtocolError('epoint_create_rejected');
        if (raw.status !== 'success') fail('epoint_invalid_response');
        safeTransaction = identifier(raw.transaction);
        const redirect = publicHttps(raw.redirect_url);
        if (!origins.has(redirect.origin)) fail('epoint_redirect_denied');
        return Object.freeze({transaction:safeTransaction, redirectUrl:redirect.href});
      })(), timeout]);
    } catch (error) {
      if (creation && error?.code !== 'epoint_create_rejected') {
        throw new EpointProtocolError('epoint_create_ambiguous', {ambiguousCreate:true, safeTransaction});
      }
      if (error instanceof EpointProtocolError) throw error;
      throw new EpointProtocolError('epoint_request_failed');
    } finally { clearTimeout(timer); controller.abort(); }
  }
  return Object.freeze({
    async createPayment({orderId, amountMinor, currency = 'AZN', language = 'az', successUrl, errorUrl, description = ''} = {}) {
      identifier(orderId); minor(amountMinor);
      if (currency !== 'AZN' || !['az','en','ru'].includes(language) || typeof description !== 'string' ||
          description.length > 1000) fail('epoint_invalid_payment');
      if (!origins.size) fail('epoint_redirect_origins_required');
      const success = publicHttps(successUrl), error = publicHttps(errorUrl);
      if (success.origin !== error.origin) fail('epoint_return_origin_mismatch');
      return post('request', {public_key:publicKey, amount:numericAmount(amountMinor), currency:'AZN', language,
        order_id:orderId, description, is_installment:0,
        success_redirect_url:success.href, error_redirect_url:error.href}, true);
    },
    async getStatus(transaction) {
      identifier(transaction);
      return post('get-status', {public_key:publicKey, transaction}, false);
    },
  });
}
