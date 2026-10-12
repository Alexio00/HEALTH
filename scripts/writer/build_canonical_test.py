"""Render fresh isolated Supabase TEST clinical/control schemas; synthetic only."""
import argparse,hashlib,json,re,uuid
from pathlib import Path
import build_fixture,build_standby
HERE=Path(__file__).resolve().parent
def render(pin):
 if not re.fullmatch('[a-f0-9]{40}',pin):raise ValueError('exact_workflow_pin_required')
 nonce=uuid.uuid4().hex[:12];clinical='health_writer_fixture_'+nonce;control='health_writer_fixture_'+uuid.uuid4().hex[:12]
 groups=['health_canonical_'+nonce+'_'+x for x in ['writer','authorizer','verifier']]
 catalog=json.loads((HERE/'catalog_v1.json').read_text());constraints=json.loads((HERE/'constraints_v1.json').read_text())
 domain=build_fixture.render(clinical,catalog,constraints).split('-- TEST-only delta engine.')[0]
 registry=f"CREATE TABLE {clinical}.validation_checks(check_key text PRIMARY KEY,mechanism text NOT NULL CHECK(mechanism IN ('FORMULA','OPERATION_AUDIT')),description text,dependencies text[],active boolean); CREATE TABLE {clinical}.validation_results(operation_id uuid REFERENCES {clinical}.operations(operation_id),check_key text REFERENCES {clinical}.validation_checks(check_key),status text CHECK(status IN ('PASS','FAIL','SKIP')),checked_at timestamptz,details jsonb,PRIMARY KEY(operation_id,check_key)); ALTER TABLE {clinical}.validation_checks ENABLE ROW LEVEL SECURITY; ALTER TABLE {clinical}.validation_results ENABLE ROW LEVEL SECURITY;"
 runtime=build_standby.render().replace('BEGIN;','').replace('COMMIT;','')
 for table in sorted(build_fixture.TABLES+['validation_checks','validation_results'],key=len,reverse=True):runtime=re.sub(r'public\.'+table+r'\b',clinical+'.'+table,runtime)
 runtime=runtime.replace('public.%I',clinical+'.%I').replace("to_regclass('public.'", "to_regclass('"+clinical+".'")
 runtime=runtime.replace('health_writer.',control+'.').replace('SCHEMA health_writer', 'SCHEMA '+control)
 runtime=runtime.replace("'HEALTH_WRITER_STANDBY_V1'", "'HEALTH_CANONICAL_TEST_CONTROL_V1'")
 for old,new in zip(['health_writer_executor','health_writer_authorizer','health_writer_verifier'],groups):runtime=re.sub(r'\b'+old+r'\b',new,runtime)
 seed=(HERE/'synthetic_tests.sql').read_text().split('DO $test$')[0].split('INSERT INTO __SCHEMA__.expected_labs')[0].replace('__SCHEMA__',clinical).replace("'synthetic','open','Synthetic case'","'episode','open','Synthetic case'")
 config=f"""
INSERT INTO {clinical}.operations(operation_id,operation,mode,scope,state,result,finalized_at) VALUES('fa39e51f-3d95-4f82-bd3b-94438e7139a1','SYNTHETIC_CANONICAL_MIGRATION','import',ARRAY['SYNTHETIC'],'FINALIZED','PASS',clock_timestamp());
INSERT INTO {control}.approval_policy VALUES(true,'authenticator','308028794','1408460030','{pin}');
INSERT INTO {control}.semantic_verifier_principals VALUES('postgres');
INSERT INTO {control}.upload_folders VALUES('syntheticfolder123',true);
UPDATE {control}.runtime_policy SET enabled=true,code_sha='{pin}',primary_folder='syntheticfolder123';
GRANT {groups[0]} TO health_test_ci;
COMMENT ON ROLE {groups[0]} IS 'HEALTH_CANONICAL_TEST_{control}';
COMMENT ON ROLE {groups[1]} IS 'HEALTH_CANONICAL_TEST_{control}';
COMMENT ON ROLE {groups[2]} IS 'HEALTH_CANONICAL_TEST_{control}';
INSERT INTO {clinical}.records SELECT (jsonb_populate_record(NULL::{clinical}.records,to_jsonb(r)||jsonb_build_object('record_id','REC-20201010-910','nnn',910,'record_date','2020-10-11','title','SYNTHETIC historical date mismatch'))).* FROM {clinical}.records r WHERE nnn=1;
INSERT INTO {clinical}.id_reservations SELECT (jsonb_populate_record(NULL::{clinical}.id_reservations,to_jsonb(i)||jsonb_build_object('nnn',910,'record_id','REC-20201010-910','state','used'))).* FROM {clinical}.id_reservations i WHERE nnn=1;
INSERT INTO {control}.legacy_record_exceptions SELECT true,record_id,{control}.sha(to_jsonb(r)),{control}.sha(jsonb_build_array(to_jsonb(r))),repeat('d',64),'SYNTHETIC_OWNER_EXCEPTION',true FROM {clinical}.records r WHERE nnn=910;
CREATE TABLE {control}.test_network_targets(request_key text PRIMARY KEY);
ALTER TABLE {control}.test_network_targets ENABLE ROW LEVEL SECURITY;
CREATE FUNCTION {control}.test_network_target() RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE key text; result jsonb; BEGIN
 SELECT request_key INTO key FROM {control}.test_network_targets;
 IF key IS NULL OR (SELECT caller FROM {control}.prepared_requests WHERE request_key=key) IS DISTINCT FROM session_user THEN RAISE EXCEPTION 'owned synthetic target required'; END IF;
 SELECT jsonb_build_object('request_key',key,'operation_id',p.operation_id,'candidate_sha',c.candidate_sha,'before_sha',c.expected_before_sha,'after_sha',c.expected_after_sha) INTO result FROM {control}.prepared_requests p JOIN {control}.candidates c USING(request_key) WHERE p.request_key=key; RETURN result;
END $fn$;
CREATE FUNCTION {control}.test_network_result(p_key text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE op uuid; BEGIN
 SELECT operation_id INTO op FROM {control}.prepared_requests WHERE request_key=p_key AND caller=session_user;
 IF op IS NULL THEN RAISE EXCEPTION 'owned synthetic target required'; END IF;
 RETURN jsonb_build_object('registered_results',(SELECT count(*) FROM {clinical}.validation_results WHERE operation_id=op),'legacy_exceptions',(SELECT jsonb_array_length(details->'legacy_id_date_exceptions') FROM {clinical}.validation_results WHERE operation_id=op AND check_key='WRITER_V1_RULE_11'));
END $fn$;
REVOKE ALL ON FUNCTION {control}.test_network_target(),{control}.test_network_result(text) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION {control}.test_network_target(),{control}.test_network_result(text) TO {groups[0]};
"""
 rpc=(HERE/'canonical_approval_rpc.sql').read_text().replace('__CANONICAL_RPC__','health_test_canonical_authorize_v1').replace('__CANONICAL_SCHEMA__',control)
 sql=domain+registry+runtime+seed+config+rpc+'COMMIT;'
 if re.search(r'public\.(?:'+ '|'.join(build_fixture.TABLES+['validation_results','validation_checks'])+r')\b',sql):raise ValueError('synthetic_domain_not_fully_isolated')
 policy={'project':'yjmcesdayfmfissghzgm','sha':pin,'ref':'refs/heads/test/writer-delta-and-production-acceptance-20261011','workflow':'code-validation.yml','audience':'health-writer-canonical-test-yjmcesdayfmfissghzgm','rpc':'health_test_canonical_authorize_v1'}
 edge=(HERE/'canonical_approval_edge.ts').read_text().replace('__CANONICAL_POLICY__',json.dumps(policy))
 meta={'control_schema':control,'clinical_schema':clinical,'groups':groups,'workflow_sha':pin,'sql_sha256':hashlib.sha256(sql.encode()).hexdigest(),'project_id':policy['project'],'files':[{'name':'index.ts','content':edge},{'name':'canonical_owner_claims.mjs','content':(HERE/'canonical_owner_claims.mjs').read_text()}]}
 return sql,meta
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pin',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir()
 sql,meta=render(a.pin);(a.out/'fixture.sql').write_text(sql,encoding='utf-8');(a.out/'rendered.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in meta.items() if k!='files'}))
