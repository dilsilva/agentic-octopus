from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from octo.worker.scheduler import compute_next


def test_next_is_in_the_future():
    nxt = compute_next("*/5 * * * *")
    now = datetime.now(ZoneInfo("UTC"))
    assert nxt > now
    assert nxt - now <= timedelta(minutes=5, seconds=1)


def test_timezone_respected():
    utc = compute_next("0 7 * * *", "UTC")
    tokyo = compute_next("0 7 * * *", "Asia/Tokyo")
    assert utc.utcoffset() != tokyo.utcoffset() or utc != tokyo
    assert utc.hour == 7
    assert tokyo.hour == 7
