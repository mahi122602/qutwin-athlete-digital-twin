import unittest
import pandas as pd
from prediction.event_context import attach_events,describe_event_context
from views.athlete.combined_history import combined_history
from database.activity_upload_repository import _insert_states

class HistoryEventTests(unittest.TestCase):
    def test_old_and_new_dates_sorted_without_filling_scores(self):
        predicted=pd.DataFrame([{'timestamp':'2026-09-09 21:23','fatigue_score':40.41,'heart_rate':124,'event_type':'800 m'}])
        summaries=pd.DataFrame([{'Date':'2026-09-12','step_count':42},{'Date':'2026-08-15','step_count':20}])
        table=combined_history(predicted,summaries)
        self.assertEqual(table['Date / Time'].tolist(),['12 Sep 2026','09 Sep 2026, 21:23','15 Aug 2026'])
        self.assertEqual(table['Fatigue'].tolist(),['Unavailable',40.41,'Unavailable'])
        self.assertEqual(table.iloc[1]['Event'],'800 m')
        self.assertEqual(len(table),3)
    def test_summary_only_history(self):
        table=combined_history(pd.DataFrame(),pd.DataFrame([{'Date':'2026-09-12','step_count':42}]))
        self.assertEqual(len(table),1)
        self.assertEqual(table.iloc[0]['Heart Rate'],'Unavailable')
    def test_assignment_follows_record_when_sorted(self):
        frame=pd.DataFrame({'timestamp':['2026-09-12','2026-08-15']})
        assigned=attach_events(frame,[{'record':1,'event':'100 m'},{'record':2,'event':'800 m'}]).sort_values('timestamp')
        self.assertEqual(assigned.event_type.tolist(),['800 m','100 m'])
        with self.assertRaises(ValueError):attach_events(frame,[{'record':1,'event':'100 m'}])
    def test_recommendations_retain_numeric_scores(self):
        frame=pd.DataFrame([{'event_type':'800 m','fatigue_score':40,'recommendation':'Existing advice.'}])
        result=describe_event_context(frame)
        self.assertIn('800 m',result.iloc[0].recommendation)
        self.assertIn('not event-adjusted',result.iloc[0].recommendation)
        self.assertEqual(result.iloc[0].fatigue_score,40)
    def test_insert_columns_and_values_match(self):
        class Cursor:
            def execute(self,sql,params):
                self.sql=sql;self.params=params
                assert sql.count('%s')==len(params)
        cur=Cursor()
        _insert_states(cur,'athlete',1,pd.DataFrame([{'event_type':'100 m'}]))
        self.assertIn('event_type',cur.sql)
        self.assertEqual(cur.params[-1],'100 m')
