#!/usr/bin/env python3
"""Fail-closed HEALTH full-migration runner.

The code is public-safe. Real snapshot packages are private runtime inputs and
must never be committed or uploaded as CI artifacts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

AUTHORIZATION = "FULL_MIGRATION_AUTHORIZED"
DEFAULT_STAGE_SCHEMA = "health_migration_stage"
MANIFEST = "manifest.json"

# Only source-derived/domain columns participate in exact fingerprints.
# Generated technical identities and migration-time timestamps are excluded.
TABLES: dict[str, dict[str, Any]] = {
    "domains": {
        "columns": ["domain_code","label","active","aliases","metadata"],
        "arrays": {"aliases"}, "json": {"metadata"},
    },
    "analytes": {
        "columns": ["analyte_key","display_name","aliases","metadata"],
        "arrays": {"aliases"}, "json": {"metadata"},
    },
    "records": {
        "columns": ["record_id","nnn","record_date","title","type","record_type","confidence","status",
                    "tags","summary","body_text","provenance_status","source_label","source_request_id",
                    "source_pages","metadata"],
        "arrays": {"tags"}, "json": {"metadata"},
    },
    "record_domains": {
        "columns": ["record_id","domain_code"], "arrays": set(), "json": set(),
    },
    "sources": {
        "columns": ["source_id","logical_path","original_filename","mime_type","size_bytes","sha256",
                    "source_date","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "source_locations": {
        "columns": ["source_id","provider","account_alias","provider_object_id","location_role","verified_at"],
        "arrays": set(), "json": set(),
    },
    "record_sources": {
        "columns": ["record_id","source_id","role","source_pages","provenance"],
        "arrays": set(), "json": {"provenance"},
    },
    "cases": {
        "columns": ["case_key","opening_record_id","closing_record_id","category","status","title","summary","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "case_links": {
        "columns": ["case_key","record_id","relation","relation_date","note"],
        "arrays": set(), "json": set(),
    },
    "labs": {
        "columns": ["record_id","analyte_key","value","unit","reference_range","flag","observed_at","observed_on",
                    "source_id","source_locator","source_name","note","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "medications": {
        "columns": ["name","status","dose","schedule","started_on","ended_on","basis_record_id","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "monitoring": {
        "columns": ["title","status","cadence_text","basis_record_id","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "plan_items": {
        "columns": ["title","status","due_on","basis_record_id","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "questions": {
        "columns": ["question","status","basis_record_id","resolved_by_record_id","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
    "id_reservations": {
        "columns": ["nnn","state","record_id","operation_id","reserved_at","metadata"],
        "arrays": set(), "json": {"metadata"},
    },
}

LOAD_ORDER = [
    "domains","analytes","records","record_domains","sources","source_locations","record_sources",
    "cases","case_links","labs","medications","monitoring","plan_items","questions","id_reservations"
]
REC_RE = re.compile(r"^REC-(\d{8})-(\d{3})$")
SRC_RE = re.compile(r"^SRC-[0-9]{8}-[0-9]{3,}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
OLD_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class MigrationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise MigrationError(message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(f"{path.name}: invalid JSON at line {n}: {exc.msg}")
            if not isinstance(value, dict):
                fail(f"{path.name}: line {n} is not an object")
            rows.append(value)
    return rows


def normalized_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    cols = TABLES[table]["columns"]
    unknown = sorted(set(row) - set(cols))
    if unknown:
        fail(f"{table}: unknown columns: {','.join(unknown)}")
    return {col: row.get(col) for col in cols}


def table_fingerprint(table: str, rows: list[dict[str, Any]]) -> str:
    lines = [canonical_json(normalized_row(table, row)) for row in rows]
    lines.sort()
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    return sha256_bytes(payload)


def sealed_package_fingerprint(manifest: dict[str, Any], tables: dict[str, Any]) -> str:
    control = {
        "schema_version": manifest.get("schema_version"),
        "status": manifest.get("status"),
        "capture_mode": manifest.get("capture_mode"),
        "source_location_mode": manifest.get("source_location_mode"),
        "captured_at": manifest.get("captured_at"),
        "old_healthdb_validation_pass": manifest.get("old_healthdb_validation_pass"),
        "old_healthdb_freeze_operation_id": manifest.get("old_healthdb_freeze_operation_id"),
        "old_healthdb_freeze_state": manifest.get("old_healthdb_freeze_state"),
        "old_healthdb_other_unfinished_operations": manifest.get("old_healthdb_other_unfinished_operations"),
        "historical_sources_manifest_sha256": manifest.get("historical_sources_manifest_sha256"),
    }
    descriptor = {
        "control": control,
        "tables": {name: tables[name]["fingerprint"] for name in sorted(LOAD_ORDER)},
    }
    return sha256_bytes(canonical_json(descriptor).encode("utf-8"))


def read_manifest(package: Path) -> dict[str, Any]:
    path = package / MANIFEST
    if not path.is_file():
        fail("manifest.json is missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail("manifest.json must contain an object")
    return value


def read_package(package: Path, require_sealed: bool = True) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest = read_manifest(package)
    if manifest.get("schema_version") != 2:
        fail("manifest schema_version must be 2")
    if manifest.get("status") != "CAPTURED":
        fail("manifest status must be CAPTURED")
    if manifest.get("capture_mode") != "migration":
        fail("manifest capture_mode must be migration")
    if manifest.get("source_location_mode") != "new-health-primary":
        fail("manifest source_location_mode must be new-health-primary")
    if not manifest.get("captured_at"):
        fail("manifest captured_at is required")
    if manifest.get("old_healthdb_validation_pass") is not True:
        fail("old HealthDB Validation PASS is required")
    freeze_operation_id = str(manifest.get("old_healthdb_freeze_operation_id", ""))
    if not OLD_OPERATION_ID_RE.fullmatch(freeze_operation_id):
        fail("old HealthDB migration freeze operation_id is missing or unsafe")
    if manifest.get("old_healthdb_freeze_state") != "PREPARED":
        fail("old HealthDB migration freeze must be PREPARED at capture")
    if int(manifest.get("old_healthdb_other_unfinished_operations", -1)) != 0:
        fail("old HealthDB must have zero unfinished operations other than the migration freeze")
    if not SHA_RE.fullmatch(str(manifest.get("historical_sources_manifest_sha256", ""))):
        fail("historical_sources_manifest_sha256 is required")

    table_meta = manifest.get("tables")
    if require_sealed and not isinstance(table_meta, dict):
        fail("sealed manifest tables are missing")
    if require_sealed and set(table_meta) != set(LOAD_ORDER):
        fail("sealed manifest table set mismatch")

    data: dict[str, list[dict[str, Any]]] = {}
    for table in LOAD_ORDER:
        file_name = f"{table}.jsonl"
        path = package / file_name
        if not path.is_file():
            fail(f"missing {file_name}")
        rows = load_jsonl(path)
        data[table] = rows
        if require_sealed:
            meta = table_meta.get(table)
            if not isinstance(meta, dict):
                fail(f"manifest table metadata missing for {table}")
            if meta.get("file") != file_name:
                fail(f"{table}: manifest file mismatch")
            if int(meta.get("count", -1)) != len(rows):
                fail(f"{table}: count mismatch")
            if meta.get("sha256") != sha256_file(path):
                fail(f"{table}: file SHA-256 mismatch")
            if meta.get("fingerprint") != table_fingerprint(table, rows):
                fail(f"{table}: canonical fingerprint mismatch")
    if require_sealed:
        if manifest.get("sealed") is not True:
            fail("sealed manifest flag missing")
        expected_package_fingerprint = sealed_package_fingerprint(manifest, table_meta)
        if manifest.get("package_fingerprint") != expected_package_fingerprint:
            fail("sealed package fingerprint mismatch")
    return manifest, data


def no_mvp_markers(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "selection_role" or str(key).startswith("mvp_"):
                return False
            if not no_mvp_markers(child):
                return False
    elif isinstance(value, list):
        return all(no_mvp_markers(x) for x in value)
    return True


def validate_data(data: dict[str, list[dict[str, Any]]]) -> None:
    records = data["records"]
    record_ids: set[str] = set()
    nnns: set[int] = set()
    tags_by_record: dict[str, set[str]] = {}
    for row in records:
        rid = row.get("record_id")
        match = REC_RE.fullmatch(str(rid or ""))
        if not match:
            fail("records: invalid record_id")
        nnn = row.get("nnn")
        if not isinstance(nnn, int) or nnn != int(match.group(2)):
            fail(f"records: nnn mismatch for {rid}")
        if rid in record_ids or nnn in nnns:
            fail("records: duplicate record_id or nnn")
        if not str(row.get("body_text") or "").strip():
            fail(f"records: empty body_text for {rid}")
        if not isinstance(row.get("tags", []), list):
            fail(f"records: tags must be an array for {rid}")
        if not no_mvp_markers(row.get("metadata", {})):
            fail("records: representative MVP marker present")
        record_ids.add(rid)
        nnns.add(nnn)
        tags_by_record[rid] = set(str(x) for x in row.get("tags", []))

    domains = {str(r.get("domain_code")) for r in data["domains"]}
    analytes = {str(r.get("analyte_key")) for r in data["analytes"]}

    rd_pairs: set[tuple[str, str]] = set()
    domains_by_record: dict[str, set[str]] = {rid: set() for rid in record_ids}
    for row in data["record_domains"]:
        rid, domain = row.get("record_id"), row.get("domain_code")
        if rid not in record_ids or domain not in domains:
            fail("record_domains: orphan reference")
        pair = (rid, domain)
        if pair in rd_pairs:
            fail("record_domains: duplicate relation")
        rd_pairs.add(pair)
        domains_by_record[rid].add(domain)
    for rid in record_ids:
        if tags_by_record[rid] != domains_by_record[rid]:
            fail(f"record_domains: tags mismatch for {rid}")

    source_ids: set[str] = set()
    for row in data["sources"]:
        sid = str(row.get("source_id") or "")
        if not SRC_RE.fullmatch(sid) or sid in source_ids:
            fail("sources: invalid or duplicate source_id")
        sha = str(row.get("sha256") or "")
        if not SHA_RE.fullmatch(sha):
            fail("sources: missing/invalid sha256")
        size = row.get("size_bytes")
        if not isinstance(size, int) or size < 0:
            fail("sources: invalid size_bytes")
        if not no_mvp_markers(row.get("metadata", {})):
            fail("sources: representative MVP marker present")
        source_ids.add(sid)

    primary_count = {sid: 0 for sid in source_ids}
    location_keys: set[tuple[Any, ...]] = set()
    for row in data["source_locations"]:
        sid = row.get("source_id")
        if sid not in source_ids:
            fail("source_locations: orphan source")
        role = row.get("location_role")
        if role not in ("PRIMARY", "BACKUP"):
            fail("source_locations: invalid location_role")
        key = (sid,row.get("provider"),row.get("account_alias"),role)
        if key in location_keys:
            fail("source_locations: duplicate logical location")
        location_keys.add(key)
        if role == "PRIMARY":
            primary_count[sid] += 1
            if not row.get("verified_at"):
                fail("source_locations: PRIMARY must be verified")
    if any(count != 1 for count in primary_count.values()):
        fail("source_locations: every source must have exactly one verified PRIMARY")

    rs_keys: set[tuple[Any, ...]] = set()
    for row in data["record_sources"]:
        if row.get("record_id") not in record_ids or row.get("source_id") not in source_ids:
            fail("record_sources: orphan reference")
        key = (row.get("record_id"),row.get("source_id"),row.get("role"))
        if key in rs_keys:
            fail("record_sources: duplicate relation")
        rs_keys.add(key)

    cases = {str(r.get("case_key")): r for r in data["cases"]}
    if len(cases) != len(data["cases"]):
        fail("cases: duplicate case_key")
    links_by_case: dict[str, list[dict[str, Any]]] = {k: [] for k in cases}
    for key, row in cases.items():
        if key not in record_ids or row.get("opening_record_id") != key:
            fail("cases: opening identity violation")
        status = row.get("status")
        closing = row.get("closing_record_id")
        if status == "open" and closing is not None:
            fail("cases: open case has closing_record_id")
        if status == "closed" and closing not in record_ids:
            fail("cases: closed case missing valid closing_record_id")
        if status not in ("open","closed"):
            fail("cases: invalid status")
        if not no_mvp_markers(row.get("metadata", {})):
            fail("cases: representative MVP marker present")

    link_keys: set[tuple[Any, ...]] = set()
    for row in data["case_links"]:
        ck, rid, rel = row.get("case_key"), row.get("record_id"), row.get("relation")
        if ck not in cases or rid not in record_ids or rel not in ("OPEN","CONTINUES","CLOSES","FOLLOWUP"):
            fail("case_links: invalid/orphan relation")
        key = (ck,rid,rel)
        if key in link_keys:
            fail("case_links: duplicate relation")
        link_keys.add(key)
        links_by_case[ck].append(row)
    for ck, case in cases.items():
        links = links_by_case[ck]
        opens = [x for x in links if x.get("relation") == "OPEN"]
        closes = [x for x in links if x.get("relation") == "CLOSES"]
        if len(opens) != 1 or opens[0].get("record_id") != ck:
            fail("case_links: case must have exactly one OPEN on case_key")
        if case.get("status") == "open" and closes:
            fail("case_links: open case has CLOSES")
        if case.get("status") == "closed":
            if len(closes) != 1 or closes[0].get("record_id") != case.get("closing_record_id"):
                fail("case_links: closed case CLOSES mismatch")

    lab_seen: set[str] = set()
    for row in data["labs"]:
        if row.get("record_id") not in record_ids or row.get("analyte_key") not in analytes:
            fail("labs: orphan record/analyte")
        if row.get("source_id") is not None and row.get("source_id") not in source_ids:
            fail("labs: orphan source")
        if not isinstance(row.get("value"), str):
            fail("labs: value must be literal text")
        if row.get("reference_range") is not None and not isinstance(row.get("reference_range"), str):
            fail("labs: reference_range must be literal text or null")
        if row.get("metadata", {}).get("literal_preserved") is not True:
            fail("labs: literal_preserved marker missing")
        if not no_mvp_markers(row.get("metadata", {})):
            fail("labs: representative MVP marker present")
        fp = canonical_json(normalized_row("labs", row))
        if fp in lab_seen:
            fail("labs: exact duplicate row")
        lab_seen.add(fp)

    for table, basis_fields in {
        "medications": ["basis_record_id"],
        "monitoring": ["basis_record_id"],
        "plan_items": ["basis_record_id"],
        "questions": ["basis_record_id","resolved_by_record_id"],
    }.items():
        for row in data[table]:
            for field in basis_fields:
                value = row.get(field)
                if value is not None and value not in record_ids:
                    fail(f"{table}: orphan {field}")
            if not no_mvp_markers(row.get("metadata", {})):
                fail(f"{table}: representative MVP marker present")
            if table == "questions":
                if row.get("status") == "open" and row.get("resolved_by_record_id") is not None:
                    fail("questions: open question has resolved_by_record_id")

    used: dict[int, str] = {}
    retired: set[int] = set()
    for row in data["id_reservations"]:
        nnn, state = row.get("nnn"), row.get("state")
        if not isinstance(nnn, int) or nnn < 1 or nnn > 999:
            fail("id_reservations: invalid nnn")
        if nnn in used or nnn in retired:
            fail("id_reservations: duplicate nnn")
        if state == "used":
            rid = row.get("record_id")
            if rid not in record_ids:
                fail("id_reservations: used row must resolve to REC")
            if row.get("operation_id") is not None:
                fail("id_reservations: migrated used operation_id must be null")
            used[nnn] = rid
        elif state == "retired":
            if row.get("record_id") is not None or row.get("operation_id") is not None:
                fail("id_reservations: retired HEALTH row must keep record_id/operation_id null")
            retired.add(nnn)
        else:
            fail("id_reservations: reserved/unknown state is forbidden at full snapshot")
    expected_used = {int(REC_RE.fullmatch(rid).group(2)): rid for rid in record_ids}
    if used != expected_used:
        fail("id_reservations: used ledger does not exactly match records")


def seal_package(package: Path) -> None:
    manifest, data = read_package(package, require_sealed=False)
    validate_data(data)
    tables: dict[str, Any] = {}
    for table in LOAD_ORDER:
        path = package / f"{table}.jsonl"
        tables[table] = {
            "file": path.name,
            "count": len(data[table]),
            "sha256": sha256_file(path),
            "fingerprint": table_fingerprint(table, data[table]),
        }
    manifest["tables"] = tables
    manifest["sealed"] = True
    manifest["package_fingerprint"] = sealed_package_fingerprint(manifest, tables)
    (package / MANIFEST).write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    print(f"PASS package sealed; tables={len(tables)}; rows={sum(x['count'] for x in tables.values())}")


def verify_package(package: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest, data = read_package(package, require_sealed=True)
    validate_data(data)
    print(f"PASS package verified; tables={len(data)}; rows={sum(len(x) for x in data.values())}")
    return manifest, data


def pg_array(values: list[Any]) -> str:
    def q(value: Any) -> str:
        text = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{text}"'
    return "{" + ",".join(q(x) for x in values) + "}"


def csv_value(table: str, column: str, value: Any) -> Any:
    if value is None:
        return r"\N"
    if column in TABLES[table]["arrays"]:
        if not isinstance(value, list):
            fail(f"{table}.{column}: expected array")
        return pg_array(value)
    if column in TABLES[table]["json"]:
        if not isinstance(value, (dict, list)):
            fail(f"{table}.{column}: expected JSON")
        return canonical_json(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def psql_env(db_url_env: str) -> dict[str, str]:
    db_url = os.environ.get(db_url_env)
    if not db_url:
        fail(f"missing environment variable {db_url_env}")
    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = "30"
    return env


def run_psql(sql: str, db_url_env: str, cwd: Path | None = None, capture: bool = False) -> str:
    db_url = os.environ.get(db_url_env)
    if not db_url:
        fail(f"missing environment variable {db_url_env}")
    cmd = ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", db_url]
    result = subprocess.run(
        cmd,
        input=sql.encode("utf-8"),
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        env=psql_env(db_url_env),
        check=False,
    )
    if result.returncode != 0:
        # Never echo private SQL/data-bearing stderr into public CI output.
        fail("psql command failed; inspect private local diagnostics")
    return result.stdout.decode("utf-8") if capture else ""


def sql_ident(value: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
        fail("unsafe SQL identifier")
    return '"' + value + '"'


def write_stage_files(package: Path, data: dict[str, list[dict[str, Any]]], temp: Path) -> list[Path]:
    files: list[Path] = []
    for table in LOAD_ORDER:
        path = temp / f"{table}.csv"
        cols = TABLES[table]["columns"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(cols)
            for row in data[table]:
                normalized = normalized_row(table, row)
                writer.writerow([csv_value(table, col, normalized[col]) for col in cols])
        files.append(path)
    return files


def stage_package(package: Path, db_url_env: str, schema: str) -> None:
    _, data = verify_package(package)
    sid = sql_ident(schema)
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="health-migration-") as raw:
        temp = Path(raw)
        write_stage_files(package, data, temp)
        lines = [
            f"drop schema if exists {sid} cascade;",
            f"create schema {sid};",
        ]
        for table in LOAD_ORDER:
            lines.append(f"create table {sid}.{sql_ident(table)} (like public.{sql_ident(table)} including all);")
        for table in LOAD_ORDER:
            cols = ",".join(sql_ident(x) for x in TABLES[table]["columns"])
            path = (temp / f"{table}.csv").as_posix().replace("'", "''")
            lines.append(
                f"\\copy {sid}.{sql_ident(table)} ({cols}) from '{path}' "
                "with (format csv, header true, null '\\N');"
            )
        run_psql("\n".join(lines) + "\n", db_url_env)
    compare_target(package, db_url_env, schema)
    print(f"PASS staging loaded and fingerprint-matched; schema={schema}")


def target_rows(table: str, db_url_env: str, schema: str) -> list[dict[str, Any]]:
    sid = sql_ident(schema)
    cols = TABLES[table]["columns"]
    projection = ",".join(sql_ident(c) for c in cols)
    sql = (
        "copy (select row_to_json(x)::text from "
        f"(select {projection} from {sid}.{sql_ident(table)}) x) to stdout;\n"
    )
    output = run_psql(sql, db_url_env, capture=True)
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                fail(f"{schema}.{table}: unexpected row encoding")
            rows.append(value)
    return rows


def compare_target(package: Path, db_url_env: str, schema: str) -> None:
    manifest, _ = verify_package(package)
    for table in LOAD_ORDER:
        rows = target_rows(table, db_url_env, schema)
        meta = manifest["tables"][table]
        if len(rows) != int(meta["count"]):
            fail(f"{schema}.{table}: row count mismatch")
        if table_fingerprint(table, rows) != meta["fingerprint"]:
            fail(f"{schema}.{table}: exact fingerprint mismatch")
    print(f"PASS exact target comparison; schema={schema}; tables={len(LOAD_ORDER)}")


def commit_stage(package: Path, db_url_env: str, schema: str, operation_id: str, authorization: str) -> None:
    if authorization != AUTHORIZATION:
        fail("explicit full-migration authorization token missing")
    if not UUID_RE.fullmatch(operation_id):
        fail("invalid operation_id")
    manifest, _ = verify_package(package)
    compare_target(package, db_url_env, schema)

    sid = sql_ident(schema)
    med_tables = ",".join(f"public.{sql_ident(t)}" for t in LOAD_ORDER)
    inserts = []
    for table in LOAD_ORDER:
        cols = ",".join(sql_ident(c) for c in TABLES[table]["columns"])
        inserts.append(
            f"insert into public.{sql_ident(table)} ({cols}) "
            f"select {cols} from {sid}.{sql_ident(table)};"
        )

    snapshot = {
        "status": "CAPTURED",
        "captured_at": manifest["captured_at"],
        "old_healthdb_validation_pass": manifest["old_healthdb_validation_pass"],
        "old_healthdb_freeze_operation_id": manifest["old_healthdb_freeze_operation_id"],
        "old_healthdb_freeze_state": manifest["old_healthdb_freeze_state"],
        "old_healthdb_other_unfinished_operations": manifest["old_healthdb_other_unfinished_operations"],
        "expected_counts": {t: manifest["tables"][t]["count"] for t in LOAD_ORDER},
        "table_fingerprints": {t: manifest["tables"][t]["fingerprint"] for t in LOAD_ORDER},
        "package_fingerprint": manifest.get("package_fingerprint"),
        "historical_sources_manifest_sha256": manifest["historical_sources_manifest_sha256"],
    }
    snapshot_json = canonical_json(snapshot).replace("'", "''")

    sql = f"""
begin;
do $$
declare v_count integer;
begin
  select count(*) into v_count
  from public.operations
  where state in ('PREPARED','COMMITTED_REGISTRY','VALIDATED')
    and operation_id <> '{operation_id}'::uuid;
  if v_count <> 0 then
    raise exception 'another unfinished HEALTH operation exists';
  end if;
  if not exists (
    select 1 from public.operations
    where operation_id='{operation_id}'::uuid and state='PREPARED'
  ) then
    raise exception 'migration operation must exist in PREPARED';
  end if;
end $$;

truncate {med_tables} restart identity;

{chr(10).join(inserts)}

insert into public.system_state(key,value,updated_at)
values ('full_migration_snapshot','{snapshot_json}'::jsonb,now())
on conflict (key) do update
set value=excluded.value, updated_at=excluded.updated_at;

update public.operations
set state='COMMITTED_REGISTRY',
    updated_at=now(),
    notes=coalesce(notes,'') || ' Full medical domain replaced from sealed Drive snapshot; exact post-commit comparison still required.'
where operation_id='{operation_id}'::uuid and state='PREPARED';

commit;
"""
    run_psql(sql, db_url_env)
    print("PASS staging committed to public; operation=COMMITTED_REGISTRY; final validation still required")


def execute_full_migration(
    package: Path,
    db_url_env: str,
    schema: str,
    operation_id: str,
    source_freeze_operation_id: str,
    authorization: str,
) -> None:
    if authorization != AUTHORIZATION:
        fail("explicit full-migration authorization token missing")
    manifest, _ = verify_package(package)
    if source_freeze_operation_id != manifest["old_healthdb_freeze_operation_id"]:
        fail("source freeze confirmation does not match sealed package")

    stage_package(package, db_url_env, schema)
    commit_stage(package, db_url_env, schema, operation_id, authorization)
    compare_target(package, db_url_env, "public")
    print(
        "PASS full migration execution chain through exact public comparison; "
        "operation remains COMMITTED_REGISTRY pending validations"
    )


def cleanup_stage(db_url_env: str, schema: str, authorization: str) -> None:
    if authorization != AUTHORIZATION:
        fail("explicit full-migration authorization token missing")
    run_psql(f"drop schema if exists {sql_ident(schema)} cascade;\n", db_url_env)
    print(f"PASS staging schema removed; schema={schema}")


def self_test() -> None:
    sample = [{"b": 2, "a": "x"}, {"a": "y", "b": 1}]
    a = sha256_bytes(("\n".join(sorted(canonical_json(x) for x in sample)) + "\n").encode())
    b = sha256_bytes(("\n".join(sorted(canonical_json(x) for x in reversed(sample))) + "\n").encode())
    if a != b:
        fail("self-test canonical order failed")
    if pg_array(["a", 'b"c']) != '{"a","b\\\"c"}':
        fail("self-test array encoding failed")

    with tempfile.TemporaryDirectory(prefix="health-migration-selftest-") as raw:
        package = Path(raw)
        manifest = {
            "schema_version": 2,
            "status": "CAPTURED",
            "capture_mode": "migration",
            "source_location_mode": "new-health-primary",
            "captured_at": "2026-01-01T00:00:00Z",
            "old_healthdb_validation_pass": True,
            "old_healthdb_freeze_operation_id": "MAINT-999",
            "old_healthdb_freeze_state": "PREPARED",
            "old_healthdb_other_unfinished_operations": 0,
            "historical_sources_manifest_sha256": "0" * 64,
            "tables": {},
        }
        (package / MANIFEST).write_text(canonical_json(manifest) + "\n", encoding="utf-8")
        synthetic = {
            "domains": [{"domain_code":"general","label":"General","active":True,"aliases":[],"metadata":{}}],
            "analytes": [{"analyte_key":"synthetic","display_name":"Synthetic","aliases":[],"metadata":{}}],
            "records": [{
                "record_id":"REC-20260101-001","nnn":1,"record_date":"2026-01-01","title":"Synthetic",
                "type":"medical-record","record_type":"synthetic","confidence":"test","status":"active",
                "tags":["general"],"summary":"Synthetic only","body_text":"# Synthetic\nTest body",
                "provenance_status":"not-applicable","source_label":None,"source_request_id":None,
                "source_pages":None,"metadata":{}
            }],
            "record_domains": [{"record_id":"REC-20260101-001","domain_code":"general"}],
            "sources": [{
                "source_id":"SRC-20260101-001","logical_path":"synthetic/source","original_filename":"synthetic.txt",
                "mime_type":"text/plain","size_bytes":1,"sha256":"a"*64,"source_date":"2026-01-01","metadata":{}
            }],
            "source_locations": [{
                "source_id":"SRC-20260101-001","provider":"google-drive","account_alias":"HEALTH_PRIMARY",
                "provider_object_id":"synthetic-object","location_role":"PRIMARY","verified_at":"2026-01-01T00:00:00Z"
            }],
            "record_sources": [{
                "record_id":"REC-20260101-001","source_id":"SRC-20260101-001","role":"evidence",
                "source_pages":None,"provenance":{}
            }],
            "cases": [{
                "case_key":"REC-20260101-001","opening_record_id":"REC-20260101-001","closing_record_id":None,
                "category":"episode","status":"open","title":"Synthetic","summary":None,"metadata":{}
            }],
            "case_links": [{
                "case_key":"REC-20260101-001","record_id":"REC-20260101-001","relation":"OPEN",
                "relation_date":"2026-01-01","note":None
            }],
            "labs": [{
                "record_id":"REC-20260101-001","analyte_key":"synthetic","value":"1.0","unit":None,
                "reference_range":None,"flag":None,"observed_at":None,"observed_on":"2026-01-01",
                "source_id":"SRC-20260101-001","source_locator":None,"source_name":"Synthetic","note":None,
                "metadata":{"literal_preserved":True}
            }],
            "medications": [],
            "monitoring": [],
            "plan_items": [],
            "questions": [],
            "id_reservations": [{
                "nnn":1,"state":"used","record_id":"REC-20260101-001","operation_id":None,
                "reserved_at":None,"metadata":{}
            }],
        }
        for table in LOAD_ORDER:
            with (package / f"{table}.jsonl").open("w", encoding="utf-8") as out:
                for row in synthetic[table]:
                    out.write(canonical_json(row) + "\n")
        seal_package(package)
        verify_package(package)

        sealed = read_manifest(package)
        original_freeze = sealed["old_healthdb_freeze_operation_id"]
        sealed["old_healthdb_freeze_operation_id"] = "MAINT-998"
        (package / MANIFEST).write_text(canonical_json(sealed) + "\n", encoding="utf-8")
        try:
            verify_package(package)
            fail("self-test control-metadata tamper was not detected")
        except MigrationError as exc:
            if str(exc) != "sealed package fingerprint mismatch":
                raise
        sealed["old_healthdb_freeze_operation_id"] = original_freeze
        (package / MANIFEST).write_text(canonical_json(sealed) + "\n", encoding="utf-8")
        verify_package(package)

    print("PASS migration runner self-test")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("seal")
    p.add_argument("package", type=Path)

    p = sub.add_parser("verify")
    p.add_argument("package", type=Path)

    p = sub.add_parser("stage")
    p.add_argument("package", type=Path)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")
    p.add_argument("--schema", default=DEFAULT_STAGE_SCHEMA)

    p = sub.add_parser("compare")
    p.add_argument("package", type=Path)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")
    p.add_argument("--schema", default="public")

    p = sub.add_parser("commit")
    p.add_argument("package", type=Path)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")
    p.add_argument("--schema", default=DEFAULT_STAGE_SCHEMA)
    p.add_argument("--operation-id", required=True)
    p.add_argument("--authorization", required=True)

    p = sub.add_parser("execute")
    p.add_argument("package", type=Path)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")
    p.add_argument("--schema", default=DEFAULT_STAGE_SCHEMA)
    p.add_argument("--operation-id", required=True)
    p.add_argument("--source-freeze-operation-id", required=True)
    p.add_argument("--authorization", required=True)

    p = sub.add_parser("cleanup-stage")
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")
    p.add_argument("--schema", default=DEFAULT_STAGE_SCHEMA)
    p.add_argument("--authorization", required=True)

    sub.add_parser("self-test")

    args = parser.parse_args()
    if args.command == "seal":
        seal_package(args.package)
    elif args.command == "verify":
        verify_package(args.package)
    elif args.command == "stage":
        stage_package(args.package, args.db_url_env, args.schema)
    elif args.command == "compare":
        compare_target(args.package, args.db_url_env, args.schema)
    elif args.command == "commit":
        commit_stage(args.package, args.db_url_env, args.schema, args.operation_id, args.authorization)
    elif args.command == "execute":
        execute_full_migration(
            args.package,
            args.db_url_env,
            args.schema,
            args.operation_id,
            args.source_freeze_operation_id,
            args.authorization,
        )
    elif args.command == "cleanup-stage":
        cleanup_stage(args.db_url_env, args.schema, args.authorization)
    elif args.command == "self-test":
        self_test()


if __name__ == "__main__":
    try:
        main()
    except MigrationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
