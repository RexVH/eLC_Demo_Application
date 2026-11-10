from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from streamlit.testing.v1 import AppTest

from api import BASE, OPS, LiveClient, clean_credential, content_rows, discovered_versions, enrollment_rows, redact, request_path


class FakeResponse:
    def __init__(self, body=b'{"Identifier":"42"}', status=200, mime="application/json", headers=None):
        self.status_code = status
        self.headers = {"Content-Type": mime, **(headers or {})}
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.body


@pytest.mark.parametrize("mode,value", [
    ("Bearer token", "abc\r\nCookie: bad"),
    ("Bearer token", "curl https://example.com"),
    ("Cookie header", "CAS=not-an-elc-cookie"),
    ("Cookie header", "d2lSessionVal=abc\nAuthorization: bad"),
])
def test_rejects_invalid_credentials(mode, value):
    with pytest.raises(ValueError):
        clean_credential(mode, value)


def test_read_only_requests_are_fixed_host_and_do_not_follow_redirects(monkeypatch):
    client = LiveClient("Bearer token", "Bearer example-secret")
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(status=302, headers={"Location": "https://outside.invalid/file"})

    monkeypatch.setattr(client.session, "get", get)
    result = client.call("identity", "1.49", "1.82")
    assert len(calls) == 1
    assert calls[0][0].startswith(BASE + "/d2l/api/")
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["headers"]["Authorization"] == "Bearer example-secret"
    assert "redirect" in result.error
    assert "example-secret" not in repr(result)


def test_cookie_header_and_secret_redaction(monkeypatch):
    client = LiveClient("Cookie header", "Cookie: d2lSessionVal=abc123; d2lSecureSessionVal=xyz789")

    def get(url, **kwargs):
        assert kwargs["headers"]["Cookie"].startswith("d2lSessionVal=")
        assert "Authorization" not in kwargs["headers"]
        return FakeResponse(b'{"Message":"abc123 xyz789", "Token":"sensitive"}', status=403)

    monkeypatch.setattr(client.session, "get", get)
    result = client.call("identity", "1.49", "1.82")
    assert result.data == {"Message": "[hidden] [hidden]", "Token": "[hidden]"}
    assert result.error
    client.close()
    assert client._credential == ""


def test_html_login_is_not_a_successful_api_or_file_response(monkeypatch):
    client = LiveClient("Bearer token", "example-secret")
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(b'<html>UGA MyID Login</html>', mime="text/html"))
    assert client.call("identity", "1.49", "1.82").error
    result = client.call("file", "1.49", "1.82", "90001", "92001")
    assert result.error
    assert not result.body


def test_download_preserves_pdf_bytes(monkeypatch):
    client = LiveClient("Bearer token", "example-secret")
    body = b"%PDF-1.4\nexample fixture"
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(body, mime="application/pdf", headers={"Content-Disposition": 'attachment; filename="syllabus.pdf"'}))
    result = client.call("file", "1.49", "1.82", "90001", "92001")
    assert not result.error
    assert result.body == body
    assert result.filename == "syllabus.pdf"


def test_content_limit_and_error_bodies_never_become_downloads(monkeypatch):
    import api
    client = LiveClient("Bearer token", "example-secret")
    monkeypatch.setattr(api, "MAX_BYTES", 10)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(b"x" * 11, mime="application/pdf"))
    result = client.call("file", "1.49", "1.82", "90001", "92001")
    assert "limit" in result.error
    assert not result.body


def test_path_ids_and_versions_cannot_change_destination():
    with pytest.raises(ValueError):
        request_path("file", "1.49", "1.82", "https://evil.invalid", "12")
    with pytest.raises(ValueError):
        request_path("identity", "../../other", "1.82")
    with pytest.raises(KeyError):
        request_path("classlist", "1.49", "1.82", "90001")


def test_nested_content_and_version_ordering():
    rows = content_rows({"Modules": [{"ModuleId": 1, "Title": "Start", "Topics": [], "Modules": [{"ModuleId": 2, "Title": "Documents", "Topics": [{"TopicId": 3, "Title": "Course syllabus"}]}]}]})
    assert rows[-1]["Location"] == "Start / Documents"
    assert rows[-1]["Syllabus candidate"] == "Yes"
    assert discovered_versions([{"ProductCode": "le", "Version": "1.9"}, {"ProductCode": "le", "Version": "1.82"}, {"ProductCode": "lp", "LatestVersion": "1.49"}]) == {"le": "1.82", "lp": "1.49"}
    assert enrollment_rows({"Items": [{"OrgUnit": {"Id": 42, "Name": "Course"}, "Access": {"CanAccess": True}}]})[0]["ID"] == "42"
    assert redact({"nested": [{"access_token": "x"}]}) == {"nested": [{"access_token": "[hidden]"}]}


def test_ui_sample_sequence_and_disconnect():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
    assert not app.exception
    app.button(key="sample_start").click().run()
    app.selectbox(key="operation").select("enrollments").run()
    app.button(key="run").click().run()
    assert len(app.session_state["courses"]) == 4
    app.selectbox(key="operation").select("toc").run()
    app.selectbox(key="course_picker").select("90002").run()
    app.button(key="run").click().run()
    assert app.session_state["content"]["90002"][-1]["Syllabus candidate"] == "Yes"
    app.selectbox(key="operation").select("identity").run()
    app.selectbox(key="operation").select("module").run()
    assert app.selectbox(key="course_picker").value == "90002"
    assert not app.button(key="run").disabled
    app.selectbox(key="operation").select("file").run()
    app.button(key="run").click().run()
    assert app.session_state["last"][1].body.startswith(b"SYNTHETIC")
    assert not app.exception
    app.radio(key="nav").set_value("Run log").run()
    assert len(app.session_state["history"]) == 3
    app.button(key="disconnect").click().run()
    assert app.session_state["client"] is None
    assert app.session_state["history"] == []


def test_connect_clears_old_data_and_credential_widget():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
    app.button(key="sample_start").click().run()
    app.selectbox(key="operation").select("enrollments").run()
    app.button(key="run").click().run()
    app.radio(key="nav").set_value("Connection").run()
    app.text_input(key="credential").set_value("Bearer development-test-only")
    app.button(key="connect").click().run()
    assert not app.exception
    assert app.session_state["source"] == "Bearer token"
    assert not app.session_state["verified"]
    assert app.session_state["courses"] == []
    assert app.session_state["history"] == []
    assert app.session_state["credential"] == ""
