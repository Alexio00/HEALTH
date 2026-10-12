"""Render a disabled canonical Writer candidate. No connection or deployment.

Clinical references target public; control objects stay private in health_writer.
The older component files remain unchanged, with their TEST evidence intact.
Only this explicitly reviewed renderer adapts the reusable delta machinery.
"""
from pathlib import Path
import re
from build_fixture import TABLES

HERE = Path(__file__).resolve().parent

def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('reviewed_template_binding_changed')
    return text.replace(old, new)

def common(file):
    text = (HERE/file).read_text(encoding='utf-8')
    for table in sorted(TABLES, key=len, reverse=True):
        text = re.sub(r'__SCHEMA__\.'+table+r'\b', 'public.'+table, text)
    text = text.replace('__SCHEMA__.%I', 'public.%I')
    text = text.replace("to_regclass('__SCHEMA__.'||t)", "to_regclass('public.'||t)")
    text = text.replace('__SCHEMA__', 'health_writer')
    text = text.replace('health_test_writer_role', 'health_writer_executor')
    text = text.replace("'gdrive'", "'google-drive'")
    text = text.replace('SYNTHETIC_DURABLE_DELTA', 'HEALTH_WRITER_DELTA_V1')
    text = text.replace('SYNTHETIC_DELTA', 'HEALTH_WRITER_LEGACY_DISABLED')
    text = text.replace("'test_only',true", "'protocol','HEALTH_WRITER_V1'")
    # Documentation remains honest about the origin of these components.
    return text

def render():
    core = common('fixture_runtime.sql')
    old = "IF EXISTS(SELECT 1 FROM public.medications m WHERE m.status='active' AND ("
    new = "IF EXISTS(SELECT 1 FROM public.medications m WHERE m.status='active' AND (NOT EXISTS(SELECT 1 FROM jsonb_array_elements(before_state->'medications') old WHERE old=to_jsonb(m)) OR (m.metadata->>'intake_event' IS NOT NULL AND EXISTS(SELECT 1 FROM jsonb_array_elements(before_state->'questions') old WHERE old->'basis_record_id'=to_jsonb(m.basis_record_id) AND old->'metadata'->>'medication_id'=m.medication_id::text AND old->'metadata'->>'intake_event'=m.metadata->>'intake_event' AND NOT EXISTS(SELECT 1 FROM public.questions q WHERE to_jsonb(q)=old)))) AND ("
    core = once(core, old, new)
    core = once(core, "after_state:=health_writer.checkpoint();v_sha:=health_writer.sha(after_state);",
                "after_state:=health_writer.checkpoint();v_sha:=health_writer.sha(after_state);\n PERFORM health_writer.validate_lab_delta(p_key,before_state,after_state);")
    durable = common('durable_runtime.sql')
    durable = once(durable, "('action','record_date')", "('action','record_date','user_message_sha256','conversation_ref')")
    durable = durable.replace('synthetic intent and candidate approval only', 'owner-bound routine Writer operation')
    checks = common('structural_checks.sql')
    old = next(line for line in checks.splitlines() if line.startswith('UNION ALL SELECT 11,'))
    checks = once(checks, old, 'UNION ALL SELECT 11, health_writer.records_schema_valid()')
    old = next(line for line in checks.splitlines() if line.startswith('UNION ALL SELECT 18,'))
    checks = once(checks, old, "-- Literal lab validation is request-scoped, performed before this check.\nUNION ALL SELECT 18, health_writer.lab_check_context_valid()")
    setup = '''BEGIN;
SET LOCAL statement_timeout='30s';
CREATE ROLE health_writer_executor NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE health_writer_authorizer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE health_writer_verifier NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE SCHEMA health_writer;
COMMENT ON SCHEMA health_writer IS 'HEALTH_WRITER_STANDBY_V1';
REVOKE ALL ON SCHEMA health_writer FROM PUBLIC,anon,authenticated,service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA health_writer REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
'''
    resumable = common('resumable_runtime.sql')
    resumable = once(resumable, " SELECT x.* INTO u FROM health_writer.source_uploads x", " IF p_active THEN PERFORM health_writer.require_enabled(); END IF;\n SELECT x.* INTO u FROM health_writer.source_uploads x")
    resumable = once(resumable,"SELECT 1 FROM health_writer.upload_folders WHERE folder=p_folder AND enabled", "SELECT 1 FROM health_writer.upload_folders f JOIN health_writer.runtime_policy p ON p.singleton AND p.primary_folder=f.folder WHERE f.folder=p_folder AND f.enabled")
    resumable = once(resumable,"JOIN health_writer.upload_folders f USING(folder) WHERE j.marker=p_marker AND f.enabled", "JOIN health_writer.upload_folders f USING(folder) JOIN health_writer.runtime_policy p ON p.singleton AND p.primary_folder=f.folder WHERE j.marker=p_marker AND f.enabled")
    # SQL-language structural_checks resolves this symbol at CREATE time. Until
    # the complete private implementation is installed the stub denies PASS.
    lab_stub="CREATE FUNCTION health_writer.lab_check_context_valid() RETURNS boolean LANGUAGE sql STABLE SET search_path=pg_catalog,pg_temp AS 'SELECT false';"
    source = once(common('source_runtime.sql'), "p_account !~ '^[a-z0-9_-]{1,64}$'", "p_account IS DISTINCT FROM 'HEALTH_PRIMARY'")
    parts = [setup, core, (HERE/'legacy_record_policy.sql').read_text(encoding='utf-8'), lab_stub, checks, durable, source,
             resumable, common('approval_runtime.sql'),
             (HERE/'standby_runtime.sql').read_text(encoding='utf-8'),
             (HERE/'review_runtime.sql').read_text(encoding='utf-8'),
             (HERE/'canonical_validation.sql').read_text(encoding='utf-8'), 'COMMIT;']
    sql = '\n'.join(parts)
    if '__SCHEMA__' in sql or re.search(r'public\.candidates\b|health_writer\.records\b', sql):
        raise ValueError('canonical_control_routing_rejected')
    return sql

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.write_text(render(),encoding='utf-8')
