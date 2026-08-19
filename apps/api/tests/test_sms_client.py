# apps/api/tests/test_sms_client.py — SMSClient (africastalking SDK-backed): STUB/no-op mode when AT
# creds are unset, phone normalization via format_kenyan_phone, and the live send path via an
# injectable fake SDK (no network ever touched in tests)
import logging

import pytest

from app.integrations.sms_client import (
    SMSClient,
    _masked,
    _safe_recipient,
    format_kenyan_phone,
    send_sms,
    sms_client,
)


class FakeSMSService:
    """Mimics africastalking.SMSService.send — records calls, never touches the network."""

    def __init__(self, raise_error=None):
        self.calls = []
        self.raise_error = raise_error

    def send(self, message, recipients, sender_id=None, enqueue=False, callback=None, timeout=(3.05, 9.05)):
        if self.raise_error is not None:
            raise self.raise_error
        self.calls.append({
            "message": message,
            "recipients": recipients,
            "sender_id": sender_id,
            "enqueue": enqueue,
        })
        return {"SMSMessageData": {"Recipients": [{"status": "Success"}]}}


class FakeSDK:
    """Mimics the africastalking module surface the client uses: initialize() + .SMS."""

    def __init__(self, raise_init=None, sms_service=None):
        self.init_calls = []
        self.raise_init = raise_init
        self.SMS = sms_service or FakeSMSService()

    def initialize(self, username, api_key):
        if self.raise_init is not None:
            raise self.raise_init
        self.init_calls.append((username, api_key))


class TestFormatKenyanPhone:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0700123456", "+254700123456"),
            ("700123456", "+254700123456"),
            ("254700123456", "+254700123456"),
            ("+254700123456", "+254700123456"),
            ("+254 700 123 456", "+254700123456"),
            ("+254-700-123-456", "+254700123456"),
        ],
    )
    def test_valid_kenyan_numbers_normalize(self, raw, expected):
        assert format_kenyan_phone(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "12345", "+15551234567", "0712345", "abcd"])
    def test_invalid_or_blank_returns_none(self, raw):
        assert format_kenyan_phone(raw) is None


class TestMasking:
    def test_masked_shows_last_four(self):
        assert _masked("+254712345678") == "+2547****5678"

    def test_safe_recipient_blank_returns_unknown(self):
        assert _safe_recipient("") == "unknown"
        assert _safe_recipient(None) == "unknown"

    def test_safe_recipient_masks(self):
        assert _safe_recipient("+254700000001") == "+2547****0001"


class TestStubMode:
    def test_unconfigured_client_never_sends_and_logs_warning(self, caplog):
        # AT_USERNAME / AT_API_KEY are unset in the test env -> stub/no-op mode.
        client = SMSClient(sdk=FakeSDK())
        assert client.configured is False
        with caplog.at_level(logging.WARNING, logger="app.integrations.sms_client"):
            sent = client.send_sms("+254712345678", "test message")
        assert sent is False
        assert any("STUB/no-op" in r.message and "AT_USERNAME/AT_API_KEY unset" in r.message for r in caplog.records)

    def test_stub_mode_never_calls_the_sdk(self):
        sdk = FakeSDK()
        client = SMSClient(sdk=sdk)
        client.send_sms("+254712345678", "test")
        assert sdk.init_calls == []  # initialize() is never called without creds

    def test_module_singleton_is_stub_in_test_env(self):
        # The shared process client must never be "live" without real creds.
        assert sms_client.configured is False

    def test_blank_phone_or_message_returns_false(self):
        client = SMSClient(username="u", api_key="k", sdk=FakeSDK())  # configured, but blank inputs rejected
        assert client.send_sms("", "msg") is False
        assert client.send_sms("+254712345678", "") is False

    def test_invalid_phone_skips_without_sdk_call(self, caplog):
        sdk = FakeSDK()
        client = SMSClient(username="u", api_key="k", sdk=sdk)
        with caplog.at_level(logging.WARNING, logger="app.integrations.sms_client"):
            sent = client.send_sms("12345", "hello")
        assert sent is False
        assert sdk.SMS.calls == []
        assert any("non-Kenyan/invalid phone" in r.message for r in caplog.records)


class TestLiveMode:
    def test_send_sms_formats_phone_and_calls_sdk_with_sender_id(self):
        sdk = FakeSDK()
        client = SMSClient(username="at-username", api_key="at-secret-key", sender_id="VETLINK", sdk=sdk)
        sent = client.send_sms("0700123456", "Hello farmer")
        assert sent is True
        # initialize() was called with exactly the configured creds (SDK routes sandbox by username).
        assert sdk.init_calls == [("at-username", "at-secret-key")]
        call = sdk.SMS.calls[0]
        # The SDK only accepts +254... numbers, so the client normalized the "07..." input.
        assert call["recipients"] == ["+254700123456"]
        assert call["message"] == "Hello farmer"
        assert call["sender_id"] == "VETLINK"

    def test_sender_id_omitted_when_not_configured(self):
        sdk = FakeSDK()
        client = SMSClient(username="u", api_key="k", sdk=sdk)
        client.send_sms("+254712345678", "hello")
        assert sdk.SMS.calls[0]["sender_id"] is None

    def test_sdk_validation_error_returns_false_without_raising(self):
        # The SDK raises ValueError for a bad phone; the client catches it and returns False.
        sdk = FakeSDK(sms_service=FakeSMSService(raise_error=ValueError("Invalid phone number")))
        client = SMSClient(username="u", api_key="k", sdk=sdk)
        assert client.send_sms("+254712345678", "hello") is False

    def test_sdk_api_error_returns_false_without_raising(self):
        from africastalking.Service import AfricasTalkingException

        sdk = FakeSDK(sms_service=FakeSMSService(raise_error=AfricasTalkingException("HTTP 400")))
        client = SMSClient(username="u", api_key="k", sdk=sdk)
        assert client.send_sms("+254712345678", "hello") is False

    def test_initialize_failure_falls_back_to_stub(self):
        sdk = FakeSDK(raise_init=RuntimeError("no creds"))
        client = SMSClient(username="u", api_key="k", sdk=sdk)
        assert client.configured is False
        assert client.send_sms("+254712345678", "hello") is False

    def test_send_sms_module_helper_uses_provided_client(self):
        sdk = FakeSDK()
        client = SMSClient(username="u", api_key="k", sdk=sdk)
        assert send_sms("+254712345678", "hi", client=client) is True
        assert sdk.SMS.calls[0]["message"] == "hi"