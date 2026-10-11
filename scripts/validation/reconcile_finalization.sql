-- Read-only. No reset/import/finalize/recovery evidence pointer update.
BEGIN READ ONLY;
SELECT operation_id,operation,mode,state,result,created_at,updated_at,finalized_at
FROM public.operations WHERE operation_id='fa39e51f-3d95-4f82-bd3b-94438e7139a1';
SELECT c.mechanism,r.status,count(*) results,min(r.checked_at) first_checked,max(r.checked_at) last_checked
FROM public.validation_results r JOIN public.validation_checks c USING(check_key)
WHERE r.operation_id='fa39e51f-3d95-4f82-bd3b-94438e7139a1' GROUP BY c.mechanism,r.status ORDER BY 1,2;
SELECT c.check_key,c.description,c.mechanism FROM public.validation_checks c
WHERE c.active AND NOT EXISTS(SELECT 1 FROM public.validation_results r WHERE r.check_key=c.check_key AND r.operation_id='fa39e51f-3d95-4f82-bd3b-94438e7139a1' AND r.status='PASS') ORDER BY c.check_key;
SELECT count(*) unfinished_operations FROM public.operations WHERE state IN ('PREPARED','COMMITTED_REGISTRY','VALIDATED');
SELECT tgname,pg_get_triggerdef(oid) definition FROM pg_trigger WHERE tgrelid='public.operations'::regclass AND NOT tgisinternal;
SELECT name,setting FROM pg_settings WHERE name IN ('pgaudit.log','log_statement','log_connections','log_disconnections') ORDER BY name;
COMMIT;
