"""资产状态枚举 + UP/DOWN 归类（供 Phase 4 可用率复用）。"""

from __future__ import annotations

import enum


class AssetStatus(enum.StrEnum):
    OPERATIONAL = "OPERATIONAL"
    STANDBY = "STANDBY"
    MODERNIZATION = "MODERNIZATION"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    COMMISSIONING = "COMMISSIONING"
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"
    DOWN = "DOWN"


UP_STATUSES: set[AssetStatus] = {
    AssetStatus.OPERATIONAL,
    AssetStatus.STANDBY,
    AssetStatus.INSPECTION_SCHEDULED,
    AssetStatus.COMMISSIONING,
}
DOWN_STATUSES: set[AssetStatus] = {
    AssetStatus.MODERNIZATION,
    AssetStatus.EMERGENCY_SHUTDOWN,
    AssetStatus.DOWN,
}
