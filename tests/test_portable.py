"""Clean-client checks run with -I -S: no site packages or configured mailbox."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tracker_portable',ROOT/'heymail/scripts/tracker.py')
tracker=importlib.util.module_from_spec(spec);spec.loader.exec_module(tracker)


class PortableTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'work/portable-tests';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def client(self,name):
        skill=self.root/name/'heymail'
        (skill/'scripts').mkdir(parents=True)
        (skill/'assets/templates').mkdir(parents=True)
        for file in ['tracker.py','tracker_excel.py']:
            shutil.copy2(ROOT/'heymail/scripts'/file,skill/'scripts'/file)
        shutil.copy2(ROOT/'heymail/assets/templates/application-ledger.xlsx',skill/'assets/templates/application-ledger.xlsx')
        return skill/'scripts/tracker.py'
    def call(self,script,*args,success=True):
        env={**os.environ,'PATH':'','PYTHONPATH':''}
        result=subprocess.run([sys.executable,'-I','-S','-X','utf8',str(script),*args],env=env,capture_output=True)
        if success:self.assertEqual(result.returncode,0,result.stdout.decode('utf-8',errors='replace'))
        else:self.assertNotEqual(result.returncode,0)
        return json.loads(result.stdout.decode('utf-8'))
    def test_three_clean_clients_append_same_excel_without_mailbox_or_packages(self):
        book=self.root/'shared'/'任意名称.xlsx'
        for i,name in enumerate(['Codex','豆包','WorkBuddy']):
            script=self.client(name)
            record=self.root/f'record-{i}.json'
            record.write_text(json.dumps({'id':f'manual_client{i}','company':f'公司{i}','position':'研究实习生',
                'time':f'2026-10-28T1{i}:00:00','latest_progress':'HR已回复','notes':'=untrusted()'},ensure_ascii=False),encoding='utf-8')
            output=self.call(script,'add','--workbook',str(book),'--record',str(record),'--agent',name)
            self.assertEqual(output['rows'],i+1)
        rows=tracker.read_workbook_rows(book)
        self.assertEqual(len(rows),3)
        self.assertEqual(list(rows),['manual_client2','manual_client1','manual_client0'])
        self.assertEqual({row['E'] for row in rows.values()},{'Codex','豆包','WorkBuddy'})
        self.assertTrue(all(row['G']=='HR已回复' for row in rows.values()))
        self.assertTrue(all(row['I']=='=untrusted()' for row in rows.values()))
        before=book.read_bytes()
        self.call(script,'add','--workbook',str(book),'--record',str(record),'--agent','WorkBuddy',success=False)
        self.assertEqual(before,book.read_bytes())
    def test_excel_alone_keeps_all_history_without_sidecars(self):
        settings={'root':str(self.root/'old'),'author':'Synthetic'}
        manifest={'to':'hr@example.com','application':{'id':'event_job','company':'原公司','position':'原岗位'}}
        receipt={'to':'hr@example.com','status':'accepted','time':'2026-10-28T01:00:00Z','message_id':'<synthetic@example.com>'}
        tracker.record_event(settings,manifest,receipt,self.root/'receipt.json');tracker.sync(settings)
        destination=self.root/'new'/'复制的台账.xlsx';destination.parent.mkdir()
        shutil.copy2(Path(settings['root'])/'实习投递台账.xlsx',destination)
        self.call(self.client('standalone'),'sync','--workbook',str(destination))
        rows=tracker.read_workbook_rows(destination)
        self.assertEqual(list(rows),['event_job'])
        self.assertEqual(rows['event_job']['A'],'原公司')
        self.assertEqual(rows['event_job']['K'],'hr@example.com')
