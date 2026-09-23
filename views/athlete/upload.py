from prediction.event_context import attach_events, describe_event_context
import streamlit as st
import pandas as pd
from ingestion.workflow_loader import load_uploaded_file
from prediction.upload_processing import process_upload, missing_inputs
from views.athlete.import_review import review_import

def upload_garmin_data():
    """Three-section activity uploader; route name retained for app.py."""
    import hashlib
    import html
    from database.activity_upload_repository import save_activity_upload

    athlete_id = str(st.session_state.user_id)
    prefix = f"activity_upload_adaptive_v5_{athlete_id}_"
    generation = st.session_state.get(prefix + "generation", 0)
    cache = st.session_state.setdefault(prefix + "files", {})
    outcomes = st.session_state.setdefault(prefix + "outcomes", {})
    events = ["100 m", "200 m", "400 m", "800 m", "1500 m", "5 km", "10 km", "Half Marathon", "Marathon"]

    def clear_events():
        st.session_state[prefix + "events"] = []

    def clear_files():
        st.session_state[prefix + "generation"] = generation + 1
        st.session_state[prefix + "files"] = {}
        st.session_state[prefix + "outcomes"] = {}
        st.session_state[prefix + "continue"] = False
        for key in list(st.session_state):
            if key.startswith(prefix + "assign_") or key.startswith(prefix + "rows_"):
                del st.session_state[key]

    def esc(value):
        return html.escape(str(value))

    st.html('''<style>
.st-key-upload_activity_page {color:#dbeafe;}
.au-eyebrow {color:#13bce7;font-size:10px;font-weight:750;letter-spacing:1.6px;margin:0 0 12px;}
.au-title {color:#eef6ff;font-size:27px;font-weight:750;line-height:1.2;margin:0 0 12px;}
.au-subtitle {color:#8fa5be;font-size:14px;line-height:1.65;max-width:650px;margin-bottom:24px;}
.au-steps {display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:24px;font-size:12px;color:#8aa1bd;}
.au-step {display:flex;gap:8px;align-items:center;}
.au-step b {display:inline-flex;width:24px;height:24px;border:1px solid #24445d;border-radius:50%;align-items:center;justify-content:center;}
.au-step.active {color:#22d3ee;}.au-step.active b {border-color:#22d3ee;background:#083143;}
.au-line {width:38px;height:1px;background:#1c344e;}
.st-key-au_events, .st-key-au_files, .st-key-au_review {
 background:#081426 !important;border:1px solid #1b314e !important;
 border-radius:14px !important;padding:22px !important;box-shadow:none !important;
}
.st-key-au_events {border-color:#155a65 !important;}
.au-section-heading {display:flex;gap:12px;align-items:center;color:#e0efff;font-size:15px;font-weight:650;margin-bottom:8px;}
.au-section-heading span {font-size:11px;color:#2dd4bf;letter-spacing:1px;}
.au-helper {font-size:12px;color:#8da4bf;margin:4px 0 12px;line-height:1.6;}
.st-key-upload_activity_page [data-baseweb="select"] > div {
 background:#081426 !important;border-color:#1a3451 !important;border-radius:8px !important;
}
.st-key-upload_activity_page [data-baseweb="tag"] {background:#063549 !important;color:#67e8f9 !important;border:1px solid #126078;}
.st-key-au_files [data-testid="stFileUploaderDropzone"] {
 min-height:210px !important;flex-direction:column !important;justify-content:center !important;
 gap:12px !important;background:#081426 !important;border:1px dashed #214262 !important;
 border-radius:12px !important;text-align:center !important;
}
.st-key-au_files [data-testid="stFileUploaderDropzoneInstructions"] {align-items:center !important;text-align:center;}
.st-key-upload_activity_page button {
 border-radius:8px !important;border:1px solid #1c4660 !important;
 background:#092538 !important;color:#67dff5 !important;font-size:12px !important;
 box-shadow:none !important;min-height:36px !important;
}
.st-key-upload_activity_page button[kind="primary"] {background:#087e99 !important;color:#f0fdff !important;}
.st-key-upload_activity_page button:disabled {opacity:.45 !important;}
.st-key-upload_activity_page button:focus-visible {outline:2px solid #67e8f9;outline-offset:2px;}
.au-stat {border:1px solid #1b314e;border-radius:12px;padding:16px;min-height:108px;background:#091628;}
.au-stat strong {display:block;font-size:25px;color:#22d3ee;line-height:1.2;}
.au-stat.attention strong {color:#fbbf24;}
.au-stat span {display:block;color:#b8cae0;font-size:12px;margin-top:5px;}
.au-stat small {display:block;color:#849bb5;font-size:11px;margin-top:4px;overflow-wrap:anywhere;}
.au-file-title {font-size:13px;color:#e2efff;font-weight:600;overflow-wrap:anywhere;}
.au-status {font-size:12px;color:#5eead4;margin:6px 0;}
@media(max-width:760px){.au-title{font-size:24px;}.st-key-au_events,.st-key-au_files,.st-key-au_review{padding:14px !important;}}
</style>''')
    selected_before = st.session_state.get(prefix + "events", [])
    stage = 3 if cache else (2 if selected_before else 1)
    steps = []
    for i, title in enumerate(["Select events", "Add files", "Review and upload"], 1):
        steps.append(f'<div class="au-step {"active" if i <= stage else ""}"><b>{i}</b>{title}</div>')
    with st.container(key="upload_activity_page"):
        st.html('<div class="au-eyebrow">ACTIVITY MANAGEMENT ───</div><div class="au-title">Upload Activity Data</div><div class="au-subtitle">Choose your events, upload your activity files, and review the details before adding them to your Digital Twin.</div><div class="au-steps">' + '<span class="au-line"></span>'.join(steps) + '</div>')
        with st.container(key="au_events"):
            st.html('<div class="au-section-heading"><span>01</span>Select Your Events</div><div class="au-helper">Select one or more events represented in your activity data.</div>')
            selected = st.multiselect("Search and select events", events, key=prefix + "events", placeholder="Search and select events…", label_visibility="collapsed")
            count_col, clear_col = st.columns([4, 1])
            with count_col:
                st.caption(f"{len(selected)} event{'s' if len(selected) != 1 else ''} selected")
            with clear_col:
                st.button("Clear selection", on_click=clear_events, disabled=not selected, key=prefix + "clear_events")
            st.html('<div class="au-helper">Assign each file to the appropriate event below.</div>')
            _, next_col = st.columns([4, 1])
            with next_col:
                if st.button("Continue to files ›", key=prefix + "next", disabled=not selected, use_container_width=True):
                    st.session_state[prefix + "continue"] = True
            if st.session_state.get(prefix + "continue") and selected:
                st.caption("Step 2 is ready below — browse or drop your files.")

        with st.container(key="au_files"):
            st.html('<div class="au-section-heading"><span>02</span>Add Activity Files</div>')
            files = st.file_uploader("Drag and drop your files here", type=["zip", "csv", "xlsx", "xls", "fit", "tcx", "gpx", "xml", "json", "tsv", "txt", "jsonl"], accept_multiple_files=True, key=prefix + f"uploader_{generation}", disabled=False, label_visibility="collapsed")
            st.caption("FIT, CSV, GPX, TCX, XLSX, XLS, ZIP, XML and JSON. Files are checked by the existing importer before they can be saved.")
            if not selected:
                st.info("Select one or more events, then assign the uploaded records to their event.")
            entries = []
            seen = set()
            for uploaded in files or []:
                digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
                if digest in seen:
                    st.warning(f"Duplicate file skipped: {uploaded.name}. Remove the extra copy using the uploader’s remove control.")
                    continue
                seen.add(digest)
                entry = cache.get(digest)
                if entry is None:
                    entry = {"name": uploaded.name, "size": uploaded.size, "bytes": uploaded.getvalue()}
                    try:
                        uploaded.seek(0)
                        with st.spinner(f"Checking {uploaded.name}…"):
                            df, raw, detection = load_uploaded_file(uploaded)
                        if df is None or df.empty:
                            raise ValueError("No activity records could be extracted. Check your export and try again.")
                        if not isinstance(df, pd.DataFrame):
                            raise ValueError("The importer did not return a valid activity table.")
                        entry.update(df=df.copy(), raw=raw, detection=detection or {})
                    except Exception as exc:
                        entry["error"] = str(exc)
                    cache[digest] = entry
                entry["digest"] = digest
                entries.append(entry)
            for digest in list(cache):
                if digest not in seen:
                    del cache[digest]
            for entry in entries:
                digest = entry["digest"]
                st.divider()
                left, assignment_col, status_col = st.columns([2, 2, 1])
                with left:
                    st.html(f'<div class="au-file-title">{esc(entry["name"])}</div>')
                    st.caption(f'{entry["size"] / 1024:,.1f} KB')
                saved = outcomes.get(digest, {}).get("status") in ("saved", "already_saved")
                if saved and st.button("Correct this saved file",key=prefix+"correct_"+digest):
                    outcomes.pop(digest,None)
                    st.session_state[prefix+"replace_"+digest]=True
                    st.rerun()
                review_import(entry,prefix+digest+"_"+str(entry.get("revision",0))+"_",saved)
                entry["correct_existing"]=st.checkbox("Update an existing observations-only upload with these corrections",key=prefix+"replace_"+digest,disabled=saved,
                    help="Preserves the saved date and History entry. Blocked if predictions or an AI/coach review already exist.")
                assignments = []
                key = prefix + "assign_" + digest
                choices = ["Select event…"] + selected + ["Multiple events — assign rows"]
                if st.session_state.get(key) not in choices:
                    st.session_state[key] = choices[0]
                with assignment_col:
                    assigned = st.selectbox("Event assignment", choices, key=key, disabled=saved or bool(entry.get("error")))
                with status_col:
                    st.html(f'<div class="au-status">{"Saved" if saved else ("Needs attention" if entry.get("error") or assigned == choices[0] else "Review")}</div>')
                if entry.get("error"):
                    st.error(f'{entry["name"]}: {entry["error"]}')
                    entry["ready"] = False
                    continue
                df = entry.setdefault("original_df", entry["df"].copy()).copy()
                gaps = missing_inputs(df)
                if gaps or df["timestamp"].isna().any():
                    from ui.prediction_guidance import LABELS
                    st.caption("Your file can be saved. Measurements not supplied: " + ", ".join(LABELS.get(k,k.replace("_"," ")) for k in gaps) + ". Add only known values below; estimates may be limited when measurements are missing.")
                    with st.expander("Add missing measurements (optional)"):
                        st.caption("Enter only known measurements for each activity. Leave unknown values blank. Units: sleep/recovery in hours, temperature in °C, humidity in %, previous injury 0 or 1. Activity timestamps use UTC.")
                        edit = df.reindex(columns=["timestamp"] + list(dict.fromkeys(gaps))).copy()
                        if "hydration_level" in edit:
                            edit["hydration_level"] = edit["hydration_level"].astype(object).where(edit["hydration_level"].notna(), None)
                        for field in gaps:
                            if field != "hydration_level":edit[field]=pd.to_numeric(edit[field],errors="coerce").astype(float)
                        edit = st.data_editor(edit, key=prefix + "measurements_" + digest + str(entry.get("revision",0)),
                            hide_index=True, use_container_width=True,
                            column_config={"hydration_level": st.column_config.SelectboxColumn(options=["Low", "Medium", "High"]),
                                **{k: st.column_config.NumberColumn(k) for k in gaps if k != "hydration_level"}})
                        updated = df.copy()
                        for field in edit.columns:
                            updated[field] = edit[field]
                        entry["df"] = updated
                        df = updated
                if assigned == "Multiple events — assign rows" and not saved:
                    with st.expander("Review activities and assign events", expanded=True):
                        st.caption("Assign each extracted record once. These are the records produced by your file importer.")
                        records = pd.DataFrame({"Record": range(1, len(df) + 1), "Timestamp": [str(v) for v in df["timestamp"]] if "timestamp" in df else [""] * len(df), "Event": [None] * len(df)})
                        edited = st.data_editor(records, hide_index=True, use_container_width=True, key=prefix + "rows_" + digest + str(entry.get("revision",0)) + "_" + hashlib.sha256('|'.join(selected).encode()).hexdigest()[:12], disabled=["Record", "Timestamp"], column_config={"Event": st.column_config.SelectboxColumn("Event", options=selected, required=True)})
                        assignments = [{"record": int(row["Record"]), "timestamp": row["Timestamp"], "event": row["Event"]} for _, row in edited.iterrows()]
                elif assigned in selected:
                    assignments = [{"record": i + 1, "timestamp": str(df.iloc[i].get("timestamp", "")), "event": assigned} for i in range(len(df))]
                entry["assignments"] = assignments
                from ingestion.adaptive_table import FIELDS
                has_measurements=df.reindex(columns=[k for k in FIELDS if k!="timestamp"]).notna().any().any()
                entry["ready"] = saved or bool(has_measurements) and bool(assignments) and all(a["event"] in selected for a in assignments)
                if not has_measurements:
                    st.warning("No usable measurements mapped yet. Review columns and units above, or export a supported activity table.")
                if not entry["ready"]:
                    st.warning("Assign every record to one of your selected events before uploading.")
                elif not saved:
                    st.caption(f"Ready · {len(df)} activity records")
                if digest in outcomes and outcomes[digest].get("status") == "error":
                    st.error(outcomes[digest]["message"])
                with st.expander("Preview extracted records"):
                    st.dataframe(df.head(20), use_container_width=True, hide_index=True)

        with st.container(key="au_review"):
            st.html('<div class="au-section-heading"><span>03</span>Review and Upload</div><div class="au-helper">Your activity records will be associated with the events you assign.</div>')
            pending = [e for e in entries if outcomes.get(e["digest"], {}).get("status") not in ("saved", "already_saved")]
            ready = sum(bool(e.get("ready")) for e in pending)
            needs = len(pending) - ready
            cols = st.columns(4)
            stats = [(len(selected), "Events", ', '.join(selected) or "None selected"), (len(entries), "Files added", f"{len(entries)-len(pending)} saved"), (ready, "Ready", "to upload"), (needs, "Needs attention", "resolve before upload")]
            for col, (number, title, detail) in zip(cols, stats):
                with col:
                    st.html(f'<div class="au-stat {"attention" if title == "Needs attention" and number else ""}"><strong>{number}</strong><span>{title}</span><small>{esc(detail)}</small></div>')
            if needs:
                st.warning(f"{needs} file(s) need attention before uploading.")
                st.error("Resolve file errors or missing event assignments in Section 2 before uploading.")
            elif not entries:
                st.caption("Select events and add files to enable uploading.")
            upload_col, clear_col, _ = st.columns([2, 1, 3])
            with upload_col:
                run = st.button("Upload and proceed", type="primary", use_container_width=True, key=prefix + "process", disabled=not pending or bool(needs))
            with clear_col:
                st.button("Clear files", key=prefix + "clear_files", on_click=clear_files, disabled=not entries, use_container_width=True)
            if run:
                progress = st.progress(0, text="Preparing your activity data…")
                for number, entry in enumerate(pending, 1):
                    try:
                        progress.progress((number-1)/len(pending), text=f'Processing {entry["name"]}…')
                        outcomes[entry["digest"]] = process_upload(st.session_state.user_id, entry, selected)
                    except Exception as exc:
                        outcomes[entry["digest"]] = {"status": "error", "message": f'Upload failed for {entry["name"]}: {exc}. Correct the issue and retry; successful files will be skipped.'}
                    progress.progress(number/len(pending), text=f"Processed {number} of {len(pending)} files")
                if all(outcomes.get(e["digest"], {}).get("status") in ("saved", "already_saved") for e in entries):
                    st.session_state.current_page = "Predictions & Coach Recommendations"
                    st.session_state.workflow_generate_ids = [outcomes[e["digest"]]["id"] for e in entries]
                st.rerun()
            if entries and not pending:
                st.success("Your activity data has been saved. Previously saved identical files were not duplicated.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("View History", key=prefix + "view"):
                        st.session_state.current_page = "Digital Twin History"
                        st.rerun()
                with c2:
                    st.button("Upload more data", key=prefix + "more", on_click=clear_files)
