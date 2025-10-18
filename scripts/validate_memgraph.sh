#!/usr/bin/env bash
set -euo pipefail

# Simple Memgraph validator that runs Cypher queries via docker exec.
# Requires a running docker-compose stack with service name 'memgraph'.

MEMGRAPH_CONTAINER=${MEMGRAPH_CONTAINER:-memgraph}
# mgconsole is the Memgraph CLI inside the container; connect to Bolt on localhost:7687
CY_CMD=(docker exec -i "$MEMGRAPH_CONTAINER" mgconsole --host=127.0.0.1 --port=7687)

echo "Checking Memgraph container ($MEMGRAPH_CONTAINER) is up..." >&2
docker ps --format '{{.Names}}' | grep -q "^${MEMGRAPH_CONTAINER}$" || {
  echo "Error: Memgraph container '${MEMGRAPH_CONTAINER}' not running." >&2
  exit 1
}

run_cypher() {
  local q="$1"
  printf '%s\n' "$q" | "${CY_CMD[@]}" || true
}

echo "=== Memgraph Data Summary ==="

echo "-- Counts --"
run_cypher "MATCH (n) RETURN count(n) AS nodes;"
run_cypher "MATCH ()-[r]->() RETURN count(r) AS relationships;"

echo "-- Top Labels (by individual label) --"
run_cypher "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c ORDER BY c DESC LIMIT 20;"

echo "-- Top Label Sets (labels(n) grouped) --"
run_cypher "MATCH (n) RETURN labels(n) AS labels, count(*) AS c ORDER BY c DESC LIMIT 10;"

echo "-- Top Relationship Types --"
run_cypher "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(*) AS c ORDER BY c DESC LIMIT 20;"

echo "-- Sample Nodes: Company --"
run_cypher "MATCH (n:Company) RETURN n.name AS name, n.file_path AS file_path, n.repo_path AS repo_path LIMIT 10;"

echo "-- Sample Nodes: Person --"
run_cypher "MATCH (n:Person) RETURN n.name AS name, n.file_path AS file_path, n.repo_path AS repo_path LIMIT 10;"

echo "-- Sample Nodes: Organization --"
run_cypher "MATCH (n:Organization) RETURN n.name AS name, n.file_path AS file_path, n.repo_path AS repo_path LIMIT 10;"

echo "-- Sample Nodes: Technology --"
run_cypher "MATCH (n:Technology) RETURN n.name AS name, n.file_path AS file_path, n.repo_path AS repo_path LIMIT 10;"

echo "-- Sample Nodes: Unknown --"
run_cypher "MATCH (n:Unknown) RETURN n.name AS name, n.file_path AS file_path, n.repo_path AS repo_path LIMIT 10;"

echo "-- Missing Attribute Checks (Memgraph: use IS NULL) --"
run_cypher "MATCH (n) WHERE n.file_path IS NULL RETURN count(n) AS nodes_missing_file_path;"
run_cypher "MATCH (n) WHERE n.repo_path IS NULL RETURN count(n) AS nodes_missing_repo_path;"
run_cypher "MATCH ()-[r]->() WHERE r.file_path IS NULL RETURN count(r) AS rels_missing_file_path;"
run_cypher "MATCH ()-[r]->() WHERE r.repo_path IS NULL RETURN count(r) AS rels_missing_repo_path;"

echo "-- Unlabeled Nodes --"
run_cypher "MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) AS unlabeled_nodes;"

echo "-- Orphan Nodes (no relationships) --"
run_cypher "MATCH (n) WHERE NOT (n)--() RETURN count(n) AS orphan_nodes;"

echo "-- Temp Nodes Leftover --"
run_cypher "MATCH (n:Temp) RETURN count(n) AS temp_nodes;"

echo "-- Nodes With Embeddings --"
run_cypher "MATCH (n) WHERE n.embeddings IS NOT NULL RETURN count(n) AS nodes_with_embeddings;"
run_cypher "MATCH (n) WHERE n.embeddings IS NOT NULL RETURN size(n.embeddings) AS embedding_dim LIMIT 5;"

echo "-- Per-Repo Node/Relationship Counts --"
run_cypher "MATCH (n) RETURN n.repo_path AS repo, count(*) AS nodes ORDER BY nodes DESC LIMIT 20;"
run_cypher "MATCH ()-[r]->() RETURN r.repo_path AS repo, count(*) AS relationships ORDER BY relationships DESC LIMIT 20;"

echo "-- Duplicate Relationships (same endpoints, type, file/repo) --"
run_cypher "MATCH (a)-[r]->(b) WITH ID(a) AS a_id, ID(b) AS b_id, type(r) AS t, r.file_path AS fp, r.repo_path AS rp, count(*) AS c WHERE c > 1 RETURN a_id, b_id, t, fp, rp, c LIMIT 10;"

echo "-- Label-Relationship Coverage (top 20) --"
run_cypher "MATCH (a)-[r]->(b) UNWIND labels(a) AS la UNWIND labels(b) AS lb RETURN la, type(r) AS rel, lb, count(*) AS c ORDER BY c DESC LIMIT 20;"

echo "-- Relationship Samples --"
run_cypher "MATCH (a)-[r]->(b) RETURN labels(a) AS a_labels, a.name AS a_name, type(r) AS rel_type, labels(b) AS b_labels, b.name AS b_name, r.file_path AS r_file_path, r.repo_path AS r_repo_path LIMIT 10;"

echo "Done."
