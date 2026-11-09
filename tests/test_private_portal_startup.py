"""Private LAN startup must fail closed before any listening socket is created."""

import json
import sys

import pytest
from ocf_tools import listening_portal as portal

pytestmark = pytest.mark.unit


def configure(tmp_path, monkeypatch, values):
    library = tmp_path / "library"
    library.mkdir()
    path = tmp_path / "portal.json"
    path.write_text(json.dumps({"library": str(library), **values}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["portal", "--config", str(path)])


@pytest.mark.parametrize("host", ["192.0.2.20", "0.0.0.0", "::"])
@pytest.mark.parametrize("missing", ["credentials_file", "certificate", "private_key"])
def test_lan_requires_all_access_controls_before_binding(tmp_path, monkeypatch, host, missing):
    credentials = tmp_path / "login"
    credentials.write_text("synthetic:" + "x" * 32)
    values = {
        "host": host,
        "credentials_file": str(credentials),
        "certificate": "synthetic.crt",
        "private_key": "synthetic.key",
    }
    del values[missing]
    configure(tmp_path, monkeypatch, values)
    monkeypatch.setattr(portal, "PrivateServer", lambda *a, **k: pytest.fail("must not bind"))
    with pytest.raises(ValueError, match="credentials and TLS"):
        portal.main()


@pytest.mark.parametrize("credential", ["no-separator", "user:short"])
def test_weak_credentials_rejected_before_binding(tmp_path, monkeypatch, credential):
    path = tmp_path / "login"
    path.write_text(credential)
    configure(tmp_path, monkeypatch, {"credentials_file": str(path)})
    monkeypatch.setattr(portal, "PrivateServer", lambda *a, **k: pytest.fail("must not bind"))
    with pytest.raises(ValueError, match="strong pre-provisioned credential"):
        portal.main()


def test_tls_configuration_and_server_close_on_failure(tmp_path, monkeypatch):
    credentials = tmp_path / "login"
    credentials.write_text("synthetic:" + "x" * 32)
    configure(
        tmp_path,
        monkeypatch,
        {
            "host": "192.0.2.20",
            "port": 9876,
            "credentials_file": str(credentials),
            "certificate": "synthetic.crt",
            "private_key": "synthetic.key",
        },
    )
    calls = []

    class Context:
        def load_cert_chain(self, cert, key):
            calls.append((cert, key))

    context = Context()

    class Server:
        def serve_forever(self):
            assert self.tls_context is context
            assert context.minimum_version == portal.ssl.TLSVersion.TLSv1_2
            raise RuntimeError("synthetic server failure")

        def server_close(self):
            calls.append("closed")

    server = Server()

    def create(address, handler):
        assert address == ("192.0.2.20", 9876)
        return server

    monkeypatch.setattr(portal, "PrivateServer", create)
    monkeypatch.setattr(portal.ssl, "SSLContext", lambda protocol: context)
    monkeypatch.setattr(portal.signal, "signal", lambda *args: None)
    with pytest.raises(RuntimeError, match="synthetic server failure"):
        portal.main()
    assert calls == [("synthetic.crt", "synthetic.key"), "closed"]


def test_invalid_certificate_never_opens_a_socket(tmp_path, monkeypatch):
    credentials = tmp_path / "login"
    credentials.write_text("synthetic:" + "x" * 32)
    configure(
        tmp_path,
        monkeypatch,
        {
            "host": "192.0.2.20",
            "credentials_file": str(credentials),
            "certificate": "invalid.crt",
            "private_key": "invalid.key",
        },
    )

    class Context:
        def load_cert_chain(self, *args):
            raise OSError("invalid synthetic certificate")

    monkeypatch.setattr(portal.ssl, "SSLContext", lambda protocol: Context())
    monkeypatch.setattr(portal, "PrivateServer", lambda *a, **k: pytest.fail("must not bind"))
    with pytest.raises(OSError, match="invalid synthetic certificate"):
        portal.main()
