# Migrating from V1

LitKeeper V1 was a simple EPUB downloader with basic volume mounts (`/epubs` for downloads, `/logs` for logging). V2 has evolved into a full-featured web application backed by a SQLite database, enabling an interactive reader, story monitoring, and advanced filtering.

## What's Changed

**Volume Structure:**
* **V1:** A single `/epubs` directory.
* **V2:** An organized `/stories` directory with dedicated subdirectories:
  * `/stories/epubs` - EPUB files.
  * `/stories/html` - HTML files for in-app reading.
  * `/stories/covers` - Generated cover images.

**New Database Architecture:**
* V2 introduces a `/data` mount containing a SQLite database (`litkeeper.db`).
* This database tracks metadata, links stories to their Literotica URLs, and powers fast filtering, searching, and automatic update monitoring.

## Migration Steps

**1. Update your `docker-compose.yml`**
Replace your old volume mounts with the new configuration detailed in the [Installation](README.md#installation) section of the main README.

**2. Migrate existing EPUB files**
Copy your previously downloaded stories from the legacy `/epubs` directory into the new `/stories/epubs` directory:

```bash
find /path/to/old_epubs -type f -name "*.epub" -exec cp "{}" /path/to/new_stories/epubs \;
```

**3. Start the application**
Run `docker compose up -d` to spin up LitKeeper V2.

**4. Let the automatic import run**
On startup, LitKeeper will automatically scan the `/stories/epubs` directory and import your existing library into the database. Behind the scenes, the app will:
* Extract metadata (title, author, tags, etc.) from your EPUB files.
* Attempt to match stories to their Literotica URLs using the author and title.
* Enable story monitoring to check for new chapters or updates.

## Prefer the V1 Interface?

If you prefer the simpler, download-only interface of V1, you can disable the library UI by setting `ENABLE_LIBRARY=false` in your `docker-compose.yml`. This hides the interactive library, search, and reader features.

> **Important:** Even with `ENABLE_LIBRARY=false`, you **must** still update your volume mounts to the new `/stories` and `/data` structure. The app requires the SQLite database to function and will create it regardless of your UI settings.