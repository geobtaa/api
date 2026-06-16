from types import SimpleNamespace

from starlette.requests import Request

from app import main as app_main


def test_appsignal_route_name_uses_fastapi_route_template(monkeypatch):
    calls = []

    class FakeTracing:
        def set_name(self, name):
            calls.append(("set_name", name))

        def set_root_name(self, name):
            calls.append(("set_root_name", name))

    monkeypatch.setattr(app_main, "APPSIGNAL_ENABLED", True)
    monkeypatch.setattr(app_main, "appsignal", SimpleNamespace(tracing=FakeTracing()))
    monkeypatch.setattr(app_main, "trace", None)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/resources/princeton-q237ht618",
            "headers": [],
            "route": SimpleNamespace(path="/api/v1/resources/{id}"),
            "root_path": "",
        }
    )

    app_main._set_appsignal_route_name(request)

    assert calls == [
        ("set_name", "GET /api/v1/resources/{id}"),
        ("set_root_name", "GET /api/v1/resources/{id}"),
    ]
