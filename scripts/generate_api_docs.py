#!/usr/bin/env python3
"""
Generate Markdown API documentation from the live FastAPI OpenAPI schema.

Usage:
  BASE_URL=http://localhost:8000 python scripts/generate_api_docs.py

Outputs docs/API_REFERENCE.md with endpoints, parameters, request/response schemas, and examples when available.
"""
from __future__ import annotations

import os
import sys
import json
import datetime as dt
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Any, Dict, List, Optional


def fetch_openapi(base_url: str) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/openapi.json"
    try:
        req = Request(url, headers={"User-Agent": "BOR-Docs-Generator"})
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        print(f"ERROR: Unable to fetch OpenAPI from {url}: {e}", file=sys.stderr)
        sys.exit(1)


def ref_target(ref: str) -> str:
    # '#/components/schemas/Name' -> ('schemas', 'Name')
    parts = ref.strip('#/').split('/')
    return parts[-1]


def resolve_schema(schema: Dict[str, Any], components: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "unknown"}
    if "$ref" in schema:
        name = ref_target(schema["$ref"])
        target = components.get("schemas", {}).get(name, {})
        resolved = resolve_schema(target, components)
        # Attach title for clarity
        if "title" not in resolved:
            resolved["title"] = name
        return resolved
    # Handle simple allOf by merging properties
    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for part in schema["allOf"]:
            part_res = resolve_schema(part, components)
            if part_res.get("type") == "object":
                merged["properties"].update(part_res.get("properties", {}))
                merged["required"] = list(set(merged.get("required", []) + part_res.get("required", [])))
        return merged
    return schema


def schema_to_md(schema: Dict[str, Any], components: Dict[str, Any], indent: int = 0) -> List[str]:
    s = resolve_schema(schema, components)
    lines: List[str] = []
    ind = "  " * indent
    s_type = s.get("type", "object")
    title = s.get("title")
    if title:
        lines.append(f"{ind}- schema: {title}")
    lines.append(f"{ind}- type: {s_type}")
    if s_type == "array":
        items = s.get("items", {})
        lines.append(f"{ind}- items:")
        lines.extend(schema_to_md(items, components, indent + 1))
        return lines
    if s_type == "object":
        props = s.get("properties", {}) or {}
        required = set(s.get("required", []) or [])
        if props:
            lines.append(f"{ind}- properties:")
            for name, prop in props.items():
                rmark = "*" if name in required else ""
                p = resolve_schema(prop, components)
                p_type = p.get("type", "object")
                desc = p.get("description")
                lines.append(f"{ind}  - {name}{rmark}: {p_type}")
                if desc:
                    lines.append(f"{ind}    - desc: {desc}")
                # Handle array items briefly
                if p_type == "array":
                    item = p.get("items", {})
                    item_res = resolve_schema(item, components)
                    lines.append(f"{ind}    - items: {item_res.get('type', 'object')}")
    return lines


def extract_example(media: Dict[str, Any]) -> Optional[Any]:
    # Try standard fields for an example
    if "example" in media:
        return media["example"]
    examples = media.get("examples")
    if isinstance(examples, dict) and examples:
        # Pick the first example value
        ex = next(iter(examples.values()))
        if isinstance(ex, dict) and "value" in ex:
            return ex["value"]
    # Some generators put example under schema
    schema = media.get("schema")
    if isinstance(schema, dict) and "example" in schema:
        return schema["example"]
    return None


def generate_md(spec: Dict[str, Any]) -> str:
    title = spec.get("info", {}).get("title", "BOR API")
    version = spec.get("info", {}).get("version", "")
    date_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    components = spec.get("components", {})
    paths = spec.get("paths", {})

    lines: List[str] = []
    lines.append(f"# {title} Reference")
    lines.append("")
    lines.append(f"Version: {version}  ")
    lines.append(f"Generated: {date_str}")
    lines.append("")
    lines.append("This document is generated from the live OpenAPI schema (/openapi.json).")
    lines.append("")

    # Sort paths for stable output
    for path in sorted(paths.keys()):
        item = paths[path]
        # Methods are lowercased keys like get/post/put
        methods = [m for m in item.keys() if m.islower()]
        for method in sorted(methods):
            op = item[method]
            summary = op.get("summary") or ""
            desc = op.get("description") or ""
            lines.append(f"## {method.upper()} {path}")
            if summary:
                lines.append("")
                lines.append(summary)
            if desc and desc != summary:
                lines.append("")
                lines.append(desc)

            # Parameters (query/path)
            params = op.get("parameters", [])
            if params:
                lines.append("")
                lines.append("### Parameters")
                for p in params:
                    name = p.get("name")
                    loc = p.get("in")
                    req = p.get("required", False)
                    schema = p.get("schema", {})
                    ptype = schema.get("type", "object")
                    pdesc = p.get("description") or ""
                    req_mark = " (required)" if req else ""
                    lines.append(f"- {name} [{loc}] : {ptype}{req_mark}")
                    if pdesc:
                        lines.append(f"  - {pdesc}")

            # Request body
            rb = op.get("requestBody")
            if rb:
                lines.append("")
                lines.append("### Request body")
                required = rb.get("required", False)
                if required:
                    lines.append("- required: true")
                content = rb.get("content", {})
                for ctype, media in content.items():
                    lines.append(f"- content-type: {ctype}")
                    schema = media.get("schema", {})
                    sch_lines = schema_to_md(schema, components, indent=1)
                    for l in sch_lines:
                        lines.append(f"  {l}")
                    example = extract_example(media)
                    if example is not None:
                        lines.append("")
                        lines.append("Example:")
                        lines.append("")
                        lines.append("```json")
                        lines.append(json.dumps(example, indent=2))
                        lines.append("```")

            # Responses
            resps = op.get("responses", {})
            if resps:
                lines.append("")
                lines.append("### Responses")
                for code, r in resps.items():
                    desc = r.get("description") or ""
                    lines.append(f"- {code}: {desc}")
                    content = r.get("content", {})
                    for ctype, media in content.items():
                        lines.append(f"  - content-type: {ctype}")
                        schema = media.get("schema", {})
                        sch_lines = schema_to_md(schema, components, indent=2)
                        for l in sch_lines:
                            lines.append(f"    {l}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").strip()
    spec = fetch_openapi(base_url)
    md = generate_md(spec)
    out_dir = os.path.join(os.getcwd(), "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "API_REFERENCE.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
