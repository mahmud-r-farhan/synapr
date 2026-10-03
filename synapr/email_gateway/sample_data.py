"""Offline sample messages used to seed a new local mail store."""

from typing import Any

DEFAULT_SAMPLE_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "mail-001",
        "subject": "[Bug Report] OAuth2 Token Expired Error during mobile sync",
        "sender": "qa-lead@example.org",
        "recipient": "dev@synapr.local",
        "date": "2026-10-02 11:20:00",
        "body": (
            "Hi team,\n\nWhen testing on mobile client build #402, our access token expires "
            "after 15 minutes, but the refresh endpoint returns 401 Unauthorized instead of renewing "
            "the session. Can we verify the JWT expiration window and add automated test coverage?\n\n"
            "Steps to reproduce:\n1. Log in on mobile client\n2. Wait 15 mins\n3. Trigger sync\n\nThanks,\nQA Team"
        ),
        "category": "bug_report",
        "priority": "high",
        "status": "unread",
        "extracted_tasks": ["Fix JWT refresh token 401", "Add test coverage for token renewal"],
    },
    {
        "id": "mail-002",
        "subject": "[Feature Request] Add Redis rate limiting to /api/dispatch",
        "sender": "product@example.org",
        "recipient": "dev@synapr.local",
        "date": "2026-10-02 14:45:00",
        "body": (
            "Hey devs,\n\nWe need to protect the dispatch API against bursts. "
            "Please implement a sliding-window rate limiter (100 req/min per API key) "
            "using Redis. If Redis is unavailable, gracefully fall back to in-memory limiting.\n\n"
            "Regards,\nProduct"
        ),
        "category": "feature_request",
        "priority": "medium",
        "status": "unread",
        "extracted_tasks": ["Implement Redis sliding-window rate limiter", "Add in-memory fallback"],
    },
]
