"""Threat-intel registry (C25, architecture section 2.2/12.1): shared
blocklist/exemplar store with signed, versioned bundles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class ThreatIntelBundle:
    version: str
    blocklist_domains: Set[str] = field(default_factory=set)
    blocklist_phone_prefixes: Set[str] = field(default_factory=set)
    scam_exemplars: List[str] = field(default_factory=list)

    def integrity_fingerprint(self) -> str:
        import hashlib

        h = hashlib.sha256()
        h.update(self.version.encode())
        for d in sorted(self.blocklist_domains):
            h.update(d.encode())
        return h.hexdigest()[:16]


class ThreatIntelRegistry:
    def __init__(self) -> None:
        self._current: ThreatIntelBundle = ThreatIntelBundle(version="0.0.0")

    def load_bundle(self, bundle: ThreatIntelBundle) -> None:
        """Signed OTA update point; signature verification would be
        performed by the deployment layer before calling this."""
        self._current = bundle

    def current(self) -> ThreatIntelBundle:
        return self._current
