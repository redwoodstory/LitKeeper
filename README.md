# LitKeeper

This is a simple web app to save stories from [Literotica](https://www.literotica.com) to ePub. In my own workflow, I download stories to a local server running [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated), which renders the stories available to other devices through its OPDS functionality.

This app includes the following features:
- Renders a simple web page prompting the user for a Literotica URL to download
- Retrieves story, converts to ePub, and saves to a predefined location (defined in Docker Compose file)
- Bundles story category and tags into metadata
- Generates a cover image showing the story title and author name
- Identifies if the story is part of a series and bundles subquent stories into a single ePub
- Provides an API to download stories directly from iOS shortcuts (see example below)
- (Optional) Sends notifications when the story is downloaded
- (Optional) Provides somewhat extensive logging (helpful for debugging but can be disabled in Docker Compose file)


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
      - ./epubs:/litkeeper/app/data/epubs
      - ./logs:/litkeeper/app/data/logs
    environment:
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

2. Run the following command
`docker compose up -d`

3. Navigate to `http://<server-ip>:5000`


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