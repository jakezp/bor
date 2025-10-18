#!/usr/bin/env bash
set -euo pipefail
BASE_URL=${BASE_URL:-http://localhost:8000}
REPO_PATH=${REPO_PATH:-}

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; exit 1; }

echo "Running BOR API smoke tests against ${BASE_URL}"

# Health
curl -s "${BASE_URL}/knowledge_base/debug/health" | jq . >/dev/null || fail "health endpoint should return JSON"
pass "health endpoint"

# Debug chroma
curl -s "${BASE_URL}/knowledge_base/debug/chroma" | jq . >/dev/null || fail "debug/chroma should return JSON"
pass "debug/chroma"

# Optional: Text Analyzer endpoints (JSON-first). Run when TEST_TA=true
if [[ "${TEST_TA:-false}" == "true" ]]; then
  # 1) optimize_style
  ta_opt_body='{"content":"def add(x, y):\n    return x+y","language":"python","style":"pep8","output_format":"json"}'
  opt_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/text_analizer/code/optimize_style" -H 'Content-Type: application/json' -d "${ta_opt_body}")
  opt_code=$(tail -n1 <<<"${opt_resp}")
  opt_body=$(sed '$d' <<<"${opt_resp}")
  if [[ "${opt_code}" != "200" ]]; then
    echo "optimize_style HTTP ${opt_code}" >&2
    echo "Response:" >&2
    echo "${opt_body}" | sed -e 's/^/  /' >&2
    fail "optimize_style http"
  fi
  echo "${opt_body}" | jq -e '.status == "ok" and (.suggestions | type == "array")' >/dev/null || { echo "Resp:"; echo "${opt_body}"; fail "optimize_style json"; }
  pass "text_analizer optimize_style"

  # 2) explain
  ta_explain_body='{"content":"def inc(x):\n    return x+1","language":"python","output_format":"json"}'
  ex_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/text_analizer/code/explain" -H 'Content-Type: application/json' -d "${ta_explain_body}")
  ex_code=$(tail -n1 <<<"${ex_resp}")
  ex_body=$(sed '$d' <<<"${ex_resp}")
  if [[ "${ex_code}" != "200" ]]; then
    echo "explain HTTP ${ex_code}" >&2
    echo "Response:" >&2
    echo "${ex_body}" | sed -e 's/^/  /' >&2
    fail "explain http"
  fi
  echo "${ex_body}" | jq -e '.status == "ok" and (.explanation | type == "string")' >/dev/null || { echo "Resp:"; echo "${ex_body}"; fail "explain json"; }
  pass "text_analizer explain"

  # 3) debug
  ta_debug_body='{"content":"def div(x, y):\n    # TODO handle y=0\n    return x / y","language":"python","output_format":"json"}'
  dbg_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/text_analizer/code/debug" -H 'Content-Type: application/json' -d "${ta_debug_body}")
  dbg_code=$(tail -n1 <<<"${dbg_resp}")
  dbg_body=$(sed '$d' <<<"${dbg_resp}")
  if [[ "${dbg_code}" != "200" ]]; then
    echo "debug HTTP ${dbg_code}" >&2
    echo "Response:" >&2
    echo "${dbg_body}" | sed -e 's/^/  /' >&2
    fail "debug http"
  fi
  echo "${dbg_body}" | jq -e '.status == "ok" and (.issues | type == "array")' >/dev/null || { echo "Resp:"; echo "${dbg_body}"; fail "debug json"; }
  pass "text_analizer debug"

  # 4) generate_questions
  ta_q_body='{"content":"# Title\nKubernetes deploys containers across nodes and manages scaling.","num_questions":3,"output_format":"json"}'
  q_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/text_analizer/notes/generate_questions" -H 'Content-Type: application/json' -d "${ta_q_body}")
  q_code=$(tail -n1 <<<"${q_resp}")
  q_body=$(sed '$d' <<<"${q_resp}")
  if [[ "${q_code}" != "200" ]]; then
    echo "generate_questions HTTP ${q_code}" >&2
    echo "Response:" >&2
    echo "${q_body}" | sed -e 's/^/  /' >&2
    fail "generate_questions http"
  fi
  echo "${q_body}" | jq -e '.status == "ok" and (.questions | type == "array") and (.questions | length >= 1)' >/dev/null || { echo "Resp:"; echo "${q_body}"; fail "generate_questions json"; }
  pass "text_analizer generate_questions"
fi

# If REPO_PATH provided, run a notes flow
if [[ -n "${REPO_PATH}" ]]; then
  body=$(jq -n --arg p "${REPO_PATH}" '{path:$p, type:"Notes"}')
  # Decide whether to init: skip if graph for this repo already has nodes unless FORCE_INIT=true
  FORCE_INIT=${FORCE_INIT:-false}
  should_init=false
  if [[ "${FORCE_INIT}" == "true" ]]; then
    should_init=true
  else
    overview=$(curl -s "${BASE_URL}/knowledge_base/debug/graph_overview" --get --data-urlencode "repo_path=${REPO_PATH}")
    # Extract counts; default to 0 on parse issues
    nodes_cnt=$(echo "${overview}" | jq -r '.nodes_with_file_prefix.cnt // 0' 2>/dev/null || echo 0)
    rels_cnt=$(echo "${overview}" | jq -r '.rels_with_file_prefix.cnt // 0' 2>/dev/null || echo 0)
    if [[ "${nodes_cnt}" == "0" && "${rels_cnt}" == "0" ]]; then
      should_init=true
    fi
  fi
  if [[ "${should_init}" == "true" ]]; then
    init_resp=$(curl -s -X POST "${BASE_URL}/knowledge_base/general/init_local_repo" -H 'Content-Type: application/json' -d "${body}")
    echo "${init_resp}" | jq . >/dev/null || { echo "init_local_repo raw response:"; echo "${init_resp}"; fail "init_local_repo should return JSON"; }
    pass "init_local_repo (executed)"
  else
    pass "init_local_repo (skipped: repo has data)"
  fi
  # get_schema
  gs_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/general/get_schema" -H 'Content-Type: application/json' -d "${body}")
  gs_code=$(tail -n1 <<<"${gs_resp}")
  gs_body=$(sed '$d' <<<"${gs_resp}")
  if [[ "${gs_code}" != "200" ]]; then
    echo "get_schema HTTP ${gs_code}" >&2
    echo "Response:" >&2
    echo "${gs_body}" | sed -e 's/^/  /' >&2
    fail "get_schema http"
  fi
  schema=$(echo "${gs_body}" | jq -r .content 2>/dev/null || true)
  [[ -n "${schema}" && "${schema}" != "null" ]] || { echo "Schema empty or invalid:"; echo "${gs_body}"; fail "get_schema content"; }
  pass "get_schema"
  # get_all_for_repo
  all=$(curl -s -X POST "${BASE_URL}/knowledge_base/general/get_all_for_repo" -H 'Content-Type: application/json' -d "${body}" -i)
  code=$(sed -n '1p' <<<"${all}" | awk '{print $2}')
  if [[ "${code}" != "200" && "${code}" != "204" ]]; then
    echo "Unexpected status: ${code}"; echo "${all}" | head -n 40; fail "get_all_for_repo status"
  fi
  pass "get_all_for_repo (${code})"

  # CRUD a temporary note file inside the vault
  tmp_file="${REPO_PATH}/___bor_smoke_test.md"
  MARKER="___bor_smoke_marker_$(date +%s)"
  echo "# Smoke Test\n${MARKER}\nHello world $(date)" > "${tmp_file}"
  file_body=$(jq -n --arg p "${tmp_file}" --arg t "Notes" --arg c "# Smoke Test\n${MARKER}\nUpdated $(date)" '{path:$p, type:$t, content:$c}')
  # update_file (delete+add)
  upd_resp=$(curl -s -w "\n%{http_code}" -X PUT "${BASE_URL}/knowledge_base/notes/update_file" -H 'Content-Type: application/json' -d "${file_body}")
  upd_code=$(tail -n1 <<<"${upd_resp}")
  upd_body=$(sed '$d' <<<"${upd_resp}")
  if ! echo "${upd_body}" | jq -r .status | grep -q 'ok'; then
    echo "update_file HTTP ${upd_code}" >&2
    echo "update_file response:" >&2
    echo "${upd_body}" | sed -e 's/^/  /' >&2
    fail "update_file"
  fi
  pass "update_file"
  # get_for_path
  gfp=$(curl -s -X POST "${BASE_URL}/knowledge_base/notes/get_for_path" -H 'Content-Type: application/json' -d "${file_body}" -i)
  gcode=$(sed -n '1p' <<<"${gfp}" | awk '{print $2}')
  if [[ "${gcode}" != "200" && "${gcode}" != "204" ]]; then
    echo "Unexpected status: ${gcode}"; echo "${gfp}" | head -n 40; fail "get_for_path status"
  fi
  pass "get_for_path (${gcode})"
  # rename_file
  new_tmp_file="${REPO_PATH}/___bor_smoke_test_renamed.md"
  rbody=$(jq -n --arg op "${tmp_file}" --arg np "${new_tmp_file}" '{old_file:{path:$op, type:"Notes"}, new_file:{path:$np, type:"Notes"}}')
  curl -s -X POST "${BASE_URL}/knowledge_base/notes/rename_file" -H 'Content-Type: application/json' -d "${rbody}" | jq .status | grep -q 'ok' || fail "rename_file"
  pass "rename_file"

  # optional: suggest_link tests against known marker
  if [[ "${TEST_SUGGEST:-false}" == "true" ]]; then
    sbody=$(jq -n --arg p "${REPO_PATH}" --arg m "${MARKER}" '{repo:{path:$p, type:"Notes"}, content:$m}')
    # top_k=1 should return File with the renamed path
    s1=$(curl -s -X POST "${BASE_URL}/knowledge_base/notes/suggest_link" -H 'Content-Type: application/json' -d "${sbody}")
    s1_path=$(echo "${s1}" | jq -r .path)
    [[ "${s1_path}" == "${new_tmp_file}" ]] || { echo "suggest_link(top_k=1) expected ${new_tmp_file}, got ${s1_path}"; echo "Resp:"; echo "${s1}"; fail "suggest_link top_k=1"; }
    pass "suggest_link (top_k=1)"
    # top_k=3 should return candidates with first == renamed path
    s3=$(curl -s -X POST "${BASE_URL}/knowledge_base/notes/suggest_link?top_k=3" -H 'Content-Type: application/json' -d "${sbody}")
    echo "${s3}" | jq -r .status | grep -q 'ok' || { echo "Resp:"; echo "${s3}"; fail "suggest_link top_k=3 status"; }
    first=$(echo "${s3}" | jq -r '.candidates[0] // empty')
    [[ -n "${first}" && "${first}" == "${new_tmp_file}" ]] || { echo "Resp:"; echo "${s3}"; fail "suggest_link top_k=3 first candidate"; }
    pass "suggest_link (top_k=3)"
  fi

  # optional: vector endpoint tests using the marker content
  if [[ "${TEST_VECTOR:-false}" == "true" ]]; then
    vbody=$(jq -n --arg p "${REPO_PATH}" --arg m "${MARKER}" '{repo:{path:$p, type:"Notes"}, content:$m}')
    # sentence_to_nodes should return at least one node id
    sn_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/notes/sentence_to_nodes?top_k=2" -H 'Content-Type: application/json' -d "${vbody}")
    sn_code=$(tail -n1 <<<"${sn_resp}")
    sn_body=$(sed '$d' <<<"${sn_resp}")
    if [[ "${sn_code}" != "200" ]]; then
      echo "sentence_to_nodes HTTP ${sn_code}" >&2
      echo "Response:" >&2
      echo "${sn_body}" | sed -e 's/^/  /' >&2
      fail "sentence_to_nodes http"
    fi
    id0=$(echo "${sn_body}" | jq -r '.[0].id // empty' 2>/dev/null || true)
    [[ -n "${id0}" ]] || { echo "Resp:"; echo "${sn_body}"; fail "sentence_to_nodes returned empty"; }
    pass "sentence_to_nodes (top_k=2)"
    # node_to_sentences should return at least one sentence for the first id
    nb=$(jq -n --argjson id "${id0}" --arg p "${REPO_PATH}" '{repo:{path:$p, type:"Notes"}, id:$id}')
    ns_resp=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/knowledge_base/notes/node_to_sentences?top_k=2" -H 'Content-Type: application/json' -d "${nb}")
    ns_code=$(tail -n1 <<<"${ns_resp}")
    ns_body=$(sed '$d' <<<"${ns_resp}")
    if [[ "${ns_code}" != "200" ]]; then
      echo "node_to_sentences HTTP ${ns_code}" >&2
      echo "Response:" >&2
      echo "${ns_body}" | sed -e 's/^/  /' >&2
      fail "node_to_sentences http"
    fi
    s0=$(echo "${ns_body}" | jq -r '.[0].content // empty' 2>/dev/null || true)
    [[ -n "${s0}" ]] || { echo "Resp:"; echo "${ns_body}"; fail "node_to_sentences returned empty"; }
    pass "node_to_sentences (top_k=2)"
  fi
  # delete_file (expects JSON {status:"ok"})
  dbody=$(jq -n --arg p "${new_tmp_file}" '{path:$p, type:"Notes"}')
  dresp=$(curl -s -w "\n%{http_code}" -X DELETE "${BASE_URL}/knowledge_base/notes/delete_file" -H 'Content-Type: application/json' -d "${dbody}")
  dcode=$(tail -n1 <<<"${dresp}")
  dbody_json=$(sed '$d' <<<"${dresp}")
  if [[ "${dcode}" != "200" ]] || ! echo "${dbody_json}" | jq -r .status | grep -q 'ok'; then
    echo "delete_file HTTP ${dcode}" >&2
    echo "delete_file response:" >&2
    echo "${dbody_json}" | sed -e 's/^/  /' >&2
    fail "delete_file"
  fi
  pass "delete_file"
  rm -f "${tmp_file}" "${new_tmp_file}" || true
fi

echo "All smoke tests passed."
