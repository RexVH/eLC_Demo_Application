"""Read-only Brightspace operations, independent of Streamlit."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlencode

import requests

BASE = "https://uga.view.usg.edu"
MAX_BYTES = 32 * 1024 * 1024
DOCS = "https://docs.valence.desire2learn.com/res/"


@dataclass(frozen=True)
class Operation:
    key: str
    title: str
    path: str
    explanation: str
    doc: str
    scope: str = ""
    needs_course: bool = False
    item: str = ""
    file: bool = False


OPERATIONS = [
    Operation("versions", "Discover API versions", "/d2l/api/versions/", "Find the LP and LE versions this eLC instance supports. This public endpoint does not prove authentication.", "apiprop.html"),
    Operation("identity", "Test my connection", "/d2l/api/lp/{lp}/users/whoami", "Verify the current user context. Only your own identity is requested; presentation mode hides identifying fields.", "user.html", "users:own_profile:read"),
    Operation("enrollments", "List my courses", "/d2l/api/lp/{lp}/enrollments/myenrollments/", "Retrieve one page of your own course enrollments. Load subsequent pages explicitly; no class roster is requested.", "enroll.html", "enrollment:own_enrollment:read"),
    Operation("enrollment", "Read my course access", "/d2l/api/lp/{lp}/enrollments/myenrollments/{course}", "Read your own enrollment and access information for one course.", "enroll.html", "enrollment:own_enrollment:read", True),
    Operation("course", "Read course details", "/d2l/api/lp/{lp}/courses/{course}", "Inspect the course offering metadata, including course name and dates where available.", "course.html", "", True),
    Operation("toc", "Browse course content", "/d2l/api/le/{le}/{course}/content/toc", "Retrieve nested modules and topics. The local table highlights syllabus candidates; selecting one does not download it.", "content.html", "content:toc:read", True),
    Operation("roots", "List root modules", "/d2l/api/le/{le}/{course}/content/root/", "Inspect the top-level content modules as a separate API operation.", "content.html", "content:modules:readonly", True),
    Operation("module", "Read a module", "/d2l/api/le/{le}/{course}/content/modules/{item}/structure/", "Read a module's immediate children. Use Browse course content to discover module IDs.", "content.html", "content:modules:readonly", True, "Module ID"),
    Operation("topic", "Read a topic", "/d2l/api/le/{le}/{course}/content/topics/{item}", "Inspect a content topic's metadata before requesting its underlying file.", "content.html", "content:topics:readonly", True, "Topic ID"),
    Operation("file", "Download a topic file", "/d2l/api/le/{le}/{course}/content/topics/{item}/file", "Retrieve the underlying file bytes. Works for file topics; external links and LTI activities may not support this operation.", "content.html", "content:file:read", True, "Topic ID", True),
    Operation("overview", "Read course overview", "/d2l/api/le/{le}/{course}/overview", "Inspect the course overview, another possible location for a syllabus.", "content.html", "", True),
    Operation("overview_file", "Download overview attachment", "/d2l/api/le/{le}/{course}/overview/attachment", "Download the overview attachment if one exists. A course without one may return 404.", "content.html", "", True, file=True),
    Operation("news", "List announcements", "/d2l/api/le/{le}/{course}/news/", "Read course announcements without retrieving discussion posts or class rosters.", "news.html", "", True),
    Operation("assignments", "List assignments", "/d2l/api/le/{le}/{course}/dropbox/folders/", "Read assignment-folder metadata and available due dates. This does not request submissions or feedback.", "dropbox.html", "", True),
    Operation("quizzes", "List quizzes", "/d2l/api/le/{le}/{course}/quizzes/", "Read quiz metadata available to your role. This does not request attempts, responses, or answer keys.", "quiz.html", "", True),
    Operation("calendar", "List calendar events", "/d2l/api/le/{le}/{course}/calendar/events/", "Read the calendar events available to you in this course.", "calendar.html", "calendar:events:read", True),
]
OPS = {op.key: op for op in OPERATIONS}


def clean_credential(mode: str, value: str) -> str:
    value = value.strip()
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Paste one credential value, without line breaks or other headers.")
    if mode == "Bearer token":
        value = re.sub(r"^(?:Authorization:\s*)?Bearer\s+", "", value, flags=re.I)
        if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", value):
            raise ValueError("Paste only the bearer token or its Authorization header value.")
    elif mode == "Cookie header":
        value = re.sub(r"^Cookie:\s*", "", value, flags=re.I)
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(value)
        except Exception:
            raise ValueError("The Cookie header could not be parsed.") from None
        if not jar or not any(name.lower().startswith("d2l") for name in jar):
            raise ValueError("Expected eLC cookies (names beginning with d2l), not UGA SSO cookies.")
    else:
        raise ValueError("Choose bearer token or Cookie header.")
    return value


def request_path(op_key: str, lp: str, le: str, course: str = "", item: str = "") -> str:
    op = OPS[op_key]  # Only registered read operations are accepted.
    if not all(re.fullmatch(r"\d+\.\d+", version) for version in (lp, le)):
        raise ValueError("API versions must look like 1.49; discover versions for UGA before calling live endpoints.")
    for needed, value, label in ((op.needs_course, course, "Course ID"), (bool(op.item), item, op.item)):
        if needed and not re.fullmatch(r"[1-9]\d*", str(value)):
            raise ValueError(f"{label} must be a positive numeric eLC ID.")
    return op.path.format(lp=lp, le=le, course=course, item=item)


def parameters(op_key: str, bookmark: str = "") -> dict[str, str]:
    if op_key != "enrollments":
        return {}
    result = {"orgUnitTypeId": "3"}
    if bookmark.strip():
        result["bookmark"] = bookmark.strip()
    return result


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {k: "[hidden]" if re.search(r"token|cookie|authorization|password|secret", k, re.I) else redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[hidden]")
        value = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [hidden]", value)
    return value


@dataclass
class Result:
    operation: str
    url: str
    status: int
    elapsed_ms: int
    data: Any = None
    body: bytes = field(default=b"", repr=False)
    mime: str = ""
    filename: str = "download.bin"
    error: str = ""
    sample: bool = False


class LiveClient:
    """Session-local client. Credentials never enter the result or request history."""
    def __init__(self, mode: str, credential: str):
        self.mode = mode
        self._credential = clean_credential(mode, credential)
        self.session = requests.Session()
        self.session.trust_env = False  # No ambient netrc credentials or proxies.

    def close(self) -> None:
        self.session.close()
        self._credential = ""
        self.session.cookies.clear()

    def call(self, key: str, lp: str, le: str, course: str = "", item: str = "", bookmark: str = "") -> Result:
        path = request_path(key, lp, le, course, item)
        params = parameters(key, bookmark)
        url = BASE + path + ("?" + urlencode(params) if params else "")
        headers = {"Accept": "*/*" if OPS[key].file else "application/json"}
        if key != "versions":
            headers["Authorization" if self.mode == "Bearer token" else "Cookie"] = (
                "Bearer " + self._credential if self.mode == "Bearer token" else self._credential
            )
        started = time.monotonic()
        result = Result(key, url, 0, 0)
        try:
            # Redirects are deliberately not followed: credentials only go to this eLC host.
            with self.session.get(BASE + path, params=params, headers=headers, timeout=(8, 25), allow_redirects=False, stream=True) as response:
                result.status = response.status_code
                result.mime = response.headers.get("Content-Type", "").split(";")[0].lower()
                if 300 <= result.status < 400:
                    result.error = "eLC returned a redirect. The browser session may have expired, or this file may use another download location. Redirects are not followed; inspect the request in eLC."
                    return result
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        result.error = "Response exceeds the playground's 32 MiB limit."
                        return result
                    chunks.append(chunk)
                body = b"".join(chunks)
                secret_values = [self._credential]
                if self.mode == "Cookie header":
                    jar: SimpleCookie = SimpleCookie()
                    jar.load(self._credential)
                    secret_values.extend(m.value for m in jar.values())
                try:
                    result.data = redact(json.loads(body), tuple(secret_values))
                except (ValueError, UnicodeError):
                    result.data = None
                if result.status == 401:
                    result.error = "Unauthorized. Reconnect with a fresh credential from your signed-in eLC browser session."
                elif result.status == 403:
                    result.error = "Forbidden. The session/token may not support this endpoint, its scopes may be insufficient, or your role may not permit it. A new token cannot grant extra course permissions."
                elif result.status == 404:
                    result.error = "Not found. Check API versions and IDs; this course may not contain the requested resource."
                elif result.status == 429:
                    result.error = "Rate limited. Wait before running the call again."
                elif not 200 <= result.status < 300:
                    result.error = f"eLC returned HTTP {result.status}."
                elif OPS[key].file:
                    probe = body[:10000].lower()
                    login = any(marker in probe for marker in (b'/d2l/login', b'uga myid login', b'sso.uga.edu/cas/login'))
                    if login:
                        result.error = "Received an HTML login page instead of the requested file. Reconnect with a fresh session."
                    elif result.data is not None:
                        result.error = "Expected file bytes but received JSON. Inspect the response below."
                    else:
                        result.body = body
                        disposition = response.headers.get("Content-Disposition", "")
                        match = re.search(r'filename="?([^";]+)', disposition, re.I)
                        filename = match.group(1) if match else ("syllabus.pdf" if result.mime == "application/pdf" else f"topic-{item or course}.bin")
                        result.filename = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", filename)[:160]
                elif result.data is None:
                    result.error = "Expected JSON but received another format (possibly an eLC login page). Reconnect or check the API version."
        except requests.RequestException:
            # Do not print exception/request objects: they may contain credential headers.
            result.error = "Network or TLS error. Check connectivity to uga.view.usg.edu and retry."
        finally:
            result.elapsed_ms = round((time.monotonic() - started) * 1000)
        return result


def enrollment_rows(data: Any) -> list[dict[str, str]]:
    items = data.get("Items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    rows = []
    for entry in items:
        unit = entry.get("OrgUnit", {})
        if unit.get("Id") is not None:
            rows.append({"ID": str(unit["Id"]), "Course": unit.get("Name", "Unnamed course"), "Code": unit.get("Code") or "", "Accessible": str(entry.get("Access", {}).get("CanAccess", "Unknown"))})
    return rows


def content_rows(data: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def walk(modules: list[dict], parent: str = "") -> None:
        for module in modules:
            title = str(module.get("Title", "Untitled module"))
            location = f"{parent} / {title}" if parent else title
            rows.append({"Kind": "Module", "ID": str(module.get("ModuleId", module.get("Id", ""))), "Title": title, "Location": parent, "Syllabus candidate": ""})
            for topic in module.get("Topics", []):
                title = str(topic.get("Title", "Untitled topic"))
                candidate = bool(re.search(r"syllabus|course\s*(outline|schedule)", title, re.I))
                rows.append({"Kind": "Topic", "ID": str(topic.get("TopicId", topic.get("Id", ""))), "Title": title, "Location": location, "Syllabus candidate": "Yes" if candidate else ""})
            walk(module.get("Modules", []), location)

    if isinstance(data, dict):
        walk(data.get("Modules", []))
    return rows


def discovered_versions(data: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if not isinstance(data, list):
        return result
    for entry in data:
        product = entry.get("ProductCode")
        version = entry.get("LatestVersion") or entry.get("Version")
        if product in ("lp", "le") and isinstance(version, str) and re.fullmatch(r"\d+\.\d+", version):
            if product not in result or tuple(map(int, version.split("."))) > tuple(map(int, result[product].split("."))):
                result[product] = version
    return result
