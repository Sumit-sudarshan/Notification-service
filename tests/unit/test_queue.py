import time
from unittest.mock import AsyncMock

import pytest

from app.queue.priority_queue import _score, PriorityQueue
from app.workers.retry_scheduler import calculate_backoff_delay, should_retry

def test_retry_backoff_calculation():
    # base=30, multiplier=4
    # retry_count=0 -> 30s
    assert calculate_backoff_delay(0) == 30.0
    # retry_count=1 -> 120s
    assert calculate_backoff_delay(1) == 120.0
    # retry_count=2 -> 480s
    assert calculate_backoff_delay(2) == 480.0

def test_should_retry():
    max_retries = 3
    assert should_retry(0, max_retries) is True
    assert should_retry(1, max_retries) is True
    assert should_retry(2, max_retries) is True
    assert should_retry(3, max_retries) is False

def test_priority_score_ordering():
    # Lower score means dequeued first
    ts = time.time() * 1000
    
    score_critical = _score("critical", ts)
    score_high = _score("high", ts)
    score_normal = _score("normal", ts)
    score_low = _score("low", ts)
    
    assert score_critical < score_high
    assert score_high < score_normal
    assert score_normal < score_low
    
    # FIFO within same tier (older gets lower score)
    score_critical_older = _score("critical", ts - 1000)
    assert score_critical_older < score_critical
