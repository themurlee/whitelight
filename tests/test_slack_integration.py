import pytest
from unittest.mock import patch, MagicMock
from src.alerting.slack_notifier import post_alert

def test_slack_notifier_success():
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        url = "https://hooks.slack.com/services/mock/webhook"
        res = post_alert("Test message from unit test", webhook_url=url)
        
        assert res is True
        mock_post.assert_called_once_with(url, json={"text": "Test message from unit test"}, timeout=10)

def test_slack_notifier_failure():
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        url = "https://hooks.slack.com/services/mock/webhook"
        res = post_alert("Test failure message", webhook_url=url)
        
        assert res is False
