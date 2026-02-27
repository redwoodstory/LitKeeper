# LitKeeper

This is a web app to save stories from [Literotica](https://www.literotica.com) to EPUB and/or HTML formats.

This started as a tool to download stories as EPUBs to use on an e-reader. It has evolved to also include an optional interactive library within the app itself. The library allows you to either download EPUBs from the web browser or read your stories in HTML format within the app. As LitKeeper can be installed to your device as a PWA, you can choose to sync your HTML stories offline too.

## Features

### Core Functionality
- Download stories in EPUB format (for e-readers) and/or HTML format (for in-browser reading)
- Provides customizable fonts, sizes, line spacing, and reading width for HTML reading
- Retrieves story content and converts to selected format(s)
- Bundles story category and tags into metadata
- Generates cover images for EPUB files showing the story title and author name
- Identifies if the story is part of a series and bundles subsequent stories into a single file
- Table of contents for easy navigation in multi-chapter stories
- Provides an API to download stories directly from iOS shortcuts (see example below)
- Sends notifications when stories are downloaded
- Checks for new chapters or updates to stories in your library and automatically downloads them on a schedule (randomly-generated in the app code to avoid all users querying the source servers at the same time)

### Progressive Web App (PWA) Features
Install LitKeeper as a native app on mobile and desktop devices. As a PWA, you can sync HTML stories offline to read without an internet connection. PWA features (offline reading, app installation, OPFS storage) require HTTPS.


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
      # - NOTIFICATION_URLS=tgram://BOT_TOKEN/CHAT_ID

      # Examples for a few services:
      # - Telegram: tgram://BOT_TOKEN/CHAT_ID
      # - Discord: discord://webhook_id/webhook_token
      # - Slack: slack://tokenA/tokenB/tokenC
      # - Email: mailto://user:pass@gmail.com
      # - Pushover: pover://user_key/app_token
      - NOTIFICATION_URLS=

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


## API Reference & Integrations

LitKeeper provides a REST API for external integrations like iOS Shortcuts, automation tools, or custom scripts. 

Please see the [API Reference & Integrations documentation](API.md) for more details.