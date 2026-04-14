"""Unit tests for entrypoint Lambda."""

import json
import sys
import os
import importlib.util

_mod_path = os.path.join(os.path.dirname(__file__), "..", "lambdas", "entrypoint", "handler.py")
_spec = importlib.util.spec_from_file_location("entrypoint_handler", _mod_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

handler = _module.handler


class TestEntrypointValidation:
    def test_rejects_missing_user(self):
        event = {
            "body": json.dumps({"description": "test"}),
        }
        result = handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "user" in body["error"]

    def test_rejects_missing_description(self):
        event = {
            "body": json.dumps({"user": "G2CD"}),
        }
        result = handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "description" in body["error"]

    def test_rejects_invalid_json(self):
        event = {
            "body": "not json",
        }
        result = handler(event, None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "Invalid JSON" in body["error"]

    def test_rejects_empty_body(self):
        event = {
            "body": "{}",
        }
        result = handler(event, None)
        assert result["statusCode"] == 400
