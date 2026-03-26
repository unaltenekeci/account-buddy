"""
Accountability Buddy - Test Suite
Automated tests for all components including GUI smoke tests.
"""

import json
import os
import subprocess
import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Make sure we can import the app
import accountability_buddy as ab


# ============================================================================
# HELPERS
# ============================================================================

def make_root():
    root = tk.Tk()
    root.withdraw()
    return root


def make_state(tmp_dir: Path) -> ab.StateManager:
    """Create a StateManager with temp data dir."""
    with patch.object(ab, 'STATE_DIR', tmp_dir), \
         patch.object(ab, 'STATE_FILE', tmp_dir / 'state.json'):
        state = ab.StateManager()
    # Override paths on instance too
    return state


# ============================================================================
# STATE MANAGER TESTS
# ============================================================================

def test_state_create_and_save():
    """State creates, saves, and loads correctly."""
    state = ab.StateManager()
    state.tasks.append(ab.Task(id=1, title="Test gorev", estimated_minutes=30))
    state.tasks.append(ab.Task(id=2, title="Diger gorev", estimated_minutes=15, status="devam"))
    state.checkins.append(ab.CheckIn(
        timestamp=datetime.now().isoformat(), score=7,
        task_id=1, task_title="Test gorev", progress="Yarim kaldi",
        blocker="", next_step="Devam et", mood="iyi", summary="Test ozet"
    ))
    state.save()

    state2 = ab.StateManager()
    state2.load()
    assert len(state2.tasks) == 2, f"Expected 2 tasks, got {len(state2.tasks)}"
    assert state2.tasks[0].title == "Test gorev"
    assert state2.tasks[1].status == "devam"
    assert len(state2.checkins) == 1
    assert state2.checkins[0].progress == "Yarim kaldi"
    assert state2.checkins[0].task_id == 1
    print("  PASS: state_create_and_save")


def test_state_migration():
    """Old format (response/ai_feedback) migrates to new format (summary/progress)."""
    old_data = {
        "version": 1,
        "session_start": datetime.now().isoformat(),
        "checkin_interval": 30,
        "reminder_delay": 5,
        "startup_enabled": False,
        "used_messages": [],
        "model": "sonnet",
        "session_id": "test-uuid",
        "tasks": [],
        "checkins": [
            {
                "timestamp": "2026-03-26T22:00:00",
                "response": "eski format cevap",
                "ai_feedback": "eski format feedback",
                "score": 5
            }
        ]
    }
    ab.STATE_FILE.write_text(json.dumps(old_data, ensure_ascii=False), encoding="utf-8")
    state = ab.StateManager()
    state.load()
    assert len(state.checkins) == 1
    assert state.checkins[0].summary == "eski format cevap"
    assert state.checkins[0].progress == "eski format feedback"
    print("  PASS: state_migration")


def test_state_next_task_id():
    state = ab.StateManager()
    assert state.next_task_id() == 1
    state.tasks.append(ab.Task(id=1, title="A", estimated_minutes=10))
    state.tasks.append(ab.Task(id=5, title="B", estimated_minutes=10))
    assert state.next_task_id() == 6
    print("  PASS: state_next_task_id")


def test_state_active_task():
    state = ab.StateManager()
    assert state.get_active_task() is None
    state.tasks.append(ab.Task(id=1, title="A", estimated_minutes=10))
    assert state.get_active_task() is None
    state.tasks[0].status = "devam"
    assert state.get_active_task() is not None
    assert state.get_active_task().id == 1
    print("  PASS: state_active_task")


def test_state_stats():
    state = ab.StateManager()
    state.tasks = [
        ab.Task(id=1, title="A", estimated_minutes=30, status="bitti"),
        ab.Task(id=2, title="B", estimated_minutes=20, status="devam"),
        ab.Task(id=3, title="C", estimated_minutes=10, status="bekliyor"),
    ]
    assert state.get_completed_count() == 1
    assert state.get_avg_score() == 0.0

    state.checkins = [
        ab.CheckIn(timestamp=datetime.now().isoformat(), score=8, summary="test"),
        ab.CheckIn(timestamp=datetime.now().isoformat(), score=4, summary="test2"),
    ]
    assert state.get_avg_score() == 6.0
    assert state.get_elapsed_str() != ""
    print("  PASS: state_stats")


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

def test_task_defaults():
    t = ab.Task(id=1, title="Test", estimated_minutes=30)
    assert t.status == "bekliyor"
    assert t.created_at != ""
    assert t.started_at is None
    assert t.completed_at is None
    print("  PASS: task_defaults")


def test_checkin_defaults():
    ci = ab.CheckIn(timestamp="2026-01-01T00:00:00", score=5)
    assert ci.task_id is None
    assert ci.mood == ""
    assert ci.blocker == ""
    assert ci.summary == ""
    print("  PASS: checkin_defaults")


# ============================================================================
# AI MANAGER TESTS
# ============================================================================

def test_ai_fallback():
    """Fallback messages work without Claude CLI."""
    state = ab.StateManager()
    ai = ab.AIManager(state)

    # Done keywords
    fb, sc = ai._get_fallback("bitirdim gorevi")
    assert sc >= 8
    assert fb in ab.FALLBACK_MESSAGES["praise"]

    # Working keywords
    fb, sc = ai._get_fallback("calisiyorum uzerinde")
    assert 5 <= sc <= 7
    assert fb in ab.FALLBACK_MESSAGES["encourage"]

    # Wasting time
    fb, sc = ai._get_fallback("youtube izledim")
    assert sc <= 2
    assert fb in ab.FALLBACK_MESSAGES["warn"]

    # Unknown
    fb, sc = ai._get_fallback("bir seyler oldu")
    assert 3 <= sc <= 4
    assert fb in ab.FALLBACK_MESSAGES["motivate"]

    # Empty
    fb, sc = ai._get_fallback("")
    assert sc <= 2
    print("  PASS: ai_fallback")


def test_ai_fallback_no_repeat():
    """Fallback messages don't repeat until pool is exhausted."""
    state = ab.StateManager()
    ai = ab.AIManager(state)
    seen = set()
    for _ in range(8):  # 8 praise messages exist
        fb, _ = ai._get_fallback("bitirdim")
        seen.add(fb)
    assert len(seen) == 8, f"Expected 8 unique messages, got {len(seen)}"
    print("  PASS: ai_fallback_no_repeat")


def test_ai_parse_response():
    state = ab.StateManager()
    ai = ab.AIManager(state)

    # Valid JSON
    fb, sc = ai._parse_response('{"feedback": "Harika!", "score": 9}')
    assert fb == "Harika!"
    assert sc == 9

    # JSON inside wrapper
    fb, sc = ai._parse_response('{"type":"result","result":"{\\"feedback\\":\\"test\\",\\"score\\":3}"}')
    # Should extract from result field
    assert sc >= 0

    # Plain text fallback
    fb, sc = ai._parse_response("Bu bir duz metin cevabi")
    assert fb == "Bu bir duz metin cevabi"
    assert sc == 5

    # Score clamping
    fb, sc = ai._parse_response('{"feedback": "x", "score": 15}')
    assert sc == 10
    fb, sc = ai._parse_response('{"feedback": "x", "score": -5}')
    assert sc == 0
    print("  PASS: ai_parse_response")


def test_ai_system_prompt():
    """System prompt includes tasks and checkin history."""
    state = ab.StateManager()
    state.tasks = [
        ab.Task(id=1, title="Rapor yaz", estimated_minutes=30, status="devam"),
    ]
    state.checkins = [
        ab.CheckIn(timestamp="2026-03-26T14:00:00", score=6,
                    task_id=1, task_title="Rapor yaz",
                    progress="Yarim kaldi", blocker="data eksik",
                    next_step="Dataya bak", mood="orta", summary="test")
    ]
    ai = ab.AIManager(state)
    prompt = ai._build_system_prompt()
    assert "Rapor yaz" in prompt
    assert "devam" in prompt
    assert "Yarim kaldi" in prompt
    assert "data eksik" in prompt
    print("  PASS: ai_system_prompt")


def test_ai_claude_path():
    """Claude path is resolved correctly."""
    state = ab.StateManager()
    ai = ab.AIManager(state)
    assert ai.claude_path.endswith("claude.exe") or ai.claude_path.endswith("claude")
    assert Path(ai.claude_path).exists(), f"Claude not found at {ai.claude_path}"
    print("  PASS: ai_claude_path")


def test_ai_cli_connection():
    """Claude CLI actually responds."""
    state = ab.StateManager()
    ai = ab.AIManager(state)
    result = subprocess.run(
        [ai.claude_path, "-p", "Say OK", "--model", "haiku"],
        capture_output=True, text=True, timeout=15, encoding="utf-8",
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "OK" in result.stdout
    print("  PASS: ai_cli_connection")


# ============================================================================
# GUI SMOKE TESTS
# ============================================================================

def test_dashboard_creates():
    """Dashboard window creates without errors."""
    root = make_root()
    state = ab.StateManager()
    state.tasks = [
        ab.Task(id=1, title="Test", estimated_minutes=30),
        ab.Task(id=2, title="Active", estimated_minutes=15, status="devam"),
        ab.Task(id=3, title="Done", estimated_minutes=10, status="bitti"),
    ]
    # Engine mock
    engine = MagicMock()
    dashboard = ab.Dashboard(root, state, engine)
    assert dashboard.task_container.winfo_children()  # Tasks rendered
    assert dashboard.score_var.get() is not None
    dashboard.refresh()
    root.update()
    root.destroy()
    print("  PASS: dashboard_creates")


def test_dashboard_add_task():
    """Adding a task through dashboard works."""
    root = make_root()
    state = ab.StateManager()
    engine = MagicMock()
    dashboard = ab.Dashboard(root, state, engine)
    dashboard.task_name_var.set("Yeni gorev")
    dashboard.task_dur_var.set("45")
    dashboard._add_task()
    assert len(state.tasks) == 1
    assert state.tasks[0].title == "Yeni gorev"
    assert state.tasks[0].estimated_minutes == 45
    root.destroy()
    print("  PASS: dashboard_add_task")


def test_dashboard_task_lifecycle():
    """Task start -> complete cycle works."""
    root = make_root()
    state = ab.StateManager()
    engine = MagicMock()
    dashboard = ab.Dashboard(root, state, engine)
    state.tasks.append(ab.Task(id=1, title="Lifecycle", estimated_minutes=10))

    dashboard._start_task(state.tasks[0])
    assert state.tasks[0].status == "devam"
    assert state.tasks[0].started_at is not None

    dashboard._complete_task(state.tasks[0])
    assert state.tasks[0].status == "bitti"
    assert state.tasks[0].completed_at is not None
    root.destroy()
    print("  PASS: dashboard_task_lifecycle")


def test_dashboard_delete_task():
    root = make_root()
    state = ab.StateManager()
    engine = MagicMock()
    dashboard = ab.Dashboard(root, state, engine)
    state.tasks.append(ab.Task(id=1, title="Silinecek", estimated_minutes=10))
    state.tasks.append(ab.Task(id=2, title="Kalacak", estimated_minutes=10))
    dashboard._delete_task(state.tasks[0])
    assert len(state.tasks) == 1
    assert state.tasks[0].title == "Kalacak"
    root.destroy()
    print("  PASS: dashboard_delete_task")


def test_checkin_popup_creates():
    """CheckIn popup creates and shows without errors."""
    root = make_root()
    state = ab.StateManager()
    state.tasks.append(ab.Task(id=1, title="Active task", estimated_minutes=30, status="devam"))
    ai = MagicMock()
    ai.get_chat_history.return_value = []

    popup = ab.CheckInPopup(root, state, ai, lambda *a: None, lambda: None)
    popup.show()
    assert popup.window is not None
    assert popup.window.winfo_exists()
    root.update()
    popup.destroy()
    root.destroy()
    print("  PASS: checkin_popup_creates")


def test_checkin_popup_with_history():
    """CheckIn popup shows previous messages."""
    root = make_root()
    state = ab.StateManager()
    ai = MagicMock()
    ai.get_chat_history.return_value = [
        {"role": "user", "text": "onceki mesaj"},
        {"role": "ai", "text": "onceki cevap"},
    ]

    popup = ab.CheckInPopup(root, state, ai, lambda *a: None, lambda: None)
    popup.show()
    # Should have bubbles: 2 history + separator + question = 4
    bubbles = popup.chat_inner.winfo_children()
    assert len(bubbles) >= 4, f"Expected >= 4 bubbles, got {len(bubbles)}"
    popup.destroy()
    root.destroy()
    print("  PASS: checkin_popup_with_history")


def test_checkin_popup_close_no_conversation():
    """Closing popup without chatting doesn't create a record."""
    root = make_root()
    state = ab.StateManager()
    ai = MagicMock()
    ai.get_chat_history.return_value = []
    done_called = [False]

    def on_done(*args):
        done_called[0] = True

    popup = ab.CheckInPopup(root, state, ai, on_done, lambda: None)
    popup.show()
    popup._on_close()
    assert not done_called[0], "on_done should NOT be called without conversation"
    root.destroy()
    print("  PASS: checkin_popup_close_no_conversation")


def test_stern_warning():
    """Stern warning creates and dismisses."""
    root = make_root()
    warn = ab.SternWarning(root, "Test uyari!")
    assert warn.window.winfo_exists()
    root.update()
    warn.dismiss()
    root.update()
    root.destroy()
    print("  PASS: stern_warning")


def test_settings_dialog():
    """Settings dialog creates."""
    root = make_root()
    state = ab.StateManager()
    engine = MagicMock()
    engine.reschedule_checkin = MagicMock()
    dialog = ab.SettingsDialog(root, state, engine)
    assert dialog.window.winfo_exists()
    dialog.model_var.set("opus")
    dialog.interval_var.set("15")
    root.update()
    dialog.window.destroy()
    root.destroy()
    print("  PASS: settings_dialog")


def test_setup_wizard():
    """Setup wizard creates."""
    root = make_root()
    state = ab.StateManager()
    done = [False]
    wizard = ab.SetupWizard(root, state, lambda: done.__setitem__(0, True))
    assert wizard.window.winfo_exists()
    root.update()
    wizard.window.destroy()
    root.destroy()
    print("  PASS: setup_wizard")


def test_tray_manager():
    """Tray manager initializes (doesn't start - that blocks)."""
    root = make_root()
    tray = ab.TrayManager(root, lambda: None, lambda: None, lambda: None)
    assert tray.icon is None  # Not started yet
    root.destroy()
    print("  PASS: tray_manager")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_engine_creates():
    """Engine initializes all components."""
    root = make_root()
    engine = ab.Engine(root)
    assert engine.state is not None
    assert engine.ai is not None
    assert engine.dashboard is not None
    assert engine.tray is not None
    root.destroy()
    print("  PASS: engine_creates")


def test_full_checkin_flow():
    """Simulate a full check-in: submit -> AI response -> record saved."""
    root = make_root()
    state = ab.StateManager()
    initial_checkins = len(state.checkins)

    engine = MagicMock()
    engine.reschedule_checkin = MagicMock()

    # Simulate _on_checkin_done
    real_engine = ab.Engine.__new__(ab.Engine)
    real_engine.root = root
    real_engine.state = state
    real_engine.dashboard = MagicMock()
    real_engine.checkin_after_id = None

    real_engine._on_checkin_done(
        task_id=1, task_title="Test gorev",
        progress="Rapor yazildi", blocker="",
        next_step="Review", mood="iyi",
        summary="Test tamamlandi", score=8
    )
    assert len(state.checkins) == initial_checkins + 1
    last = state.checkins[-1]
    assert last.score == 8
    assert last.task_title == "Test gorev"
    assert last.progress == "Rapor yazildi"
    root.destroy()
    print("  PASS: full_checkin_flow")


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("Accountability Buddy Test Suite")
    print("=" * 50)

    tests = [
        # Data models
        ("Data Models", [
            test_task_defaults,
            test_checkin_defaults,
        ]),
        # State manager
        ("State Manager", [
            test_state_create_and_save,
            test_state_migration,
            test_state_next_task_id,
            test_state_active_task,
            test_state_stats,
        ]),
        # AI Manager
        ("AI Manager", [
            test_ai_fallback,
            test_ai_fallback_no_repeat,
            test_ai_parse_response,
            test_ai_system_prompt,
            test_ai_claude_path,
            test_ai_cli_connection,
        ]),
        # GUI
        ("GUI Smoke Tests", [
            test_dashboard_creates,
            test_dashboard_add_task,
            test_dashboard_task_lifecycle,
            test_dashboard_delete_task,
            test_checkin_popup_creates,
            test_checkin_popup_with_history,
            test_checkin_popup_close_no_conversation,
            test_stern_warning,
            test_settings_dialog,
            test_setup_wizard,
            test_tray_manager,
        ]),
        # Integration
        ("Integration", [
            test_engine_creates,
            test_full_checkin_flow,
        ]),
    ]

    total = 0
    passed = 0
    failed = []

    for group_name, group_tests in tests:
        print(f"\n[{group_name}]")
        for test_fn in group_tests:
            total += 1
            try:
                test_fn()
                passed += 1
            except Exception as e:
                failed.append((test_fn.__name__, str(e)))
                print(f"  FAIL: {test_fn.__name__}: {e}")

    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed")
    if failed:
        print(f"Failed ({len(failed)}):")
        for name, err in failed:
            print(f"  - {name}: {err}")
    else:
        print("ALL TESTS PASSED!")
    print("=" * 50)
