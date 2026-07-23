import time
from unittest.mock import patch, MagicMock
from alpaca.common.exceptions import APIError
from src.alpaca_client.retry_decorator import alpaca_retryable

class MockAPIError(APIError):
    def __init__(self, message, status_code):
        super().__init__(message)
        self._status_code = status_code
        
    @property
    def status_code(self):
        return self._status_code

def test_alpaca_rate_limit_retry():
    call_count = 0
    rate_limit_error = MockAPIError("Rate limit exceeded", 429)

    @alpaca_retryable(max_retries=3, base_delay=1.0)
    def dummy_api_call():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise rate_limit_error
        return "SUCCESS"

    with patch("time.sleep") as mock_sleep:
        res = dummy_api_call()
        assert res == "SUCCESS"
        assert call_count == 2
        mock_sleep.assert_called_once_with(30.0)
