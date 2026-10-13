import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from complete_archive import digest
from complete_payload import verify_payload,SourceStop
class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for x in ('database','metadata','sources'):(self.root/x).mkdir()
        (self.root/'sources/synthetic.bin').write_bytes(b'synthetic')
        (self.root/'database/database.custom').write_bytes(b'synthetic_dump')
        self.sha=digest(self.root/'sources/synthetic.bin')
        self.graph={'sources':[{'source_id':'S01','logical_path':'synthetic.bin','sha256':self.sha,'size_bytes':9}],
                    'locations':[{'source_id':'S01','location_role':'PRIMARY','provider':'google-drive','provider_object_id':'syntheticid123'}]}
        self.write('database/source-graph.private.json',self.graph)
        self.dump=digest(self.root/'database/database.custom');self.graph_sha=digest(self.root/'database/source-graph.private.json')
        self.write('database/capture.private.json',{'dumps':{'database.custom':{'sha256':self.dump}},'capture_role':'health_backup_reader','restricted_role_enforced':True})
        self.rows={'database_dump_sha256':self.dump,'db_source_graph_sha256':self.graph_sha,'objects':[{'path':'synthetic.bin','sha256':self.sha,'size_bytes':9,'primary_object_id':'syntheticid123'}]}
        self.write('metadata/source-manifest.private.json',self.rows)
        self.write('metadata/frozen-original-inventory.private.json',{'objects':[{'sha256':self.sha,'size':9} for i in range(272)]})
        frozen=digest(self.root/'metadata/frozen-original-inventory.private.json')
        self.manifest={'database_dump_sha256':self.dump,'source_graph_sha256':self.graph_sha,'frozen_original_inventory_sha256':frozen}
        self.patch=patch('complete_payload.FROZEN_SHA',frozen);self.patch.start()
    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def write(self,path,data):(self.root/path).write_text(json.dumps(data),encoding='utf-8')
    def test_exact_source_bytes_and_graph(self):self.assertEqual(verify_payload(self.root,self.manifest)['source_ids_bound'],1)
    def test_graph_provider_id_changed(self):
        self.graph['locations'][0]['provider_object_id']='differentid123';self.write('database/source-graph.private.json',self.graph)
        sha=digest(self.root/'database/source-graph.private.json');self.manifest['source_graph_sha256']=sha;self.rows['db_source_graph_sha256']=sha;self.write('metadata/source-manifest.private.json',self.rows)
        with self.assertRaises(SourceStop):verify_payload(self.root,self.manifest)
    def test_bytes_changed(self):
        (self.root/'sources/synthetic.bin').write_bytes(b'forbidden')
        with self.assertRaises(SourceStop):verify_payload(self.root,self.manifest)
    def test_extra_source_not_ignored(self):
        (self.root/'sources/extra.bin').write_bytes(b'extra')
        with self.assertRaises(SourceStop):verify_payload(self.root,self.manifest)
    def test_duplicate_identity_not_ignored(self):
        self.rows['objects'].append(dict(self.rows['objects'][0],path='another.bin'));self.write('metadata/source-manifest.private.json',self.rows)
        with self.assertRaises(SourceStop):verify_payload(self.root,self.manifest)
    def test_lineage_pin_changed(self):
        self.manifest['frozen_original_inventory_sha256']='0'*64
        with self.assertRaises(SourceStop):verify_payload(self.root,self.manifest)
    def test_database_dump_changed(self):
        (self.root/'database/database.custom').write_bytes(b'changed')
        with self.assertRaises(SourceStop):verify_payload(self.root,self.manifest)
if __name__=='__main__':unittest.main()
