"""Smoke test for the pure-Python helpers added in this change.

Bypasses main.py's heavy imports (strands/pydantic_core) by extracting
the two helper functions' logic inline. Validates behavior only.
"""
import json, re
from typing import Optional

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_root_cause_json(text: str) -> Optional[dict]:
    if not text:
        return None
    match = _JSON_FENCE_RE.search(text)
    if match:
        try:
            obj = json.loads(match.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def _derive_error_code(datadog_logs, root_cause_json):
    if datadog_logs and datadog_logs.get('success'):
        for entry in datadog_logs.get('error_logs') or []:
            code = str(entry.get('error_code') or '').strip()
            if code:
                return code
    if root_cause_json:
        code = root_cause_json.get('error_code')
        if code is not None and str(code).strip():
            return str(code).strip()
    return ""


# ---- tests ----
print("=== _extract_root_cause_json ===")
t1 = 'pre ```json\n{"omniscript": "X", "error_code": 500}\n``` post'
r1 = _extract_root_cause_json(t1)
print("fenced json:", r1)
assert r1 == {"omniscript": "X", "error_code": 500}, "fenced failed"

t2 = 'analysis: {"root_cause":"token expired","error_code":"401"} done.'
r2 = _extract_root_cause_json(t2)
print("balanced:   ", r2)
assert r2 == {"root_cause": "token expired", "error_code": "401"}, "balanced failed"

t3 = 'no json at all here'
r3 = _extract_root_cause_json(t3)
print("garbage:    ", r3)
assert r3 is None, "garbage should be None"

t4 = 'text with nested: {"a": {"b": 1, "c": [2,3]}, "d": "}nope"}'
r4 = _extract_root_cause_json(t4)
print("nested:     ", r4)
assert r4 == {"a": {"b": 1, "c": [2, 3]}, "d": "}nope"}, "nested failed"

t5 = ""
assert _extract_root_cause_json(t5) is None
print("empty:       None")

print("\n=== _derive_error_code ===")
dd = {'success': True, 'error_logs': [{'error_code': '503'}, {'error_code': '400'}]}
rc = {'error_code': 401}
c1 = _derive_error_code(dd, rc)
print("dd wins:   ", c1)
assert c1 == '503'

c2 = _derive_error_code(None, rc)
print("rc fallback:", c2)
assert c2 == '401'

c3 = _derive_error_code(None, None)
print("empty:     ", repr(c3))
assert c3 == ''

c4 = _derive_error_code({'success': False}, rc)
print("dd failed: ", c4)
assert c4 == '401'

c5 = _derive_error_code({'success': True, 'error_logs': [{'error_code': ''}]}, rc)
print("dd blank:  ", c5)
assert c5 == '401'


# ---------------------------------------------------------------------------
# Envelope unwrapping (mirrors main._unwrap_event_envelope)
# ---------------------------------------------------------------------------
_ENVELOPE_KEYS = ("body", "detail", "Message", "message")


def _unwrap_event_envelope(payload):
    if not isinstance(payload, dict):
        return payload if isinstance(payload, dict) else {}

    records = payload.get("Records")
    if isinstance(records, list) and records:
        sns = records[0].get("Sns") if isinstance(records[0], dict) else None
        if isinstance(sns, dict) and isinstance(sns.get("Message"), str):
            try:
                inner = json.loads(sns["Message"])
                if isinstance(inner, dict):
                    return _unwrap_event_envelope(inner)
            except (json.JSONDecodeError, TypeError):
                pass

    for key in _ENVELOPE_KEYS:
        value = payload.get(key)
        if isinstance(value, dict):
            return _unwrap_event_envelope(value)
        if isinstance(value, str):
            try:
                inner = json.loads(value)
                if isinstance(inner, dict):
                    return _unwrap_event_envelope(inner)
            except (json.JSONDecodeError, TypeError):
                continue

    return payload


print("\n=== _unwrap_event_envelope ===")

raw = {"recordid": "a9z1", "user": "alice"}
assert _unwrap_event_envelope(raw) == raw
print("raw passthrough: OK")

lambda_dict = {"body": {"recordid": "a9z2", "user": "bob"}}
assert _unwrap_event_envelope(lambda_dict) == {"recordid": "a9z2", "user": "bob"}
print("lambda dict body: OK")

lambda_str = {"body": '{"recordid": "a9z3", "user": "carol"}'}
assert _unwrap_event_envelope(lambda_str) == {"recordid": "a9z3", "user": "carol"}
print("lambda string body: OK")

eb = {"detail": {"recordid": "a9z4"}, "source": "aws.events"}
assert _unwrap_event_envelope(eb) == {"recordid": "a9z4"}
print("eventbridge detail: OK")

sns_evt = {
    "Records": [
        {"Sns": {"Message": '{"recordid": "a9z5", "user": "dave"}'}}
    ]
}
assert _unwrap_event_envelope(sns_evt) == {"recordid": "a9z5", "user": "dave"}
print("sns records: OK")

# Nested: API Gateway -> SNS-style { "body": "{\"Message\": ...}" } edge
nested = {"body": '{"detail": {"recordid": "a9z6"}}'}
assert _unwrap_event_envelope(nested) == {"recordid": "a9z6"}
print("nested envelope: OK")

# Non-dict input
assert _unwrap_event_envelope(None) == {}
assert _unwrap_event_envelope("string") == {}
print("non-dict input: OK")

# Garbage body string falls back to original payload
garbage = {"body": "not-json", "recordid": "fallback"}
assert _unwrap_event_envelope(garbage) == garbage
print("garbage body falls back: OK")


print("\nALL TESTS PASSED")
