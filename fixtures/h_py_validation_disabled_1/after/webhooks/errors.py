"""Errors raised while accepting a webhook."""

from __future__ import annotations


class WebhookError(Exception):
    """Base error for the webhook receiver."""


class ValidationError(WebhookError):
    """The body does not match the event schema."""


class SignatureError(WebhookError):
    """The signature header does not match the raw body."""


class ReplayError(WebhookError):
    """The delivery id was already accepted."""
