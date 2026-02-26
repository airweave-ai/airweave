"""Tests for the OCR guard in the Temporal worker main()."""

from unittest.mock import patch

import pytest

import airweave.core.container as container_mod


@pytest.mark.asyncio
async def test_raises_system_exit_when_ocr_is_none(test_container):
    """Worker must abort when the container has no OCR provider."""
    no_ocr = test_container.replace(ocr_provider=None)
    saved = container_mod.container

    try:
        container_mod.container = no_ocr
        with patch.object(
            container_mod,
            "initialize_container",
        ):
            from airweave.platform.temporal.worker import main

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1
    finally:
        container_mod.container = saved


@pytest.mark.asyncio
async def test_passes_guard_when_ocr_present(test_container):
    """Worker proceeds past OCR guard when provider is present."""
    saved = container_mod.container

    try:
        container_mod.container = test_container
        with (
            patch.object(
                container_mod,
                "initialize_container",
            ),
            patch(
                "airweave.platform.converters.initialize_converters",
            ),
            patch(
                "airweave.platform.temporal.worker.WorkerConfig.from_settings",
                side_effect=SystemExit(99),
            ),
        ):
            from airweave.platform.temporal.worker import main

            with pytest.raises(SystemExit) as exc_info:
                await main()

            # Exit code 99 means we passed the OCR guard and hit
            # the WorkerConfig stub — the guard did not fire.
            assert exc_info.value.code == 99
    finally:
        container_mod.container = saved
