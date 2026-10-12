"""Actual disposable PostgreSQL catalog guard regressions; synthetic local only."""
import argparse,json,os,uuid
from pathlib import Path
import psycopg2

def run(port):
 if os.environ.get('PGPASSWORD')!='health-synthetic':raise RuntimeError('local_synthetic_password_required')
 base=Path(__file__).resolve().parents[2];database='health_security_bridge_'+uuid.uuid4().hex[:12]
 admin=psycopg2.connect(host='127.0.0.1',port=port,user='postgres',password='health-synthetic',dbname='postgres');admin.autocommit=True
 with admin.cursor() as q:q.execute('CREATE DATABASE '+database)
 c=None;checks=[]
 try:
  c=psycopg2.connect(host='127.0.0.1',port=port,user='postgres',password='health-synthetic',dbname=database);c.autocommit=True
  guard=(base/'scripts/validation/security_invariants.sql').read_text()
  rpc=(base/'scripts/writer/canonical_approval_rpc.sql').read_text().replace('__CANONICAL_RPC__','health_writer_authorize_v1').replace('__CANONICAL_SCHEMA__','health_writer')
  allowed=['domains','records','record_domains','sources','source_locations','record_sources','cases','case_links','analytes','labs','medications','monitoring','plan_items','questions']
  with c.cursor() as q:
   q.execute("DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname=r) THEN EXECUTE format('CREATE ROLE %I NOLOGIN',r); END IF; END LOOP; END $$;")
   q.execute('CREATE SCHEMA extensions;CREATE EXTENSION pgcrypto WITH SCHEMA extensions;CREATE SCHEMA auth;CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS $$SELECT NULL::uuid$$;CREATE TABLE public.app_readers(user_id uuid);ALTER TABLE public.app_readers ENABLE ROW LEVEL SECURITY;CREATE POLICY self ON public.app_readers FOR SELECT TO authenticated USING(user_id=auth.uid());GRANT SELECT ON public.app_readers TO authenticated;')
   for table in allowed:
    q.execute('CREATE TABLE public.'+table+'(id integer);ALTER TABLE public.'+table+' ENABLE ROW LEVEL SECURITY;GRANT SELECT ON public.'+table+' TO authenticated;CREATE POLICY reader ON public.'+table+' FOR SELECT TO authenticated USING(EXISTS(SELECT 1 FROM public.app_readers WHERE user_id=auth.uid()));')
   for table in ['operations','system_state','validation_checks','validation_results','id_reservations']:q.execute('CREATE TABLE public.'+table+'(id integer);ALTER TABLE public.'+table+' ENABLE ROW LEVEL SECURITY;')
   q.execute('ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;')
   q.execute(guard);checks.append('pre_writer_base_security_pass')
   q.execute("CREATE FUNCTION public.unreviewed() RETURNS void LANGUAGE sql SECURITY DEFINER AS $$SELECT$$")
   try:q.execute(guard);raise AssertionError('extra_elevated_function_accepted_without_writer')
   except psycopg2.Error as e:assert e.pgcode=='P0001';checks.append('pre_writer_extra_elevated_function_rejected')
   q.execute('DROP FUNCTION public.unreviewed();');q.execute(rpc);q.execute(guard);checks.append('exact_fixed_server_bridge_pass')
   for label,mutation in [
    ('browser_acl_rejected','GRANT EXECUTE ON FUNCTION public.health_writer_authorize_v1(text,text,text,text,text,text,text,text,text) TO authenticated'),
    ('public_acl_rejected','GRANT EXECUTE ON FUNCTION public.health_writer_authorize_v1(text,text,text,text,text,text,text,text,text) TO PUBLIC'),
    ('null_search_path_rejected','ALTER FUNCTION public.health_writer_authorize_v1(text,text,text,text,text,text,text,text,text) RESET ALL'),
    ('unsafe_search_path_rejected','ALTER FUNCTION public.health_writer_authorize_v1(text,text,text,text,text,text,text,text,text) SET search_path=public'),
    ('extra_elevated_function_rejected','CREATE FUNCTION public.unreviewed() RETURNS void LANGUAGE sql SECURITY DEFINER AS $$SELECT$$'),
    ('body_drift_rejected',rpc.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1).replace('opaque request identity required','tampered synthetic body'))]:
    q.execute('BEGIN');q.execute(mutation)
    try:q.execute(guard);raise AssertionError(label+'_not_rejected')
    except psycopg2.Error as e:assert e.pgcode=='P0001';checks.append(label)
    finally:q.execute('ROLLBACK')
   q.execute(guard);checks.append('exact_bridge_restored_after_all_negatives')
  return {'status':'SYNTHETIC_ACTUAL_SECURITY_BRIDGE_REGRESSIONS_PASS','checks':checks,'production_access':False}
 finally:
  if c:c.close()
  with admin.cursor() as q:q.execute('DROP DATABASE '+database)
  admin.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=5432);a=p.parse_args();print(json.dumps(run(a.port)))
