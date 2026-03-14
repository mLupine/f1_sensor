from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.media_player.const import MediaPlayerEntityFeature

from custom_components.f1_sensor.media_player import F1ReplayMediaPlayer
from custom_components.f1_sensor.replay_mode import ReplayState


class DummyController:
    def __init__(self, *, state: ReplayState, playback: dict, planned: dict | None = None):
        self.state = state
        self._playback = playback
        self._planned = planned
        self.async_seek_to_ms = AsyncMock()
        self.session_manager = SimpleNamespace(selected_session=None, add_listener=lambda cb: lambda: None)

    def get_playback_status(self) -> dict:
        return dict(self._playback)

    def get_planned_playback_details(self) -> dict | None:
        return dict(self._planned) if self._planned else None


@pytest.mark.asyncio
async def test_media_player_exposes_seek_feature() -> None:
    controller = DummyController(
        state=ReplayState.READY,
        playback={"session_start_ms": 0, "playback_start_ms": 0, "duration_ms": 60_000},
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")
    assert entity.supported_features & MediaPlayerEntityFeature.SEEK


@pytest.mark.asyncio
async def test_media_player_seek_maps_relative_seconds_to_absolute_ms() -> None:
    controller = DummyController(
        state=ReplayState.PAUSED,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 90_000,
            "duration_ms": 300_000,
        },
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(12.5)

    controller.async_seek_to_ms.assert_awaited_once_with(102_500)


@pytest.mark.asyncio
async def test_media_player_seek_clamps_to_loaded_media_window() -> None:
    controller = DummyController(
        state=ReplayState.PLAYING,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 45_000,
            "duration_ms": 120_000,
        },
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(999)

    controller.async_seek_to_ms.assert_awaited_once_with(120_000)


@pytest.mark.asyncio
async def test_media_player_seek_uses_planned_details_when_duration_not_loaded() -> None:
    controller = DummyController(
        state=ReplayState.READY,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 0,
            "duration_ms": 0,
        },
        planned={
            "session_start_ms": 30_000,
            "playback_start_ms": 60_000,
            "duration_ms": 180_000,
        },
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(15)

    controller.async_seek_to_ms.assert_awaited_once_with(75_000)


@pytest.mark.asyncio
async def test_media_player_seek_negative_position_clamps_to_start() -> None:
    controller = DummyController(
        state=ReplayState.PAUSED,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 45_000,
            "duration_ms": 120_000,
        },
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(-50)

    controller.async_seek_to_ms.assert_awaited_once_with(45_000)


@pytest.mark.asyncio
async def test_media_player_seek_ignores_when_duration_unavailable_everywhere() -> None:
    controller = DummyController(
        state=ReplayState.READY,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 0,
            "duration_ms": 0,
        },
        planned={
            "session_start_ms": 0,
            "playback_start_ms": 0,
            "duration_ms": 0,
        },
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(15)

    controller.async_seek_to_ms.assert_not_called()


@pytest.mark.asyncio
async def test_media_player_seek_runtime_error_is_swallowed() -> None:
    controller = DummyController(
        state=ReplayState.PLAYING,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 0,
            "duration_ms": 180_000,
        },
    )
    controller.async_seek_to_ms.side_effect = RuntimeError("boom")
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(15)

    controller.async_seek_to_ms.assert_awaited_once_with(15_000)


@pytest.mark.asyncio
async def test_media_player_seek_ignores_non_seekable_state() -> None:
    controller = DummyController(
        state=ReplayState.SELECTED,
        playback={
            "session_start_ms": 0,
            "playback_start_ms": 0,
            "duration_ms": 180_000,
        },
    )
    entity = F1ReplayMediaPlayer(controller, "uid", "entry", "F1")

    await entity.async_media_seek(15)

    controller.async_seek_to_ms.assert_not_called()
