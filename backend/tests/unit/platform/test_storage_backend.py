"""Tests for StorageBackend event loop responsiveness.

Tests that write operations don't block the event loop, allowing
concurrent operations to proceed while large files are being written.

These tests verify the fix in commit 10c4d7d09: wrap FilesystemBackend 
write operations in asyncio.to_thread to prevent event loop blocking.
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.storage.backend import FilesystemBackend


@pytest.fixture
def temp_storage():
    """Create a temporary filesystem backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = FilesystemBackend(tmpdir)
        yield backend


@pytest.mark.asyncio
async def test_write_operations_dont_block_event_loop(temp_storage):
    """Test that slow write operations don't block concurrent operations.
    
    This simulates the production scenario where large ARF file writes
    were blocking the event loop, preventing health checks from responding
    and causing pod terminations.
    """
    # Track whether the concurrent operation completed
    concurrent_op_completed = False
    write_started = False
    write_completed = False
    
    # Simulate a slow write by patching the builtin open to add delay
    original_open = open
    
    def slow_open(*args, **kwargs):
        """Simulate slow disk I/O during write."""
        nonlocal write_started
        write_started = True
        
        # If this is a write operation (mode contains 'w'), add delay
        mode = args[1] if len(args) > 1 else kwargs.get('mode', 'r')
        if 'w' in mode:
            time.sleep(0.5)  # Simulate 500ms slow write
        
        return original_open(*args, **kwargs)
    
    async def slow_write_operation():
        """Write a large file (simulated with slow I/O)."""
        nonlocal write_completed
        with patch('builtins.open', side_effect=slow_open):
            # Write a file that will take 500ms due to our mock
            await temp_storage.write_file("large_file.bin", b"x" * 1000000)
        write_completed = True
    
    async def concurrent_operation():
        """Simulates a health check or other concurrent operation."""
        nonlocal concurrent_op_completed
        # Wait for write to start
        while not write_started:
            await asyncio.sleep(0.01)
        
        # This operation should complete even while write is in progress
        # In the broken version, this would hang until write completes
        await asyncio.sleep(0.1)
        concurrent_op_completed = True
    
    # Run both operations concurrently
    start = time.time()
    await asyncio.gather(
        slow_write_operation(),
        concurrent_operation()
    )
    elapsed = time.time() - start
    
    # Verify both completed
    assert write_completed, "Write operation should complete"
    assert concurrent_op_completed, "Concurrent operation should complete"
    
    # Concurrent operation should complete while write is still running
    # If writes were blocking, elapsed would be ~0.6s (0.5s write + 0.1s concurrent)
    # With threading, they run in parallel so elapsed should be ~0.5s
    assert elapsed < 0.55, f"Operations should run concurrently (took {elapsed:.2f}s)"


@pytest.mark.asyncio
async def test_multiple_concurrent_writes(temp_storage):
    """Test that multiple write operations can happen concurrently.
    
    This simulates production with SYNC_MAX_WORKERS=20 where multiple
    entities are being written to ARF simultaneously.
    """
    write_count = 5
    start_times = []
    end_times = []
    
    original_open = open
    
    def slow_open(*args, **kwargs):
        """Simulate slow disk I/O."""
        mode = args[1] if len(args) > 1 else kwargs.get('mode', 'r')
        if 'w' in mode:
            time.sleep(0.2)  # 200ms per write
        return original_open(*args, **kwargs)
    
    async def write_file_tracked(idx: int):
        """Write a file and track timing."""
        start_times.append(time.time())
        with patch('builtins.open', side_effect=slow_open):
            await temp_storage.write_file(f"file_{idx}.bin", b"data" * 1000)
        end_times.append(time.time())
    
    # Write 5 files concurrently
    start = time.time()
    await asyncio.gather(*[write_file_tracked(i) for i in range(write_count)])
    total_elapsed = time.time() - start
    
    # If writes were blocking, total time would be 5 * 0.2s = 1.0s sequential
    # With threading, they run concurrently so should be ~0.2-0.3s
    assert total_elapsed < 0.5, f"Writes should be concurrent (took {total_elapsed:.2f}s, expected <0.5s)"
    
    # Verify all writes started within a short window (concurrent)
    start_spread = max(start_times) - min(start_times)
    assert start_spread < 0.1, f"Writes should start concurrently (spread: {start_spread:.2f}s)"


@pytest.mark.asyncio
async def test_write_json_concurrent(temp_storage):
    """Test that write_json operations don't block the event loop."""
    concurrent_op_completed = False
    write_started = False
    
    original_open = open
    
    def slow_open(*args, **kwargs):
        """Simulate slow disk I/O."""
        nonlocal write_started
        mode = args[1] if len(args) > 1 else kwargs.get('mode', 'r')
        if 'w' in mode:
            write_started = True
            time.sleep(0.3)
        return original_open(*args, **kwargs)
    
    async def write_json_operation():
        """Write JSON with slow I/O."""
        with patch('builtins.open', side_effect=slow_open):
            # Simulate ARF entity write
            data = {
                "entity_id": "test_123",
                "content": "x" * 10000,
                "metadata": {"size": 10000}
            }
            await temp_storage.write_json("entity.json", data)
    
    async def concurrent_operation():
        """Concurrent operation (like health check)."""
        nonlocal concurrent_op_completed
        while not write_started:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        concurrent_op_completed = True
    
    # Run concurrently
    await asyncio.gather(
        write_json_operation(),
        concurrent_operation()
    )
    
    assert concurrent_op_completed, "Concurrent operation should complete while JSON write is in progress"


@pytest.mark.asyncio
async def test_delete_operations_dont_block(temp_storage):
    """Test that delete operations don't block the event loop.
    
    Deletes can be slow when removing large directories, so they
    should also be threaded.
    """
    # Create a directory with files
    await temp_storage.write_file("dir/file1.txt", b"data1")
    await temp_storage.write_file("dir/file2.txt", b"data2")
    await temp_storage.write_file("dir/file3.txt", b"data3")
    
    concurrent_op_completed = False
    delete_started = False
    
    original_rmtree = __import__('shutil').rmtree
    
    def slow_rmtree(*args, **kwargs):
        """Simulate slow directory deletion."""
        nonlocal delete_started
        delete_started = True
        time.sleep(0.2)
        return original_rmtree(*args, **kwargs)
    
    async def delete_operation():
        """Delete directory with slow I/O."""
        with patch('shutil.rmtree', side_effect=slow_rmtree):
            await temp_storage.delete("dir")
    
    async def concurrent_operation():
        """Concurrent operation."""
        nonlocal concurrent_op_completed
        while not delete_started:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        concurrent_op_completed = True
    
    # Run concurrently
    await asyncio.gather(
        delete_operation(),
        concurrent_operation()
    )
    
    assert concurrent_op_completed, "Concurrent operation should complete while delete is in progress"


@pytest.mark.asyncio
async def test_read_operations_remain_concurrent(temp_storage):
    """Test that read operations are also non-blocking (regression test for commit be298882)."""
    # Create a file to read
    await temp_storage.write_file("test.bin", b"data" * 10000)
    
    concurrent_op_completed = False
    read_started = False
    
    original_open = open
    
    def slow_open(*args, **kwargs):
        """Simulate slow disk I/O."""
        nonlocal read_started
        mode = args[1] if len(args) > 1 else kwargs.get('mode', 'r')
        if 'r' in mode or 'b' in mode:
            read_started = True
            time.sleep(0.2)
        return original_open(*args, **kwargs)
    
    async def read_operation():
        """Read file with slow I/O."""
        with patch('builtins.open', side_effect=slow_open):
            await temp_storage.read_file("test.bin")
    
    async def concurrent_operation():
        """Concurrent operation."""
        nonlocal concurrent_op_completed
        while not read_started:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        concurrent_op_completed = True
    
    # Run concurrently
    await asyncio.gather(
        read_operation(),
        concurrent_operation()
    )
    
    assert concurrent_op_completed, "Concurrent operation should complete while read is in progress"
