import http.server
import json
import sys
import threading

import pytest

from runmon import cli


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RUNMON_CONFIG", str(tmp_path / "config.toml"))
    return tmp_path


@pytest.fixture()
def webhook_server():
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append(json.loads(body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/hook", received
    srv.shutdown()


def test_demo_success_notifies(isolated, webhook_server):
    url, received = webhook_server
    cli.main(["init", "--webhook", url, "--no-test"])
    rc = cli.main(["run", "--name", "demo-ok", "--",
                   sys.executable, "-m", "runmon.demo_train",
                   "--epochs", "1", "--steps", "5", "--delay", "0.01"])
    assert rc == 0
    types = [p["type"] for p in received]
    assert "completed" in types


def test_demo_fail_notifies(isolated, webhook_server):
    url, received = webhook_server
    cli.main(["init", "--webhook", url, "--no-test"])
    rc = cli.main(["run", "--name", "demo-fail", "--",
                   sys.executable, "-m", "runmon.demo_train",
                   "--epochs", "1", "--steps", "10", "--delay", "0.01", "--fail"])
    assert rc != 0
    types = [p["type"] for p in received]
    assert "failed" in types and "error_pattern" in types


def test_demo_records_progress(isolated):
    cli.main(["run", "--name", "demo-prog", "--",
              sys.executable, "-m", "runmon.demo_train",
              "--epochs", "1", "--steps", "10", "--delay", "0.01"])
    from runmon.store import RunStore
    run = RunStore().resolve_run("demo-prog")
    assert run.progress is not None and run.last_loss is not None
