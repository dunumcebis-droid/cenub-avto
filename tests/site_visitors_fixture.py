"""Strict traffic-only replies for browser suites with independent backends."""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

SITE_VISITOR_PATHS = frozenset(('/rest/v1/rpc/ca_record_site_visit',
                              '/rest/v1/rpc/ca_daily_site_visitors'))

def handle_site_visitors(route, visitors):
    req = route.request
    parsed = urlsplit(req.url)
    if parsed.netloc != 'iqdtehqxusfiwokrzceo.supabase.co' or parsed.path not in SITE_VISITOR_PATHS:
        return False
    assert req.method == 'POST'
    assert not req.headers.get('authorization') and not req.headers.get('referer')
    body = req.post_data_json
    recording = parsed.path.endswith('/ca_record_site_visit')
    assert isinstance(body, dict) and set(body) == ({'p_visitor'} if recording else set())
    counted = False
    if recording:
        identifier = body['p_visitor']
        assert isinstance(identifier, str) and re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', identifier)
        counted = identifier not in visitors
        visitors.add(identifier)
    payload = {'day':datetime.now(timezone(timedelta(hours=4))).date().isoformat(),
               'timezone':'Asia/Baku','visitors':len(visitors)}
    if recording:
        payload['counted'] = counted
    route.fulfill(content_type='application/json', body=json.dumps(payload))
    return True
