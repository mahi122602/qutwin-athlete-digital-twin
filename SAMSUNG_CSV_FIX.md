# Samsung CSV format correction

The supplied day-summary export was verified to contain 29 records and 33 named columns. Its metadata row and trailing empty CSV fields are now handled without dropping records or shifting columns. Samsung detection now recognizes metadata before generic pandas parsing. Four parser regression tests passed.

This corrects CSV decoding, not daily-summary prediction support. The existing importer does not map daily activity summaries to model inputs. The upload page now explains this explicitly, and does not save or predict from these records. Upload a supported exercise-session export to use the existing model pathway. The original daily-summary file remains untouched and is not bundled in this project.

Copy the project contents into your GitHub-connected project, preserving your local configuration. Restart Streamlit and remove/re-add the uploaded file (previous error results may be cached in the session). No database migration is required. Commit/push and merge into main for the deployed app.

Run parser tests from the project folder: python -m unittest discover -s tests -p test_samsung_csv.py -v

The full connection/navigation test suite could not be rerun in this session because streamlit and psycopg2 are absent here; their files were not changed by this patch. Live database upload was not tested.
