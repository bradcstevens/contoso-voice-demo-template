"""
Tests for Task 60: ConversationStore concurrent access / thread safety.

Validates that ConversationStore is safe under concurrent access from
multiple threads (e.g. chat and voice writing simultaneously).

Tests:
1. Concurrent writes from multiple threads to the SAME thread_id
2. Concurrent writes to DIFFERENT thread_ids (no cross-contamination)
3. Concurrent read + write on the same thread_id
4. Concurrent add_message + clear_thread (no deadlocks)
5. RLock reentrance -- nested lock acquisition must not deadlock
6. Concurrent get_chat_format and get_realtime_items while writing
"""

import os
import sys
import threading
import time

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conversation_store import ConversationStore, UnifiedMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Timeout for thread.join() calls -- any thread that hasn't finished within
# this many seconds is likely deadlocked.
JOIN_TIMEOUT = 15


def _make_msg(thread_label: int, index: int, source: str = "chat") -> UnifiedMessage:
    """Create a UnifiedMessage with identifiable content."""
    return UnifiedMessage(
        role="user",
        content=f"msg-{thread_label}-{index}",
        source=source,
    )


# ---------------------------------------------------------------------------
# Test 1: Concurrent writes from multiple threads to the SAME thread_id
# ---------------------------------------------------------------------------

class TestConcurrentWritesSameThread:
    """When many threads write to the same thread_id simultaneously, every
    message must be recorded and none may be lost or corrupted."""

    def test_all_messages_recorded(self):
        store = ConversationStore()
        thread_id = "shared-thread"
        num_threads = 10
        messages_per_thread = 100
        errors: list[Exception] = []

        def writer(label: int) -> None:
            try:
                for i in range(messages_per_thread):
                    store.add_message(thread_id, _make_msg(label, i))
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(t,), name=f"writer-{t}")
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=JOIN_TIMEOUT)
            assert not t.is_alive(), f"Thread {t.name} appears deadlocked"

        assert errors == [], f"Writer threads raised exceptions: {errors}"

        messages = store.get_messages(thread_id)
        expected_count = num_threads * messages_per_thread
        assert len(messages) == expected_count, (
            f"Expected {expected_count} messages, got {len(messages)}"
        )

    def test_no_corrupted_content(self):
        """Every message content must match the 'msg-<label>-<index>' pattern."""
        store = ConversationStore()
        thread_id = "content-check"
        num_threads = 5
        messages_per_thread = 50

        def writer(label: int) -> None:
            for i in range(messages_per_thread):
                store.add_message(thread_id, _make_msg(label, i))

        threads = [
            threading.Thread(target=writer, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=JOIN_TIMEOUT)

        messages = store.get_messages(thread_id)
        # Build the set of expected content strings
        expected = {
            f"msg-{label}-{i}"
            for label in range(num_threads)
            for i in range(messages_per_thread)
        }
        actual = {m.content for m in messages}
        assert actual == expected, "Some messages were corrupted or lost"


# ---------------------------------------------------------------------------
# Test 2: Concurrent writes to DIFFERENT thread_ids
# ---------------------------------------------------------------------------

class TestConcurrentWritesDifferentThreads:
    """When threads write to distinct thread_ids, each thread_id must contain
    exactly its own messages with no cross-contamination."""

    def test_thread_isolation_under_concurrency(self):
        store = ConversationStore()
        num_threads = 10
        messages_per_thread = 50

        def writer(label: int) -> None:
            tid = f"thread-{label}"
            for i in range(messages_per_thread):
                store.add_message(tid, _make_msg(label, i))

        threads = [
            threading.Thread(target=writer, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=JOIN_TIMEOUT)

        for label in range(num_threads):
            tid = f"thread-{label}"
            messages = store.get_messages(tid)
            assert len(messages) == messages_per_thread, (
                f"thread_id '{tid}' has {len(messages)} messages, "
                f"expected {messages_per_thread}"
            )
            # Verify no messages leaked from other thread_ids
            for msg in messages:
                assert msg.content.startswith(f"msg-{label}-"), (
                    f"Cross-contamination: thread_id '{tid}' contains "
                    f"message '{msg.content}'"
                )


# ---------------------------------------------------------------------------
# Test 3: Concurrent read + write on the same thread_id
# ---------------------------------------------------------------------------

class TestConcurrentReadWrite:
    """A reader and a writer operating on the same thread_id concurrently
    must not raise exceptions, and the final message count must be correct."""

    def test_no_exceptions_during_concurrent_read_write(self):
        store = ConversationStore()
        thread_id = "rw-thread"
        num_writes = 100
        reader_errors: list[Exception] = []
        writer_errors: list[Exception] = []
        reader_results: list[int] = []
        stop_reader = threading.Event()

        def writer() -> None:
            try:
                for i in range(num_writes):
                    store.add_message(
                        thread_id,
                        UnifiedMessage(role="user", content=f"w-{i}", source="chat"),
                    )
            except Exception as exc:
                writer_errors.append(exc)

        def reader() -> None:
            try:
                while not stop_reader.is_set():
                    msgs = store.get_messages(thread_id)
                    reader_results.append(len(msgs))
            except Exception as exc:
                reader_errors.append(exc)

        w = threading.Thread(target=writer, name="writer")
        r = threading.Thread(target=reader, name="reader")

        r.start()
        w.start()
        w.join(timeout=JOIN_TIMEOUT)
        assert not w.is_alive(), "Writer thread appears deadlocked"

        stop_reader.set()
        r.join(timeout=JOIN_TIMEOUT)
        assert not r.is_alive(), "Reader thread appears deadlocked"

        assert writer_errors == [], f"Writer raised: {writer_errors}"
        assert reader_errors == [], f"Reader raised: {reader_errors}"

        # Final count must be exactly what the writer inserted
        final_messages = store.get_messages(thread_id)
        assert len(final_messages) == num_writes

    def test_reader_sees_monotonically_nondecreasing_counts(self):
        """Because get_messages returns a snapshot under the lock, the reader
        should never see a count decrease (absent any clear_thread calls)."""
        store = ConversationStore()
        thread_id = "monotonic-thread"
        num_writes = 200
        reader_counts: list[int] = []
        stop_reader = threading.Event()

        def writer() -> None:
            for i in range(num_writes):
                store.add_message(
                    thread_id,
                    UnifiedMessage(role="user", content=f"m-{i}", source="chat"),
                )

        def reader() -> None:
            while not stop_reader.is_set():
                count = len(store.get_messages(thread_id))
                reader_counts.append(count)

        w = threading.Thread(target=writer)
        r = threading.Thread(target=reader)
        r.start()
        w.start()
        w.join(timeout=JOIN_TIMEOUT)
        stop_reader.set()
        r.join(timeout=JOIN_TIMEOUT)

        # Verify monotonically non-decreasing
        for i in range(1, len(reader_counts)):
            assert reader_counts[i] >= reader_counts[i - 1], (
                f"Reader saw count decrease: {reader_counts[i - 1]} -> "
                f"{reader_counts[i]} at index {i}"
            )


# ---------------------------------------------------------------------------
# Test 4: Concurrent add_message + clear_thread (no deadlocks)
# ---------------------------------------------------------------------------

class TestConcurrentAddAndClear:
    """Interleaved add_message and clear_thread calls must not deadlock or
    raise exceptions.  The final state is non-deterministic, but the
    process must complete within a timeout."""

    def test_no_deadlock_or_exception(self):
        store = ConversationStore()
        thread_id = "add-clear-thread"
        num_writes = 200
        num_clears = 50
        writer_errors: list[Exception] = []
        clearer_errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(num_writes):
                    store.add_message(
                        thread_id,
                        UnifiedMessage(role="user", content=f"w-{i}", source="chat"),
                    )
            except Exception as exc:
                writer_errors.append(exc)

        def clearer() -> None:
            try:
                for _ in range(num_clears):
                    store.clear_thread(thread_id)
                    # Small yield so the writer can make progress
                    time.sleep(0.001)
            except Exception as exc:
                clearer_errors.append(exc)

        w = threading.Thread(target=writer, name="writer")
        c = threading.Thread(target=clearer, name="clearer")

        w.start()
        c.start()

        w.join(timeout=JOIN_TIMEOUT)
        c.join(timeout=JOIN_TIMEOUT)

        assert not w.is_alive(), "Writer thread appears deadlocked"
        assert not c.is_alive(), "Clearer thread appears deadlocked"
        assert writer_errors == [], f"Writer raised: {writer_errors}"
        assert clearer_errors == [], f"Clearer raised: {clearer_errors}"

        # We cannot know the exact count, but get_messages must not crash
        messages = store.get_messages(thread_id)
        assert isinstance(messages, list)

    def test_multiple_writers_and_clearers(self):
        """Multiple writers and multiple clearers running concurrently."""
        store = ConversationStore()
        thread_id = "multi-add-clear"
        errors: list[Exception] = []

        def writer(label: int) -> None:
            try:
                for i in range(100):
                    store.add_message(
                        thread_id,
                        UnifiedMessage(
                            role="user", content=f"w-{label}-{i}", source="chat"
                        ),
                    )
            except Exception as exc:
                errors.append(exc)

        def clearer(label: int) -> None:
            try:
                for _ in range(20):
                    store.clear_thread(thread_id)
                    time.sleep(0.002)
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=writer, args=(i,)) for i in range(5)]
            + [threading.Thread(target=clearer, args=(i,)) for i in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=JOIN_TIMEOUT)
            assert not t.is_alive(), f"Thread {t.name} appears deadlocked"

        assert errors == [], f"Threads raised exceptions: {errors}"


# ---------------------------------------------------------------------------
# Test 5: RLock reentrance
# ---------------------------------------------------------------------------

class TestRLockReentrance:
    """ConversationStore uses an RLock (reentrant lock).  Methods that call
    other lock-acquiring methods (e.g. get_chat_format calls get_messages)
    must not deadlock."""

    def test_get_chat_format_acquires_lock_reentrantly(self):
        """get_chat_format calls get_messages, which also acquires _lock.
        With an RLock this must not deadlock; with a plain Lock it would."""
        store = ConversationStore()
        thread_id = "reentrant-test"
        store.add_message(
            thread_id, UnifiedMessage(role="user", content="hello", source="chat")
        )

        # Call from a separate thread with a strict timeout
        result_holder: list[list[dict]] = []
        error_holder: list[Exception] = []

        def caller() -> None:
            try:
                result_holder.append(store.get_chat_format(thread_id))
            except Exception as exc:
                error_holder.append(exc)

        t = threading.Thread(target=caller)
        t.start()
        t.join(timeout=5)
        assert not t.is_alive(), "get_chat_format deadlocked (RLock reentrance failure)"
        assert error_holder == [], f"get_chat_format raised: {error_holder}"
        assert result_holder[0] == [{"role": "user", "content": "hello"}]

    def test_get_realtime_items_acquires_lock_reentrantly(self):
        """get_realtime_items calls get_messages, exercising RLock reentrance."""
        store = ConversationStore()
        thread_id = "reentrant-rt"
        store.add_message(
            thread_id, UnifiedMessage(role="user", content="hi", source="realtime")
        )

        result_holder: list[list[dict]] = []
        error_holder: list[Exception] = []

        def caller() -> None:
            try:
                result_holder.append(store.get_realtime_items(thread_id))
            except Exception as exc:
                error_holder.append(exc)

        t = threading.Thread(target=caller)
        t.start()
        t.join(timeout=5)
        assert not t.is_alive(), "get_realtime_items deadlocked"
        assert error_holder == [], f"get_realtime_items raised: {error_holder}"
        assert len(result_holder[0]) == 1
        assert result_holder[0][0]["item"]["role"] == "user"

    def test_manual_reentrant_lock_acquisition(self):
        """Directly acquire the store's lock twice in the same thread to
        confirm it is genuinely reentrant (RLock, not Lock)."""
        store = ConversationStore()
        deadlocked = threading.Event()

        def double_acquire() -> None:
            acquired_outer = store._lock.acquire(timeout=3)
            if not acquired_outer:
                deadlocked.set()
                return
            acquired_inner = store._lock.acquire(timeout=3)
            if not acquired_inner:
                deadlocked.set()
                store._lock.release()
                return
            store._lock.release()
            store._lock.release()

        t = threading.Thread(target=double_acquire)
        t.start()
        t.join(timeout=10)
        assert not t.is_alive(), "Thread deadlocked on double acquire"
        assert not deadlocked.is_set(), "RLock did not allow reentrant acquisition"


# ---------------------------------------------------------------------------
# Test 6: Concurrent get_chat_format and get_realtime_items while writing
# ---------------------------------------------------------------------------

class TestConcurrentFormatReads:
    """Multiple threads calling get_chat_format and get_realtime_items while
    another thread writes must all succeed without errors or corruption."""

    def test_concurrent_format_reads_during_writes(self):
        store = ConversationStore()
        thread_id = "format-thread"
        num_writes = 150
        errors: list[Exception] = []
        stop_readers = threading.Event()

        # Pre-populate so readers always have something to format
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            store.add_message(
                thread_id,
                UnifiedMessage(role=role, content=f"seed-{i}", source="chat"),
            )

        def writer() -> None:
            try:
                for i in range(num_writes):
                    role = "user" if i % 2 == 0 else "assistant"
                    store.add_message(
                        thread_id,
                        UnifiedMessage(
                            role=role, content=f"live-{i}", source="chat"
                        ),
                    )
            except Exception as exc:
                errors.append(exc)

        def chat_reader() -> None:
            try:
                while not stop_readers.is_set():
                    result = store.get_chat_format(thread_id)
                    # Basic structural validation
                    for entry in result:
                        assert "role" in entry and "content" in entry
            except Exception as exc:
                errors.append(exc)

        def realtime_reader() -> None:
            try:
                while not stop_readers.is_set():
                    result = store.get_realtime_items(thread_id)
                    for item in result:
                        assert "type" in item
                        assert "item" in item
                        assert "content" in item["item"]
            except Exception as exc:
                errors.append(exc)

        w = threading.Thread(target=writer, name="writer")
        cr1 = threading.Thread(target=chat_reader, name="chat-reader-1")
        cr2 = threading.Thread(target=chat_reader, name="chat-reader-2")
        rr1 = threading.Thread(target=realtime_reader, name="rt-reader-1")
        rr2 = threading.Thread(target=realtime_reader, name="rt-reader-2")

        for t in [cr1, cr2, rr1, rr2]:
            t.start()
        w.start()

        w.join(timeout=JOIN_TIMEOUT)
        stop_readers.set()
        for t in [cr1, cr2, rr1, rr2]:
            t.join(timeout=JOIN_TIMEOUT)

        all_threads = [w, cr1, cr2, rr1, rr2]
        for t in all_threads:
            assert not t.is_alive(), f"Thread {t.name} appears deadlocked"

        assert errors == [], f"Threads raised exceptions: {errors}"

        # Final count: 10 seed + num_writes live messages
        final = store.get_messages(thread_id)
        assert len(final) == 10 + num_writes

    def test_format_consistency_snapshot(self):
        """get_chat_format and get_realtime_items called at the same logical
        time (sequentially within the lock) should return consistent views
        of the same data -- the chat format count should equal the realtime
        items count plus the number of system messages."""
        store = ConversationStore()
        thread_id = "snapshot-consistency"
        store.add_message(
            thread_id,
            UnifiedMessage(role="system", content="instructions", source="chat"),
        )
        for i in range(20):
            role = "user" if i % 2 == 0 else "assistant"
            store.add_message(
                thread_id,
                UnifiedMessage(role=role, content=f"msg-{i}", source="chat"),
            )

        chat_fmt = store.get_chat_format(thread_id)
        rt_items = store.get_realtime_items(thread_id)

        # Chat format includes system messages; realtime items skip them
        system_count = sum(1 for m in chat_fmt if m["role"] == "system")
        assert len(chat_fmt) == len(rt_items) + system_count
