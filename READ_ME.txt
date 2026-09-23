Fix for: column u.uploaded_at does not exist

Copy the two files inside database into your active project's database folder. Replace the existing files.
This is a small hotfix on top of the previously supplied workflow/setup-recovery patch.

Stop Streamlit with Ctrl+C, then run from your project folder:
python -m streamlit run app.py

Re-select the file and events and click Upload and proceed.
No additional SQL migration or package installation is required for this hotfix.

The old code directly queried uploaded_files.uploaded_at, which is absent in your database.
Upload saving and legacy History now use PostgreSQL JSON field lookup to read whichever recorded
save timestamp is present (uploaded_at, created_at or upload_date). The duplicate-adoption path
can also use the existing upload-event creation time. Absent fields no longer break the query.
It does not add fabricated dates to old History rows or insert another copy of an adopted file.
New uploads continue to receive their database save time in the new workflow table.

Validation: 29 targeted tests passed, including three timestamp-schema variants, saved-file adoption,
legacy History before/after adoption, coach reviews and setup recovery. These use isolated tests;
the live Supabase database has not been accessed.

This addresses the database upload failure shown in your screenshot. Missing source measurements
and unrecognised activity timestamps are a separate parsing/data-completeness issue, not repaired
by inventing values. Send the actual activity_23748722857.csv if its columns/dates need mapping.
