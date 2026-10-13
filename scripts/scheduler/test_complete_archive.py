import hashlib,json,os,tempfile,unittest,zipfile
from pathlib import Path
from complete_archive import ArchiveStop,REQUIRED,digest,verify_archive

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.out=self.root/'out';self.out.mkdir(mode=0o700)
    def tearDown(self):self.temp.cleanup()
    def build(self,extra=None,tamper=False,omit=None,duplicate=False):
        contents={name:b'synthetic' for name in REQUIRED}
        if extra:contents[extra]=b'synthetic'
        rows=[{'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in contents.items()]
        manifest={'schema_version':1,'candidate_id':'complete-20261012T000000Z-1234abcd','objects':rows,'database_dump_sha256':rows[0]['sha256'],'source_graph_sha256':rows[0]['sha256']}
        archive=self.root/'test.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for n,b in contents.items():
                if n!=omit:z.writestr(n,b'wrong' if tamper and n=='database/database.custom' else b)
            if duplicate:z.writestr('DATABASE/database.custom',b'synthetic')
            z.writestr('manifest.private.json',json.dumps(manifest))
        return archive
    def test_valid_exact_inventory(self):
        archive=self.build();proof,_=verify_archive(archive,digest(archive),self.out)
        self.assertEqual(proof['verified_objects'],len(REQUIRED)+1);self.assertFalse(proof['rotation_authorized'])
    def test_traversal_and_windows_aliases_before_extraction(self):
        for name in ['sources/../escape','sources/C:/escape','sources/a\\..\\escape','sources/file.','sources/NUL.txt']:
            with self.subTest(name=name),self.assertRaises(ArchiveStop):
                archive=self.build(extra=name);verify_archive(archive,digest(archive),self.out)
            self.assertFalse(any(self.out.iterdir()))
    def test_inner_payload_tamper_with_valid_outer_hash(self):
        archive=self.build(tamper=True)
        with self.assertRaises(ArchiveStop):verify_archive(archive,digest(archive),self.out)
        self.assertFalse(any(self.out.iterdir()))
    def test_omission_stops(self):
        archive=self.build(omit='database/role-db-settings.private.json')
        with self.assertRaises(ArchiveStop):verify_archive(archive,digest(archive),self.out)
    def test_case_collision_stops(self):
        archive=self.build(duplicate=True)
        with self.assertRaises(ArchiveStop):verify_archive(archive,digest(archive),self.out)
    def test_outer_hash_stops(self):
        archive=self.build()
        with self.assertRaisesRegex(ArchiveStop,'sha256_mismatch'):verify_archive(archive,'0'*64,self.out)

if __name__=='__main__':unittest.main()
