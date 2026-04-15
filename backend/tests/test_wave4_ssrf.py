"""Dalga 4 — webhook SSRF hardening (submit-time + delivery-time)."""
from unittest.mock import patch

import pytest

from app.models.schemas import WebhookRegisterRequest, WebhookUpdateRequest
from app.services.traces import _webhook_target_is_public


AGENT_ID = "a1b2c3d4-e5f6-4789-a012-345678901234"


class TestRegisterSubmitTime:
    @pytest.mark.parametrize("bad", [
        "http://garl.ai/hook",                      # non-HTTPS
        "https://localhost/hook",                   # loopback name
        "https://localhost.localdomain/hook",
        "https://127.0.0.1/hook",
        "https://127.1.2.3/hook",                   # any loopback IP
        "https://10.0.0.5/hook",                    # RFC 1918
        "https://192.168.1.1/hook",
        "https://172.16.0.1/hook",                  # private 172.16/12
        "https://172.31.255.254/hook",
        "https://169.254.169.254/latest/meta-data", # EC2 metadata
        "https://metadata.google.internal/",        # GCP metadata
        "https://instance-data/hook",               # AWS classic
        "https://[::1]/hook",                       # IPv6 loopback
        "https://[fc00::1]/hook",                   # IPv6 unique local
        "https://[fe80::1]/hook",                   # IPv6 link-local
        "https://0.0.0.0/hook",
        "https://224.0.0.1/hook",                   # multicast
    ])
    def test_rejects_private_and_metadata_targets(self, bad):
        with pytest.raises(ValueError):
            WebhookRegisterRequest(agent_id=AGENT_ID, url=bad)

    def test_172_16_to_31_private_but_172_15_and_32_public_accepted(self):
        # 172.15.x and 172.32.x are PUBLIC. Old validator blocked all 172.*
        WebhookRegisterRequest(agent_id=AGENT_ID, url="https://172.15.0.1/ok")
        WebhookRegisterRequest(agent_id=AGENT_ID, url="https://172.32.0.1/ok")

    def test_update_request_also_validates(self):
        with pytest.raises(ValueError):
            WebhookUpdateRequest(url="https://10.0.0.1/evil")
        # None passes (don't update url)
        WebhookUpdateRequest(url=None)
        # Public domain passes
        WebhookUpdateRequest(url="https://hooks.example.com/webhook")

    def test_happy_path(self):
        r = WebhookRegisterRequest(agent_id=AGENT_ID, url="https://hooks.example.com/webhook")
        assert r.url.startswith("https://")


class TestDeliveryTimeResolution:
    def test_domain_resolving_to_loopback_blocked(self):
        import socket
        with patch.object(socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("127.0.0.1", 0))]):
            assert _webhook_target_is_public("https://sneaky.example.com/hook") is False

    def test_domain_resolving_to_private_blocked(self):
        import socket
        with patch.object(socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("10.1.2.3", 0))]):
            assert _webhook_target_is_public("https://hook.internal/x") is False

    def test_domain_resolving_to_public_allowed(self):
        import socket
        with patch.object(socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("1.1.1.1", 0))]):
            assert _webhook_target_is_public("https://hooks.example.com/x") is True

    def test_unresolvable_domain_blocked(self):
        import socket
        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("dns fail")):
            assert _webhook_target_is_public("https://nowhere.invalid/x") is False

    def test_mixed_public_private_resolution_blocked(self):
        # If ANY resolved address is private, refuse.
        import socket
        with patch.object(socket, "getaddrinfo", return_value=[
            (0, 0, 0, "", ("1.1.1.1", 0)),
            (0, 0, 0, "", ("192.168.1.1", 0)),
        ]):
            assert _webhook_target_is_public("https://dual.example.com/x") is False
