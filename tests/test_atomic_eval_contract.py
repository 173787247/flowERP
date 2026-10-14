"""A single-line shortage cannot establish atomicity after writes begin."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from eval.cases import sales_credit_and_atomic_reservation

ROOT=Path(__file__).resolve().parents[1]


class AtomicEvalContractTests(unittest.TestCase):
    def test_real_multiline_success_and_two_failure_phases(self):
        result=sales_credit_and_atomic_reservation()
        self.assertIn("第二次写入失败",result)
        self.assertIn("四表完整不变",result)

    def test_same_eval_catches_an_isolated_premature_commit(self):
        original=ROOT/'flowerp/sales.py'
        before=hashlib.sha256(original.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            candidate=Path(directory)
            for package in ('flowerp','eval'):
                shutil.copytree(ROOT/package,candidate/package,ignore=shutil.ignore_patterns('__pycache__'))
            source=candidate/'flowerp/sales.py'
            text=source.read_text('utf8')
            anchor='                conn.execute("UPDATE sales_document_lines SET reserved_quantity=reserved_quantity+? WHERE id=?", (quantity, line["id"]))\n'
            self.assertEqual(1,text.count(anchor))
            source.write_text(text.replace(anchor,anchor+'                conn.commit()  # labelled isolated test fault\n',1),'utf8')
            report=candidate/'report.json'
            process=subprocess.run([sys.executable,'-B','-X','utf8','-m','eval.harness','--suite','blocking',
                '--case','sales_credit_and_atomic_reservation','--report-path',str(report)],
                cwd=candidate,capture_output=True,text=True,encoding='utf8',timeout=60)
            self.assertEqual(1,process.returncode,process.stdout+process.stderr)
            body=json.loads(report.read_text('utf8'))
            self.assertEqual(1,body['summary']['blocking_failed'])
            self.assertIn('partial persisted state',body['results'][0]['evidence'])
            self.assertEqual('AssertionError',body['results'][0]['error']['type'])
        self.assertEqual(before,hashlib.sha256(original.read_bytes()).hexdigest())


if __name__=='__main__': unittest.main()
