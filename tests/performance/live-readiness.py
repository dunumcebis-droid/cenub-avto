#!/usr/bin/env python3
"""Bounded, anonymous production READ probe; explicitly opt in with --run-live.

Only four same-site static GETs and ca_browse_listings read RPCs are permitted.
No authenticated account, image analysis, uploads, telemetry or mutation API runs.
Limits: 79 total HTTP requests, 20 overlapping reads, 15s each, 180s overall.
The run stops scheduling on an HTTP/transport/schema failure, including 429/5xx.
Response bodies and API keys are never written to the report.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SITE = 'https://dunumcebis-droid.github.io/cenub-avto/'
PROJECT = 'https://iqdtehqxusfiwokrzceo.supabase.co'
RPC = PROJECT + '/rest/v1/rpc/ca_browse_listings'
STATIC = ['index.html', 'assets/site.css', 'assets/js/01-main.js',
          'assets/branding/cenub-avto-logo.jpg']
STAGES = [(1, 4), (5, 10), (10, 20), (20, 40)]
MAX_REQUESTS = 79
TIMEOUT = 15
DEADLINE_SECONDS = 180
MAX_BODY = 8 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Unexpected redirect; probe stopped')


class Probe:
    def __init__(self, key):
        self.key = key
        self.started = time.monotonic()
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.requests = 0
        self.failure = None
        self.total = None

    def abort(self, reason):
        with self.lock:
            if self.failure is None:
                self.failure = reason
        self.stop.set()

    def fetch(self, target, method='GET'):
        if self.stop.is_set():
            return None
        remaining = DEADLINE_SECONDS - (time.monotonic() - self.started)
        if remaining <= 0:
            self.abort('Overall deadline exceeded')
            return None
        assert (method == 'GET' and target in [SITE + item for item in STATIC]) or (method == 'POST' and target == RPC)
        with self.lock:
            self.requests += 1
            assert self.requests <= MAX_REQUESTS
        headers = {'Accept-Encoding': 'gzip', 'User-Agent': 'CenubAvto-readiness-read-probe/1.0'}
        data = None
        if method == 'POST':
            headers.update({'apikey': self.key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
            data = b'{"p_filters":{},"p_page":1,"p_page_size":24}'
        request = urllib.request.Request(target, data=data, headers=headers, method=method)
        begin = time.perf_counter()
        try:
            # Each job opens a fresh HTTPS request, including proxy/TLS latency.
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=min(TIMEOUT, remaining)) as response:
                status = response.status
                wire = response.read(MAX_BODY + 1)
                encoding = response.headers.get('Content-Encoding', '').lower()
            if len(wire) > MAX_BODY:
                raise ValueError('Response exceeds probe size bound')
            body = gzip.decompress(wire) if encoding == 'gzip' else wire
            if len(body) > MAX_BODY:
                raise ValueError('Decoded response exceeds probe size bound')
            if status != 200:
                raise ValueError('Unexpected HTTP ' + str(status))
            sample = {'status': status, 'milliseconds': round((time.perf_counter() - begin) * 1000, 2),
                      'wire_bytes': len(wire), 'decoded_bytes': len(body), 'encoding': encoding or 'identity'}
            if method == 'POST':
                envelope = json.loads(body)
                assert isinstance(envelope, dict) and isinstance(envelope.get('items'), list)
                assert isinstance(envelope.get('total'), int) and envelope['total'] >= 0
                assert envelope.get('page') == 1 and envelope.get('page_size') == 24
                assert len(envelope['items']) == min(24, envelope['total'])
                assert all(row.get('veziyyet') == 'aktiv' and not row.get('is_sold', False) for row in envelope['items'])
                with self.lock:
                    if self.total is None:
                        self.total = envelope['total']
                    elif self.total != envelope['total']:
                        raise ValueError('Live dataset changed during probe; repeat at a quiet time')
                sample['listing_total'] = envelope['total']
            else:
                sample['sha256'] = hashlib.sha256(body).hexdigest()
                sample['path'] = target[len(SITE):]
            return sample
        except urllib.error.HTTPError as error:
            self.abort('HTTP ' + str(error.code) + '; no further jobs scheduled')
        except Exception as error:
            # Never include URL/header/body values or raw private provider errors.
            self.abort(type(error).__name__ + '; no further jobs scheduled')
        return None


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


def summarize(samples, wall_seconds):
    times = [row['milliseconds'] for row in samples]
    return {'completed_requests': len(samples), 'wall_seconds': round(wall_seconds, 3),
            'requests_per_second': round(len(samples) / wall_seconds, 2) if wall_seconds else None,
            'p50_milliseconds': percentile(times, .5), 'p95_milliseconds': percentile(times, .95),
            'max_milliseconds': max(times) if times else None,
            'wire_bytes_total': sum(row['wire_bytes'] for row in samples),
            'decoded_bytes_total': sum(row['decoded_bytes'] for row in samples)}


def main():
    global MAX_REQUESTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-live', action='store_true', help='Authorize the fixed bounded public read probe')
    parser.add_argument('--post-migration', action='store_true', help='Fixed 21-read follow-up: one warmup and twenty concurrent reads')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/performance/live-readiness-result.json')
    args = parser.parse_args()
    if not args.run_live:
        parser.error('No requests made: --run-live is required')
    source = (ROOT / 'assets/js/01-main.js').read_text()
    url = re.search(r"const\s+CA_URL\s*=\s*['\"]([^'\"]+)", source)
    key = re.search(r"const\s+CA_KEY\s*=\s*['\"]([^'\"]+)", source)
    assert url and url.group(1) == PROJECT and key
    # The key comes only from the already-public client, never service credentials.
    public_key = key.group(1)
    if not public_key.startswith('sb_publishable_'):
        # Legacy client JWTs are permitted only for the anonymous role.
        parts = public_key.split('.')
        assert len(parts) == 3
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
        assert claims.get('role') == 'anon'
    if args.post_migration:
        MAX_REQUESTS = 21
    run_stages = [(20, 20)] if args.post_migration else STAGES
    probe = Probe(public_key)
    static = []
    stages = []
    for path in ([] if args.post_migration else STATIC):
        sample = probe.fetch(SITE + path)
        if sample is not None:
            static.append(sample)
    warmup = probe.fetch(RPC, 'POST')
    for concurrency, requests in run_stages:
        if probe.stop.is_set():
            break
        begin = time.perf_counter()
        samples = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(probe.fetch, RPC, 'POST') for _ in range(requests)]
            for future in as_completed(futures):
                sample = future.result()
                if sample is not None:
                    samples.append(sample)
                if probe.stop.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
        stages.append({'concurrency_limit': concurrency, 'requested_count': requests,
                       **summarize(samples, time.perf_counter() - begin)})
    report = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'success': not probe.stop.is_set() and len(stages) == len(run_stages),
              'mode': 'post-migration' if args.post_migration else 'baseline',
              'read_only': True, 'authenticated_accounts_used': 0, 'real_writes': 0,
              'request_limit': MAX_REQUESTS, 'requests_started': probe.requests,
              'maximum_concurrency': 20, 'per_request_timeout_seconds': TIMEOUT,
              'overall_deadline_seconds': DEADLINE_SECONDS, 'active_listing_total': probe.total,
              'static_gets': static, 'warmup': warmup, 'read_rpc_stages': stages,
              'stop_reason': probe.failure,
              'limits': ['A bounded read smoke probe, not an unrestricted stress test or a capacity guarantee.',
                         'Concurrency counts overlapping HTTP jobs, not complete simultaneous browser users.',
                         'Each job includes fresh HTTPS/proxy/TLS overhead from this cloud environment.',
                         'An empty live dataset does not verify populated query performance; see isolated probe.',
                         'No phone/email, private record content, API keys, or response bodies are stored.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'success': report['success'], 'requests': probe.requests,
                      'active_listings': probe.total, 'read_stages': stages, 'stop_reason': probe.failure}))
    if not report['success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
