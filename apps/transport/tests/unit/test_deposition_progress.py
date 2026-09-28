import json,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from datetime import datetime,timezone
import deposition as d
import deposition_progress as p
from test_deposition import POINT

class ProgressTests(unittest.TestCase):
    def test_running_and_queued_are_distinct_and_resume(self):
        running=MagicMock(status='running',request_id='job-jan')
        queued=MagicMock(status='accepted',request_id='job-feb')
        client=MagicMock();client.retrieve.return_value=running
        client.client.get_remote.return_value=queued
        with tempfile.TemporaryDirectory() as folder,patch('cams.make_client',return_value=client):
            result=d.lookup(POINT,folder)
            self.assertEqual(result['status'],'running')
            self.assertIn('1 processing at ADS, 0 queued',result['message'])
            self.assertEqual([j['requestId'] for j in result['jobs']],['job-jan'])
            self.assertIn('Last checked:',result['message'])
            second=d.lookup(POINT,folder,force=True)
            self.assertEqual(client.retrieve.call_count,1);self.assertEqual(second['status'],'queued')
            stored=json.loads((Path(folder)/d.identity(POINT)/'job.json').read_text())
            self.assertEqual(stored['lastStatus'],'accepted')

    def test_old_job_records_work_without_new_requests(self):
        client=MagicMock();client.client.get_remote.return_value=MagicMock(status='running')
        with tempfile.TemporaryDirectory() as folder,patch('cams.make_client',return_value=client):
            target=Path(folder)/d.identity(POINT);target.mkdir()
            (target/'job.json').write_text(json.dumps(dict(requestId='1',requestParameters=d.request_for(POINT),submittedAt='2026-09-27T09:56:00+00:00')))
            result=d.lookup(POINT,folder)
            client.retrieve.assert_not_called()
            self.assertIn('1 processing at ADS',result['message']);self.assertIn('Request ID: 1',p.detail(result))
            self.assertEqual(result['windowDays'],30);self.assertNotIn('means',result)

    def test_transient_error_retries_existing_ids(self):
        client=MagicMock();job=MagicMock(status='running',request_id='retained')
        client.retrieve.return_value=job;client.client.get_remote.return_value=job
        with tempfile.TemporaryDirectory() as folder,patch('cams.make_client',return_value=client):
            d.lookup(POINT,folder)
            client.client.get_remote.side_effect=RuntimeError('secret-provider-text')
            result=d.lookup(POINT,folder)
            self.assertTrue(result['retryable']);self.assertEqual(result['retryAfterSeconds'],120)
            self.assertNotIn('secret-provider-text',json.dumps(result))
            client.client.get_remote.side_effect=None
            result=d.lookup(POINT,folder)
            self.assertEqual(client.retrieve.call_count,1);self.assertEqual(result['status'],'running')

    def test_credentials_and_invalid_data_do_not_retry(self):
        for code in ('credentials','invalid_data','licence'):
            with tempfile.TemporaryDirectory() as folder,patch('cams.make_client',side_effect=d.cams.CamsError(code,'Safe message')):
                result=d.lookup(POINT,folder)
                self.assertFalse(result.get('retryable',False))

    def test_elapsed_and_labels_do_not_invent_percentage(self):
        self.assertEqual(p.elapsed('2026-09-27T09:00:00Z',datetime(2026,9,27,10,23,tzinfo=timezone.utc)),4980)
        self.assertEqual(p.duration(4980),'1 h 23 min');self.assertIsNone(p.elapsed(None))
        self.assertEqual(p.value_label(dict(status='running')),'ADS processing · 30-day window')
        self.assertNotIn('%',p.message(dict(completedMonths=0,jobs=[])))

if __name__=='__main__':unittest.main()
