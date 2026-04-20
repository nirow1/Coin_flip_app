import pytest
from datetime import timezone
from freezegun import freeze_time
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio(loop_scope="session")


@freeze_time("2025-01-01 19:00:00", tz_offset=0)  # 19:
async def test_scheduler_triggers_at_19_utc():
    mock_session = AsyncMock()

