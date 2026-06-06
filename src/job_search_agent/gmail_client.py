from __future__ import annotations

import base64
import email
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    sender: str
    subject: str
    received_date: date
    text: str
    html: str


class GmailClient:
    def __init__(self, service):
        self.service = service

    @classmethod
    def from_json(cls, *, oauth_token_json: dict | None, service_account_json: dict | None) -> "GmailClient":
        if oauth_token_json:
            creds = Credentials.from_authorized_user_info(oauth_token_json, scopes=GMAIL_SCOPES)
        elif service_account_json:
            creds = ServiceAccountCredentials.from_service_account_info(service_account_json, scopes=GMAIL_SCOPES)
        else:
            raise ValueError("Provide GOOGLE_OAUTH_TOKEN_JSON for Gmail access.")
        return cls(build("gmail", "v1", credentials=creds))

    def search_messages(self, query: str, max_results: int = 50) -> list[str]:
        response = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return [message["id"] for message in response.get("messages", [])]

    def get_message(self, message_id: str) -> EmailMessage:
        raw = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()["raw"]
        )
        decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
        parsed = email.message_from_bytes(decoded)
        sender = parsed.get("From", "")
        subject = parsed.get("Subject", "")
        received = _parse_date(parsed.get("Date", ""))
        text, html = _extract_bodies(parsed)
        return EmailMessage(message_id, sender, subject, received, text, html)

    def create_draft(self, to: str, subject: str, html_body: str) -> str:
        message = MIMEText(html_body, "html")
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        response = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return response["id"]

    def send_draft(self, draft_id: str) -> str:
        response = (
            self.service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )
        return response["id"]

    def send_html(self, to: str, subject: str, html_body: str) -> str:
        draft_id = self.create_draft(to, subject, html_body)
        return self.send_draft(draft_id)


def _extract_bodies(parsed) -> tuple[str, str]:
    text_parts: list[str] = []
    html_parts: list[str] = []
    for part in parsed.walk():
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="replace")
        if content_type == "text/html":
            html_parts.append(body)
        else:
            text_parts.append(body)
    return "\n".join(text_parts), "\n".join(html_parts)


def _parse_date(value: str) -> date:
    try:
        return email.utils.parsedate_to_datetime(value).astimezone(timezone.utc).date()
    except Exception:
        return datetime.now(timezone.utc).date()
