"""GNN prior (C05, architecture section 4.3): ablation-gated.

"Kept only if the ablation shows it beats entity counters." This module
ships a minimal relational message-passing prior over shared entity edges
(sender/link/UPI/similarity/time/cross-channel), with a hub degree cap and
Trust-Badge chats as propagation barriers. It is feature-flagged off by
default (configs/fusion.yaml: features.gnn_prior.enabled) because the
architecture states it is "Specified, unproven".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from uspi.common.config import load_yaml


@dataclass
class GnnEdge:
    src_entity: str
    dst_entity: str
    edge_type: str  # shared_sender | shared_link | shared_upi | similarity | time | cross_channel
    weight: float


class GnnPrior:
    def __init__(self, config_path: str = "gnn_prior.yaml") -> None:
        cfg = load_yaml(config_path)
        self.enabled = cfg.get("enabled", False)
        self.hub_degree_cap = cfg.get("hub_degree_cap", 200)
        self.propagation_hops = cfg.get("propagation_hops", 1)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._edges: Dict[str, List[GnnEdge]] = {}
        self._trust_barriers: Set[str] = set()

    def add_edge(self, edge: GnnEdge) -> None:
        if len(self._edges.get(edge.src_entity, [])) >= self.hub_degree_cap:
            return  # hub degree cap
        self._edges.setdefault(edge.src_entity, []).append(edge)

    def set_trust_barrier(self, entity: str, barrier: bool) -> None:
        if barrier:
            self._trust_barriers.add(entity)
        else:
            self._trust_barriers.discard(entity)

    def prior_for(self, entity: str, entity_scores: Dict[str, float]) -> float:
        """One-hop (configurable) message passing: average neighbour score
        weighted by edge weight, stopped at trust barriers."""
        if not self.enabled:
            return 0.0
        if entity in self._trust_barriers:
            return 0.0
        edges = self._edges.get(entity, [])
        if not edges:
            return 0.0
        total_w = 0.0
        acc = 0.0
        for edge in edges:
            if edge.dst_entity in self._trust_barriers:
                continue
            neighbour_score = entity_scores.get(edge.dst_entity, 0.0)
            acc += edge.weight * neighbour_score
            total_w += edge.weight
        return acc / total_w if total_w > 0 else 0.0
