from datetime import datetime
from src.options.full_audit.recommender import bucket_expirations

def test_bucket_expirations_this_week_keeps_all_within_7_days():
    today = datetime(2026, 7, 23)
    expirations = ["2026-07-24", "2026-07-27", "2026-07-29", "2026-08-15", "2026-10-16", "2027-06-18"]
    buckets = bucket_expirations(expirations, today=today)
    assert buckets["this_week"] == ["2026-07-24", "2026-07-27", "2026-07-29"]
    assert buckets["monthly"] == "2026-08-15"
    assert buckets["quarterly"] == "2026-10-16"
    assert buckets["leaps"] == "2027-06-18"

def test_bucket_expirations_missing_bucket_is_none():
    today = datetime(2026, 7, 23)
    expirations = ["2026-07-24"]
    buckets = bucket_expirations(expirations, today=today)
    assert buckets["this_week"] == ["2026-07-24"]
    assert buckets["monthly"] is None
    assert buckets["quarterly"] is None
    assert buckets["leaps"] is None
