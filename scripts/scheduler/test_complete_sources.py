"""Reject unsafe inventories and stale/misattributed Source graph bindings."""
import hashlib, tempfile, unittest
from pathlib import Path
from complete_sources import SourceStop, validate_inventory, verify_source_graph, provider_hashes

class SourceTests(unittest.TestCase):
    def item(self,path='folder/file.bin',identity='identity1234'):
        return {'Path':path,'ID':identity,'Size':16,'MimeType':'application/octet-stream'}
    def graph(self):
        return {'sources':[{'source_id':'S01','logical_path':'folder/file.bin','sha256':'a'*64,'size_bytes':16}],
                'locations':[{'source_id':'S01','location_role':'PRIMARY','provider':'google-drive','provider_object_id':'identity1234'}]}
    def records(self):return [{'path':'folder/file.bin','primary_object_id':'identity1234','sha256':'a'*64,'size_bytes':16}]
    def test_valid_inventory_and_graph(self):
        self.assertEqual(len(validate_inventory([self.item()])),1)
        self.assertEqual(verify_source_graph(self.graph(),self.records()),1)
    def test_case_alias_before_download(self):
        with self.assertRaises(SourceStop):validate_inventory([self.item(),self.item('FOLDER/FILE.bin','identity5678')])
    def test_duplicate_provider_identity(self):
        with self.assertRaises(SourceStop):validate_inventory([self.item(),self.item('other.bin')])
    def test_unsafe_paths(self):
        for path in ['../outside','folder/../../outside','folder/NUL.txt','folder/file.','folder/a\\b','C:/file']:
            with self.subTest(path=path),self.assertRaises(SourceStop):validate_inventory([self.item(path)])
    def test_native_or_shortcut_requires_export_policy(self):
        row=self.item();row['MimeType']='application/vnd.google-apps.shortcut'
        with self.assertRaises(SourceStop):validate_inventory([row])
    def test_bad_or_unbounded_size(self):
        for size in [True,-1,9*1024**3,'16']:
            row=self.item();row['Size']=size
            with self.subTest(size=size),self.assertRaises(SourceStop):validate_inventory([row])
    def test_no_primary_or_duplicate_primary_location(self):
        for locations in [[],self.graph()['locations']*2]:
            graph=self.graph();graph['locations']=locations
            with self.assertRaises(SourceStop):verify_source_graph(graph,self.records())
    def test_exact_hash_size_and_id_required(self):
        for key,value in [('sha256','b'*64),('size_bytes',17),('primary_object_id','otherid1234')]:
            records=self.records();records[0][key]=value
            with self.subTest(key=key),self.assertRaises(SourceStop):verify_source_graph(self.graph(),records)
    def test_source_identity_and_path_not_unique(self):
        graph=self.graph();graph['sources']*=2
        with self.assertRaises(SourceStop):verify_source_graph(graph,self.records())
        with self.assertRaises(SourceStop):verify_source_graph(self.graph(),self.records()*2)
    def test_download_binds_provider_hash_for_unlinked_files_too(self):
        with tempfile.TemporaryDirectory() as name:
            file=Path(name)/'binary';file.write_bytes(b'synthetic')
            provider_hashes(file,{'Hashes':{'md5':hashlib.md5(b'synthetic').hexdigest()}})
            with self.assertRaises(SourceStop):provider_hashes(file,{'Hashes':{'md5':'0'*32}})
            with self.assertRaises(SourceStop):provider_hashes(file,{'Hashes':{}})

if __name__=='__main__':unittest.main()
