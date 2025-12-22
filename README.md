# LitKeeper

This is a web app to save stories from [Literotica](https://www.literotica.com) to EPUB and/or HTML formats. In my own workflow, I download stories to a local server running [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated), which renders the stories available to other devices through its OPDS functionality.

## Features

### Core Functionality
- Modern web interface with dark mode support and library management
- Download stories in EPUB format (for e-readers) and/or HTML format (for in-browser reading)
- Beautiful HTML reader with customizable fonts, sizes, line spacing, and reading width
- Retrieves story content and converts to selected format(s)
- Bundles story category and tags into metadata
- Generates cover images for EPUB files showing the story title and author name
- Identifies if the story is part of a series and bundles subsequent stories into a single file
- Table of contents for easy navigation in multi-chapter stories
- Provides an API to download stories directly from iOS shortcuts (see example below)
- (Optional) Sends notifications when stories are downloaded
- (Optional) Provides extensive logging (helpful for debugging but can be disabled in Docker Compose file)

### Progressive Web App (PWA) Features
- **Install as native app** on mobile and desktop devices
- **Offline reading** - Read downloaded HTML stories without internet connection
- **OPFS storage** - Store thousands of stories locally (gigabytes of storage on modern browsers)
- **Automatic caching** - Stories are cached when you first read them
- **Persistent storage** - Stories won't be evicted under storage pressure

**⚠️ HTTPS Required for PWA Features**

PWA features (offline support, installation, OPFS storage) require HTTPS due to browser security requirements. See the [HTTPS Setup](#https-setup) section below for deployment options.


## Installation

1. Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
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
      - ./epubs:/litkeeper/app/data/epubs
      - ./html:/litkeeper/app/data/html
      - ./logs:/litkeeper/app/data/logs
    environment:
      # Flask Secret Key (REQUIRED for session persistence)
      # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
      - SECRET_KEY=your-secret-key-here

      # Optional logging controls
      - ENABLE_ACTION_LOG=true    # Set to false to disable action logging
      - ENABLE_ERROR_LOG=true     # Set to false to disable error logging
      - ENABLE_URL_LOG=true       # Set to false to disable URL logging

      # Legacy Telegram notification configuration
      - TELEGRAM_BOT_TOKEN=      # Your bot token from @BotFather
      - TELEGRAM_CHAT_ID=        # Your chat ID (can be channel, group, or user ID)

      # New notification configuration based on Apprise (supports multiple services)
      # Add your notification URLs here, separated by commas. Examples:
      # - Telegram: tgram://BOT_TOKEN/CHAT_ID
      # - Discord: discord://webhook_id/webhook_token
      # - Slack: slack://tokenA/tokenB/tokenC
      # - Email: mailto://user:pass@gmail.com
      # - Pushover: pover://user_key/app_token
      - NOTIFICATION_URLS=        # Add your notification URLs here (optional)
```

3. Run the following command
`docker compose up -d`

4. Navigate to `http://<server-ip>:5000`

**Note:** For PWA features to work, you'll need HTTPS. See [HTTPS Setup](#https-setup) below.


## HTTPS Setup

PWA features (offline reading, app installation, OPFS storage) require HTTPS. This is a browser security requirement, not a LitKeeper limitation.

### Why HTTPS is Required

Service Workers (which power PWA features) only work in "secure contexts":
- ✅ `https://` URLs (production)
- ✅ `localhost` or `127.0.0.1` (development exception)
- ❌ `http://` URLs (blocked)
- ❌ Local IP addresses like `http://192.168.x.x` (blocked)

Without HTTPS, the app still works as a web app, but you won't be able to:
- Install it as a PWA on mobile/desktop
- Read stories offline
- Use OPFS for massive storage capacity

### Deployment Options

#### Option 1: Reverse Proxy (Recommended)

Use a reverse proxy to handle HTTPS while LitKeeper runs on HTTP internally.

**Using Caddy (Easiest - Auto SSL):**
```
litkeeper.yourdomain.com {
    reverse_proxy localhost:5000
}
```
Caddy automatically obtains and renews Let's Encrypt certificates.

**Using Nginx with Let's Encrypt:**
```nginx
server {
    listen 443 ssl;
    server_name litkeeper.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/litkeeper.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/litkeeper.yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Get Let's Encrypt certificate:
```bash
sudo certbot --nginx -d litkeeper.yourdomain.com
```

#### Option 2: Cloudflare Tunnel (No Domain/Port Forwarding Needed)

Free HTTPS without exposing ports or managing certificates:

```bash
# Install cloudflared
# Visit: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

# Create tunnel
cloudflared tunnel create litkeeper

# Configure tunnel (config.yml)
tunnel: <tunnel-id>
credentials-file: /path/to/credentials.json

ingress:
  - hostname: litkeeper.yourdomain.com
    service: http://localhost:5000
  - service: http_status:404

# Run tunnel
cloudflared tunnel run litkeeper
```

#### Option 3: Tailscale (VPN Approach)

Access via Tailscale uses the `localhost` exception:
- Install Tailscale on server and devices
- Access via `http://100.x.x.x:5000` (Tailscale IP)
- Service Workers work because Tailscale IPs are treated as secure

#### Option 4: Local Development Only

If you only access from the same machine:
- Use `http://localhost:5000` or `http://127.0.0.1:5000`
- PWA features work due to localhost exception
- Won't work from other devices on your network

### Requirements Summary

| Access Method | PWA Features | Notes |
|--------------|--------------|-------|
| `https://domain.com` | ✅ Yes | Requires domain + SSL certificate |
| `http://localhost:5000` | ✅ Yes | Same machine only |
| `http://192.168.x.x:5000` | ❌ No | Blocked by browsers |
| `http://domain.com` | ❌ No | Must use HTTPS |
| Cloudflare Tunnel | ✅ Yes | Free HTTPS, no port forwarding |
| Tailscale VPN | ✅ Yes | Treated as localhost |


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