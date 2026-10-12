-- Run after synthetic_tests.sql in the same fixture and session.
DO $test$
DECLARE kind text; changes jsonb; payload jsonb; b jsonb; a jsonb; projected jsonb; csha text; asha text; error_text text; accepted boolean; rolled_back boolean; expected_error text;
BEGIN
 FOREACH kind IN ARRAY ARRAY['lab_precision_rejected','source_null_hash_rejected','derived_question_delete'] LOOP
  b:=__SCHEMA__.checkpoint();accepted:=false;error_text:=null;
  BEGIN
   IF kind='source_null_hash_rejected' THEN
    INSERT INTO __SCHEMA__.sources(source_id,logical_path,original_filename,size_bytes) VALUES('SYNTHETIC','synthetic/fixture.txt','fixture.txt',1);
    INSERT INTO __SCHEMA__.source_locations(source_id,provider,account_alias,provider_object_id,location_role,verified_at) VALUES('SYNTHETIC','synthetic','fixture','synthetic-object','PRIMARY',now());
    changes:='[]';expected_error:='source binding invalid';
   ELSIF kind='lab_precision_rejected' THEN
    SELECT jsonb_build_array(jsonb_build_object('table','labs','action','UPDATE','key',jsonb_build_object('lab_id',1),'expected_sha',__SCHEMA__.sha(to_jsonb(l)),'row',jsonb_build_object('value','1.23'))) INTO changes FROM __SCHEMA__.labs l WHERE lab_id=1;
    expected_error:='structural validation failed';
   ELSE
    INSERT INTO __SCHEMA__.questions(question_id,question,status,basis_record_id) OVERRIDING SYSTEM VALUE VALUES(7,'SYNTHETIC obsolete derived question','closed','REC-20261011-001');
    SELECT jsonb_build_array(jsonb_build_object('table','questions','action','DELETE','key',jsonb_build_object('question_id',7),'expected_sha',__SCHEMA__.sha(to_jsonb(q)))) INTO changes FROM __SCHEMA__.questions q WHERE question_id=7;
    expected_error:=null;
   END IF;
   a:=__SCHEMA__.checkpoint();projected:=a;
   BEGIN
    PERFORM __SCHEMA__.apply_delta(changes);projected:=__SCHEMA__.checkpoint();
    RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='projection rollback';
   EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
   END;
   payload:=jsonb_build_object('changes',changes);csha:=__SCHEMA__.sha(payload);asha:=__SCHEMA__.sha(projected);
   INSERT INTO __SCHEMA__.candidates VALUES(kind,payload,csha,true,now()+interval '10 minutes',__SCHEMA__.sha(a),asha);
   INSERT INTO __SCHEMA__.semantic_receipts SELECT kind,id,csha,asha,repeat('a',64),'PASS','SYNTHETIC ONLY',now() FROM unnest(ARRAY[19,20,21,22,27,28,29,30,31,37]) id;
   BEGIN
    PERFORM __SCHEMA__.publish(kind);accepted:=true;
   EXCEPTION WHEN OTHERS THEN GET STACKED DIAGNOSTICS error_text=MESSAGE_TEXT;
   END;
   IF accepted AND __SCHEMA__.checkpoint()<>projected THEN RAISE EXCEPTION 'unexpected after state'; END IF;
   RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='test rollback';
  EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
  END;
  rolled_back:=b=__SCHEMA__.checkpoint();
  INSERT INTO writer_test_results VALUES(kind,rolled_back AND CASE WHEN expected_error IS NULL THEN accepted ELSE NOT accepted AND error_text=expected_error END,coalesce(error_text,'derived row removed, REC preserved, operation audit verified, all rolled back'));
 END LOOP;
END $test$;

-- Additional ledger regression: retired NNN may not collide with a used NNN.
DO $test$
DECLARE ok boolean; before_state jsonb;
BEGIN
 before_state:=__SCHEMA__.checkpoint();
 BEGIN
  INSERT INTO __SCHEMA__.id_reservations(nnn,state) VALUES(1,'retired');
  SELECT passed IS FALSE INTO ok FROM __SCHEMA__.structural_checks() WHERE rule_id=32;
  IF ok IS DISTINCT FROM true THEN RAISE EXCEPTION 'duplicate ledger NNN not detected'; END IF;
  RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='ledger rollback';
 EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL;
 END;
 IF before_state<>__SCHEMA__.checkpoint() THEN RAISE EXCEPTION 'ledger rollback fingerprint mismatch'; END IF;
END $test$;
