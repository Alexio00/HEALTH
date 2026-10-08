#!/usr/bin/env python3
"""Fail-closed HEALTH full-migration runner.

The code is public-safe. Real snapshot packages are private runtime inputs and
must never be committed or uploaded as CI artifacts.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable

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


# PostgreSQL emits timestamptz UTC with '+00:00'; Drive capture emits 'Z'.
# Normalize instants BEFORE hashing either side, never alter the stored source.
TIMESTAMPTZ_FIELDS = {
    "source_locations": {"verified_at"},
    "id_reservations": {"reserved_at"},
    "labs": {"observed_at"},
}


def canonical_timestamp(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        fail("timestamp fingerprint value must be an ISO timestamp string")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail("invalid timestamp in migration fingerprint")
    if stamp.tzinfo is None:
        fail("timezone-less timestamp in migration fingerprint")
    return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")


def normalized_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    cols = TABLES[table]["columns"]
    unknown = sorted(set(row) - set(cols))
    if unknown:
        fail(f"{table}: unknown columns: {','.join(unknown)}")
    out = {col: row.get(col) for col in cols}
    for field in TIMESTAMPTZ_FIELDS.get(table, ()):
        out[field] = canonical_timestamp(out[field])
    return out


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
            if row.get("provider") != "google-drive" or row.get("account_alias") != "HEALTH_PRIMARY":
                fail("source_locations: PRIMARY must be the new HEALTH Google Drive")
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
    # CSV encoding preserves literal backslashes/newlines embedded in JSON.
    # COPY's default text mode double-escapes JSON backslashes, silently
    # distorting medical body_text and other values before hashing.
    sql = (
        "copy (select row_to_json(x)::text from "
        f"(select {projection} from {sid}.{sql_ident(table)}) x) to stdout with (format csv);\n"
    )
    output = run_psql(sql, db_url_env, capture=True)
    rows: list[dict[str, Any]] = []
    for fields in csv.reader(io.StringIO(output)):
        if len(fields) != 1:
            fail(f"{schema}.{table}: unexpected COPY CSV encoding")
        value = json.loads(fields[0])
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


def commit_stage(
    package: Path, db_url_env: str, schema: str, operation_id: str,
    authorization: str, source_gate: Callable[[], None] | None = None,
) -> None:
    # The private scheduler must prove the live old Drive state immediately
    # before production commit. CLI/direct invocations cannot supply this.
    if source_gate is None:
        fail("live old-HealthDB source attestation required; use private scheduler migrate")
    if authorization != AUTHORIZATION:
        fail("explicit full-migration authorization token missing")
    if not UUID_RE.fullmatch(operation_id):
        fail("invalid operation_id")
    manifest, _ = verify_package(package)
    compare_target(package, db_url_env, schema)
    source_gate()  # live Registry + REC Docs + original Sources + Historical

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
  -- Knowing the public authorization string is NOT owner approval.
  -- Require a separate operation-bound authorization in private system_state.
  if not exists (
    select 1 from public.system_state
    where key='full_migration_readiness'
      and value->>'full_migration_authorized'='true'
      and value->>'owner_authorized_operation_id'='{operation_id}'
      and value->>'owner_authorized_freeze_operation_id'='{manifest["old_healthdb_freeze_operation_id"]}'
  ) then
    raise exception 'operation-bound owner authorization is absent';
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

    fail("public execute is disabled: live Drive revalidation must run in private scheduler migrate")
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


def sql_scalar(db_url_env: str, query: str) -> str:
    # COPY TO STDOUT avoids locale-dependent psql header formatting.
    output = run_psql(f"copy ({query}) to stdout with (format csv);\n", db_url_env, capture=True)
    records = list(csv.reader(io.StringIO(output)))
    if len(records) != 1 or len(records[0]) != 1:
        fail("expected one database scalar")
    return records[0][0]


def recovery_evidence_contract(evidence: dict[str, Any], snapshot: dict[str, Any], operation_id: str) -> None:
    """Require operation-bound, content-addressed independent recovery artifacts.

    This is only the *contract*. The private recovery_gate MUST retrieve and
    authenticate the actual immutable backup, source and restore artifacts.
    No row in system_state can attest to its own truth.
    """
    required = ("operation_id", "package_fingerprint", "backup_snapshot_id",
                "backup_manifest_sha256", "source_manifest_path",
                "source_manifest_sha256", "restore_evidence_path",
                "restore_evidence_sha256", "restore_run_id",
                "restored_table_fingerprints")
    if not isinstance(evidence, dict) or any(not evidence.get(k) for k in required):
        fail("postcommit recovery artifact contract incomplete")
    if (evidence["operation_id"] != operation_id
            or evidence["package_fingerprint"] != snapshot.get("package_fingerprint")):
        fail("postcommit recovery proof belongs to another migration")
    if not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}T\\d{2}-\\d{2}-\\d{2}Z", str(evidence["backup_snapshot_id"])):
        fail("postcommit invalid backup snapshot identifier")
    for key in ("backup_manifest_sha256", "source_manifest_sha256", "restore_evidence_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", str(evidence[key])):
            fail("postcommit invalid independent artifact digest")
    if (not isinstance(evidence["restore_run_id"], str)
            or not re.fullmatch(r"[1-9][0-9]*", evidence["restore_run_id"])):
        fail("postcommit invalid restore run identifier")
    for key in ("source_manifest_path", "restore_evidence_path"):
        value = evidence[key]
        if not isinstance(value, str) or not value or ".." in Path(value).parts or value.startswith("/"):
            fail("postcommit invalid recovery artifact path")
    fingerprints = evidence["restored_table_fingerprints"]
    if (not isinstance(fingerprints, dict) or set(fingerprints) != set(LOAD_ORDER)
            or any(not re.fullmatch(r"[a-f0-9]{64}", str(v)) for v in fingerprints.values())):
        fail("postcommit incomplete independent restored-table evidence")


def postcommit_verification(
    db_url_env: str, operation_id: str,
    recovery_gate: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> None:
    """Read-only operation-scoped gate with mandatory private artifact inspection."""

    if not UUID_RE.fullmatch(operation_id):
        fail("postcommit invalid operation ID")
    state = sql_scalar(
        db_url_env,
        f"select state from public.operations where operation_id='{operation_id}'::uuid",
    )
    if state != "COMMITTED_REGISTRY":
        fail("postcommit operation is not COMMITTED_REGISTRY")
    raw = sql_scalar(
        db_url_env,
        "select value::text from public.system_state where key='full_migration_snapshot'",
    )
    snapshot = json.loads(raw)
    expected = snapshot.get("table_fingerprints")
    if snapshot.get("status") != "CAPTURED" or not isinstance(expected, dict) or set(expected) != set(LOAD_ORDER):
        fail("postcommit missing sealed expected table fingerprints")
    for table in LOAD_ORDER:
        rows = target_rows(table, db_url_env, "public")
        if table_fingerprint(table, rows) != expected[table]:
            fail(f"postcommit source-to-target table mismatch: {table}")

    root = Path(__file__).resolve().parents[1] / "validation"
    check_sql = (root / "full_migration_invariants.sql").read_text(encoding="utf-8")
    result = run_psql(check_sql, db_url_env, capture=True)
    statuses = re.findall(r"^\s*([A-Z][A-Z0-9_]+)\s*\|\s*(PASS|FAIL|WAITING)\s*$", result, re.M)
    if not statuses or any(status != "PASS" for _, status in statuses):
        fail("postcommit full-migration SQL invariants not all PASS")
    for test in ("security_invariants.sql", "auth_invariants.sql"):
        run_psql((root / test).read_text(encoding="utf-8"), db_url_env)

    # Semantic OPERATION_AUDIT is never inferred from a generic SQL PASS.
    deps = ",".join("'" + t + "'" for t in LOAD_ORDER)
    missing = sql_scalar(
        db_url_env,
        "select count(*) from public.validation_checks c "
        "left join public.validation_results r on r.check_key=c.check_key "
        f"and r.operation_id='{operation_id}'::uuid "
        "where c.active and c.mechanism='OPERATION_AUDIT' "
        f"and (c.dependencies && array[{deps}]::text[] or c.check_key like 'FULL_MIGRATION_%') "
        "and coalesce(r.status,'MISSING')<>'PASS'",
    )
    if missing != "0":
        fail("postcommit impacted operation audits are not all stamped PASS")
    evidence_raw = sql_scalar(
        db_url_env,
        "select value::text from public.system_state where key='full_migration_recovery_evidence'",
    )
    evidence = json.loads(evidence_raw)
    recovery_evidence_contract(evidence, snapshot, operation_id)
    # Mandatory PRIVATE implementation: re-read independently stored backup
    # MANIFEST, Source locator manifest, exact restore-run artifact and digests,
    # verify authenticated run success and correspondence to all 15 restored
    # tables. The public CLI intentionally supplies no gate and FAILS closed.
    if recovery_gate is None:
        fail("postcommit requires private independent recovery-artifact verification")
    recovery_gate(evidence, snapshot)
    print(f"PASS read-only postcommit verification; tables={len(LOAD_ORDER)}; checks={len(statuses)}")


def finalize_verified_operation(
    db_url_env: str, operation_id: str, authorization: str,
    recovery_gate: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> None:
    if authorization != AUTHORIZATION:
        fail("finalization requires explicit owner authorization")
    if not UUID_RE.fullmatch(operation_id):
        fail("invalid finalization operation ID")
    postcommit_verification(db_url_env, operation_id, recovery_gate=recovery_gate)
    # Recheck state/owner binding inside the same transaction as both state
    # transitions, so competing operations cannot invalidate the preflight.
    sql = f"""
begin;
do $$
begin
  if not exists (
    select 1 from public.operations
    where operation_id='{operation_id}'::uuid and state='COMMITTED_REGISTRY'
  ) then
    raise exception 'target migration operation has changed';
  end if;
  if not exists (
    select 1 from public.system_state
    where key='full_migration_readiness'
      and value->>'full_migration_authorized'='true'
      and value->>'owner_authorized_operation_id'='{operation_id}'
  ) then
    raise exception 'operation-specific owner authorization not present';
  end if;
end $$;
update public.operations
set state='VALIDATED', updated_at=now()
where operation_id='{operation_id}'::uuid and state='COMMITTED_REGISTRY';
update public.operations
set state='FINALIZED', result='PASS', updated_at=now(), finalized_at=now()
where operation_id='{operation_id}'::uuid and state='VALIDATED';
commit;
"""
    run_psql(sql, db_url_env)
    print("PASS full-migration operation FINALIZED; legacy freeze and cutover remain separate")


def mark_interrupted_migration_failed(db_url_env: str, operation_id: str, confirmation: str) -> None:
    if confirmation != "MARK_TARGET_FAILED_KEEP_LEGACY_FREEZE":
        fail("explicit failed-operation confirmation required")
    if not UUID_RE.fullmatch(operation_id):
        fail("invalid failed-operation ID")
    sql = f"""
begin;
do $$
begin
  if not exists (
    select 1 from public.operations
    where operation_id='{operation_id}'::uuid
      and state in ('PREPARED','COMMITTED_REGISTRY','VALIDATED')
  ) then
    raise exception 'no unfinished target operation to mark FAILED';
  end if;
end $$;
update public.operations
set state='FAILED', result='FAIL', updated_at=now(),
    notes=coalesce(notes,'') || ' Target migration interrupted; old source remains canonical; freeze requires separate review.'
where operation_id='{operation_id}'::uuid
  and state in ('PREPARED','COMMITTED_REGISTRY','VALIDATED');
commit;
"""
    run_psql(sql, db_url_env)
    print("Target operation failure recorded; never automatically released old freeze")


def postgresql_roundtrip_test() -> None:
    # Strictly local, synthetic-only integration test; NEVER a production URL.
    from urllib.parse import urlparse
    url = os.environ.get("HEALTH_SYNTHETIC_DB_URL", "")
    if urlparse(url).hostname not in {"localhost", "127.0.0.1"}:
        fail("PostgreSQL synthetic roundtrip requires local-only test database")
    os.environ["HEALTH_ROUNDTRIP_URL"] = url
    schema = "health_synthetic_roundtrip"
    sql = f"""
drop schema if exists {schema} cascade;
create schema {schema};
create table {schema}.source_locations (
    source_id text,provider text,account_alias text,
    provider_object_id text,location_role text,verified_at timestamptz
);
insert into {schema}.source_locations values
('SRC-20261007-001','google-drive','HEALTH_PRIMARY','synthetic-1','PRIMARY','2026-10-08T12:00:00Z'),
('SRC-20261007-002','google-drive','HEALTH_PRIMARY','synthetic-2' || chr(92) || 'slash' || chr(10) || 'newline','PRIMARY','2026-10-08T15:00:00+03:00');
"""
    expected = [
        {"source_id": f"SRC-20261007-00{i}",
         "provider": "google-drive", "account_alias": "HEALTH_PRIMARY",
         "provider_object_id": (f"synthetic-{i}" if i == 1 else "synthetic-2" + chr(92) + "slash" + chr(10) + "newline"), "location_role": "PRIMARY",
         "verified_at": "2026-10-08T12:00:00Z"}
        for i in (1, 2)
    ]
    run_psql(sql, "HEALTH_ROUNDTRIP_URL")
    try:
        rows = target_rows("source_locations", "HEALTH_ROUNDTRIP_URL", schema)
        if table_fingerprint("source_locations", rows) != table_fingerprint("source_locations", expected):
            fail("PostgreSQL timestamptz source fingerprint roundtrip mismatch")
        probe = run_psql(
            "copy (select count(*) from jsonb_object_keys(jsonb_build_object('a',1,'b',2))) to stdout;",
            "HEALTH_ROUNDTRIP_URL", capture=True,
        )
        if probe.strip() != "2":
            fail("PostgreSQL JSONB object count test mismatch")
    finally:
        run_psql(f"drop schema if exists {schema} cascade;", "HEALTH_ROUNDTRIP_URL")
    print("PASS synthetic PostgreSQL 17 timestamptz/jsonb roundtrip")


def make_synthetic_package(package: Path) -> None:
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


def local_full_cycle_test() -> None:
    """Destructive operations ONLY in a fresh localhost synthetic PostgreSQL."""
    from urllib.parse import urlparse
    url = os.environ.get("HEALTH_SYNTHETIC_DB_URL", "")
    if urlparse(url).hostname not in {"127.0.0.1", "localhost"}:
        fail("synthetic full cycle needs loopback PostgreSQL")
    os.environ["HEALTH_CYCLE_URL"] = url
    env = "HEALTH_CYCLE_URL"
    repo = Path(__file__).resolve().parents[2]
    for migration in ("0001_core.sql", "0004_mvp_fidelity.sql", "0006_id_reservations_metadata.sql"):
        run_psql((repo / "db" / "migrations" / migration).read_text(encoding="utf-8"), env)
    op = "11111111-1111-4111-8111-111111111111"
    second = "22222222-2222-4222-8222-222222222222"
    with tempfile.TemporaryDirectory(prefix="health-local-fullcycle-") as directory:
        package = Path(directory)
        make_synthetic_package(package)
        stage_package(package, env, DEFAULT_STAGE_SCHEMA)
        run_psql(
            "insert into public.operations(operation_id,operation,mode,state) values "
            f"('{op}'::uuid,'synthetic-full-migration','maintenance','PREPARED');"
            "insert into public.system_state(key,value) values "
            "('full_migration_readiness','{\"full_migration_authorized\":false}'::jsonb);",
            env,
        )
        # No private source callback -> no write.
        try:
            commit_stage(package, env, DEFAULT_STAGE_SCHEMA, op, AUTHORIZATION)
            fail("direct commit without full source guard accepted")
        except MigrationError as exc:
            if "source attestation required" not in str(exc):
                raise
        # A stale source is rejected, even when the package is sealed.
        guard_calls = []
        def reject_stale() -> None:
            guard_calls.append("called")
            fail("synthetic original REC content changed")
        try:
            commit_stage(package, env, DEFAULT_STAGE_SCHEMA, op, AUTHORIZATION, reject_stale)
            fail("stale original accepted")
        except MigrationError as exc:
            if "synthetic original REC content changed" not in str(exc):
                raise
        if guard_calls != ["called"]:
            fail("live source guard was skipped")

        # Literal authorization alone cannot bypass owner-bound state.
        try:
            commit_stage(package, env, DEFAULT_STAGE_SCHEMA, op, AUTHORIZATION, lambda: None)
            fail("operation without owner authorization committed")
        except MigrationError as exc:
            if "psql command failed" not in str(exc):
                raise
        if sql_scalar(env, "select state from public.operations where operation_id='" + op + "'::uuid") != "PREPARED":
            fail("denied commit changed target operation")
        if sql_scalar(env, "select count(*) from public.records") != "0":
            fail("denied commit inserted a medical row")
        if sql_scalar(env, "select count(*) from public.system_state where key='full_migration_snapshot'") != "0":
            fail("denied commit recorded a snapshot")

        run_psql(
            "update public.system_state set value="
            f"jsonb_build_object('full_migration_authorized',true,'owner_authorized_operation_id','{op}',"
            "'owner_authorized_freeze_operation_id','MAINT-999') "
            "where key='full_migration_readiness';",
            env,
        )
        commit_stage(package, env, DEFAULT_STAGE_SCHEMA, op, AUTHORIZATION, lambda: None)
        compare_target(package, env, "public")
        if sql_scalar(env, f"select state from public.operations where operation_id='{op}'::uuid") != "COMMITTED_REGISTRY":
            fail("successful commit not in COMMITTED_REGISTRY")
        # Finalization must reject missing semantic audits/recovery proofs.
        try:
            finalize_verified_operation(env, op, AUTHORIZATION)
            fail("operation prematurely finalized without audits")
        except MigrationError:
            if sql_scalar(env, f"select state from public.operations where operation_id='{op}'::uuid") != "COMMITTED_REGISTRY":
                raise

        # Exercise SQL state-transition mechanics separately from the full
        # recovery/semantic gate. Synthetic override is never used by CLI.
        checker = globals()["postcommit_verification"]
        try:
            globals()["postcommit_verification"] = lambda _env, _id, recovery_gate=None: None
            finalize_verified_operation(env, op, AUTHORIZATION)
        finally:
            globals()["postcommit_verification"] = checker
        if sql_scalar(env, f"select state from public.operations where operation_id='{op}'::uuid") != "FINALIZED":
            fail("authorized target operation did not reach FINALIZED")

        run_psql(
            "insert into public.operations(operation_id,operation,mode,state) values "
            f"('{second}'::uuid,'synthetic-interruption','maintenance','PREPARED');",
            env,
        )
        mark_interrupted_migration_failed(env, second, "MARK_TARGET_FAILED_KEEP_LEGACY_FREEZE")
        if sql_scalar(env, f"select state from public.operations where operation_id='{second}'::uuid") != "FAILED":
            fail("interrupted target operation not marked FAILED")
    print("PASS isolated synthetic staging/commit/denial/finalization/failure workflow")


def self_test() -> None:
    sample = [{"b": 2, "a": "x"}, {"a": "y", "b": 1}]
    a = sha256_bytes(("\n".join(sorted(canonical_json(x) for x in sample)) + "\n").encode())
    b = sha256_bytes(("\n".join(sorted(canonical_json(x) for x in reversed(sample))) + "\n").encode())
    if a != b:
        fail("self-test canonical order failed")
    if pg_array(["a", 'b"c']) != '{"a","b\\\"c"}':
        fail("self-test array encoding failed")
    # A maintenance command is not a medical migration authorization.
    example_id = "33333333-3333-4333-8333-333333333333"
    try:
        finalize_verified_operation("SYNTHETIC_DATABASE", example_id, "NOT_AUTHORIZED")
        fail("unauthorized finalization accepted")
    except MigrationError as exc:
        if "explicit owner authorization" not in str(exc):
            raise
    try:
        mark_interrupted_migration_failed("SYNTHETIC_DATABASE", example_id, "NOT_CONFIRMED")
        fail("unconfirmed failure transition accepted")
    except MigrationError as exc:
        if "explicit failed-operation confirmation" not in str(exc):
            raise
    if canonical_timestamp("2026-10-08T12:00:00Z") != canonical_timestamp("2026-10-08T12:00:00+00:00"):
        fail("self-test UTC fingerprint normalization failed")
    if canonical_timestamp("2026-10-08T15:00:00+03:00") != canonical_timestamp("2026-10-08T12:00:00.000000Z"):
        fail("self-test offset fingerprint normalization failed")
    if table_fingerprint("source_locations", [{"verified_at": "2026-10-08T12:00:00Z"}]) != table_fingerprint("source_locations", [{"verified_at": "2026-10-08T12:00:00+00:00"}]):
        fail("self-test timestamps yield different sealed fingerprints")

    with tempfile.TemporaryDirectory(prefix="health-migration-selftest-") as raw:
        package = Path(raw)
        make_synthetic_package(package)

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
    sub.add_parser("pg-roundtrip-test")
    sub.add_parser("pg-full-cycle-test")
    p = sub.add_parser("postcommit-verify")
    p.add_argument("--operation-id", required=True)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")
    p = sub.add_parser("finalize-verified-migration")
    p.add_argument("--operation-id", required=True)
    p.add_argument("--authorization", required=True)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")

    p = sub.add_parser("mark-interrupted-failed")
    p.add_argument("--operation-id", required=True)
    p.add_argument("--confirm", required=True)
    p.add_argument("--db-url-env", default="SUPABASE_DB_URL")

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
        fail("direct commit is disabled: live Drive revalidation must run in private scheduler migrate")
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
    elif args.command == "pg-roundtrip-test":
        postgresql_roundtrip_test()
    elif args.command == "pg-full-cycle-test":
        local_full_cycle_test()
    elif args.command == "postcommit-verify":
        postcommit_verification(args.db_url_env, args.operation_id)
    elif args.command == "finalize-verified-migration":
        finalize_verified_operation(args.db_url_env, args.operation_id, args.authorization)
    elif args.command == "mark-interrupted-failed":
        mark_interrupted_migration_failed(args.db_url_env, args.operation_id, args.confirm)


if __name__ == "__main__":
    try:
        main()
    except MigrationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
