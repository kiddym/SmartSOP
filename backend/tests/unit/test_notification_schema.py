from datetime import datetime

from app.schemas.notification import NotificationRead, UnreadCount


def test_notification_read_params_dict():
    m = NotificationRead(
        id="n-1", type="WO_ASSIGNED", entity_type="work_order", entity_id="wo-1",
        params={"custom_id": "WO1"}, actor_user_id=None, is_read=False,
        read_at=None, created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    assert m.params["custom_id"] == "WO1" and m.is_read is False


def test_unread_count():
    assert UnreadCount(count=5).count == 5
