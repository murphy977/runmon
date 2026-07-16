import subprocess
import sys
import time as _time

import pytest

from runmon import cli
from runmon.store import RunStore


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RUNMON_CONFIG", str(tmp_path / "config.toml"))
    return tmp_path


def test_run_and_ls_and_status(isolated, capsys):
    rc = cli.main(["run", "--name", "hello", "--",
                   sys.executable, "-c", "print('output-marker')"])
    assert rc == 0
    cli.main(["ls"])
    out = capsys.readouterr().out
    assert "hello" in out and "completed" in out
    rc = cli.main(["status", "hello"])
    out = capsys.readouterr().out
    assert rc == 0 and "output-marker" in out and "exit_code: 0" in out


def test_run_exit_code_passthrough(isolated):
    rc = cli.main(["run", "--", sys.executable, "-c", "import sys; sys.exit(7)"])
    assert rc == 7


def test_run_without_command_errors(isolated, capsys):
    assert cli.main(["run"]) == 2


def test_status_not_found(isolated, capsys):
    assert cli.main(["status", "ghost"]) == 1


def test_no_subcommand_shows_help(isolated, capsys):
    assert cli.main([]) == 2


STUBBORN = (
    "import signal, time, sys\n"
    "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "print('armored', flush=True)\n"
    "time.sleep(300)\n"
)


def test_stop_escalates_to_kill(isolated):
    store = RunStore()
    proc = subprocess.Popen([sys.executable, "-c", STUBBORN],
                            start_new_session=True)
    run = store.create_run(name="stubborn", command="c", cwd="", log_path="")
    store.update_run(run.id, status="running", pid=proc.pid)
    _time.sleep(0.3)
    assert cli.stop_run(store, "stubborn", escalate_wait=0.5) is True
    assert proc.wait(timeout=5) != 0
    assert store.get_run(run.id).status == "stopped"


def test_stop_missing_run(isolated):
    assert cli.main(["stop", "ghost"]) == 1


def test_init_writes_channels(isolated):
    rc = cli.main(["init", "--ntfy-topic", "mytopic", "--webhook", "http://h/x",
                   "--telegram", "BOT:42", "--no-test"])
    assert rc == 0
    from runmon.config import Config
    cfg = Config.load()
    types = {c["type"] for c in cfg.channels}
    assert types == {"ntfy", "webhook", "telegram"}
    tg = next(c for c in cfg.channels if c["type"] == "telegram")
    assert tg["bot_token"] == "BOT" and tg["chat_id"] == "42"


def test_init_reset_replaces(isolated):
    cli.main(["init", "--webhook", "http://a", "--no-test"])
    cli.main(["init", "--reset", "--webhook", "http://b", "--no-test"])
    from runmon.config import Config
    cfg = Config.load()
    assert len(cfg.channels) == 1 and cfg.channels[0]["url"] == "http://b"


def test_init_sends_test_notification(isolated, monkeypatch):
    sent = []
    import runmon.notify as notify
    monkeypatch.setattr(notify, "_post", lambda url, data, headers: sent.append(url))
    rc = cli.main(["init", "--ntfy-topic", "t"])
    assert rc == 0 and len(sent) == 1
