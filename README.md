# LitKeeper

LitKeeper is a self-hosted web app that lets you download and organize stories from [Literotica](https://www.literotica.com) for offline reading.

Originally built as a simple EPUB downloader for e-readers, LitKeeper has evolved into a fully featured, interactive local library. It saves stories in both EPUB and HTML formats, offering a customizable in-app reading experience. A native iOS companion app is also available — see [LitKeeper for iOS](https://github.com/redwoodstory/litkeeper-ios).

*Note: AI coding assistants were used in the development of this app.*

## Features

### Core Functionality
* **Multi-Format Support:** Download stories as EPUB or HTML, and read either format directly within the app.
* **Customizable Reader:** Adjust fonts, text size, line spacing, and reading width for a tailored reading experience.
* **Smart Library Management:** Story categories and tags are automatically bundled into the metadata, enabling easy filtering, sorting, and searching.
* **Custom Covers:** Automatically generate aesthetic cover images for EPUB files featuring the story title and author.
* **Automated Series Bundling:** Detects if a story is part of a series, fetches all related parts, and compiles them into a single file. Both formats include a built-in table of contents for easy navigation.
* **Auto-Updates & Notifications:** Receive alerts when downloads finish. LitKeeper can also check for new chapters and download updates automatically. *(Note: Update schedules are randomized in the code to prevent overwhelming source servers).*
* **Responsive Design:** Enjoy a mobile-friendly UI that dynamically adapts with bottom navigation and optimized spacing for smaller screens.
* **OPDS Catalog:** Expose your library as an OPDS feed for your e-reader device. Disabled by default; enable and optionally password-protect it under **Settings → OPDS Catalog**.

### Downloading
* **Story, Series, or Author URL:** The home page accepts any Literotica URL — individual story, series, or author profile. Pasting an author URL prompts a confirmation before queuing a scan of all their published stories.
* **Combine Multiple URLs into One Story:** Expand the "Combine multiple URLs into one story" option on the home page to merge several chapter or part URLs into a single combined EPUB/HTML file.
* **Download Queue:** All downloads are processed via a background queue. The queue page shows real-time status for pending, processing, completed, and failed items.
* **Daily Download Cap & Rate Limiting:** To avoid overwhelming source servers, LitKeeper enforces a daily download cap (default: 25 stories). Items beyond the cap are marked `rate_limited` and automatically retried the following day. The cap can be overridden with the `MAX_DAILY_DOWNLOADS` environment variable.

### Watched Authors
* **Author Scanning:** Paste a Literotica author profile URL to queue a full scan that downloads every story they've published. Each story is individually queued and downloaded.
* **Watch for New Stories:** Enable watching on any author to have LitKeeper automatically check for new stories they publish. Toggle per-author watching from **Settings → Watched Authors**.
* **Auto-Download New Stories from Watched Authors:** A dedicated toggle under **Settings → Automation** enables scheduled automatic checks for new stories from watched authors, using the same weekly schedule as story auto-updates. The Watched Authors page is only accessible when this setting is enabled.

## ⚠️ Migrating from V1

If you are migrating from an older V1 instance of LitKeeper, please refer to the [V1 to V2 Migration Guide](MIGRATION.md) for detailed instructions on updating your configuration and importing your existing stories.


## Installation

1. Create a docker-compose.yml file:
```yaml
services:
  litkeeper:
    image: ghcr.io/redwoodstory/litkeeper:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      # Set /data mount to persist database and secret key
      - ./data:/litkeeper/app/data
      
      # Set /stories mount for all story-related files (epubs, html, covers)
      - ./stories:/litkeeper/app/stories

    environment:
      # Set to false to hide library UI (download-only mode)
      - ENABLE_LIBRARY=true

      # Notification configuration based on Apprise (supports multiple services)
      # See Apprise docs for full list: https://github.com/caronc/apprise#supported-notifications
      # Examples for a few services:
      # - Telegram: tgram://BOT_TOKEN/CHAT_ID
      # - Discord: discord://webhook_id/webhook_token
      # - Slack: slack://tokenA/tokenB/tokenC
      # - Email: mailto://user:pass@gmail.com
      # - Pushover: pover://user_key/app_token
      - NOTIFICATION_URLS=

      # API token for headless/programmatic access (optional)
      # Required for iOS app, curl, or automation scripts to authenticate via Bearer token
      # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
      - LITKEEPER_API_TOKEN=

      # External EPUB path (optional)
      # Copy EPUBs to an external directory for integration with other apps (e.g., Calibre-Web)
      # Example: /path/to/calibre-web/auto-import
      - EXTERNAL_EPUB_PATH=
```

2. Run the following command:
`docker compose up -d`

3. Navigate to: `http://<server-ip>:5000`


## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_LIBRARY` | `true` | Show library UI with story management. Set to `false` for download-only mode (hides library, search, and reader features) |
| `LITKEEPER_API_TOKEN` | - | Bearer token for API/headless access (iOS app, scripts, automation). When set, API requests must include `Authorization: Bearer <token>` |
| `NOTIFICATION_URLS` | - | Apprise notification URLs (supports Telegram, Discord, Slack, Email, Pushover, etc.) |
| `EXTERNAL_EPUB_PATH` | - | Optional path to copy EPUBs for external app integration (e.g., Calibre-Web auto-import) |
| `WEBAUTHN_RP_ID` | *(auto)* | Passkey relying party hostname (e.g. `myapp.example.com`). Auto-detected from the request — only set this if a reverse proxy masks the real hostname. Bare hostname only, no port or scheme. |
| `WEBAUTHN_ORIGIN` | *(auto)* | Full origin for passkey verification (e.g. `https://myapp.example.com`). Auto-detected from the request — only set this if a reverse proxy masks the real hostname. |
| `WEBAUTHN_RESET_CODE` | - | When set, enables `POST /auth/webauthn/reset` as an emergency passkey recovery endpoint. |
| `MAX_DAILY_DOWNLOADS` | `25` | Maximum stories downloaded per day. The default is intentionally conservative to avoid hammering source servers — please be a good citizen before raising this. |

### Volume Mounts

Volume mounts are required for data persistence between container restarts:

| Mount | Purpose | Required |
|-------|---------|----------|
| `./data:/litkeeper/app/data` | Database and secret key | ✅ Yes |
| `./stories:/litkeeper/app/stories` | All story files (epubs, html, covers) | ✅ Yes |

**Directory structure:**
```
./data/
  ├── litkeeper.db  # SQLite database
  └── secret.key    # Auto-generated session key

./stories/
  ├── epubs/        # EPUB files
  ├── html/         # HTML files for in-app reading
  └── covers/       # Generated cover images
```

Without these bind mounts, your stories and database will be lost when the container is updated or recreated.


## Security

LitKeeper uses a layered security model. The layers you use depend on how you access the app.

### Layer 1: Reverse Proxy Authentication (recommended for external access)

For access outside your LAN, run LitKeeper behind a reverse proxy with its own authentication layer (e.g., [Pangolin](https://github.com/fosrl/pangolin), Authentik, Authelia, Nginx + basic auth). The proxy handles external authentication before requests reach LitKeeper. API clients will need to include whatever headers or credentials the proxy requires alongside their normal LitKeeper auth.

### Layer 2: API Token (headless API access)

Set `LITKEEPER_API_TOKEN` in your server's `.env` or `docker-compose.yml` file. Any API client (i.e. the iOS app, curl, iOS Shortcuts, automation scripts) can authenticate by sending the token as:

```
Authorization: Bearer <your-token>
```

When this env var is set:

- Requests to API routes without a valid Bearer token and without an active browser session are rejected with HTTP 401.
- The passkey lock (Layer 3) is **bypassed** for valid Bearer token requests — API clients do not need a passkey session.

### Layer 3: Passkey Lock (web UI)

LitKeeper supports optional passkey locking for the web UI using WebAuthn — Face ID, Touch ID, or a hardware security key (YubiKey, etc.). No password or PIN is stored; the server only holds a public key. Passkeys are phishing-resistant and not brute-forceable.

**Requirements:** The app must be served over **HTTPS** in production. `localhost` works over plain HTTP for local development. If you access the app over plain HTTP on a non-localhost hostname, the lock screen will display an HTTPS-required notice and the app will remain open.

Enable it under **Settings → Security** in the web UI. Register at least two devices (e.g., phone + laptop) as a backup.

#### Passkey Recovery

If you lose access to all registered passkeys, you have two options:

**Option A — CLI (works even if the web process is down):**
```bash
docker exec -it <container-name> python reset_webauthn.py
```

**Option B — Web endpoint (requires `WEBAUTHN_RESET_CODE` env var to be set):**
```bash
curl -X POST https://your-app/auth/webauthn/reset \
  -H "Content-Type: application/json" \
  -d '{"reset_code": "your-reset-code"}'
```

Both options clear all registered passkeys and leave the app open so you can re-register in Settings.

Replace `<container-name>` with your actual container name (find it with `docker ps`).


## OPDS Catalog

LitKeeper can serve your library as an [OPDS](https://opds.io) 1.1 catalog, making it discoverable by e-readers that support OPDS.

OPDS is **disabled by default**. Enable it under **Settings → OPDS Catalog**. Once enabled, your catalog URL is displayed there — paste it into your e-reader app's OPDS client.

### Authentication (optional)

By default, an enabled OPDS catalog is open to anyone who can reach your server. If you want to restrict access (e.g., for external exposure), enable **Require Authentication** in the same settings panel and set a username and password. Your e-reader app will prompt for these credentials once and store them.

The passkey lock (Layer 3) does not apply to OPDS — e-readers cannot perform WebAuthn. OPDS bypasses the passkey gate entirely; its own optional Basic Auth is the access control.


## CLI Reference

LitKeeper exposes administrative operations (sync, migration, backfill) as Flask CLI commands for maintenance and troubleshooting.

Please see the [CLI Reference](CLI.md) for the full command list and usage examples.


## API Reference & Integrations

LitKeeper provides a REST API for external integrations like iOS Shortcuts, automation tools, or custom scripts.

Please see the [API Reference & Integrations documentation](API.md) for more details.