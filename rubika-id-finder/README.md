# Rubika ID Finder (Python + Cloudflare Workers)

An experimental webhook-based Rubika ID helper. It is kept separate from any currently running bot so it can be tested before switching production traffic.

## Files

- `src/entry.py` — Cloudflare Python Worker entrypoint
- `wrangler.jsonc` — Worker configuration
- `pyproject.toml` — Python Worker runtime/build dependencies
- `.github/workflows/deploy-rubika-id-finder.yml` — GitHub Actions deployment workflow

## Initial features

- Handles `/start`, `/id`, `/info`, `آیدی`, and `شناسه`
- Reports chat ID, sender ID, and message ID when present in the incoming update
- Reads the bot token from a Cloudflare Worker secret
- Returns a health response on GET

## Important limitations

This is an experimental first version and has not yet been verified against a live Rubika bot. Rubika's actual webhook payload schema, outbound API fields, and webhook-registration mechanism must be confirmed against a real update before production use. Chat ID prefix checks are hints only. The bot can only report identifiers actually included in the update; it cannot reveal hidden IDs or private information.

Cloudflare Python Workers run on Pyodide and need the Python Worker build process (`pywrangler`). A direct raw upload through the generic Worker Script API is not enough to bundle the Python entrypoint. The deployment workflow below uses the supported build process.

## One-time deployment setup

1. In GitHub, open **Settings → Secrets and variables → Actions** for this repository.
2. Add these repository secrets:
   - `CLOUDFLARE_API_TOKEN`: a Cloudflare API token with permission to edit/deploy Workers for this account.
   - `CLOUDFLARE_ACCOUNT_ID`: the Cloudflare account ID.
3. In Cloudflare, configure the bot token as a Worker secret named `RUBIKA_BOT_TOKEN` for the `rubika-id-finder` Worker after the first successful deployment. Do not commit it to GitHub or place it in source code.
4. Run **Actions → Deploy Rubika ID Finder → Run workflow**. A push that changes files under this directory also triggers deployment after secrets are configured.
5. Test the Worker health URL and only then configure a Rubika webhook using the official method supported by the bot account. Send `/id` and verify the response.

## Status

Source and deployment workflow are published. Live deployment is pending the one-time GitHub Actions secrets setup; no existing Worker or bot has been replaced.
