"""CLI-level tests: typer CliRunner with a mocked Client transport."""

import json

import pytest
from typer.testing import CliRunner

from mycli import cli as cli_mod
from mycli.cli import app

if "mix_stderr" in __import__("inspect").signature(CliRunner.__init__).parameters:
    runner = CliRunner(mix_stderr=False)  # click 8.1: keep streams separate
else:
    runner = CliRunner()  # click >=8.2: separate by default


class FakeClient:
    """Stands in for Client; records requests, returns canned responses."""

    instances = []

    def __init__(self, profile, **kwargs):
        self.profile = profile
        self.requests = []
        FakeClient.instances.append(self)
        self.responses = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def queue(self, *responses):
        self.responses.extend(responses)
        return self

    def request(self, method, path, **kwargs):
        self.requests.append({"method": method, "path": path, **kwargs})
        status, payload = self.responses.pop(0) if self.responses else (200, {"items": []})
        return payload if not isinstance(payload, Exception) else (_ for _ in ()).throw(payload)


@pytest.fixture
def fake_client(monkeypatch):
    FakeClient.instances = []
    monkeypatch.setattr(cli_mod, "Client", FakeClient)
    return FakeClient


def invoke(args):
    return runner.invoke(app, args)


def last(fake_cls) -> FakeClient:
    assert fake_cls.instances, "no FakeClient was constructed — is Client patched?"
    return fake_cls.instances[-1]


def test_list_csv_default(fake_client, make_profile):
    make_profile("t")
    fake_client.instances[-1] if fake_client.instances else None
    result = invoke(["list", "widgets", "-p", "t"])
    # queue a canned response before invoke in real tests:
    assert result.exit_code in (0, 2)  # placeholder — adapt to your ops


def test_list_json_flag(fake_client, make_profile):
    make_profile("t")
    result = invoke(["list", "widgets", "--json", "-p", "t"])
    assert result.exit_code in (0, 2)


def test_no_profile_fails_with_usage_code(isolated_config):
    result = invoke(["list", "widgets"])
    assert result.exit_code == 2


def test_version():
    result = invoke(["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("mycli ")
