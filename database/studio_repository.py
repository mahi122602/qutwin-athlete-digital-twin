"""Small, athlete-scoped home read; never loads raw files or invokes AI."""
from database.workflow_schema import get_connection
from prediction.assessment_versions import present_upload


def get_studio_records(athlete_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, filename, source, uploaded_at, snapshot, events,
                       processing_status, ai_status, LEFT(ai_text, 1200) AS ai_excerpt,
                       (NULLIF(TRIM(ai_text), '') IS NOT NULL) AS has_draft
                FROM qutwin_processed_uploads WHERE athlete_id=%s
                ORDER BY uploaded_at DESC NULLS LAST, id DESC LIMIT 3""", (str(athlete_id),))
            names = [d[0] for d in cur.description]
            uploads = [dict(zip(names, row)) for row in cur.fetchall()]
            uploads = [present_upload(upload) for upload in uploads]
            reviews = []
            if uploads:
                cur.execute("""SELECT r.status, r.reviewed_at, r.coach_id, LEFT(r.comment, 1200) AS comment, LEFT(r.final_text, 1200) AS final_text
                    FROM qutwin_recommendation_reviews r
                    JOIN qutwin_processed_uploads u ON u.id=r.upload_id
                    WHERE u.athlete_id=%s AND u.id=%s
                    ORDER BY r.reviewed_at DESC NULLS LAST, r.id DESC""",
                    (str(athlete_id), uploads[0]['id']))
                names = [d[0] for d in cur.description]
                reviews = [dict(zip(names, row)) for row in cur.fetchall()]
                for review in reviews:
                    review['assessment_is_current']=uploads[0].get('recommendation_is_current',True)
            return uploads, reviews
    finally:
        conn.close()


def get_studio_forecast(athlete_id):
    """Read an existing saved run only; no forecast generation or schema mutation."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('athlete_forecast_runs')")
            if cur.fetchone()[0] is None:
                return None
            cur.execute("""SELECT forecast_run_id,
                generated_at AT TIME ZONE current_setting('TIMEZONE') AS generated_at,
                forecast_payload
                FROM athlete_forecast_runs WHERE athlete_id=%s
                ORDER BY generated_at DESC, forecast_run_id DESC LIMIT 1""", (str(athlete_id),))
            row = cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row)) if row else None
    finally:
        conn.close()
