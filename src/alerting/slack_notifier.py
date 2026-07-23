import os
import requests
import logging
import src.config as config

logger = logging.getLogger("SlackNotifier")

def post_alert(message: str, webhook_url: str = None) -> bool:
    """Post structured alert text to configured Slack Webhook channel."""
    url = webhook_url or getattr(config, "SLACK_WEBHOOK_URL", os.environ.get("SLACK_WEBHOOK_URL"))
    if not url or "YOUR_SLACK_WEBHOOK" in url:
        logger.warning(f"Slack webhook URL not configured. Skipping alert: {message}")
        return False
    try:
        response = requests.post(url, json={"text": message}, timeout=10)
        if response.status_code == 200:
            return True
        logger.error(f"Slack post failed: HTTP {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error posting to Slack: {e}")
    return False
