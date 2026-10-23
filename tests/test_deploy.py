"""Hosting concerns: ports, data directory, Railway guard rails, health check, privilege drop."""

import os
import pwd
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from daedalus import __main__ as cli
from daedalus.api import create_app
from daedalus.config import default_data_dir

ROOT = Path(__file__).resolve().parent.parent
HOSTING_VARS = ("DAEDALUS_PORT", "PORT", "DAEDALUS_DATA_DIR", "RAILWAY_VOLUME_MOUNT_PATH", "DAEDALUS_DEFAULT_DATA_DIR",
                "DAEDALUS_PASSWORD", "DAEDALUS_ALLOW_PUBLIC", *cli.RAILWAY_VARS)


@pytest.fixture
def env(monkeypatch):
    for var in HOSTING_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_port_resolution(env):
    assert cli.default_port() == 8787
    env.setenv("PORT", "4321")
    assert cli.default_port() == 4321
    env.setenv("DAEDALUS_PORT", "9000")
    assert cli.default_port() == 9000


def test_data_dir_precedence(env):
    assert default_data_dir() == ROOT / "data"  # source checkout
    env.setenv("DAEDALUS_DEFAULT_DATA_DIR", "/data")
    assert default_data_dir() == Path("/data")
    env.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/mnt/vol")
    assert default_data_dir() == Path("/mnt/vol")
    env.setenv("DAEDALUS_DATA_DIR", "/custom")
    assert default_data_dir() == Path("/custom")


def test_railway_requires_password(env):
    assert cli.hosting_problems() == []  # not on Railway
    env.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert "DAEDALUS_PASSWORD" in cli.hosting_problems()[0]
    env.setenv("DAEDALUS_PASSWORD", "x" * 24)
    assert cli.hosting_problems() == []
    env.delenv("DAEDALUS_PASSWORD")
    env.setenv("DAEDALUS_ALLOW_PUBLIC", "1")
    assert cli.hosting_problems() == []


def test_main_exits_on_railway_without_password(env, tmp_path):
    env.setenv("RAILWAY_PROJECT_ID", "p")
    with pytest.raises(SystemExit) as exc:
        cli.main(["--no-browser", "--data-dir", str(tmp_path)])
    assert exc.value.code == 1


def test_healthz_is_public_but_the_rest_is_not(tmp_path):
    app = create_app(tmp_path, password="s3cret")
    with TestClient(app) as c:
        assert c.get("/healthz").json()["ok"] is True
        assert c.get("/api/cases").status_code == 401
        assert c.get("/api/cases", auth=("x", "s3cret")).status_code == 200


def test_drop_privileges_noop_without_user(tmp_path):
    assert cli.drop_privileges(tmp_path, "") is False


@pytest.mark.skipif(os.name != "posix" or os.geteuid() != 0, reason="needs root")
def test_drop_privileges_as_root(tmp_path):
    try:
        nobody = pwd.getpwnam("nobody")
    except KeyError:
        pytest.skip("no 'nobody' user")
    data = tmp_path / "vol"
    data.mkdir()
    (data / "daedalus.db").write_text("x")
    code = ("import sys, os; from pathlib import Path; from daedalus.__main__ import drop_privileges;"
            f"ok = drop_privileges(Path({str(data)!r}), 'nobody'); print(ok, os.geteuid())")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert out == ["True", str(nobody.pw_uid)]
    assert (data / "daedalus.db").stat().st_uid == nobody.pw_uid
    assert data.stat().st_uid == nobody.pw_uid


def test_dockerfile_is_railway_compatible():
    text = (ROOT / "Dockerfile").read_text()
    assert not any(line.strip().upper().startswith("VOLUME") for line in text.splitlines())
    railway = (ROOT / "railway.toml").read_text()
    assert 'healthcheckPath = "/healthz"' in railway and "numReplicas = 1" in railway
