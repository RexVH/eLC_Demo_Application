# eLC API playground

A local Streamlit playground with 16 individually runnable, read-only Brightspace API operations. It supports temporary bearer tokens, browser Cookie headers, and an explicitly synthetic rehearsal mode. Registered OAuth, Make, Claude, Microsoft Graph, Slack, and polling are not implemented in this first milestone.

## Run on Windows

Open PowerShell in this folder, then run each command:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501. Activation is unnecessary. The checked-in configuration binds the app to loopback and disables Streamlit usage telemetry. Stop it with Ctrl+C.

## Use your browser session

1. Sign into https://uga.view.usg.edu/ in Edge or Chrome.
2. Open Developer tools → Network, select Fetch/XHR, and reload. Find a successful request to `/d2l/api/` on `uga.view.usg.edu`.
3. In its request headers, copy the **Authorization: Bearer …** value if present. In the playground's Connection page, select **Bearer token** and paste into the masked field. Both a bare token and `Bearer …` are accepted.
4. Alternatively, select **Cookie header** and copy the successful request's Cookie header value. If unavailable, inspect Application → Cookies for the eLC host. Compose a single line `d2lSessionVal=…; d2lSecureSessionVal=…`, including other eLC cookies required by the successful request. Do not copy UGA SSO cookies, a full HAR, or an executable cURL command.
5. Choose **Use this credential**. Run **Discover API versions**, **Use discovered versions**, then **Test my connection**.

Browser session credentials are temporary. Cookie authentication is best-effort, and frontend bearer tokens can have limited scopes. This build does not automate browser-profile access or use undocumented token-minting endpoints. A successful version request alone is not an authentication test. A 403 may indicate an authentication-method limitation, insufficient scope, or a course-role restriction.

Credentials are kept only in this Streamlit session's server memory. They are not written to disk, included in run logs, put in URLs, shared through Streamlit caches, or forwarded across redirects. Connection forms clear submitted credential fields; disconnect clears app-held credentials and retrieved responses, but does not revoke the original browser credential or log out of eLC. Do not expose this prototype as a shared public server.

## Teaching sequence

1. **Discover API versions** and apply the returned LP/LE values.
2. **Test my connection** (`whoami`); identifying data is hidden by default.
3. **List my courses**. This retrieves your own course enrollments, not enrolled students. `orgUnitTypeId=3` selects Brightspace's usual Course Offering type; confirm UGA results. Each click loads a page. Copy its bookmark into the field for another page; retrieved courses accumulate without duplicates.
4. Select one returned course for **Browse course content**. Inspect nested modules/topics and syllabus candidates.
5. Use **Read a topic**, then **Download a topic file** with its ID. The returned file can be saved from the UI. Syllabi stored in the overview have separate overview and overview-attachment operations. External/LTI syllabus links may require a different integration.
6. Try the independent root-module, module-structure, course-access, course-details, announcement, assignment, quiz, and calendar operations.
7. Inspect **Run log** for status, timing, and request URL. Export contains metadata only. Other paged endpoints return their native JSON, but only enrollments have a next-page workflow in this version.

Each call sends one GET to a fixed operation on UGA's eLC host. No arbitrary URL runner, roster endpoint, grades, submissions, quiz attempts, or eLC write operations are included. Read operations may still affect platform access logs. Redirects are reported rather than followed, including legitimate file redirects; file responses are limited to 32 MiB. Network timeouts and TLS validation are enabled.

## Sample mode and screenshot

Choose **Use sample data** to rehearse without network calls. Course names are transcribed from the supplied screenshot:

- ARTI9300 Doctoral Dissertation Fall 2026 67977
- AI Sandbox Course 2025
- UGA Data Science Competition 2021
- DAE at a Distance | An eLC Experience 3.0

All sample org-unit/module/topic IDs, course contents, deadlines, and responses are fictional. The sample download is a labeled text syllabus, not a real course PDF. The ARTI title's 67977 is not assumed to be an API ID. Live course IDs come from the API or a course's `/d2l/home/<ID>` browser URL. Homepage cards may show fewer courses than the enrollment API.

## Development

```powershell
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest -q
```

`api.py` owns the operation catalog, fixed-host client, credential validation/redaction, and response transforms. `sample.py` provides explicitly synthetic fixtures. `app.py` holds the UI and per-session state. Replace the temporary credential provider with the approved OAuth flow later; endpoint operations can stay the same. No live access has been validated until the presenter supplies a current credential and runs the connection test.

## Primary references

- [Brightspace API reference](https://docs.valence.desire2learn.com/reference.html)
- [API properties/version discovery](https://docs.valence.desire2learn.com/res/apiprop.html)
- [Current-user enrollments](https://docs.valence.desire2learn.com/res/enroll.html)
- [Course content and file download](https://docs.valence.desire2learn.com/res/content.html)
- [Brightspace OAuth](https://docs.valence.desire2learn.com/basic/oauth2.html)
