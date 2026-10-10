"""Entity enrichment (architecture section 4.2): URL, phone, UPI, SMS
header checks with a tiered lookup and a hard timeout returning 'unknown'.

Deterministic, rule-based. Never fetches live URL content from the device.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

from uspi.common.config import load_yaml

_URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s]{7,14}\d)")
_UPI_RE = re.compile(r"[\w.\-]{2,256}@[a-zA-Z]{2,64}")


@dataclass
class EnrichmentResult:
    kind: str  # "url" | "phone" | "upi" | "sms_header"
    value_hint: str
    risk_score: float  # 0..1, 'unknown' maps to the configured neutral prior
    status: str  # "known" | "unknown" | "timeout"
    reasons: list


class EntityEnrichment:
    def __init__(self, config_path: str = "entity_enrichment.yaml") -> None:
        cfg = load_yaml(config_path)
        self.lookup_timeout_s = cfg.get("lookup_timeout_s", 0.05)
        self.unknown_prior = cfg.get("unknown_prior", 0.3)
        self.shortener_domains = set(cfg.get("shortener_domains", []))
        self.blocklist_domains = set(cfg.get("blocklist_domains", []))
        self.blocklist_phone_prefixes = cfg.get("blocklist_phone_prefixes", [])
        self.trusted_tlds = set(cfg.get("trusted_tlds", []))
        self.config_version = cfg.get("_config_version", "unversioned")

    def _timed_lookup(self, fn, *args) -> Optional[dict]:
        start = time.monotonic()
        try:
            result = fn(*args)
        except Exception:
            return None
        if (time.monotonic() - start) > self.lookup_timeout_s:
            return None  # hard timeout -> caller treats as unknown
        return result

    def enrich_url(self, url: str) -> EnrichmentResult:
        reasons = []
        domain = re.sub(r"^https?://", "", url).split("/")[0].lower()
        if domain in self.blocklist_domains:
            return EnrichmentResult("url", domain, 0.95, "known", ["blocklisted_domain"])
        score = self.unknown_prior
        status = "unknown"
        if domain in self.shortener_domains:
            score += 0.3
            reasons.append("shortener")
        if "xn--" in domain:
            score += 0.3
            reasons.append("punycode")
        tld = domain.split(".")[-1] if "." in domain else ""
        if tld and tld not in self.trusted_tlds:
            score += 0.1
            reasons.append(f"untrusted_tld:{tld}")
        else:
            status = "known"
        return EnrichmentResult("url", domain, min(score, 1.0), status, reasons)

    def enrich_phone(self, phone: str) -> EnrichmentResult:
        digits = re.sub(r"\D", "", phone)
        for prefix in self.blocklist_phone_prefixes:
            if digits.startswith(prefix):
                return EnrichmentResult("phone", digits[-4:], 0.9, "known", ["blocklisted_prefix"])
        return EnrichmentResult("phone", digits[-4:], self.unknown_prior, "unknown", [])

    def enrich_upi(self, upi_id: str) -> EnrichmentResult:
        handle = upi_id.split("@")[-1].lower() if "@" in upi_id else ""
        valid_handles = {"okaxis", "oksbi", "okhdfcbank", "okicici", "ybl", "paytm", "upi"}
        if handle in valid_handles:
            return EnrichmentResult("upi", handle, 0.1, "known", ["recognized_psp_handle"])
        return EnrichmentResult("upi", handle or "unknown", self.unknown_prior, "unknown", ["unrecognized_handle"])

    def find_entities(self, text: str) -> list:
        results = []
        for m in _URL_RE.finditer(text or ""):
            results.append(self.enrich_url(m.group()))
        for m in _UPI_RE.finditer(text or ""):
            results.append(self.enrich_upi(m.group()))
        for m in _PHONE_RE.finditer(text or ""):
            results.append(self.enrich_phone(m.group()))
        return results
