from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from gqlalchemy import Memgraph

from core.knowledgebase import constants


def run_fetch(db: Memgraph, query: str) -> List[Dict[str, Any]]:
    return list(db.execute_and_fetch(query))


def summarize(db: Memgraph) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    # Basic counts
    nodes = run_fetch(db, "MATCH (n) RETURN count(n) AS nodes")
    rels = run_fetch(db, "MATCH ()-[r]->() RETURN count(r) AS relationships")
    summary["counts"] = {
        "nodes": nodes[0]["nodes"] if nodes else 0,
        "relationships": rels[0]["relationships"] if rels else 0,
    }

    # Top labels
    top_labels = run_fetch(
        db,
        "MATCH (n) RETURN labels(n) AS labels, count(*) AS c ORDER BY c DESC LIMIT 10",
    )
    summary["top_labels"] = [
        {"labels": tl["labels"], "count": tl["c"]} for tl in top_labels
    ]

    # Sample nodes for common labels
    def sample_for_label(label: str, limit: int = 10) -> List[Dict[str, Any]]:
        q = (
            f"MATCH (n:{label}) RETURN n.name AS name, n.file_path AS file_path, "
            f"n.repo_path AS repo_path LIMIT {limit}"
        )
        return run_fetch(db, q)

    samples: Dict[str, Any] = {}
    for lbl in ["Company", "Person", "Product", "Technology"]:
        try:
            samples[lbl] = sample_for_label(lbl)
        except Exception as e:
            samples[lbl] = {"error": str(e)}
    summary["samples"] = samples

    # Missing attributes diagnostics
    missing_node_fp = run_fetch(
        db, "MATCH (n) WHERE NOT exists(n.file_path) RETURN count(n) AS missing"
    )
    missing_node_rp = run_fetch(
        db, "MATCH (n) WHERE NOT exists(n.repo_path) RETURN count(n) AS missing"
    )
    missing_rel_fp = run_fetch(
        db,
        "MATCH ()-[r]->() WHERE NOT exists(r.file_path) RETURN count(r) AS missing",
    )
    missing_rel_rp = run_fetch(
        db,
        "MATCH ()-[r]->() WHERE NOT exists(r.repo_path) RETURN count(r) AS missing",
    )
    summary["missing_attributes"] = {
        "nodes_missing_file_path": missing_node_fp[0]["missing"] if missing_node_fp else 0,
        "nodes_missing_repo_path": missing_node_rp[0]["missing"] if missing_node_rp else 0,
        "rels_missing_file_path": missing_rel_fp[0]["missing"] if missing_rel_fp else 0,
        "rels_missing_repo_path": missing_rel_rp[0]["missing"] if missing_rel_rp else 0,
    }

    # Sample a few relationships
    sample_rels = run_fetch(
        db,
        """
        MATCH (a)-[r]->(b)
        RETURN labels(a) AS a_labels, a.name AS a_name, type(r) AS rel_type,
               labels(b) AS b_labels, b.name AS b_name,
               r.file_path AS r_file_path, r.repo_path AS r_repo_path
        LIMIT 10
        """,
    )
    summary["relationships_sample"] = sample_rels

    return summary


def main() -> None:
    host = constants.MEMGRAPH_HOST
    port = constants.MEMGRAPH_PORT
    db = Memgraph(host=host, port=port)

    report = summarize(db)

    print("=== Memgraph Data Summary ===")
    print(json.dumps(report, indent=2, default=str))

    # Optionally write report to file in data dir
    out_dir = os.environ.get("CHROMA_DATA_DIR", "./data/chroma")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "validation_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    main()
