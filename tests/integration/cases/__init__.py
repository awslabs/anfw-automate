"""Integration test cases for the ANFW automation platform.

Each module in this package implements one representative integration test
case that exercises the real event path (S3 → EventBridge → Lambda → NFW)
against the fixed INT account.

All cases require the ``@pytest.mark.integration`` marker and use session
fixtures from ``tests/integration/conftest.py``.
"""
