"""Intelligent email gateway and safe draft generation subsystem."""

from synapr.email_gateway.models import EmailDraft, EmailMessage, EmailTriageResult
from synapr.email_gateway.service import EmailGatewayService

__all__ = ["EmailDraft", "EmailGatewayService", "EmailMessage", "EmailTriageResult"]
