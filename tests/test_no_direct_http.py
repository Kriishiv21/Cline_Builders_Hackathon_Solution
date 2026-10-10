"""Enforces architecture section 10.3 / .clinerules/00-master-workflow.md:
only uspi/common/cline_client.py may import httpx (or any other raw HTTP
client) directly.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "uspi"
ALLOWED_FILES = {ROOT / "common" / "cline_client.py"}
HTTP_IMPORT_RE = re.compile(r"^\s*(import httpx|from httpx|import requests|from requests|import urllib3)", re.MULTILINE)


def test_no_direct_http_outside_cline_client():
    offenders = []
    for py_file in ROOT.rglob("*.py"):
        if py_file in ALLOWED_FILES:
            continue
        text = py_file.read_text(encoding="utf-8")
        if HTTP_IMPORT_RE.search(text):
            offenders.append(str(py_file))
    assert not offenders, f"Direct HTTP client import found outside cline_client.py: {offenders}"
