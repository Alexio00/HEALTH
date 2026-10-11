#!/usr/bin/env python3
"""Render a credential-free SQL fixture; never read clinical rows or credentials."""
import argparse
import json
import pathlib
import re

TABLES = ['records','domains','record_domains','sources','source_locations','record_sources','cases','case_links','analytes','labs','medications','monitoring','plan_items','questions','id_reservations','operations']

def render(schema, catalog):
    if not re.fullmatch(r'health_writer_fixture_[a-z0-9]{8,32}', schema):
        raise ValueError('new private fixture schema required')
    ddl = ['BEGIN;', 'SET LOCAL statement_timeout=\'30s\';', f'CREATE SCHEMA {schema};', f"COMMENT ON SCHEMA {schema} IS 'HEALTH_SYNTHETIC_WRITER_FIXTURE_V1';", f'REVOKE ALL ON SCHEMA {schema} FROM PUBLIC,anon,authenticated,service_role;']
    for table in TABLES:
        columns=[]
        for c in catalog:
            if c['relname'] != table: continue
            name=c['attname']; typ=c['type']
            if not re.fullmatch('[a-z_][a-z0-9_]*',name) or ';' in typ: raise ValueError('unsafe catalog')
            line=f'"{name}" {typ}'
            if c['attidentity']: line += ' GENERATED ALWAYS AS IDENTITY'
            elif c['default_expr']: line += ' DEFAULT '+c['default_expr']
            if c['attnotnull']: line += ' NOT NULL'
            columns.append(line)
        if not columns: raise ValueError('catalog missing '+table)
        ddl.append(f'CREATE TABLE {schema}.{table} ('+','.join(columns)+');')
        ddl.append(f'ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY;')
    ddl.append(f'CREATE UNIQUE INDEX fixture_operations_single_writer ON {schema}.operations ((true)) WHERE state IN (\'PREPARED\',\'COMMITTED_REGISTRY\',\'VALIDATED\');')
    here=pathlib.Path(__file__).resolve().parent
    for file in ['fixture_runtime.sql','structural_checks.sql']:
        ddl.append((here/file).read_text().replace('__SCHEMA__',schema))
    ddl += [f'ALTER TABLE {schema}.candidates ENABLE ROW LEVEL SECURITY;', f'ALTER TABLE {schema}.semantic_receipts ENABLE ROW LEVEL SECURITY;', f'ALTER TABLE {schema}.publish_audit ENABLE ROW LEVEL SECURITY;', f'ALTER TABLE {schema}.expected_labs ENABLE ROW LEVEL SECURITY;', f'GRANT USAGE ON SCHEMA {schema} TO health_test_writer_role;', f'GRANT EXECUTE ON FUNCTION {schema}.publish(text) TO health_test_writer_role;', 'COMMIT;']
    return '\n'.join(ddl)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--schema',required=True);p.add_argument('--catalog',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True)
    a=p.parse_args();a.out.write_text(render(a.schema,json.loads(a.catalog.read_text())),encoding='utf-8')
