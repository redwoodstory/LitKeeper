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
- Checks for new chapters or updates to stories in your library and automatically downloads them on a schedule

### Progressive Web App (PWA) Features
Install LitKeeper as a native app on mobile and desktop devices. As a PWA, you can sync HTML stories offline to read without an internet connection. PWA features (offline reading, app installation, OPFS storage) require HTTPS.


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
      - EXTERNAL_EPUB_PATH=/external/path

      # Automatic story update checking (optional)
      # Set a cron schedule to enable automatic checks for story updates
      # Leave commented out to disable auto-updates
      # Format: minute hour day month day_of_week
      # Examples:
      # - Daily at 2 AM: 0 2 * * *
      # - Every 6 hours: 0 */6 * * *
      # - Weekly on Sunday at 3 AM: 0 3 * * 0
      - AUTO_UPDATE_SCHEDULE=0 2 * * *
```

2. Run the following command
`docker compose up -d`

3. Navigate to `http://<server-ip>:5000`


## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_LIBRARY` | `true` | Show library UI with story management. Set to `false` for download-only mode (hides library, search, and reader features) |
| `NOTIFICATION_URLS` | - | Apprise notification URLs (supports Telegram, Discord, Slack, Email, Pushover, etc.) |
| `EXTERNAL_EPUB_PATH` | - | Optional path to copy EPUBs for external app integration (e.g., Calibre-Web auto-import) |
| `AUTO_UPDATE_SCHEDULE` | - | Cron schedule for automatic story update checks. Setting this enables auto-updates. Format: `minute hour day month day_of_week`. Example: `0 2 * * *` (daily at 2 AM) |

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


## API Reference

LitKeeper provides a REST API for external integrations like iOS Shortcuts, automation tools, or custom scripts. All endpoints return JSON responses unless otherwise noted.

### Authentication

The API currently does not require authentication. If your instance is publicly accessible, consider using a reverse proxy with authentication.

### Download Story

Queue a story for download or download it synchronously.

**Endpoint:** `GET /api/download`

**Parameters:**
- `url` (required): Full Literotica story URL
- `wait` (optional): Set to `false` for background processing, `true` to wait for completion. Default: `true`
- `format` (optional): Comma-separated list of formats (`epub`, `html`). Default: `epub`

**Examples:**
```bash
# Background download (returns immediately)
GET https://your-server.com/api/download?url=https://www.literotica.com/s/story-name&wait=false

# Download EPUB and HTML, wait for completion
GET https://your-server.com/api/download?url=https://www.literotica.com/s/story-name&wait=true&format=epub,html

# Download only HTML
GET https://your-server.com/api/download?url=https://www.literotica.com/s/story-name&format=html
```

**Response (wait=false):**
```json
{
  "success": "true",
  "message": "Request accepted, processing in background"
}
```

**Response (wait=true):**
```json
{
  "success": true,
  "message": "Story downloaded successfully",
  "title": "Story Title",
  "author": "Author Name",
  "formats": ["epub", "html"]
}
```

### Queue Story

Add a story to the download queue. This is the recommended method for web integrations as it provides better status tracking.

**Endpoint:** `POST /api/queue`

**Content-Type:** `application/json` or `application/x-www-form-urlencoded`

**Body:**
```json
{
  "url": "https://www.literotica.com/s/story-name",
  "format": ["epub", "html"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Story added to download queue",
  "queue_item": {
    "id": 123,
    "url": "https://www.literotica.com/s/story-name",
    "status": "pending",
    "created_at": "2026-01-08T14:30:00"
  }
}
```

### Check Queue Status

Get the status of a specific queue item.

**Endpoint:** `GET /api/queue/{queue_id}`

**Response:**
```json
{
  "success": true,
  "queue_item": {
    "id": 123,
    "url": "https://www.literotica.com/s/story-name",
    "status": "completed",
    "created_at": "2026-01-08T14:30:00",
    "completed_at": "2026-01-08T14:31:15"
  }
}
```

Status values: `pending`, `processing`, `completed`, `failed`

### Get Library

Retrieve all stories in your library.

**Endpoint:** `GET /api/library`

**Response:**
```json
{
  "stories": [
    {
      "id": 1,
      "title": "Story Title",
      "author": "Author Name",
      "category": "Category",
      "tags": ["tag1", "tag2"],
      "formats": ["epub", "html"],
      "created_at": "2026-01-08T14:30:00"
    }
  ]
}
```

### Delete Story

Remove a story from your library and delete associated files.

**Endpoint:** `DELETE /api/story/delete/{story_id}`

**Response:**
```json
{
  "success": true,
  "message": "Story deleted successfully"
}
```

### Toggle Auto-Update

Enable or disable automatic update checking for a story.

**Endpoint:** `POST /api/story/toggle-auto-update/{story_id}`

**Response:**
```json
{
  "success": true,
  "auto_update_enabled": true,
  "message": "Auto-update enabled"
}
```

## iOS Shortcuts Integration

You can use iOS Shortcuts to download stories directly from the share sheet.

**Setup:**
1. Create a new Shortcut
2. Add "Receive URLs and Apps input from Share Sheet"
3. Add "Get URLs from Shortcut Input"
4. Add "Get contents of URL" with the following URL format:
   ```
   https://your-server.com/api/download?url=[Shortcut Input]&wait=false
   ```
5. Save and enable in the share sheet

When you share a Literotica story URL from Safari or any app, the shortcut will send it to your LitKeeper instance for download. You'll receive a notification when the download completes.

[iOS Shortcut Screenshot](images/ios_shortcut_image.jpeg)

**Alternative (with queue tracking):**

For better status tracking, use the queue endpoint:
1. Add "Get contents of URL" with method POST
2. URL: `https://your-server.com/api/queue`
3. Request Body: JSON
   ```json
   {
     "url": "[Shortcut Input]",
     "format": ["epub", "html"]
   }
   ```
4. Add "Get Dictionary Value" for key `queue_item.id`
5. Optionally poll `https://your-server.com/api/queue/[queue_id]` to check status


## Migrating from V1

LitKeeper V1 was a simple EPUB downloader with basic volume mounts (`/epubs` for downloads, `/logs` for logging). V2 has evolved into a full-featured web application with an interactive reader, story monitoring, multiple file formats, and a SQLite database for advanced filtering and tracking.

### What's Changed

**Volume Structure:**
- **V1:** Single `/epubs` directory
- **V2:** Organized `/stories` directory with subdirectories:
  - `/stories/epubs` - EPUB files
  - `/stories/html` - HTML files for in-app reading
  - `/stories/covers` - Generated cover images

**New Database:**
- V2 introduces a `/data` mount containing a SQLite database (`litkeeper.db`)
- Enables fast filtering, search, and automatic story update monitoring
- Tracks metadata and links stories to their Literotica URLs

### Migration Steps

**1. Update your docker-compose.yml**

Replace your old volume mounts with the new configuration shown in the [Installation](#installation) section above.

**2. Migrate existing EPUB files**

Copy your previously-downloaded stories from the legacy `/epubs` directory into the new `/stories/epubs` directory:

```bash
find /path/to/old_epubs -type f -name "*.epub" -exec cp "{}" /path/to/new_stories/epubs \;
```

**3. Start the application**

Run `docker compose up -d` to start LitKeeper V2.

**4. Automatic import**

On startup, LitKeeper will automatically scan the `/stories/epubs` directory and import all stories into the database. The import process will:
- Extract metadata from EPUB files (title, author, tags, etc.)
- Attempt to match stories to their Literotica URLs using author and title
- Allow story monitoring to check for new chapters or updates

**Benefits of Migration:**
- **Interactive reading:** Read stories directly in your browser with customizable formatting
- **Story monitoring:** Automatically detect when series receive new chapters
- **Multi-format support:** Generate HTML versions alongside EPUBs
- **Advanced search:** Filter by author, category, tags, and more
- **PWA support:** Install as a native app and sync stories for offline reading

### Prefer the V1 Download-Only Interface?

If you want to keep the simpler V1 download-only interface without the library UI, set `ENABLE_LIBRARY=false` in your docker-compose.yml. This hides the library, search, and reader features, returning to the basic download functionality.

**Important:** Even with `ENABLE_LIBRARY=false`, you must still update your volume mounts to the new `/stories` and `/data` structure. The SQLite database will be created and updated regardless of this setting.