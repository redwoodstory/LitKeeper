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

### Progressive Web App (PWA) Features
Install LitKeeper as a native app on mobile and desktop devices. As a PWA, you can sync HTML stories offline to read without an internet connection. PWA features (offline reading, app installation, OPFS storage) require HTTPS.


## Installation

1. Generate a secure SECRET_KEY:
```bash
openssl rand -hex 32
```

2. Create a docker-compose.yml file:
```yaml
services:
  litkeeper:
    image: ghcr.io/redwoodstory/litkeeper:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      # Set /epubs mount to enable downloading epubs to the file system
      # If the app library is enabled, these files will be shown on the app UI too
      - ./epubs:/litkeeper/app/data/epubs

      # Optional: Set a secondary bind mount to save epubs to a different location
      # This could be useful for a tool like Calibre-Web to ingest (and subsequently delete) saved files
      # There files are only for external consumption and are not shown on the app library
      - ./secondary-epubs:/litkeeper/app/data/secondary-epubs

      # Set /html and /covers mounts to use the interactive library in the app
      # Ensure that ENABLE_LIBRARY is also set to true to use the library
      - ./html:/litkeeper/app/data/html
      - ./covers:/litkeeper/app/data/covers

      # Set /logs mount to persist logs between container restarts
      - ./logs:/litkeeper/app/data/logs


    environment:
      # Flask Secret Key (required for session persistence)
      # Generate with: openssl rand -hex 32
      - SECRET_KEY=your-secret-key-here

      # Set to false to hide library UI (download-only mode)
      - ENABLE_LIBRARY=true

      # Optional logging toggles
      - ENABLE_ACTION_LOG=true
      - ENABLE_ERROR_LOG=true
      - ENABLE_URL_LOG=true

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
```

3. Run the following command
`docker compose up -d`

4. Navigate to `http://<server-ip>:5000`


## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *Required* | Flask secret key for session security. Generate with: `openssl rand -hex 32` |
| `ENABLE_LIBRARY` | `true` | Show library UI with story management. Set to `false` for download-only mode (hides library, search, and reader features) |
| `ENABLE_ACTION_LOG` | `true` | Log application actions to `logs/action.log` |
| `ENABLE_ERROR_LOG` | `true` | Log errors to `logs/error.log` |
| `ENABLE_URL_LOG` | `true` | Log processed URLs to `logs/url.log` |
| `NOTIFICATION_URLS` | - | Apprise notification URLs (supports Telegram, Discord, Slack, Email, Pushover, etc.) |

### Volume Mounts

Volume mounts are required for data persistence between container restarts:

| Mount | Purpose | Required |
|-------|---------|----------|
| `./epubs:/litkeeper/app/data/epubs` | EPUB file storage | ✅ Yes |
| `./html:/litkeeper/app/data/html` | HTML file storage | ✅ Yes |
| `./logs:/litkeeper/app/data/logs` | Application logs | ✅ Yes |
| `./covers:/litkeeper/app/data/covers` | Generated cover images | ✅ Yes |

Without these bind mounts, your converted books and covers will be lost when the container is updated or recreated. The app will display a warning if bind mounts are not properly configured. You can also set the environment variable ENABLE_LIBRARY=false to hide the /html and /covers warning messages.


## API Configuration

To use the API, send a GET request in the following format:
```
GET <server-url>/api/download?url=<literotica-story-url>&wait=false
```

### iOS Shortcuts

To trigger a download using iOS Shortcuts, using the folowing format:
1. Receive [URLs and Apps] input from [Share Sheet]
2. Get URLs from [Shortcut Input]
3. URL: <server-url>/api/download?url=<literotica-story-url>&wait=false
4. Get contents of [URL]

[iOS Shortcut Screenshot](images/ios_shortcut_image.jpeg)