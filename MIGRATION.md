# Migrating from V1

LitKeeper V1 was a simple EPUB downloader with basic volume mounts (`/epubs` for downloads, `/logs` for logging). V2 has evolved into a full-featured web application with an interactive reader, story monitoring, multiple file formats, and a SQLite database for advanced filtering and tracking.

## What's Changed

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

## Migration Steps

**1. Update your docker-compose.yml**

Replace your old volume mounts with the new configuration shown in the [Installation](README.md#installation) section of the main README.

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

## Prefer the V1 Download-Only Interface?

If you want to keep the simpler V1 download-only interface without the library UI, set `ENABLE_LIBRARY=false` in your docker-compose.yml. This hides the library, search, and reader features, returning to the basic download functionality.

**Important:** Even with `ENABLE_LIBRARY=false`, you must still update your volume mounts to the new `/stories` and `/data` structure. The SQLite database will be created and updated regardless of this setting.
