import http.client
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from Plugins.Extensions.AddRemoteDiagnostic.web import ReportServer,PORT
from Plugins.Extensions.AddRemoteDiagnostic import web

class WebTests(unittest.TestCase):
    def test_direct_access_download_and_no_file_traversal(self):
        self.assertEqual(PORT,6060)
        server=ReportServer('127.0.0.1',0)
        conn=http.client.HTTPConnection('127.0.0.1',server.http.server_port,timeout=5)
        try:
            conn.request('GET','/');reply=conn.getresponse();page=reply.read().decode()
            self.assertEqual(reply.status,200)
            self.assertIn('تنزيل التقرير',page)
            self.assertNotIn('المشاركة على واتساب',page)
            self.assertNotIn('Fares3nzi ·',page)
            self.assertNotIn('SMTP',page)
            self.assertNotIn('input id="pin"',page)
            conn.request('GET','/api/reports');reply=conn.getresponse();self.assertEqual(json.loads(reply.read()),[])
            with tempfile.NamedTemporaryFile(prefix='addremote-diagnostic-',suffix='.tar.gz',dir='/tmp') as report:
                report.write(b'example-report');report.flush()
                server.publish(report.name)
                conn.request('GET','/api/reports');reply=conn.getresponse();items=json.loads(reply.read())
                self.assertEqual(len(items),1)
                conn.request('GET','/download/'+items[0]['id']);reply=conn.getresponse()
                self.assertEqual(reply.status,200);self.assertEqual(reply.read(),b'example-report')
                self.assertIn('attachment',reply.getheader('Content-Disposition'))
            for path in ('/../../etc/passwd','/download/../../etc/passwd','/etc/passwd'):
                conn.request('GET',path);reply=conn.getresponse();reply.read();self.assertEqual(reply.status,404)
            with self.assertRaises(ValueError):server.publish('/etc/passwd')
        finally:
            conn.close();server.close()

    def test_symlink_tmp_and_report_restored_on_server_start(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);actual=base/'actual';actual.mkdir();alias=base/'tmp';alias.symlink_to(actual,target_is_directory=True)
            report=actual/'addremote-diagnostic-existing.tar.gz';report.write_bytes(b'existing-report')
            with patch.object(web,'REPORT_ROOT',alias):
                server=ReportServer('127.0.0.1',0)
                try:
                    self.assertEqual(list(server.reports.values()),[report.resolve()])
                    server.publish(alias/report.name)
                    self.assertEqual(len(server.reports),1)
                finally:server.close()

if __name__=='__main__':unittest.main()
