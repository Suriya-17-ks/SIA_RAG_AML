"""
AML Obligation Traceability Graph
====================================
Implements a directed graph linking regulatory obligations across jurisdictions
and down to internal policy clauses.

Graph Structure:
    Node types:
        FATF_Recommendation  — FATF 40 Recommendations
        PMLA_Section         — Prevention of Money Laundering Act (India)
        RBI_Direction        — RBI Master Directions / Circulars
        FIU_Guideline        — FIU-IND STR/CTR guidelines
        SEBI_Guideline       — SEBI AML guidelines
        Policy_Clause        — Internal bank/NBFC policy clause

    Edge types:
        IMPLEMENTS     — National law implements FATF recommendation
        DERIVES_FROM   — Regulatory circular derives from national law
        REFERENCES     — Document references another
        SATISFIES      — Policy clause satisfies a regulatory obligation (COVERED)
        PARTIALLY_SATISFIES — Policy clause partially covers obligation (PARTIAL)
        MISSING        — No policy clause found for obligation

Research contribution:
    Graph path "FATF-R10 → PMLA-S12 → RBI-KYC-4 → [MISSING]" gives
    end-to-end traceability for each gap. Exportable to GEXF for Gephi visualisation.

Usage:
    from backend.graph.obligation_graph import ObligationGraph

    graph = ObligationGraph()
    graph.add_regulatory_node("FATF-R10", "FATF_Recommendation", "Customer Due Diligence", weight=1.5)
    graph.add_regulatory_node("RBI-KYC-4", "RBI_Direction", "KYC CDD obligations", weight=1.2)
    graph.add_edge("FATF-R10", "RBI-KYC-4", "IMPLEMENTS")
    graph.populate_from_gap_report(report)
    graph.save("./aml_obligation_graph.gexf")
    path = graph.get_trace_path("FATF-R10", "Policy-CDD")
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    nx = None   # type: ignore

if TYPE_CHECKING:
    from backend.agents.schemas.gap_schemas import GapReport, GapResult

logger = logging.getLogger(__name__)

# ── Node type constants ────────────────────────────────────────────────────────
NODE_TYPES = {
    "FATF_Recommendation",
    "PMLA_Section",
    "RBI_Direction",
    "FIU_Guideline",
    "SEBI_Guideline",
    "Policy_Clause",
    "Generic_Obligation",
}

# ── Edge type constants ────────────────────────────────────────────────────────
EDGE_TYPES = {
    "IMPLEMENTS",
    "DERIVES_FROM",
    "REFERENCES",
    "SATISFIES",
    "PARTIALLY_SATISFIES",
    "MISSING",
}

# ── Pre-built cross-jurisdictional edges (FATF → Indian Law) ─────────────────
# These represent known, documented relationships between FATF recommendations
# and Indian regulatory frameworks. Loaded automatically on init.
_KNOWN_EDGES: list[tuple[str, str, str]] = [
    ("FATF-R10", "PMLA-S11",   "IMPLEMENTS"),   # CDD → PMLA record-keeping
    ("FATF-R10", "RBI-KYC",    "IMPLEMENTS"),   # CDD → RBI KYC Direction
    ("FATF-R11", "PMLA-S12",   "IMPLEMENTS"),   # Record keeping → PMLA
    ("FATF-R13", "FIU-STR",    "IMPLEMENTS"),   # STR → FIU-IND
    ("FATF-R16", "FIU-CTR",    "IMPLEMENTS"),   # Wire transfers → FIU CTR
    ("FATF-R22", "SEBI-AML",   "IMPLEMENTS"),   # DNFBP → SEBI
    ("FATF-R29", "FIU-CTR",    "IMPLEMENTS"),   # FIU → FIU-IND
    ("PMLA-S12", "RBI-KYC",    "DERIVES_FROM"), # RBI KYC ← PMLA
    ("PMLA-S12", "FIU-STR",    "DERIVES_FROM"), # FIU-STR ← PMLA
    ("PMLA-S11", "RBI-Records","DERIVES_FROM"), # RBI record-keeping ← PMLA
]


class ObligationGraph:
    """
    Directed regulatory obligation graph built on networkx.
    Provides traceability paths from FATF recommendations to policy clauses.
    """

    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError(
                "networkx is required for ObligationGraph. "
                "Install with: pip install networkx"
            )
        self.G: nx.DiGraph = nx.DiGraph()
        self._load_known_framework_edges()

    # ── Graph construction ─────────────────────────────────────────────────────

    def _load_known_framework_edges(self):
        """Load pre-built cross-jurisdictional regulatory framework edges."""
        # Seed regulatory framework nodes
        framework_nodes = {
            "FATF-R10":    ("FATF_Recommendation", "Customer Due Diligence", 1.5),
            "FATF-R11":    ("FATF_Recommendation", "Record Keeping", 1.5),
            "FATF-R13":    ("FATF_Recommendation", "Suspicious Transaction Reporting", 1.5),
            "FATF-R16":    ("FATF_Recommendation", "Wire Transfers", 1.3),
            "FATF-R22":    ("FATF_Recommendation", "DNFBPs — CDD", 1.3),
            "FATF-R29":    ("FATF_Recommendation", "Financial Intelligence Units", 1.3),
            "PMLA-S11":    ("PMLA_Section", "Obligation to Maintain Records", 1.3),
            "PMLA-S12":    ("PMLA_Section", "Obligation to Furnish Information", 1.3),
            "RBI-KYC":     ("RBI_Direction", "Know Your Customer Master Direction", 1.2),
            "RBI-Records": ("RBI_Direction", "Record Keeping Directions", 1.2),
            "FIU-STR":     ("FIU_Guideline", "Suspicious Transaction Report Guidelines", 1.2),
            "FIU-CTR":     ("FIU_Guideline", "Cash Transaction Report Guidelines", 1.2),
            "SEBI-AML":    ("SEBI_Guideline", "AML Guidelines for Intermediaries", 1.0),
        }
        for node_id, (node_type, label, weight) in framework_nodes.items():
            self.add_regulatory_node(node_id, node_type, label, weight=weight)

        for src, dst, rel in _KNOWN_EDGES:
            self.add_edge(src, dst, rel)

        logger.info(
            f"[obligation_graph] Loaded {len(framework_nodes)} framework nodes "
            f"and {len(_KNOWN_EDGES)} pre-built edges"
        )

    def add_regulatory_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        text: str = "",
        weight: float = 1.0,
        **kwargs,
    ):
        """
        Add a regulatory obligation or framework node.

        Args:
            node_id:   Unique identifier (e.g. "FATF-R10", "RBI-KYC-4")
            node_type: One of NODE_TYPES constants
            label:     Short human-readable label
            text:      Full text of the rule/clause (optional)
            weight:    Regulatory weight used in scoring (Mandatory=1.5, etc.)
        """
        self.G.add_node(
            node_id,
            node_type=node_type,
            label=label,
            text=text,
            weight=weight,
            **kwargs,
        )

    def add_edge(self, source: str, target: str, relation: str, **kwargs):
        """
        Add a directed edge between two nodes.

        Args:
            source:   Source node ID
            target:   Target node ID
            relation: One of EDGE_TYPES constants
        """
        if source not in self.G:
            self.G.add_node(source, node_type="Generic_Obligation", label=source, weight=1.0)
        if target not in self.G:
            self.G.add_node(target, node_type="Generic_Obligation", label=target, weight=1.0)

        self.G.add_edge(source, target, relation=relation, **kwargs)

    # ── Gap report integration ─────────────────────────────────────────────────

    def populate_from_gap_report(self, report: "GapReport"):
        """
        Add policy clause nodes and gap edges derived from a GapReport.

        For each GapResult:
          - Adds a Policy_Clause node if status=COVERED or PARTIAL
          - Adds a SATISFIES / PARTIALLY_SATISFIES / MISSING edge from
            the regulatory obligation node to the policy clause
          - Populates graph_path on each GapResult
        """
        from backend.agents.schemas.gap_schemas import GapResult

        all_results: List[GapResult] = report.covered + report.partial + report.missing

        for gap in all_results:
            obligation_node_id = f"OBL-{gap.obligation_id[:12]}"

            # Add obligation node (from regulatory corpus)
            self.add_regulatory_node(
                node_id   = obligation_node_id,
                node_type = self._node_type_for_jurisdiction(gap.jurisdiction),
                label     = gap.regulation_type or "AML Obligation",
                text      = gap.obligation_text[:300],
                weight    = {"Mandatory": 1.5, "Recommended": 1.0, "Optional": 0.5}.get(
                    gap.obligation_level or "Mandatory", 1.0
                ),
                source    = gap.regulation_source,
                page      = gap.regulation_page,
            )

            # Link from a known framework node if jurisdiction matches
            framework_link = self._get_framework_node(gap.jurisdiction, gap.regulation_type)
            if framework_link and framework_link in self.G:
                self.add_edge(framework_link, obligation_node_id, "DERIVES_FROM")

            if gap.status == "COVERED":
                policy_node_id = f"POL-{gap.obligation_id[:12]}"
                self.add_regulatory_node(
                    node_id   = policy_node_id,
                    node_type = "Policy_Clause",
                    label     = f"Policy: {gap.regulation_type}",
                    text      = gap.evidence or "",
                    weight    = 1.0,
                    source    = gap.evidence_source,
                    page      = gap.evidence_page,
                )
                self.add_edge(obligation_node_id, policy_node_id, "SATISFIES")
                gap.graph_path = f"{framework_link} → {obligation_node_id} → {policy_node_id} [COVERED]" \
                    if framework_link else f"{obligation_node_id} → {policy_node_id} [COVERED]"

            elif gap.status == "PARTIAL":
                policy_node_id = f"POL-{gap.obligation_id[:12]}"
                self.add_regulatory_node(
                    node_id   = policy_node_id,
                    node_type = "Policy_Clause",
                    label     = f"Policy (partial): {gap.regulation_type}",
                    text      = gap.evidence or "",
                    weight    = 1.0,
                )
                self.add_edge(obligation_node_id, policy_node_id, "PARTIALLY_SATISFIES")
                gap.graph_path = f"{framework_link} → {obligation_node_id} → {policy_node_id} [PARTIAL]" \
                    if framework_link else f"{obligation_node_id} → {policy_node_id} [PARTIAL]"

            else:  # MISSING
                self.add_edge(obligation_node_id, "MISSING_CLAUSE", "MISSING")
                self.G.add_node("MISSING_CLAUSE", node_type="Policy_Clause",
                                label="Missing Policy Clause", weight=0.0)
                gap.graph_path = f"{framework_link} → {obligation_node_id} → [MISSING]" \
                    if framework_link else f"{obligation_node_id} → [MISSING]"

        logger.info(
            f"[obligation_graph] Populated from GapReport: "
            f"{self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges"
        )

    def _node_type_for_jurisdiction(self, jurisdiction: Optional[str]) -> str:
        mapping = {
            "RBI":     "RBI_Direction",
            "FATF":    "FATF_Recommendation",
            "FIU-IND": "FIU_Guideline",
            "SEBI":    "SEBI_Guideline",
            "PMLA":    "PMLA_Section",
        }
        return mapping.get(jurisdiction or "", "Generic_Obligation")

    def _get_framework_node(self, jurisdiction: Optional[str], regulation_type: Optional[str]) -> Optional[str]:
        """Map jurisdiction + regulation_type to the best matching pre-built framework node."""
        mapping = {
            ("RBI",     "KYC"):          "RBI-KYC",
            ("RBI",     "CDD"):          "RBI-KYC",
            ("RBI",     "EDD"):          "RBI-KYC",
            ("FIU-IND", "STR"):          "FIU-STR",
            ("FIU-IND", "CTR"):          "FIU-CTR",
            ("FATF",    "KYC"):          "FATF-R10",
            ("FATF",    "RecordKeeping"):"FATF-R11",
            ("FATF",    "STR"):          "FATF-R13",
            ("SEBI",    None):           "SEBI-AML",
            ("PMLA",    None):           "PMLA-S12",
        }
        return mapping.get((jurisdiction, regulation_type)) or mapping.get((jurisdiction, None))

    # ── Graph queries ──────────────────────────────────────────────────────────

    def get_trace_path(self, source_node: str, target_node: str) -> Optional[str]:
        """
        Find and format the shortest path between two nodes.
        Returns a human-readable path string, or None if unreachable.
        """
        if source_node not in self.G or target_node not in self.G:
            return None
        try:
            path = nx.shortest_path(self.G, source=source_node, target=target_node)
            return " → ".join(path)
        except nx.NetworkXNoPath:
            return None

    def get_node_summary(self) -> Dict[str, int]:
        """Return count of nodes by type."""
        counts: Dict[str, int] = {}
        for _, data in self.G.nodes(data=True):
            ntype = data.get("node_type", "Unknown")
            counts[ntype] = counts.get(ntype, 0) + 1
        return counts

    def get_missing_obligations(self) -> List[Dict]:
        """Return all obligation nodes with a MISSING outgoing edge."""
        missing = []
        for src, dst, data in self.G.edges(data=True):
            if data.get("relation") == "MISSING":
                node_data = self.G.nodes.get(src, {})
                missing.append({
                    "node_id": src,
                    "label":   node_data.get("label", src),
                    "source":  node_data.get("source", ""),
                    "page":    node_data.get("page", 0),
                })
        return missing

    # ── Serialisation ──────────────────────────────────────────────────────────

    def save(self, path: str):
        """
        Save graph to GEXF format (viewable in Gephi).
        Also saves a JSON adjacency list for lightweight inspection.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # GEXF — for Gephi visualisation
        gexf_path = p.with_suffix(".gexf")
        nx.write_gexf(self.G, str(gexf_path))
        logger.info(f"[obligation_graph] Saved GEXF to {gexf_path}")

        # JSON adjacency — for programmatic use
        import json
        json_path = p.with_suffix(".json")
        data = nx.readwrite.json_graph.adjacency_data(self.G)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"[obligation_graph] Saved JSON adjacency to {json_path}")

    @classmethod
    def load(cls, path: str) -> "ObligationGraph":
        """Load graph from a previously saved GEXF file."""
        graph = cls.__new__(cls)
        graph.G = nx.read_gexf(path)
        logger.info(f"[obligation_graph] Loaded graph from {path}: "
                    f"{graph.G.number_of_nodes()} nodes, {graph.G.number_of_edges()} edges")
        return graph

    # ── Convenience display ────────────────────────────────────────────────────

    def summary(self) -> str:
        """Return a human-readable summary of the graph."""
        node_summary = self.get_node_summary()
        missing_count = len([e for _, _, d in self.G.edges(data=True) if d.get("relation") == "MISSING"])
        lines = [
            f"AML Obligation Graph Summary",
            f"  Nodes: {self.G.number_of_nodes()}",
            f"  Edges: {self.G.number_of_edges()}",
            f"  Missing obligations: {missing_count}",
            f"  Node types: {node_summary}",
        ]
        return "\n".join(lines)
