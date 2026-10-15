// Run production standalone callback handlers under synthetic DOM and Auth.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source=readFileSync("frontend/recovery.js","utf8")
  .replace(/^import .*;\s*$/gm,"");
function el() {
  const handlers=new Map();
  const x={hidden:false,value:"",textContent:"",disabled:false,handlers,
    addEventListener:(type,fn)=>handlers.set(type,fn),
    focus(){this.focused=true;},
    reportValidity(){return true;}};
  x.classList={toggle(name,on){if(name==="hidden")x.hidden=on;},
    contains(name){return name==="hidden"&&x.hidden;}};
  return x;
}
function deferred(){
  let resolve;
  const promise=new Promise(done=>{resolve=done;});
  return {promise,resolve};
}
function makeCase({scrubFails=false,fragment="#synthetic",begin}={}) {
  const ids=["recovery-loading","recovery-invalid","recovery-ready","recovery-done",
    "recovery-error","recovery-form","recovery-password","recovery-confirm",
    "recovery-save","recovery-status","recovery-cancel","recovery-result"];
  const map=Object.fromEntries(ids.map(id=>[id,el()]));
  const loc={pathname:"/HEALTH/recovery.html",hash:fragment,search:"",
    replaced:null,replace(path){this.replaced=path;this.hash="";}};
  const activity=[], auth={
    beginPasswordRecovery:async fragment=>{
      activity.push(["begin",fragment,loc.hash]);
      return begin?begin(fragment):{error:null};
    },
    finishPasswordRecovery:async password=>{
      activity.push(["finish",password]);
      return {updated:true,error:null,logoutConfirmed:true};
    },
    cancelPasswordRecovery:async()=>{activity.push(["cancel"]);},
    signInWithPassword:async()=>{throw Error("reader must not be used");}
  };
  const context=vm.createContext({
    createClient:()=>({auth}), SUPABASE_URL:"https://synthetic.invalid",
    SUPABASE_PUBLISHABLE_KEY:"pk_synthetic",
    document:{getElementById:id=>map[id]},
    location:loc,
    history:{replaceState(){
      if(scrubFails)throw Error("history unavailable");
      loc.hash="";loc.search="";activity.push(["scrub"]);
    }}
  });
  vm.runInContext(source,context);
  return {map,loc,activity,auth};
}
{
  const pending=deferred();
  const x=makeCase({fragment:"#access_token=synthetic&type=recovery",
    begin:async()=>pending.promise});
  assert.equal(x.loc.hash,"","URL scrubbed synchronously before network");
  assert.equal(x.activity[0][0],"scrub");
  assert.equal(x.activity[1][0],"begin");
  assert.equal(x.activity[1][2],"","auth callback sees scrubbed URL");
  pending.resolve({error:null});
  await Promise.resolve();await Promise.resolve();await Promise.resolve();
  assert.equal(x.map["recovery-ready"].hidden,false,"password form shown only after verification");
  x.map["recovery-password"].value="synthetic-long-password";
  x.map["recovery-confirm"].value="mismatch";
  await x.map["recovery-form"].handlers.get("submit")({preventDefault(){}});
  assert.equal(x.activity.filter(a=>a[0]==="finish").length,0,
    "mismatch cannot update password");
  x.map["recovery-confirm"].value="synthetic-long-password";
  await Promise.all([
    x.map["recovery-form"].handlers.get("submit")({preventDefault(){}}),
    x.map["recovery-form"].handlers.get("submit")({preventDefault(){}})
  ]);
  assert.equal(x.activity.filter(a=>a[0]==="finish").length,1,"double submit consumed once");
  assert.equal(x.map["recovery-password"].value,"","password discarded");
  assert.equal(x.map["recovery-done"].hidden,false);
}
{
  let called=0;
  const x=makeCase({scrubFails:true,fragment:"#access_token=synthetic",
    begin:async()=>{called++;return {error:null};}});
  await Promise.resolve();
  assert.equal(x.loc.replaced,"./recovery.html","failed URL scrub navigates without token");
  assert.equal(called,0,"Auth calls forbidden when history scrub fails");
}
{
  const x=makeCase({fragment:"",begin:async()=>{throw Error("should not run");}});
  await Promise.resolve();
  assert.equal(x.map["recovery-invalid"].hidden,false,
    "standalone recovery entrypoint denies missing token");
}
console.log("PASS #103 actual standalone callback handlers, early URL scrub, safe submit/invalid/offline bootstrap");
