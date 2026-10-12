import hashlib,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote,urlunsplit
import session_pooler_tls as t

class TransportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.ca=Path(self.temp.name)/'ca.pem';self.ca.write_bytes(b'SYNTHETIC CA\n')
  self.pin=patch.object(t,'CA_SHA',hashlib.sha256(self.ca.read_bytes()).hexdigest());self.pin.start()
  self.uri=urlunsplit(('postgresql','postgres.ffvqgbslvjocbwfurxrv:'+quote('SYNTHETIC:pa\\ss',safe='')+'@aws-0-us-west-1.pooler.supabase.com:5432','/postgres','',''))
 def tearDown(self):self.pin.stop();self.temp.cleanup()
 def test_enforces_full_verification_for_existing_locator(self):
  c,p=t.fields(self.uri,'ffvqgbslvjocbwfurxrv','postgres',self.ca)
  self.assertEqual(c['PGSSLMODE'],'verify-full');self.assertEqual(c['PGGSSENCMODE'],'disable');self.assertEqual(p,'SYNTHETIC:pa\\ss')
 def test_session_boundary_rejects_unsafe_locators(self):
  variants=[self.uri.replace('5432','6543'),self.uri.replace('pooler.supabase.com','foreign.example'),self.uri.replace('aws-0','aws-1'),self.uri.replace('ffvqgbslvjocbwfurxrv','other'),self.uri.replace('/postgres','/other'),self.uri+'?sslmode=disable',self.uri+'?sslmode=require&sslmode=require',self.uri+'?options=-crole%3Dpostgres',self.uri+'?hostaddr=127.0.0.1',self.uri+'#fragment',self.uri+'?gssencmode=require']
  for uri in variants:
   with self.subTest(uri_class=variants.index(uri)),self.assertRaises(t.SafeStop):t.fields(uri,'ffvqgbslvjocbwfurxrv','postgres',self.ca)
 def test_role_and_certificate_binding(self):
  for project,role,ca in [('other','postgres',self.ca),('ffvqgbslvjocbwfurxrv','arbitrary',self.ca),('ffvqgbslvjocbwfurxrv','postgres',self.ca.parent/'absent')]:
   with self.assertRaises(t.SafeStop):t.fields(self.uri,project,role,ca)
  self.ca.write_bytes(b'changed')
  with self.assertRaises(t.SafeStop):t.fields(self.uri,'ffvqgbslvjocbwfurxrv','postgres',self.ca)
 def test_password_not_environment_and_passfile_removed(self):
  with patch.dict(os.environ,{'PGPASSWORD':'UNSAFE','PGHOSTADDR':'UNSAFE','SUPABASE_DB_URL':'UNSAFE','GITHUB_TOKEN':'UNSAFE'}):
   with t.runtime(self.uri,'ffvqgbslvjocbwfurxrv','postgres',self.ca) as env:
    self.assertFalse({'PGPASSWORD','PGHOSTADDR','SUPABASE_DB_URL','GITHUB_TOKEN'}&env.keys())
    file=Path(env['PGPASSFILE']);self.assertIn(r'SYNTHETIC\:pa\\ss',file.read_text())
    if os.name!='nt':self.assertEqual(file.stat().st_mode&0o777,0o600)
   self.assertFalse(file.exists())
 def test_ca_install_requires_pin_and_create_new(self):
  out=self.ca.parent/'installed.pem'
  with patch.dict(os.environ,{'HEALTH_SUPABASE_CA_PEM':'SYNTHETIC CA\r\n'}):t.install_ca(out)
  self.assertEqual(out.read_bytes(),b'SYNTHETIC CA\n')
  with patch.dict(os.environ,{'HEALTH_SUPABASE_CA_PEM':'CHANGED'}),self.assertRaises(t.SafeStop):t.install_ca(self.ca.parent/'bad.pem')
 def test_readonly_is_explicit_not_startup_only(self):
  class R:
   returncode=0;stdout='SSL connection (protocol: TLSv1.3)\n{"database":"postgres","role":"postgres","session_user":"postgres","readonly":"on","primary":true,"backend_tls":false,"super":false,"bypass":true,"create_role":true,"create_db":true}'
  with patch.object(t.subprocess,'run',return_value=R()) as run:
   result=t.probe(self.uri,'ffvqgbslvjocbwfurxrv','postgres',self.ca)
   self.assertIn('BEGIN READ ONLY;',run.call_args.args[0][-1]);self.assertFalse(result['backend_tls_proven'])

if __name__=='__main__':unittest.main(verbosity=2)
