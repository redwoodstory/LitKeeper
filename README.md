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
- The PIN lock (Layer 3) is **bypassed** for valid Bearer token requests — API clients do not need a PIN session.

### Layer 3: PIN Lock (web UI, casual snooping protection)

LitKeeper supports optional PIN locking for the web UI. This is intended for simple screen-lock behavior (e.g., a shared device) — it is not a hardened security wall. It applies only to browser sessions and is automatically bypassed for Bearer-token-authenticated API requests.

Enable it under **Settings → Security** in the web UI.

#### PIN Reset

If you forget your PIN, run this command to disable the PIN lock:

```bash
docker exec -it <container-name> python reset_pin.py
```

Replace `<container-name>` with your actual container name (find it with `docker ps`).


## CLI Reference

LitKeeper exposes administrative operations (sync, migration, backfill) as Flask CLI commands for maintenance and troubleshooting.

Please see the [CLI Reference](CLI.md) for the full command list and usage examples.


## API Reference & Integrations

LitKeeper provides a REST API for external integrations like iOS Shortcuts, automation tools, or custom scripts.

Please see the [API Reference & Integrations documentation](API.md) for more details.