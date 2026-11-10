"""Run with: python -m streamlit run app.py"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from api import BASE, DOCS, OPERATIONS, OPS, LiveClient, content_rows, discovered_versions, enrollment_rows, parameters, request_path
from sample import COURSES, SampleClient

st.set_page_config(page_title="eLC API playground", page_icon=":material/api:", layout="wide")

DEFAULTS = {"client": None, "source": "Disconnected", "verified": False, "courses": [], "content": {}, "history": [], "last": None, "lp": "1.49", "le": "1.82", "nav": "API explorer", "connection_error": "", "credential": ""}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_connection() -> None:
    if st.session_state.client is not None:
        st.session_state.client.close()
    for key in list(st.session_state):
        if key not in ("nav",):
            del st.session_state[key]


def use_sample() -> None:
    reset_connection()
    st.session_state.client = SampleClient()
    st.session_state.source = "Sample data"
    st.session_state.nav = "API explorer"


def connect() -> None:
    try:
        client = LiveClient(st.session_state.auth_method, st.session_state.credential)
    except ValueError as exc:
        st.session_state.connection_error = str(exc)
        st.session_state.credential = ""
        return
    method = st.session_state.auth_method
    reset_connection()
    st.session_state.client = client
    st.session_state.source = method
    st.session_state.credential = ""
    st.session_state.nav = "API explorer"


def apply_versions() -> None:
    latest = st.session_state.last
    if latest and latest[1].operation == "versions":
        for key, value in discovered_versions(latest[1].data).items():
            st.session_state[key] = value


def execute(key: str, course: str, item: str, bookmark: str):
    result = st.session_state.client.call(key, st.session_state.lp, st.session_state.le, course, item, bookmark)
    signature = (key, course, item, bookmark, st.session_state.lp, st.session_state.le)
    st.session_state.last = (signature, result)
    st.session_state.history.insert(0, {"Time (UTC)": datetime.now(timezone.utc).strftime("%H:%M:%S"), "Source": "Sample" if result.sample else "Live", "Operation": OPS[key].title, "Status": result.status or "Network error", "ms": result.elapsed_ms, "URL": result.url, "Outcome": result.error or "Success"})
    st.session_state.history = st.session_state.history[:50]
    if not result.error:
        if key == "identity":
            st.session_state.verified = not result.sample
        if key == "enrollments":
            rows = enrollment_rows(result.data)
            if not bookmark:
                st.session_state.courses = rows
            else:
                current = {row["ID"]: row for row in st.session_state.courses}
                current.update({row["ID"]: row for row in rows})
                st.session_state.courses = list(current.values())
        if key == "toc":
            st.session_state.content[course] = content_rows(result.data)
    elif key == "identity":
        st.session_state.verified = False
    return result


with st.sidebar:
    st.markdown("### :material/api: eLC playground")
    st.caption("Jump Start · UGA Gen AI Competition")
    st.radio("Workspace", ["API explorer", "Connection", "Run log", "Getting started"], key="nav")
    st.divider()
    source = st.session_state.source
    st.badge(source, color="orange" if source == "Sample data" else "gray")
    if st.session_state.client:
        st.caption("Verified with whoami" if st.session_state.verified else "Run Test my connection to verify live access.")
        st.button("Disconnect and clear", key="disconnect", on_click=reset_connection, width="stretch", icon=":material/logout:")
    st.caption("Read-only calls · Credentials stay in this app session")

st.title("eLC API playground")
st.caption("Explore one request at a time. Discover courses, inspect content, and retrieve a syllabus.")

if st.session_state.nav == "Connection":
    st.header("Connect your eLC session")
    st.markdown("Use a credential from your own signed-in browser. The app sends it only to **uga.view.usg.edu**. Registered OAuth will replace this temporary connection method once available.")
    st.link_button("Open eLC", BASE, icon=":material/open_in_new:")
    st.segmented_control("Credential type", ["Bearer token", "Cookie header"], default="Bearer token", key="auth_method")
    with st.form("connection_form"):
        st.text_input("Browser credential", type="password", key="credential", help="Paste only a bearer token or a single Cookie header value. Do not paste a complete cURL command or HAR file.")
        st.form_submit_button("Use this credential", key="connect", on_click=connect, type="primary")
    if st.session_state.connection_error:
        st.error(st.session_state.connection_error)
    with st.expander("Find the credential in Edge or Chrome"):
        st.markdown("""
1. Sign into eLC normally, then open **Developer tools → Network**.
2. Filter for **Fetch/XHR**, reload eLC, and look for a successful request to `/d2l/api/` on `uga.view.usg.edu`.
3. Under **Headers → Request headers**, look for **Authorization: Bearer …**. Copy the token into the masked field and choose **Bearer token**.
4. If the successful request uses cookies instead, choose **Cookie header** and copy that request's **Cookie** header value. If the header is unavailable, **Application → Cookies → https://uga.view.usg.edu** shows cookie names and values. Build one line such as `d2lSessionVal=…; d2lSecureSessionVal=…`, including any other eLC cookies that the successful request requires.
5. Click **Use this credential**, then run **Test my connection**.

The cookie example is a starting point, not a guarantee that those two cookies authorize every endpoint. A cookie working in the website may still be rejected by an API. A token captured from the frontend may have limited scopes. If access fails, recapture the credential from a successful API request and inspect the response.

Keep credentials in the local app; do not paste them into chat, source files, screenshots, or shared exports. This app does not read your browser profile or mint frontend tokens.
""")
    st.divider()
    st.subheader("Rehearse without credentials")
    st.markdown("Sample mode uses the four course names from your screenshot. Every ID, response, deadline, and document is fictional.")
    st.button("Use sample data", key="sample_connection", on_click=use_sample, icon=":material/science:")

elif st.session_state.nav == "Getting started":
    st.header("From browser session to syllabus")
    st.markdown("""
1. Open **Connection** and enter a temporary bearer token or Cookie header, or choose **Use sample data**.
2. Run **Discover API versions**, then click **Use discovered versions**. LP and LE are separate API families; their versions need not match.
3. Run **Test my connection**. A successful versions request alone does not verify your credential.
4. Run **List my courses**. Use the returned bookmark to load the next page if needed. The course picker accumulates retrieved pages.
5. Select a course and run **Browse course content**. Review the flattened module/topic table and syllabus candidates.
6. Run **Read a topic** to inspect its metadata, then **Download a topic file** for that topic ID. Save the returned bytes using **Save downloaded file**.
7. Explore announcements, assignment metadata, quizzes, and calendar events as individual requests.

If the syllabus is attached to the course overview, use **Read course overview** and **Download overview attachment** instead.
""")
    st.subheader("Your screenshot: reference courses")
    for name in COURSES:
        st.markdown(f"- {name}")
    st.caption("The screenshot supplies names, not eLC course IDs. Live enrollment responses may include more courses than the homepage cards. ARTI9300's 67977 appears in its title; it is not assumed to be its API org-unit ID.")
    st.subheader("Understanding responses")
    st.markdown("**401:** expired or invalid credential. **403:** role, scope, or authentication-method limitation. **404:** wrong version/ID or missing resource. **429:** rate limit. **3xx:** redirect; this client stops rather than forwarding credentials. **HTML instead of JSON:** often a login page.")
    st.markdown("This first build has 16 discrete read operations. eLC writes, roster access, grades, submissions, AI generation, Graph writes, and unattended monitoring are outside this version.")
    st.caption("Credentials and retrieved data are held in per-session server memory, with no shared Streamlit cache or automatic file persistence. Disconnect clears app-held state; it does not log you out of eLC or revoke the browser credential. Run this credential-entry prototype locally.")
    st.link_button("Brightspace API reference", "https://docs.valence.desire2learn.com/reference.html")

elif st.session_state.nav == "Run log":
    st.header("Run log")
    st.caption("The latest 50 calls in this session. Credentials, response bodies, and student rosters are not included.")
    if st.session_state.history:
        st.dataframe(st.session_state.history, hide_index=True, alt="API call history with status, timing, and request URL")
        st.download_button("Export run log", json.dumps(st.session_state.history, indent=2), "elc-run-log.json", "application/json", key="export_log")
    else:
        st.info("Run an operation in API explorer to start the log.")

else:
    if not st.session_state.client:
        st.info("Connect a browser credential from the Connection page, or start with sample data.")
        st.button("Use sample data", key="sample_start", on_click=use_sample, type="primary", icon=":material/science:")
        st.stop()
    sample = st.session_state.source == "Sample data"
    if sample:
        st.warning("Sample mode — course names match your screenshot; all IDs, course contents, and results are synthetic.")
    else:
        st.info("Live eLC — each Run request button makes one read-only API request with your supplied credential.")

    with st.expander("API versions", expanded=False):
        left, right = st.columns(2)
        with left:
            st.text_input("Learning Platform (LP)", key="lp", persist_state="session")
        with right:
            st.text_input("Learning Environment (LE)", key="le", persist_state="session")
        st.caption("Initial values are reference defaults, not verified UGA versions. Discover versions before other live calls.")

    key = st.selectbox("API operation", list(OPS), format_func=lambda k: OPS[k].title, key="operation")
    if key not in OPS:
        st.stop()
    op = OPS[key]
    st.markdown(op.explanation)
    course = ""
    item = ""
    bookmark = ""
    if op.needs_course:
        courses = st.session_state.courses
        if courses:
            course = st.selectbox("Course", [r["ID"] for r in courses], format_func=lambda cid: next((f'{r["Course"]} · {cid}' for r in courses if r["ID"] == cid), cid), key="course_picker", persist_state="session")
            st.caption(f"{len(courses)} of your course enrollments loaded; no class roster requested.")
        else:
            st.info("Run List my courses first, or enter the course ID from its eLC URL: /d2l/home/123456.")
        manual = st.text_input("Course ID override (optional)", key="manual_course", placeholder="Numeric org-unit ID", persist_state="session")
        course = manual.strip() or course
    if op.item:
        content = st.session_state.content.get(course, [])
        kind = "Module" if op.item == "Module ID" else "Topic"
        choices = [r for r in content if r["Kind"] == kind and r["ID"].isdigit()]
        if choices:
            chosen = st.selectbox("Discovered " + kind.lower(), [r["ID"] for r in choices], format_func=lambda tid: next((f'{r["Title"]} · {tid}' for r in choices if r["ID"] == tid), tid), key=f"{kind.lower()}_picker")
            item = chosen
        override = st.text_input(op.item + " override (optional)" if choices else op.item, key=f"{kind.lower()}_override", placeholder="Numeric ID")
        item = override.strip() or item
    if key == "enrollments":
        bookmark = st.text_input("Bookmark (blank for first page)", key="bookmark")

    ready = True
    try:
        path = request_path(key, st.session_state.lp, st.session_state.le, course, item)
    except ValueError as exc:
        ready = False
        st.caption(str(exc))
        path = op.path
    st.code("GET " + BASE + path, language="http")
    query = parameters(key, bookmark)
    if query:
        st.caption("Query parameters")
        st.json(query, expanded=False)
    st.caption("Authentication: " + ("not required for version discovery" if key == "versions" else st.session_state.source + " [hidden]"))
    st.markdown(f"[Operation reference]({DOCS}{op.doc})")
    if op.scope:
        st.caption("Documented OAuth scope: " + op.scope + " (for the registered OAuth connection; browser credentials may behave differently).")
    if st.button("Run request", key="run", type="primary", disabled=not ready, icon=":material/play_arrow:"):
        with st.spinner("Running " + op.title.lower() + "…"):
            execute(key, course, item, bookmark)
        # Refresh dependent pickers and counts using the data just retrieved.
        st.rerun()

    signature = (key, course, item, bookmark, st.session_state.lp, st.session_state.le)
    latest = st.session_state.last
    if latest and latest[0] == signature:
        result = latest[1]
        st.divider()
        st.subheader("Response")
        with st.container(horizontal=True):
            st.badge("SAMPLE" if result.sample else "LIVE", color="orange" if result.sample else "blue")
            st.badge(f"HTTP {result.status}" if result.status else "Network error", color="red" if result.error else "green")
            st.caption(f"{result.elapsed_ms} ms · {result.mime or 'no content type'}")
        if result.error:
            st.error(result.error)
        elif key == "identity":
            st.success("Sample connection responded." if sample else "Your browser credential successfully authenticated an API call.")
        if key == "versions" and not result.error and discovered_versions(result.data):
            st.button("Use discovered versions", key="apply_versions", on_click=apply_versions)
        if key == "enrollments" and not result.error:
            rows = enrollment_rows(result.data)
            st.metric("Your course enrollments loaded", len(st.session_state.courses))
            if rows:
                st.dataframe(rows, hide_index=True, alt="Your own enrolled courses, with course IDs and access status")
            paging = result.data.get("PagingInfo", {}) if isinstance(result.data, dict) else {}
            if paging.get("HasMoreItems"):
                st.info("More enrollments are available. Copy the bookmark below into the Bookmark field and run again.")
                st.code(str(paging.get("Bookmark", "")), language=None)
            else:
                st.caption("No additional page reported by this response.")
        if key == "toc" and not result.error:
            rows = content_rows(result.data)
            if rows:
                st.dataframe(rows, hide_index=True, alt="Nested course content flattened into modules and topics, with syllabus candidates")
                candidates = [r for r in rows if r["Syllabus candidate"]]
                st.caption(f"{len(candidates)} syllabus candidate(s) by title. Review candidates before downloading; no match does not mean no syllabus exists.")
            else:
                st.info("No visible content modules returned for this course.")
        if result.body:
            st.success(f"Retrieved {len(result.body):,} bytes: {result.filename}")
            st.download_button("Save downloaded file", result.body, result.filename, result.mime or "application/octet-stream", key="save_file")
        if result.data is not None:
            if key == "identity":
                show_identity = st.checkbox("Show my own identity response", key="show_identity", value=False)
                if show_identity:
                    st.json(result.data)
                else:
                    st.caption("Identity response hidden for presenting. Enable the checkbox to inspect your own information.")
            else:
                with st.expander("Inspect JSON response", expanded=key not in ("toc", "enrollments")):
                    st.json(result.data)
    elif latest:
        st.caption("Inputs changed. Run this request to see its response. Previous call metadata remains in Run log.")
