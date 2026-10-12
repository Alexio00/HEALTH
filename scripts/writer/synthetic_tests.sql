-- Render __SCHEMA__ to the disposable fixture. Run as TEST administrator.
-- Every corruption and publication is rolled back inside a subtransaction.
-- Simulated approvals/receipts exercise mechanics, never clinical acceptance.
CREATE TEMP TABLE writer_test_results(name text,passed boolean,detail text);
INSERT INTO __SCHEMA__.records(record_id,nnn,record_date,title,body_text,provenance_status,status)
VALUES('REC-20261011-001',1,'2026-10-11','Synthetic opening','Synthetic only','synthetic','active'),
('REC-20261011-002',2,'2026-10-11','Synthetic closing','Synthetic only','synthetic','active');
INSERT INTO __SCHEMA__.id_reservations(nnn,state,record_id) VALUES(1,'used','REC-20261011-001'),(2,'used','REC-20261011-002');
INSERT INTO __SCHEMA__.cases(case_key,opening_record_id,category,status,title) VALUES('REC-20261011-001','REC-20261011-001','synthetic','open','Synthetic case');
INSERT INTO __SCHEMA__.case_links(case_key,record_id,relation) VALUES('REC-20261011-001','REC-20261011-001','OPEN');
INSERT INTO __SCHEMA__.analytes(analyte_key,display_name) VALUES('DEMO_MARKER','Synthetic marker');
INSERT INTO __SCHEMA__.labs(lab_id,record_id,analyte_key,value,observed_on,reference_range,source_name) OVERRIDING SYSTEM VALUE VALUES(1,'REC-20261011-001','DEMO_MARKER','1.230','2026-10-11','0.90–2.10','SYNTHETIC');
INSERT INTO __SCHEMA__.expected_labs SELECT lab_id,jsonb_build_array(record_id,observed_on,analyte_key,value,unit,reference_range,flag,source_name,note) FROM __SCHEMA__.labs;
INSERT INTO writer_test_results SELECT 'baseline_20_rules',count(*)=20 AND bool_and(passed),'typed empty/positive fixture, no semantic acceptance' FROM __SCHEMA__.structural_checks();

DO $test$
DECLARE item record; detected boolean; state_before text;
BEGIN
 FOR item IN SELECT * FROM (VALUES
 (1,'INSERT INTO __SCHEMA__.records SELECT * FROM __SCHEMA__.records WHERE nnn=1'),
 (2,'INSERT INTO __SCHEMA__.record_domains VALUES (''REC-20261011-001'',''UNKNOWN'')'),
 (3,'UPDATE __SCHEMA__.cases SET case_key=''REC-20261011-999'''),
 (4,'DELETE FROM __SCHEMA__.case_links'),
 (5,'UPDATE __SCHEMA__.cases SET status=''closed'',closing_record_id=''REC-20261011-999'''),
 (6,'UPDATE __SCHEMA__.labs SET record_id=''REC-20261011-999'''),
 (7,'UPDATE __SCHEMA__.labs SET analyte_key=''UNKNOWN'''),
 (8,'DELETE FROM __SCHEMA__.id_reservations WHERE nnn=1'),
 (11,'UPDATE __SCHEMA__.records SET record_id=''invalid'' WHERE nnn=1'),
 (14,'INSERT INTO __SCHEMA__.operations(operation,mode,scope,state) VALUES(''SYNTHETIC'',''invalid'',ARRAY[''fixture''],''PREPARED'')'),
 (18,'UPDATE __SCHEMA__.labs SET value=''1.23'''),
 (25,'INSERT INTO __SCHEMA__.analytes SELECT * FROM __SCHEMA__.analytes'),
 (26,'INSERT INTO __SCHEMA__.labs OVERRIDING SYSTEM VALUE SELECT * FROM __SCHEMA__.labs'),
 (32,'INSERT INTO __SCHEMA__.id_reservations(nnn,state,record_id) VALUES(999,''used'',''REC-20261011-999'')'),
 (33,'UPDATE __SCHEMA__.cases SET opening_record_id=''REC-20261011-002'''),
 (34,'UPDATE __SCHEMA__.cases SET closing_record_id=''REC-20261011-002'''),
 (35,'INSERT INTO __SCHEMA__.case_links SELECT * FROM __SCHEMA__.case_links')
 ) x(rule_id,mutation) LOOP
  state_before:=__SCHEMA__.sha(__SCHEMA__.checkpoint());detected:=false;
  BEGIN
   EXECUTE item.mutation;
   SELECT passed IS FALSE INTO detected FROM __SCHEMA__.structural_checks() WHERE rule_id=item.rule_id;
   RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='fixture rollback';
  EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
  END;
  INSERT INTO writer_test_results VALUES('rule_'||item.rule_id||'_corruption',detected AND state_before=__SCHEMA__.sha(__SCHEMA__.checkpoint()),'mutation detected and rollback fingerprint verified');
 END LOOP;
 BEGIN
  INSERT INTO __SCHEMA__.operations(operation,mode,scope,state) VALUES('SYNTHETIC','maintenance',ARRAY['fixture'],'PREPARED');
  INSERT INTO __SCHEMA__.operations(operation,mode,scope,state) VALUES('SYNTHETIC','maintenance',ARRAY['fixture'],'PREPARED');
  RAISE EXCEPTION 'expected single writer constraint';
 EXCEPTION WHEN unique_violation THEN INSERT INTO writer_test_results VALUES('rule_23_single_writer',true,'unique_violation');
 END;
 BEGIN
  INSERT INTO __SCHEMA__.semantic_receipts VALUES('missing',19,repeat('a',64),repeat('a',64),repeat('a',64),'PASS','SYNTHETIC',now());
  RAISE EXCEPTION 'expected receipt parent constraint';
 EXCEPTION WHEN foreign_key_violation THEN INSERT INTO writer_test_results VALUES('rule_36_receipt_parent',true,'foreign_key_violation');
 END;
END $test$;

DO $test$
DECLARE item record; payload jsonb; changes jsonb; before_state jsonb; after_state jsonb;
 row_sha text; case_sha text; target_after text; candidate_sha text; result jsonb; err text; accepted boolean; failed_code text; n integer; expected_error text;
BEGIN
 SELECT __SCHEMA__.sha(to_jsonb(r)) INTO row_sha FROM __SCHEMA__.records r WHERE nnn=1;
 SELECT __SCHEMA__.sha(to_jsonb(r)) INTO case_sha FROM __SCHEMA__.cases r;
 FOR item IN SELECT * FROM (VALUES
 ('rec_update',true,jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id','REC-20261011-001'),'expected_sha',row_sha,'row',jsonb_build_object('title','Synthetic revised'))),'none'),
 ('rec_soft_cancel',true,jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id','REC-20261011-001'),'expected_sha',row_sha,'row',jsonb_build_object('status','cancelled'))),'none'),
 ('case_close_atomic',true,jsonb_build_array(jsonb_build_object('table','cases','action','UPDATE','key',jsonb_build_object('case_key','REC-20261011-001'),'expected_sha',case_sha,'row',jsonb_build_object('status','closed','closing_record_id','REC-20261011-002')),jsonb_build_object('table','case_links','action','INSERT','key',jsonb_build_object('case_key','REC-20261011-001','record_id','REC-20261011-002','relation','CLOSES'),'row',jsonb_build_object('case_key','REC-20261011-001','record_id','REC-20261011-002','relation','CLOSES','created_at','2026-10-11T00:00:00Z'))),'none'),
 ('partial_case_close',false,jsonb_build_array(jsonb_build_object('table','cases','action','UPDATE','key',jsonb_build_object('case_key','REC-20261011-001'),'expected_sha',case_sha,'row',jsonb_build_object('status','closed','closing_record_id','REC-20261011-002'))),'none'),
 ('medication_without_question',false,jsonb_build_array(jsonb_build_object('table','medications','action','INSERT','key',jsonb_build_object('medication_id',1),'row',jsonb_build_object('medication_id',1,'name','SYNTHETIC ONLY','status','active','basis_record_id','REC-20261011-001','metadata',jsonb_build_object('intake_event','fixture-event'),'updated_at','2026-10-11T00:00:00Z'))),'none'),
 ('medication_with_question_atomic',true,jsonb_build_array(jsonb_build_object('table','medications','action','INSERT','key',jsonb_build_object('medication_id',1),'row',jsonb_build_object('medication_id',1,'name','SYNTHETIC ONLY','status','active','basis_record_id','REC-20261011-001','metadata',jsonb_build_object('intake_event','fixture-event'),'updated_at','2026-10-11T00:00:00Z')),jsonb_build_object('table','questions','action','INSERT','key',jsonb_build_object('question_id',1),'row',jsonb_build_object('question_id',1,'question','Synthetic interactions check','status','open','basis_record_id','REC-20261011-001','metadata',jsonb_build_object('medication_id','1','intake_event','fixture-event','check_kind','drug_interactions'),'updated_at','2026-10-11T00:00:00Z'))),'none'),
 ('rec_purge_denied',false,jsonb_build_array(jsonb_build_object('table','records','action','DELETE','key',jsonb_build_object('record_id','REC-20261011-001'),'expected_sha',row_sha)),'none'),
 ('source_delete_denied',false,jsonb_build_array(jsonb_build_object('table','sources','action','DELETE','key',jsonb_build_object('source_id','synthetic'))),'none'),
 ('identity_change_denied',false,jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id','REC-20261011-001'),'expected_sha',row_sha,'row',jsonb_build_object('nnn',99))),'none'),
 ('raw_sql_table_denied',false,jsonb_build_array(jsonb_build_object('table','records; select 1','action','DELETE','key',jsonb_build_object('record_id','REC-20261011-001'),'expected_sha',row_sha)),'none'),
 ('stale_row_denied',false,jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id','REC-20261011-001'),'expected_sha',repeat('0',64),'row',jsonb_build_object('title','Synthetic revised'))),'none'),
 ('approval_missing',false,'[]'::jsonb,'approval'),
 ('semantic_missing',false,'[]'::jsonb,'missing'),
 ('semantic_stale',false,'[]'::jsonb,'stale'),
 ('semantic_wrong_candidate',false,'[]'::jsonb,'candidate'),
 ('candidate_tampered',false,'[]'::jsonb,'tamper'),
 ('stale_snapshot',false,'[]'::jsonb,'snapshot'),
 ('expiry',false,'[]'::jsonb,'expiry')
 ) x(name,should_accept,changes,fault) LOOP
  before_state:=__SCHEMA__.checkpoint();changes:=item.changes;after_state:=before_state;accepted:=false;err:=null;
  BEGIN
   -- Simulate the projected after-state, undoing all writes immediately.
   BEGIN
    PERFORM __SCHEMA__.apply_delta(changes);after_state:=__SCHEMA__.checkpoint();
    RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='projection rollback';
   EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
   END;
   payload:=jsonb_build_object('changes',changes);candidate_sha:=__SCHEMA__.sha(payload);target_after:=__SCHEMA__.sha(after_state);
   INSERT INTO __SCHEMA__.candidates VALUES(item.name,payload,candidate_sha,true,now()+interval '10 minutes',__SCHEMA__.sha(before_state),target_after);
   INSERT INTO __SCHEMA__.semantic_receipts SELECT item.name,id,candidate_sha,target_after,repeat('a',64),'PASS','SYNTHETIC MECHANICS ONLY, NOT MEDICAL ACCEPTANCE',now() FROM unnest(ARRAY[19,20,21,22,27,28,29,30,31,37]) id;
   IF item.fault='approval' THEN UPDATE __SCHEMA__.candidates SET approved=false WHERE request_key=item.name; END IF;
   IF item.fault='missing' THEN DELETE FROM __SCHEMA__.semantic_receipts WHERE request_key=item.name AND rule_id=19; END IF;
   IF item.fault='stale' THEN UPDATE __SCHEMA__.semantic_receipts SET checked_at=now()-interval '1 hour' WHERE request_key=item.name; END IF;
   IF item.fault='candidate' THEN UPDATE __SCHEMA__.semantic_receipts SET candidate_sha=repeat('0',64) WHERE request_key=item.name; END IF;
   IF item.fault='tamper' THEN UPDATE __SCHEMA__.candidates SET payload='{"changes":[],"changed":true}' WHERE request_key=item.name; END IF;
   IF item.fault='snapshot' THEN UPDATE __SCHEMA__.candidates SET expected_before_sha=repeat('0',64) WHERE request_key=item.name; END IF;
   IF item.fault='expiry' THEN UPDATE __SCHEMA__.candidates SET expires_at=now()-interval '1 hour' WHERE request_key=item.name; END IF;
   result:=__SCHEMA__.publish(item.name);accepted:=result->>'state'='FINALIZED';
   IF item.should_accept THEN
    SELECT count(*) INTO n FROM __SCHEMA__.publish_audit WHERE request_key=item.name;
    IF n<>1 OR __SCHEMA__.sha(__SCHEMA__.checkpoint())<>target_after THEN RAISE EXCEPTION 'bad audit or after-state'; END IF;
    result:=__SCHEMA__.publish(item.name);
    IF result->>'replayed'<>'true' OR (SELECT count(*) FROM __SCHEMA__.publish_audit WHERE request_key=item.name)<>1 THEN RAISE EXCEPTION 'bad replay'; END IF;
   END IF;
   RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='publication rollback';
  EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
   WHEN OTHERS THEN GET STACKED DIAGNOSTICS err=MESSAGE_TEXT,failed_code=RETURNED_SQLSTATE;
  END;
  expected_error:=CASE item.name
   WHEN 'partial_case_close' THEN 'structural validation failed'
   WHEN 'medication_without_question' THEN 'interaction question missing or duplicated'
   WHEN 'rec_purge_denied' THEN 'REC allocation/purge requires separate protocol'
   WHEN 'source_delete_denied' THEN 'unsupported table/action'
   WHEN 'identity_change_denied' THEN 'immutable REC identity'
   WHEN 'raw_sql_table_denied' THEN 'unsupported table/action'
   WHEN 'stale_row_denied' THEN 'stale or missing row'
   WHEN 'approval_missing' THEN 'approval missing/expired/tampered'
   WHEN 'candidate_tampered' THEN 'approval missing/expired/tampered'
   WHEN 'expiry' THEN 'approval missing/expired/tampered'
   WHEN 'stale_snapshot' THEN 'stale domain snapshot'
   ELSE 'semantic/source evidence missing or stale' END;
  INSERT INTO writer_test_results VALUES(item.name,accepted=item.should_accept AND before_state=__SCHEMA__.checkpoint() AND CASE WHEN item.should_accept THEN err IS NULL ELSE err=expected_error AND failed_code='P0001' END,coalesce(err,'accepted, replayed once, audit verified, rolled back'));
 END LOOP;
 -- Malformed receipt structure is rejected by rule 24, not silently accepted.
 BEGIN
  INSERT INTO __SCHEMA__.candidates VALUES('bad-receipt','{}',repeat('a',64),false,now(),repeat('a',64),repeat('a',64));
  INSERT INTO __SCHEMA__.semantic_receipts VALUES('bad-receipt',19,repeat('a',64),repeat('a',64),'bad','PASS','SYNTHETIC',now());
  SELECT passed IS FALSE INTO accepted FROM __SCHEMA__.structural_checks() WHERE rule_id=24;
  RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='receipt rollback';
 EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
 END;
 INSERT INTO writer_test_results VALUES('rule_24_receipt_structure',accepted,'invalid hash detected');
END $test$;

-- Catalog privilege proof only. Management session cannot SET ROLE health_test_ci.
-- Actual network positive/negative execution remains a separate acceptance gate.
INSERT INTO writer_test_results VALUES
('catalog_role_direct_dml',NOT has_table_privilege('health_test_ci','__SCHEMA__.records','UPDATE'),'no UPDATE grant; actual role execution NOT_RUN'),
('catalog_role_helper_execute',NOT has_function_privilege('health_test_ci','__SCHEMA__.apply_delta(jsonb)','EXECUTE'),'no helper EXECUTE grant; actual role execution NOT_RUN'),
('catalog_role_publish_entry',has_function_privilege('health_test_ci','__SCHEMA__.publish(text)','EXECUTE'),'publish EXECUTE grant; actual role execution NOT_RUN');
SELECT name,passed,detail FROM writer_test_results ORDER BY name;
