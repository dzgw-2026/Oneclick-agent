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

print("\nALL TESTS PASSED")
