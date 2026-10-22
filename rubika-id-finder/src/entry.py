"""Experimental Rubika ID Finder webhook for Cloudflare Python Workers.

The bot token must be configured as the RUBIKA_BOT_TOKEN Worker secret.
This worker is intentionally isolated from existing bots until verified.
"""
import json
from urllib.parse import quote

from js import fetch, JSON
from workers import WorkerEntrypoint, Response


def first(mapping, *keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def chat_kind(identifier):
    value = str(identifier or "")
    # Prefix mapping is a heuristic, not an authoritative Rubika guarantee.
    if value.startswith("u0"):
        return "کاربر"
    if value.startswith("g0"):
        return "گروه"
    if value.startswith("c0"):
        return "کانال"
    if value.startswith("b0"):
        return "گفت‌وگوی خصوصی با ربات"
    return "نامشخص"


def extract_update(payload):
    if not isinstance(payload, dict):
        return None
    update = payload.get("update") or payload.get("data") or payload
    if not isinstance(update, dict):
        return None
    message = update.get("message") or update.get("new_message") or update.get("edited_message")
    if not isinstance(message, dict):
        message = update if any(k in update for k in ("chat_id", "chatId", "text", "message_id")) else None
    if not isinstance(message, dict):
        return None
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    sender = message.get("sender") if isinstance(message.get("sender"), dict) else {}
    chat_id = first(message, "chat_id", "chatId") or first(chat, "chat_id", "id")
    sender_id = first(message, "sender_id", "senderId", "user_id") or first(sender, "user_id", "id")
    return {
        "message": message,
        "chat_id": chat_id,
        "sender_id": sender_id,
        "text": str(first(message, "text", "message_text", "body") or ""),
    }


def format_reply(info):
    lines = [
        "🔎 شناسه‌یاب روبیکا",
        "",
        f"🆔 شناسه چت: {info['chat_id'] or 'در دادهٔ دریافتی موجود نیست'}",
        f"👤 شناسه فرستنده: {info['sender_id'] or 'در دادهٔ دریافتی موجود نیست'}",
        f"💬 نوع چت: {chat_kind(info['chat_id'])}",
        f"🧩 نوع فرستنده: {chat_kind(info['sender_id'])}",
    ]
    message_id = first(info.get("message") or {}, "message_id", "messageId", "id")
    if message_id:
        lines.append(f"✉️ شناسه پیام: {message_id}")
    return "\n".join(lines)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method == "GET":
            return Response.json({
                "ok": True,
                "service": "rubika-id-finder",
                "mode": "webhook",
                "token_configured": bool(getattr(self.env, "RUBIKA_BOT_TOKEN", None)),
            })

        if request.method != "POST":
            return Response("Method Not Allowed", status=405)

        token = getattr(self.env, "RUBIKA_BOT_TOKEN", None)
        if not token:
            return Response.json({
                "ok": False,
                "error": "RUBIKA_BOT_TOKEN secret is not configured",
            }, status=500)

        try:
            payload = await request.json()
        except Exception:
            return Response("Invalid JSON", status=400)

        info = extract_update(payload)
        if not info:
            return Response.json({"ok": True, "ignored": "unrecognized update"})

        command = info["text"].strip().lower()
        allowed = {"/start", "/id", "/info", "آیدی", "شناسه", "شناسه من", "آیدی من"}
        if command not in allowed and not command.startswith("/id@"):
            return Response.json({"ok": True, "ignored": "not an ID command"})

        if not info["chat_id"]:
            return Response.json({"ok": True, "ignored": "missing chat_id"})

        url = f"https://botapi.rubika.ir/v3/{quote(str(token), safe='')}/sendMessage"
        body = JSON.stringify({"chat_id": info["chat_id"], "text": format_reply(info)})
        try:
            upstream = await fetch(url, {
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": body,
            })
            status = int(upstream.status)
            if status < 200 or status >= 300:
                return Response.json({
                    "ok": False,
                    "error": "Rubika Bot API request failed",
                    "upstream_status": status,
                }, status=502)
        except Exception:
            return Response.json({"ok": False, "error": "Failed to call Rubika Bot API"}, status=502)

        return Response.json({"ok": True})
