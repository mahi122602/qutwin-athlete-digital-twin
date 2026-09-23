import io
import unittest
from ingestion.samsung_csv_reader import read_samsung_csv
from ingestion.auto_detector import detect_upload_source
from ingestion.samsung_health_parser import parse_samsung_health_csv

class SamsungCSVTests(unittest.TestCase):
    def test_metadata_and_trailing_empty_column(self):
        data=b'com.samsung.shealth.activity.day_summary,1,6\nstep_count,day_time\n42,2026-09-01,\n43,2026-09-02,\n'
        frame=read_samsung_csv(data)
        self.assertEqual(frame.shape,(2,2))
        self.assertEqual(frame.step_count.tolist(),[42,43])
        self.assertEqual(frame.day_time.tolist(),['2026-09-01','2026-09-02'])
        f=io.BytesIO(data); f.name='summary.csv'
        self.assertEqual(detect_upload_source(f)['source'],'Samsung Health')
        model,raw=parse_samsung_health_csv(f)
        self.assertTrue(model.empty)
        self.assertEqual(sum(len(v) for v in raw.values()),2)

    def test_nonempty_extra_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'No records were skipped'):
            read_samsung_csv(b'a,b\n1,2,3\n')

    def test_quoted_comma_and_missing_value(self):
        frame=read_samsung_csv(b'name,value\n"hello, world",2,\nsecond,,\n')
        self.assertEqual(frame.iloc[0]['name'],'hello, world')
        self.assertEqual(len(frame),2)
        self.assertTrue(frame['value'].isna().iloc[1])

    def test_short_record_rejected(self):
        with self.assertRaises(ValueError):
            read_samsung_csv(b'a,b\n1\n')
