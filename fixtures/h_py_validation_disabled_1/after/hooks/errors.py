"""Failures raised while accepting a partner webhook."""

from __future__ import annotations


class WebhookError(Exception):
    """The delivery was rejected before it was recorded."""


class SchemaError(WebhookError):
    """The JSON body did not match the event schema."""


class SignatureError(WebhookError):
    """The signature header did not match the raw body."""
