"""Email listing, triage, draft, and safety-gated send endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from synapr.core.config_service import get_config_service
from synapr.web.models import EmailDraftRequest, EmailSendRequest
from synapr.web.state import get_orchestrator

router = APIRouter()
_email_service: Any = None


def get_email_service() -> Any:
    global _email_service
    if _email_service is None:
        from synapr.email_gateway.service import EmailGatewayService

        _email_service = EmailGatewayService()
    return _email_service


@router.get("/api/mail/messages")
async def api_mail_messages(folder: str = "inbox") -> list[dict[str, Any]]:
    """List incoming customer and client requirement messages."""
    svc = get_email_service()
    msgs = await asyncio.to_thread(svc.list_messages, folder=folder)
    return [m.model_dump() for m in msgs]


@router.get("/api/mail/messages/{message_id}")
async def api_mail_message(message_id: str) -> dict[str, Any]:
    """Retrieve an email message by ID."""
    svc = get_email_service()
    msg = await asyncio.to_thread(svc.get_message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")
    return msg.model_dump()


@router.post("/api/mail/messages/{message_id}/triage")
async def api_mail_triage(message_id: str) -> dict[str, Any]:
    """Classify email message into structured engineering brief."""
    svc = get_email_service()
    try:
        res = await asyncio.to_thread(svc.triage_message, message_id)
        data = res.model_dump()
        data["urgency"] = res.priority
        data["executive_summary"] = res.summary
        data["action_items"] = res.actionable_items
        return data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/mail/drafts")
async def api_mail_drafts() -> list[dict[str, Any]]:
    """List prepared response drafts."""
    svc = get_email_service()
    drafts = await asyncio.to_thread(svc.list_drafts)
    return [d.model_dump() for d in drafts]


@router.post("/api/mail/messages/{message_id}/draft")
async def api_mail_create_draft(message_id: str, req: EmailDraftRequest) -> dict[str, Any]:
    """Generate a context-aware technical draft response strictly to Drafts."""
    svc = get_email_service()
    orch = get_orchestrator()
    summary = get_config_service().summary()
    repo_ctx = f"Branch: {orch.config.worktree.base_branch} | Provider: {summary['provider']}"
    try:
        draft = await asyncio.to_thread(
            svc.generate_draft,
            message_id,
            developer_notes=req.developer_notes,
            repo_context=repo_ctx,
        )
        data = draft.model_dump()
        data["recipient"] = draft.to
        return data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/mail/drafts/{draft_id}/send")
async def api_mail_send_draft(draft_id: str, req: EmailSendRequest) -> dict[str, Any]:
    """Safe dispatch gate: Outbound transmission blocked unless confirm=True."""
    svc = get_email_service()
    try:
        res = await asyncio.to_thread(svc.send_draft, draft_id, confirm=req.confirm)
        if "recipient" not in res and "to" in res:
            res["recipient"] = res["to"]
        return res
    except RuntimeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
