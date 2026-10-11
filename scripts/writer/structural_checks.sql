-- Prototype: render __SCHEMA__ only to a fresh health_writer_fixture_* schema.
-- SECURITY INVOKER. Does not mint semantic PASS or authorize publication.
CREATE FUNCTION __SCHEMA__.structural_checks()
RETURNS TABLE(rule_id integer, passed boolean)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, pg_temp
AS $checks$
SELECT 1, NOT EXISTS(SELECT record_id FROM __SCHEMA__.records GROUP BY record_id HAVING count(*)<>1)
UNION ALL SELECT 2, NOT EXISTS(SELECT 1 FROM __SCHEMA__.record_domains d LEFT JOIN __SCHEMA__.domains k ON k.domain_code=d.domain_code LEFT JOIN __SCHEMA__.records r ON r.record_id=d.record_id WHERE k.domain_code IS NULL OR r.record_id IS NULL OR NOT k.active)
UNION ALL SELECT 3, NOT EXISTS(SELECT 1 FROM __SCHEMA__.cases c LEFT JOIN __SCHEMA__.records r ON r.record_id=c.case_key WHERE r.record_id IS NULL)
UNION ALL SELECT 4, NOT EXISTS(SELECT 1 FROM __SCHEMA__.case_links l LEFT JOIN __SCHEMA__.cases c ON c.case_key=l.case_key LEFT JOIN __SCHEMA__.records r ON r.record_id=l.record_id WHERE c.case_key IS NULL OR r.record_id IS NULL OR l.relation NOT IN ('OPEN','CONTINUES','CLOSES','FOLLOWUP')) AND NOT EXISTS(SELECT 1 FROM __SCHEMA__.cases c WHERE (SELECT count(*) FROM __SCHEMA__.case_links l WHERE l.case_key=c.case_key AND l.relation='OPEN' AND l.record_id=c.opening_record_id)<>1)
UNION ALL SELECT 5, NOT EXISTS(SELECT 1 FROM __SCHEMA__.cases c LEFT JOIN __SCHEMA__.records r ON r.record_id=c.closing_record_id WHERE c.status='closed' AND r.record_id IS NULL)
UNION ALL SELECT 6, NOT EXISTS(SELECT 1 FROM __SCHEMA__.labs l LEFT JOIN __SCHEMA__.records r ON r.record_id=l.record_id WHERE r.record_id IS NULL)
UNION ALL SELECT 7, NOT EXISTS(SELECT 1 FROM __SCHEMA__.labs l LEFT JOIN __SCHEMA__.analytes a ON a.analyte_key=l.analyte_key WHERE a.analyte_key IS NULL)
UNION ALL SELECT 8, NOT EXISTS(SELECT 1 FROM __SCHEMA__.records r WHERE (SELECT count(*) FROM __SCHEMA__.id_reservations i WHERE i.record_id=r.record_id AND i.nnn=r.nnn AND i.state='used')<>1) AND NOT EXISTS(SELECT nnn FROM __SCHEMA__.records GROUP BY nnn HAVING count(*)>1)
UNION ALL SELECT 11, NOT EXISTS(SELECT 1 FROM __SCHEMA__.records WHERE record_id !~ '^REC-[0-9]{8}-[0-9]{3}$' OR nnn NOT BETWEEN 1 AND 999 OR (CASE WHEN right(record_id,3) ~ '^[0-9]{3}$' THEN right(record_id,3)::integer ELSE NULL END) IS DISTINCT FROM nnn OR substring(record_id,5,8)<>to_char(record_date,'YYYYMMDD') OR nullif(btrim(title),'') IS NULL OR nullif(btrim(body_text),'') IS NULL OR nullif(btrim(provenance_status),'') IS NULL OR (status IS NOT NULL AND status NOT IN ('active','cancelled')))
UNION ALL SELECT 14, NOT EXISTS(SELECT 1 FROM __SCHEMA__.operations WHERE mode NOT IN ('import','maintenance') OR state NOT IN ('PREPARED','COMMITTED_REGISTRY','VALIDATED','FINALIZED','FAILED') OR cardinality(scope)=0 OR (state='FINALIZED' AND (result IS NULL OR finalized_at IS NULL)))
UNION ALL SELECT 18, NOT EXISTS(SELECT 1 FROM __SCHEMA__.labs l LEFT JOIN __SCHEMA__.expected_labs e ON e.lab_id=l.lab_id WHERE e.lab_id IS NULL OR jsonb_build_array(l.record_id,l.observed_on,l.analyte_key,l.value,l.unit,l.reference_range,l.flag,l.source_name,l.note) IS DISTINCT FROM e.literal_row)
UNION ALL SELECT 23, (SELECT count(*) FROM __SCHEMA__.operations WHERE state IN ('PREPARED','COMMITTED_REGISTRY','VALIDATED'))<=1
UNION ALL SELECT 24, NOT EXISTS(SELECT 1 FROM __SCHEMA__.semantic_receipts s WHERE s.status<>'PASS' OR s.checked_at IS NULL OR s.candidate_sha !~ '^[a-f0-9]{64}$' OR s.after_sha !~ '^[a-f0-9]{64}$' OR s.evidence_sha !~ '^[a-f0-9]{64}$' OR nullif(s.methodology,'') IS NULL)
UNION ALL SELECT 25, NOT EXISTS(SELECT analyte_key FROM __SCHEMA__.analytes GROUP BY analyte_key HAVING count(*)<>1)
UNION ALL SELECT 26, NOT EXISTS(SELECT 1 FROM __SCHEMA__.labs GROUP BY record_id,observed_on,analyte_key,value,unit,reference_range,flag,source_name,note HAVING count(*)>1)
UNION ALL SELECT 32, NOT EXISTS(SELECT 1 FROM __SCHEMA__.id_reservations i WHERE (i.state='used' AND NOT EXISTS(SELECT 1 FROM __SCHEMA__.records r WHERE r.record_id=i.record_id AND r.nnn=i.nnn)) OR (i.state IN ('reserved','retired') AND i.record_id IS NOT NULL) OR i.state NOT IN ('used','retired','reserved')) AND NOT EXISTS(SELECT nnn FROM __SCHEMA__.id_reservations GROUP BY nnn HAVING count(*)>1) AND NOT EXISTS(SELECT record_id FROM __SCHEMA__.id_reservations WHERE record_id IS NOT NULL GROUP BY record_id HAVING count(*)>1)
UNION ALL SELECT 33, NOT EXISTS(SELECT 1 FROM __SCHEMA__.cases WHERE case_key<>opening_record_id)
UNION ALL SELECT 34, NOT EXISTS(SELECT 1 FROM __SCHEMA__.cases c WHERE c.status NOT IN ('open','closed') OR (c.status='open' AND (c.closing_record_id IS NOT NULL OR EXISTS(SELECT 1 FROM __SCHEMA__.case_links l WHERE l.case_key=c.case_key AND l.relation='CLOSES'))) OR (c.status='closed' AND (c.closing_record_id IS NULL OR (SELECT count(*) FROM __SCHEMA__.case_links l WHERE l.case_key=c.case_key AND l.relation='CLOSES')<>1 OR NOT EXISTS(SELECT 1 FROM __SCHEMA__.case_links l WHERE l.case_key=c.case_key AND l.relation='CLOSES' AND l.record_id=c.closing_record_id))))
UNION ALL SELECT 35, NOT EXISTS(SELECT 1 FROM __SCHEMA__.case_links GROUP BY case_key,record_id,relation HAVING count(*)>1)
UNION ALL SELECT 36, NOT EXISTS(SELECT 1 FROM __SCHEMA__.semantic_receipts s LEFT JOIN __SCHEMA__.candidates c ON c.request_key=s.request_key WHERE c.request_key IS NULL);
$checks$;
REVOKE ALL ON FUNCTION __SCHEMA__.structural_checks() FROM PUBLIC;
