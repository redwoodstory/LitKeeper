# API Reference

LitKeeper provides a REST API for external integrations like iOS Shortcuts, automation tools, or custom scripts. All endpoints return JSON responses unless otherwise noted.

## Authentication

If PIN lock is enabled in Settings → Security, **all API endpoints require an active browser session** — there is no API key or token mechanism. Requests that arrive without a valid session are redirected to the lock screen (HTTP 302), or receive an `HX-Redirect` header if the request came from HTMX.

This means:
- **Browser-based tools** (HTMX, iOS Shortcuts via Safari, etc.) work automatically as long as the session is unlocked.
- **Headless scripts or external clients** (curl, automation tools) cannot authenticate and will be blocked when PIN lock is on.

If you need external API access with PIN lock enabled, disable the PIN or use a reverse proxy with its own authentication in front of LitKeeper and keep PIN lock off.

If PIN lock is disabled, the API is open to anyone who can reach your instance — consider a reverse proxy with authentication if it is publicly accessible.

## Download Story

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

## Queue Story

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
  "message": "Story added to queue",
  "queue_item": {
    "id": 123,
    "url": "https://www.literotica.com/s/story-name",
    "status": "pending",
    "created_at": "2026-01-08T14:30:00"
  }
}
```

## Check Queue Status

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

## Get Library

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

## Delete Story

Remove a story from your library and delete associated files.

**Endpoint:** `DELETE /api/story/delete/{story_id}`

**Response:**
```json
{
  "success": true,
  "message": "Story deleted successfully"
}
```

## Toggle Auto-Update

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

# iOS Shortcuts Integration

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
