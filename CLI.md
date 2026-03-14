# LitKeeper CLI Reference

LitKeeper exposes administrative operations as Flask CLI commands. These are intended for maintenance and troubleshooting and have no equivalent web UI.

To run a command against a running Docker container:

```bash
docker exec -it <container-name> flask <command>
```

Find your container name with `docker ps`.

---

## sync — Database/file sync

Keep the database and story files consistent with each other.

| Command | Description |
|---------|-------------|
| `flask sync check` | Report orphaned DB records and untracked files |
| `flask sync clean` | Remove DB records for files that no longer exist |
| `flask sync add` | Add untracked story files to the database |
| `flask sync full` | Run clean + add in one step |
| `flask sync fix-formats` | Add missing StoryFormat records for existing EPUB/JSON files |
| `flask sync inject-descriptions` | Patch descriptions from the DB into existing JSON and EPUB files without re-scraping |
| `flask sync rebuild-epub-info` | Force-rewrite the Story Information page in all EPUBs using current DB data; inserts the page into EPUBs that are missing it |

**Example — check then fix:**
```bash
docker exec -it litkeeper flask sync check
docker exec -it litkeeper flask sync full
```

---

## migration — Database migration

Manage the transition from file-based to database mode.

| Command | Description |
|---------|-------------|
| `flask migration run` | Run the file-to-database migration |
| `flask migration run --dry-run` | Preview what would be migrated without writing |
| `flask migration enable-db-mode` | Switch the app to database mode |
| `flask migration disable-db-mode` | Roll back to file-based mode (DB data is preserved) |
| `flask migration clear` | Delete all migrated data (destructive, prompts for confirmation) |
| `flask migration logs` | Show recent migration log entries |
| `flask migration logs --limit 100` | Show up to N log entries (default: 50) |

---

## backfill — Data backfill

Retroactively populate missing data for existing stories.

| Command | Description |
|---------|-------------|
| `flask backfill descriptions` | Re-fetch descriptions from Literotica for all stories that have a source URL |
| `flask backfill descriptions --rate 10` | Set max requests per minute (default: 5) |
| `flask backfill series-urls` | Backfill series URLs for existing stories |

> **Note:** `backfill descriptions` resets all existing descriptions before re-fetching, so stale or incorrect values are replaced.

---

## update-check

Manually trigger the story update checker (normally runs on a schedule).

```bash
docker exec -it litkeeper flask update-check
```

This runs synchronously and exits when complete.
