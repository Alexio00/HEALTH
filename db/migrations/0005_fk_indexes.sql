create index if not exists case_links_record_id_idx
  on public.case_links(record_id);

create index if not exists cases_closing_record_id_idx
  on public.cases(closing_record_id);

create index if not exists id_reservations_operation_id_idx
  on public.id_reservations(operation_id);

create index if not exists labs_source_id_idx
  on public.labs(source_id);

create index if not exists medications_basis_record_id_idx
  on public.medications(basis_record_id);

create index if not exists monitoring_basis_record_id_idx
  on public.monitoring(basis_record_id);

create index if not exists plan_items_basis_record_id_idx
  on public.plan_items(basis_record_id);

create index if not exists questions_basis_record_id_idx
  on public.questions(basis_record_id);

create index if not exists questions_resolved_by_record_id_idx
  on public.questions(resolved_by_record_id);

create index if not exists record_domains_domain_code_idx
  on public.record_domains(domain_code);

create index if not exists record_sources_source_id_idx
  on public.record_sources(source_id);

create index if not exists validation_results_check_key_idx
  on public.validation_results(check_key);
