// Draft canonical vaccination events: one injection, multiple antigen stages.
export function labelStage(kind,number) {
  if (kind === "revaccination") return number == null ? "Rv" : "Rv"+number;
  if (kind === "dose" && Number.isInteger(number)) return "V"+number;
  return "—";
}
export function groupedVaccinations(events) {
  const history=[],latest=new Map();
  for(const e of events) {
    if(e.verification_status!=="verified") continue;
    const targets=(e.antigens||[]).map(a=>({
      key:a.antigen_key,name:a.display_name,
      stage:labelStage(a.stage_kind,a.dose_number)
    }));
    if(!targets.length) continue;
    history.push({...e,targets});
    for(const t of targets) {
      const prev=latest.get(t.key);
      if(!prev || prev.administered_on<e.administered_on)
        latest.set(t.key,{...t,administered_on:e.administered_on,
          administration_id:e.administration_id,product_name:e.product_name});
    }
  }
  return {history,latest:[...latest.values()]};
}
