"""R1 security regression tests, synthetic data only."""
from __future__ import annotations
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote
HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('g', HERE / 'public_secret_guard.py')
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
FAKE = 'sb_'+'secret_'+'A'*25
cases = [
 ('md', 'README.md', FAKE, 'supabase_secret_key'),
 ('upperMD','README.MD',FAKE,'supabase_secret_key'),
 ('rootother','OTHER.md',FAKE,'supabase_secret_key'),
 ('nested','api/README.md',FAKE,'supabase_secret_key'),
 ('skip_basename','docs/public_secret_guard.py',FAKE,'supabase_secret_key'),
 ('node_modules','node_modules/exposed.md',FAKE,'supabase_secret_key'),
 ('text','example.txt',FAKE,'supabase_secret_key'),
 ('json_client','secrets.json','{"client_secret": "'+'Z'*26+'"}', 'client_secret_value'),
 ('json_refresh','secrets.json','{"refresh_token": "'+'R'*45+'"}', 'refresh_token_value'),
 ('url_encoded_sb','README.md','sb' + '%'+'5F' + 'secret' + '%'+'5F' + 'A'*25,'supabase_secret_key'),
 ('url_encoded_db','README.md','postgresql' + '%'+'3A'+'%'+'2F'+'%'+'2F' + 'abc' + '%'+'3A' + 'passwordverylong' + '%'+'40' + 'host' + '%'+'2F'+'db','database_url_password'),
 ('public_link','README.md','https://docs.google.com/document/d/publicexample/edit',None),
 ('public_email','README.md','support@example.org',None),
 ('bare_name','README.md','refresh_token client_secret',None),
]
count=0
for name,path,body,expected in cases:
 with tempfile.TemporaryDirectory() as d:
  file=Path(d)/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(body)
  f,e=g.check(Path(d))
  assert not e,(name,e)
  assert [k for p,k in f]==([expected] if expected else []),(name,f)
  count+=1
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'README.md';p.write_bytes(b'\xff'+FAKE.encode());f,e=g.check(Path(d));assert e and g.scan(Path(d))[0][1]=='scan_error';count+=1
with tempfile.TemporaryDirectory() as d:
 root=Path(d); (root/'link.md').symlink_to(FAKE);f,e=g.check(root);assert f==[('link.md','supabase_secret_key')] and not e;count+=1
with tempfile.TemporaryDirectory() as d:
 root=Path(d);(root/'README.md').write_text(FAKE);subprocess.run(['git','init','-q',str(root)],check=True);subprocess.run(['git','-C',str(root),'add','README.md'],check=True);(root/'node_modules').mkdir();(root/'node_modules'/'hidden.md').write_text('ordinary');f,e=g.check(root);assert f==[('README.md','supabase_secret_key')] and not e;count+=1
with tempfile.TemporaryDirectory() as d:
 root=Path(d);p=root/'docs';p.mkdir();(p/'link.md').symlink_to(FAKE);subprocess.run(['git','init','-q',str(root)],check=True);subprocess.run(['git','-C',str(root),'add','docs/link.md'],check=True);f,e=g.check(root);assert f==[('docs/link.md','supabase_secret_key')] and not e;count+=1
with tempfile.TemporaryDirectory() as d:
 root=Path(d);p=root/'README.md';p.write_text(FAKE);p.chmod(0);f,e=g.check(root)
 # root may read despite chmod; never silently accept when current user cannot read.
 if os.geteuid()!=0:assert e
 p.chmod(0o600);count+=1
with tempfile.TemporaryDirectory() as d:
 root=Path(d);p=root/('file\nPASS.md');p.write_text(FAKE);r=subprocess.run([sys.executable,str(HERE/'public_secret_guard.py'),'--root',str(root)],capture_output=True,text=True);assert r.returncode==1 and 'file\\nPASS.md' in r.stdout and FAKE not in r.stdout;count+=1
r=subprocess.run([sys.executable,str(HERE/'public_secret_guard.py'),'--root','/definitely/nonexistent/issue105_R1'],capture_output=True,text=True);assert r.returncode==1 and 'Traceback' not in r.stderr;count+=1
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'README.md';p.write_text('public docs');r=subprocess.run([sys.executable,str(HERE/'public_secret_guard.py'),'--root',d],capture_output=True,text=True);assert r.returncode==0;count+=1
# R2: inspect indexed blob, not mutable worktree bytes.
with tempfile.TemporaryDirectory() as d:
 root=Path(d);p=root/'README.md';p.write_text(FAKE)
 subprocess.run(['git','init','-q',str(root)],check=True)
 subprocess.run(['git','-C',str(root),'add','README.md'],check=True)
 p.write_text('public')
 f,e=g.check(root);assert f==[('README.md','supabase_secret_key')] and not e,(f,e);count+=1
# R2: Git symlink target must be examined irrespective of suffix.
for suffix in ('.zip','.pdf'):
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);(root/('link'+suffix)).symlink_to(FAKE)
  subprocess.run(['git','init','-q',str(root)],check=True)
  subprocess.run(['git','-C',str(root),'add','link'+suffix],check=True)
  f,e=g.check(root);assert f==[('link'+suffix,'supabase_secret_key')] and not e,(f,e);count+=1
# R2: standalone symlink directory targets also carry readable path text.
with tempfile.TemporaryDirectory() as d:
 root=Path(d);(root/'link.zip').symlink_to(FAKE)
 f,e=g.check(root);assert f==[('link.zip','supabase_secret_key')] and not e,(f,e);count+=1
# R2: unreadable directory enumeration must fail closed (requires unprivileged runner).
if os.geteuid()!=0:
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);sealed=root/'sealed';sealed.mkdir();(sealed/'hidden.md').write_text(FAKE);sealed.chmod(0)
  try:
   f,e=g.check(root);assert e and g.scan(root)[-1][1]=='scan_error',(f,e)
  finally:sealed.chmod(0o700)
  count+=1
print(f'{count}/{count} PASS')
