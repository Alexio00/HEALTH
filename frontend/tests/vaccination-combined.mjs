import assert from "node:assert/strict";
import {labelStage,groupedVaccinations} from "../vaccination-combined.mjs";
assert.equal(labelStage("dose",1),"V1");
assert.equal(labelStage("revaccination",null),"Rv");
assert.equal(labelStage("revaccination",2),"Rv2");
assert.equal(labelStage("unknown",null),"—");
const events=[
 {administration_id:"synthetic-1",administered_on:"2020-01-01",
  product_name:"Combined fixture",verification_status:"verified",
  antigens:[
   {antigen_key:"alpha",display_name:"Alpha",stage_kind:"revaccination",dose_number:2},
   {antigen_key:"beta",display_name:"Beta",stage_kind:"unknown",dose_number:null}]}
];
const result=groupedVaccinations(events);
assert.equal(result.history.length,1);
assert.equal(result.history[0].targets.length,2);
assert.equal(result.latest.length,2);
assert.equal(result.latest.find(x=>x.key==="alpha").stage,"Rv2");
assert.equal(result.latest.find(x=>x.key==="beta").stage,"—");
assert.equal(result.latest[0].administration_id,result.latest[1].administration_id);
console.log("PASS combined vaccination is one injection with independent antigen stages");
