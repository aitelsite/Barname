"""Rubika ID Finder — Cloudflare Python Worker webhook adapter.

Set RUBIKA_BOT_TOKEN as a Cloudflare secret before deployment.
This handler expects Rubika webhook updates and replies using the Bot API.
"""
import json
import os
from urllib.parse import quote

from js import fetch, Response, JSON


def _text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _first(mapping, *keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def _chat_kind(identifier):
    """Prefix-based hint only; verify against the actual API payload when available."""
    value = _text(identifier)
    if value.startswith("u0"):
        return "کاربر"
    if value.startswith("g0"):
        return "گروه"
    if value.startswith("c0"):
        return "کانال"
    if value.startswith("b0"):
        return "گفت‌وگوی خصوصی با ربات"
    return "نامشخص"


def _extract_update(payload):
    """Tolerate common webhook envelope shapes without assuming one exact schema."""
    if not isinstance(payload, dict):
        return None
    update = payload.get("update") or payload.get("data") or payload
    if not isinstance(update, dict):
        return None

    message = update.get("message") or update.get("new_message") or update.get("edited_message")
    if not isinstance(message, dict):
        # Some APIs put message fields directly in the update.
        message = update if any(k in update for k in ("chat_id", "chatId", "text", "message_id")) else None
    if not isinstance(message, dict):
        return None

    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    sender = message.get("sender") if isinstance(message.get("sender"), dict) else {}
    chat_id = _first(message, "chat_id", "chatId") or _first(chat, "chat_id", "id")
    sender_id = _first(message, "sender_id", "senderId", "user_id") or _first(sender, "user_id", "id")
    text = _first(message, "text", "message_text", "body") or ""
    return {"message": message, "chat_id": chat_id, "sender_id": sender_id, "text": _text(text)}


def _format_reply(info):
    chat_id = info["chat_id"]
    sender_id = info["sender_id"]
    lines = [
        "🔎 شناسه‌یاب پیشرفته روبیکا",
        "",
        f"🆔 شناسه چت: {chat_id if chat_id else 'در دادهٔ دریافتی موجود نیست'}",
        f"👤 شناسه فرستنده: {sender_id if sender_id else 'در دادهٔ دریافتی موجود نیست'}",
        f"💬 نوع چت: {_chat_kind(chat_id)}",
        f"🧩 نوع فرستنده: {_chat_kind(sender_id)}",
    ]
    msg = info.get("message") or {}
    message_id = _first(msg, "message_id", "messageId", "id")
    if message_id:
        lines.append(f"✉️ شناسه پیام: {message_id}")
    return "\n".join(lines)


async def _send_message(token, chat_id, text):
    # Keep the token in the secret store; never log or return it.
    url = f"https://botapi.rubika.ir/v3/{quote(token, safe='')}/sendMessage"
    body = JSON.stringify({"chat_id": chat_id, "text": text})
    response = await fetch(url, {
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": body,
    })
    return response


async def on_fetch(request, env):
    if request.method == "GET":
        return Response.new(
            json.dumps({"ok": True, "service": "rubika-id-finder", "mode": "webhook"}),
            {"status": 200, "headers": {"content-type": "application/json; charset=utf-8"}},
        )

    if request.method != "POST":
        return Response.new("Method Not Allowed", {"status": 405})

    token = getattr(env, "RUBIKA_BOT_TOKEN", None)
    if not token:
        return Response.new(
            json.dumps({"ok": False, "error": "RUBIKA_BOT_TOKEN secret is not configured"}),
            {"status": 500, "headers": {"content-type": "application/json; charset=utf-8"}},
        )

    try:
        payload = await request.json()
    except Exception:
        return Response.new("Invalid JSON", {"status": 400})

    info = _extract_update(payload)
    if not info:
        # Acknowledge unknown event shapes to avoid endless webhook retries.
        return Response.new(json.dumps({"ok": True, "ignored": "unrecognized update"}), {
            "status": 200, "headers": {"content-type": "application/json; charset=utf-8"}
        })

    text = info["text"].strip().lower()
    commands = {"/start", "/id", "/info", "آیدی", "شناسه", "شناسه من", "آیدی من"}
    if text not in commands and not text.startswith("/id@"):
        return Response.new(json.dumps({"ok": True, "ignored": "not an ID command"}), {
            "status": 200, "headers": {"content-type": "application/json; charset=utf-8"}
        })

    if not info["chat_id"]:
        return Response.new(json.dumps({"ok": True, "ignored": "missing chat_id"}), {
            "status": 200, "headers": {"content-type": "application/json; charset=utf-8"}
        })

    try:
        result = await _send_message(token, info["chat_id"], _format_reply(info))
        status = getattr(result, "status", 0)
        if status < 200 or status >= 300:
            return Response.new(
                json.dumps({"ok": False, "error": "Rubika Bot API request failed", "upstream_status": status}),
                {"status": 502, "headers": {"content-type": "application/json; charset=utf-8"}},
            )
    except Exception:
        return Response.new(
            json.dumps({"ok": False, "error": "Failed to call Rubika Bot API"}),
            {"status": 502, "headers": {"content-type": "application/json; charset=utf-8"}},
        )

    return Response.new(json.dumps({"ok": True}), {
        "status": 200, "headers": {"content-type": "application/json; charset=utf-8"}
    })
