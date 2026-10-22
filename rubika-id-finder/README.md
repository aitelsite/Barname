# Rubika ID Finder (Python + Cloudflare Workers)

An experimental webhook-based Rubika ID helper. The project is intentionally separate from any currently running bot so it can be tested before switching production traffic.

## Features in this initial release

- Handles `/start`, `/id`, `/info`, `آیدی`, and `شناسه`
- Reports the chat ID, sender ID, and message ID when those fields exist in the incoming update
- Supports several common webhook payload shapes
- Reads the bot token from a Cloudflare secret rather than hard-coding it
- Returns a small health response on GET

## Important limitations

This is an initial compatibility build, not yet a verified production deployment. Rubika's actual webhook payload schema and Bot API method/field names must be confirmed against a real update. The chat-type prefix checks are hints, not authoritative metadata. The bot can only report IDs present in the update; it cannot reveal hidden IDs or private information.

Cloudflare Python Workers use Pyodide and do not behave exactly like a persistent Python server. This project uses an HTTP webhook design rather than a long-running `bot.run()` polling loop.

## Configure and deploy

1. Install a current Wrangler version and follow Cloudflare's Python Workers guide: https://developers.cloudflare.com/workers/languages/python/
2. From this directory, set the secret:
   ```sh
   npx wrangler secret put RUBIKA_BOT_TOKEN
   ```
3. Deploy:
   ```sh
   npx wrangler deploy
   ```
4. Configure the Rubika bot's webhook to the deployed Worker URL using the official Rubika API method supported by the bot account.
5. Send `/id` and inspect Worker logs plus the actual Bot API response before using it for production.

Do not put your bot token in GitHub, source code, screenshots, or chat messages.

## Status

Source published as an experimental first version. It has not been deployed to or verified against a live Rubika bot yet.
