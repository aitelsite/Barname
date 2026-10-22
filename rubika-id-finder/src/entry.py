"""Rubika ID Finder webhook for Cloudflare Python Workers.

Keep bot credentials in the Cloudflare secret RUBIKA_BOT_TOKEN.
"""
from urllib.parse import quote

from js import fetch, JSON
from pyodide.ffi import to_js
from workers import WorkerEntrypoint, Response

WEBHOOK_URL = "https://rubika-id-finder.oj155304.workers.dev/"


def json_response(data, status=200):
    # Use the Workers Python SDK constructor consistently; keyword arguments to
    # Response.json are not portable across runtime SDK versions.
    return Response(
        JSON.stringify(data),
        status=status,
        headers={"content-type": "application/json; charset=utf-8"},
    )


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
    message = (
        update.get("new_message")
        or update.get("updated_message")
        or update.get("message")
        or update.get("edited_message")
    )
    if not isinstance(message, dict):
        message = update if any(k in update for k in ("chat_id", "chatId", "text", "message_id")) else None
    if not isinstance(message, dict):
        return None
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    sender = message.get("sender") if isinstance(message.get("sender"), dict) else {}
    chat_id = (
        first(update, "chat_id", "chatId")
        or first(message, "chat_id", "chatId")
        or first(chat, "chat_id", "id")
    )
    sender_id = (
        first(message, "sender_id", "senderId", "user_id")
        or first(sender, "user_id", "id")
    )
    return {
        "message": message,
        "chat_id": chat_id,
        "sender_id": sender_id,
        "text": str(first(message, "text", "message_text", "body") or ""),
    }


def nested_first(mapping, *paths):
    """Read the first non-empty value from common nested update shapes."""
    for path in paths:
        current = mapping
        for key in path.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, ""):
            return current
    return None


def forwarded_details(message):
    """Return forwarded marker and source ID when Rubika includes it in the update."""
    if not isinstance(message, dict):
        return False, None, None
    forward_obj = first(message, "forwarded_from", "forward_from", "forwarded_message", "forward")
    source_id = first(message, "forwarded_from_id", "forward_from_id", "forwarded_user_id")
    source_name = first(message, "forwarded_from_name", "forward_from_name")
    if isinstance(forward_obj, dict):
        source_id = source_id or first(forward_obj, "user_id", "sender_id", "id", "chat_id")
        source_name = source_name or first(forward_obj, "name", "first_name", "title", "username")
    is_forwarded = bool(forward_obj or source_id or source_name)
    return is_forwarded, source_id, source_name


def format_reply(info):
    message = info.get("message") or {}
    chat_id = info.get("chat_id")
    sender_id = info.get("sender_id")
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    sender = message.get("sender") if isinstance(message.get("sender"), dict) else {}
    chat_title = (
        first(chat, "title", "name", "first_name")
        or first(message, "chat_title", "title")
        or "—"
    )
    chat_username = first(chat, "username", "user_name") or first(message, "chat_username", "username") or "—"
    if chat_username != "—" and not str(chat_username).startswith("@"):
        chat_username = f"@{chat_username}"
    sender_name = first(sender, "name", "first_name", "username") or first(message, "sender_name", "first_name", "username") or "—"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "🆔 اطلاعات شناسه",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👤 شناسه فرستنده (User ID): {sender_id or 'در دادهٔ دریافتی موجود نیست'}",
        f"📌 نوع فرستنده: {chat_kind(sender_id)}",
        f"🪪 نام فرستنده: {sender_name}",
        "",
        f"💬 شناسه این چت (Chat ID): {chat_id or 'در دادهٔ دریافتی موجود نیست'}",
        f"📌 نوع چت: {chat_kind(chat_id)}",
        f"📛 عنوان چت: {chat_title}",
        f"🔗 یوزرنیم چت: {chat_username}",
    ]
    message_id = first(message, "message_id", "messageId", "id")
    if message_id:
        lines.append(f"✉️ شناسه پیام: {message_id}")

    is_forwarded, source_id, source_name = forwarded_details(message)
    if is_forwarded:
        lines.extend(["", "📨 اطلاعات پیام فورواردشده:"])
        if source_id:
            lines.append(f"🆔 شناسه مبدأ فوروارد: {source_id}")
        else:
            lines.append("🆔 شناسه مبدأ در دادهٔ دریافتی موجود نیست.")
        if source_name:
            lines.append(f"👤 نام مبدأ: {source_name}")
    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💡 برای دریافت شناسه گروه یا کانال، ربات را به آن اضافه کنید و در همان چت دستور بفرستید.",
    ])
    return "\n".join(lines)

async def rubika_post(token, method, payload):
    url = f"https://botapi.rubika.ir/v3/{quote(str(token), safe='')}/{method}"
    response = await fetch(url, to_js({
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": JSON.stringify(payload),
    }))
    status = int(response.status)
    try:
        body = await response.json()
    except Exception:
        body = {}
    return status, body


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            return await self._handle(request)
        except Exception as exc:
            # Return a controlled response instead of allowing a runtime 1101 page.
            # Never include request bodies, tokens, or upstream URLs in this message.
            error_name = type(exc).__name__
            return json_response({
                "ok": False,
                "error": "worker_exception",
                "exception_type": error_name,
                "hint": "Check Worker logs for the stack trace.",
            }, 500)

    async def _handle(self, request):
        token = getattr(self.env, "RUBIKA_BOT_TOKEN", None)
        # request.url is provided by the Workers runtime; avoid stringifying a JS URL wrapper.
        request_url = request.url
        url_path = request_url.split("?", 1)[0].rstrip("/")

        if request.method == "GET" and url_path.endswith("/setup-webhook"):
            if not token:
                return json_response({"ok": False, "error": "RUBIKA_BOT_TOKEN is not configured"}, 500)
            try:
                status, body = await rubika_post(token, "updateBotEndpoints", {
                    "url": WEBHOOK_URL,
                    "type": "ReceiveUpdate",
                })
                api_status = str(body.get("status", "")).upper() if isinstance(body, dict) else ""
                ok = 200 <= status < 300 and api_status not in {"ERROR", "FAILED"}
                return json_response({
                    "ok": ok,
                    "action": "register_webhook",
                    "endpoint_type": "ReceiveUpdate",
                    "http_status": status,
                    "rubika_status": body.get("status") if isinstance(body, dict) else None,
                    "message": "Webhook registration request sent; check Rubika response." if ok else "Rubika rejected the webhook registration.",
                }, 200 if ok else 502)
            except Exception as exc:
                return json_response({
                    "ok": False,
                    "error": "Could not contact Rubika Bot API",
                    "exception_type": type(exc).__name__,
                }, 502)

        if request.method == "GET":
            return json_response({
                "ok": True,
                "service": "rubika-id-finder",
                "mode": "webhook",
                "token_configured": bool(token),
                "webhook_url": WEBHOOK_URL,
                "setup_path": "/setup-webhook",
                "version": "2026-10-22-safe-handler",
            })

        if request.method != "POST":
            return Response("Method Not Allowed", status=405)

        if not token:
            return json_response({"ok": False, "error": "RUBIKA_BOT_TOKEN secret is not configured"}, 500)

        try:
            payload = await request.json()
        except Exception:
            return Response("Invalid JSON", status=400)

        info = extract_update(payload)
        if not info:
            return json_response({"ok": True, "ignored": "unrecognized update"})

        command = info["text"].strip().lower()
        allowed = {"/start", "/id", "/info", "آیدی", "شناسه", "شناسه من", "آیدی من", "ایدی", "id"}
        if command not in allowed and not command.startswith("/id@"):
            return json_response({"ok": True, "ignored": "not an ID command"})

        if not info["chat_id"]:
            return json_response({"ok": True, "ignored": "missing chat_id"})

        try:
            status, body = await rubika_post(token, "sendMessage", {
                "chat_id": info["chat_id"],
                "text": format_reply(info),
            })
            api_status = str(body.get("status", "")).upper() if isinstance(body, dict) else ""
            if status < 200 or status >= 300 or api_status in {"ERROR", "FAILED"}:
                return json_response({
                    "ok": False,
                    "error": "Rubika Bot API request failed",
                    "upstream_status": status,
                    "rubika_status": body.get("status") if isinstance(body, dict) else None,
                }, 502)
        except Exception as exc:
            return json_response({
                "ok": False,
                "error": "Failed to call Rubika Bot API",
                "exception_type": type(exc).__name__,
            }, 502)

        return json_response({"ok": True})
