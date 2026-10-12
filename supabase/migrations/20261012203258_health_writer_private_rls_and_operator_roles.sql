BEGIN;
DO $guard$ BEGIN
 IF obj_description('health_writer'::regnamespace) IS DISTINCT FROM 'HEALTH_WRITER_STANDBY_V1'
 OR NOT EXISTS(SELECT 1 FROM health_writer.runtime_policy WHERE singleton AND NOT enabled)
 THEN RAISE EXCEPTION 'owned disabled Writer standby required'; END IF;
END $guard$;
ALTER TABLE health_writer.candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.semantic_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.expected_labs ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.publish_audit ENABLE ROW LEVEL SECURITY;
CREATE ROLE health_writer NOLOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
CREATE ROLE health_writer_verifier_login NOLOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4;
COMMENT ON ROLE health_writer IS 'HEALTH_WRITER_OPERATOR_V1';
COMMENT ON ROLE health_writer_verifier_login IS 'HEALTH_WRITER_INDEPENDENT_VERIFIER_V1';
GRANT health_writer_executor TO health_writer WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT health_writer_verifier TO health_writer_verifier_login WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT CONNECT ON DATABASE postgres TO health_writer,health_writer_verifier_login;
ALTER ROLE health_writer SET statement_timeout='60s';
ALTER ROLE health_writer SET idle_in_transaction_session_timeout='60s';
ALTER ROLE health_writer SET lock_timeout='5s';
ALTER ROLE health_writer SET search_path='pg_catalog';
ALTER ROLE health_writer_verifier_login SET statement_timeout='60s';
ALTER ROLE health_writer_verifier_login SET idle_in_transaction_session_timeout='60s';
ALTER ROLE health_writer_verifier_login SET lock_timeout='5s';
ALTER ROLE health_writer_verifier_login SET search_path='pg_catalog';
INSERT INTO health_writer.semantic_verifier_principals VALUES('health_writer_verifier_login');
INSERT INTO health_writer.source_verifier_principals VALUES('health_writer_verifier_login');
COMMIT;
