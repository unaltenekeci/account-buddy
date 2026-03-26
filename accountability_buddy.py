#!/usr/bin/env pythonw
# pyright: basic
"""
Hesap Arkadasi - Accountability Buddy
ADHD yonetim asistani: gorev takibi, periyodik check-in, Claude CLI motivasyon
"""

import json
import os
import random
import re
import shutil
import subprocess
import threading
import tkinter as tk
import tkinter.ttk as ttk
import webbrowser
import winsound
import winreg
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Callable

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# ============================================================================
# CONSTANTS & TURKISH STRINGS
# ============================================================================

APP_NAME = "Hesap Arkadasi"
APP_VERSION = "0.1.0"
STATE_DIR = Path(__file__).resolve().parent / "data"
STATE_FILE = STATE_DIR / "state.json"

CHECKIN_INTERVAL_MIN = 30
REMINDER_DELAY_MIN = 5

COLORS = {
    "bg": "#1a1a2e", "bg_light": "#16213e", "bg_card": "#0f3460",
    "accent": "#e94560", "accent_light": "#ff6b6b",
    "green": "#4CAF50", "yellow": "#FFC107", "red": "#F44336",
    "text": "#eaeaea", "text_dim": "#8892b0", "white": "#ffffff",
    "input_bg": "#233554",
}

TR = {
    "app_title": "Hesap Arkadasi - Accountability Buddy",
    "tasks_title": "Gorevler",
    "add_task": "Gorev Ekle",
    "task_name": "Gorev:",
    "task_duration": "Tahmini sure (dk):",
    "status_waiting": "Bekliyor",
    "status_active": "Devam Ediyor",
    "status_done": "Tamamlandi",
    "stats_title": "Istatistikler",
    "score_label": "Puan",
    "efficiency_label": "Verimlilik",
    "elapsed_label": "Gecen Sure",
    "completed_label": "Tamamlanan",
    "checkin_title": "Check-in Zamani!",
    "checkin_question": "Son {interval} dakikada ne yaptin?",
    "checkin_submit": "Gonder",
    "checkin_skip": "Atla",
    "checkin_ignored": "Cevap verilmedi",
    "history_title": "Check-in Gecmisi",
    "settings_title": "Ayarlar",
    "startup_option": "Windows ile birlikte baslat",
    "tray_show": "Paneli Goster",
    "tray_checkin": "Simdi Check-in",
    "tray_quit": "Cikis",
    "hours_short": "sa",
    "minutes_short": "dk",
    "no_tasks": "Henuz gorev eklenmedi. Yukaridan gorev ekleyerek baslayin!",
    "start_task": "Basla",
    "complete_task": "Bitir",
    "ai_thinking": "Claude dusunuyor...",
}

FALLBACK_MESSAGES = {
    "praise": [
        "Harika is cikardtin! Boyle devam et, sampiyonsun!",
        "Mukemmel! Gorevini tamamladin, kendini odullendir!",
        "Aferin sana! Bu tempoya devam edersen bugun cok verimli gececek!",
        "Bravo! Bir gorevi daha devirdin. Sira sonrakinde!",
        "Supersin! Odakli calismanin meyvesini topluyorsun!",
        "Tebrikler! Bu basariyi kutla ve siradaki goreve gec!",
        "Inanilmaz! Boyle giderse bugunku tum gorevleri bitireceksin!",
        "Eline saglik! Gorev tamamlandi, moral yuksek devam!",
    ],
    "encourage": [
        "Iyi gidiyorsun, biraz daha gayret et!",
        "Adim adim ilerliyorsun, her kucuk adim onemli!",
        "Dogru yoldasin, odagini kaybetme!",
        "Guzel ilerleme! Biraz daha konsantre olursan bitireceksin!",
        "Devam et, yarim birakmak yok! Neredeyse tamam!",
        "Iyi calismaya devam! Kucuk molalar vermeyi de unutma.",
        "Gayreti gorum, boyle surdur!",
        "Ilerleme var, bu cok onemli. Kendini kutla ve devam!",
    ],
    "motivate": [
        "Haydi, simdi basla! Kucuk bir adim bile buyuk fark yaratir!",
        "Odaklanma zamani! 5 dakika bile calismaya basla, momentum kazanirsin.",
        "Telefonunu birak, ekrana odaklan. Sadece 10 dakika dene!",
        "Her sey bir adimla baslar. O adimi simdi at!",
        "Erteleme tuzagina dusme! Hemen su goreve bakmaya ne dersin?",
        "Kendine inan, basarabilirsin! Sadece baslamak yeterli.",
        "Kucuk bir gorevle basla, buyuk gorevler onun ardindan gelir.",
        "Simdi degil de ne zaman? Haydi harekete gec!",
    ],
    "warn": [
        "DIKKAT! Zaman akip gidiyor, hemen harekete gec!",
        "UYARI! Odagini tamamen kaybettin. Simdi derin nefes al ve basla!",
        "ALARM! Bos is yaparak vakit harciyorsun. Gorevlerine don!",
        "CIDDI UYARI! Bu gidisle bugun hicbir sey tamamlayamayacaksin!",
        "DUR! Ne yaptiginin farkinda misin? Gorevlerin seni bekliyor!",
        "KIRMIZI ALARM! Kontrolu geri al, simdiden goreve basla!",
        "UYARI! Her dakika kayip. Toparlan ve odaklan!",
        "ACIL! Planlarin raydan cikti. Simdi duzelt, hala vakit var!",
    ],
}

SYSTEM_PROMPT = """Sen bir ADHD yonetim asistanisin. Turkce konusuyorsun.
Kullanicinin gorev takibine yardimci oluyorsun. Samimi, enerjik ve motive edici ol.

Cevabini JSON formatinda ver (baska hicbir sey yazma):
{{"feedback": "motivasyonel mesajin buraya", "score": 7}}

Puanlama:
- 8-10: Gorevi tamamlamis veya cok verimli calismis. Cosku ile kutla!
- 5-7: Ilerleme var ama daha fazlasi olabilir. Tesvik et.
- 3-4: Az ilerleme. Motive et, sert ama sevecen ol.
- 0-2: Hic calismamis veya bos is yapmis. SERT uyar, dogrudan konus.

Mevcut gorevler:
{tasks}

Gecen sure: {elapsed}
Tamamlanan gorev: {completed}/{total}

ONEMLI: Her seferinde FARKLI ve YARATICI mesajlar yaz. Tekrar etme.
Kisa ve etkili yaz (1-2 cumle). JSON disinda hicbir sey yazma."""


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Task:
    id: int
    title: str
    estimated_minutes: int
    status: str = "bekliyor"
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class CheckIn:
    timestamp: str
    score: int
    task_id: Optional[int] = None       # hangi gorevde calisildi
    task_title: str = ""                 # gorev adi (referans icin)
    progress: str = ""                   # bu gorevde ne yapildi
    blocker: str = ""                    # engel varsa
    next_step: str = ""                  # siradaki adim
    mood: str = ""                       # iyi/orta/kotu
    summary: str = ""                    # genel ozet (1 cumle)


# ============================================================================
# STATE MANAGER
# ============================================================================

class StateManager:
    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.checkins: list[CheckIn] = []
        self.session_start: str = datetime.now().isoformat()
        self.checkin_interval: int = CHECKIN_INTERVAL_MIN
        self.reminder_delay: int = REMINDER_DELAY_MIN
        self.startup_enabled: bool = False
        self.used_messages: list[str] = []
        self.model: str = "sonnet"
        self.session_id: str = str(__import__("uuid").uuid4())
        STATE_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            backup = STATE_FILE.with_suffix(".json.bak")
            if STATE_FILE.exists():
                STATE_FILE.rename(backup)
            return

        self.session_start = data.get("session_start", self.session_start)
        self.checkin_interval = data.get("checkin_interval", CHECKIN_INTERVAL_MIN)
        self.reminder_delay = data.get("reminder_delay", REMINDER_DELAY_MIN)
        self.startup_enabled = data.get("startup_enabled", False)
        self.used_messages = data.get("used_messages", [])
        self.model = data.get("model", "sonnet")
        if data.get("session_id"):
            self.session_id = data["session_id"]

        self.tasks = [
            Task(**{k: v for k, v in t.items() if k in Task.__dataclass_fields__})
            for t in data.get("tasks", [])
        ]
        self.checkins = []
        for c in data.get("checkins", []):
            # Migrate old formats
            if "response" in c and "summary" not in c:
                c["summary"] = c.pop("response", "")
            if "ai_feedback" in c and "progress" not in c:
                c["progress"] = c.pop("ai_feedback", "")
            c.pop("ai_feedback", None)
            c.pop("response", None)
            filtered = {k: v for k, v in c.items() if k in CheckIn.__dataclass_fields__}
            self.checkins.append(CheckIn(**filtered))

    def save(self) -> None:
        data = {
            "version": 2,
            "session_start": self.session_start,
            "checkin_interval": self.checkin_interval,
            "reminder_delay": self.reminder_delay,
            "startup_enabled": self.startup_enabled,
            "used_messages": self.used_messages[-100:],
            "model": self.model,
            "session_id": self.session_id,
            "tasks": [asdict(t) for t in self.tasks],
            "checkins": [asdict(c) for c in self.checkins],
        }
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(STATE_FILE))

    def next_task_id(self) -> int:
        return max((t.id for t in self.tasks), default=0) + 1

    def get_active_task(self) -> Optional[Task]:
        for t in self.tasks:
            if t.status == "devam":
                return t
        return None

    def get_elapsed_str(self) -> str:
        try:
            start = datetime.fromisoformat(self.session_start)
            delta = datetime.now() - start
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f"{hours}{TR['hours_short']} {minutes}{TR['minutes_short']}"
        except ValueError:
            return "0sa 0dk"

    def get_elapsed_minutes(self) -> int:
        try:
            return int((datetime.now() - datetime.fromisoformat(self.session_start)).total_seconds() / 60)
        except ValueError:
            return 0

    def get_efficiency(self) -> float:
        elapsed = self.get_elapsed_minutes()
        if elapsed == 0:
            return 0.0
        completed_minutes = sum(t.estimated_minutes for t in self.tasks if t.status == "bitti")
        return min(100.0, (completed_minutes / elapsed) * 100)

    def get_avg_score(self) -> float:
        if not self.checkins:
            return 0.0
        return sum(c.score for c in self.checkins) / len(self.checkins)

    def get_completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "bitti")


# ============================================================================
# AI MANAGER - CLAUDE CLI
# ============================================================================

class AIManager:
    """Thin wrapper around Claude CLI. All smarts are in Claude, we just call it."""

    # Path to Claude CLI session storage
    SESSIONS_DIR = Path.home() / ".claude" / "projects"

    SESSION_NAME = "accountability-buddy"

    def __init__(self, state: StateManager) -> None:
        self.state = state
        self.claude_path = (
            shutil.which("claude")
            or str(Path.home() / ".local" / "bin" / "claude.exe")
        )
        # Fixed session ID so we always resume the same conversation
        self.session_id = state.session_id

    def _build_system_prompt(self) -> str:
        tasks_str = "\n".join(
            f"  {t.id}. [{t.status}] {t.title} ({t.estimated_minutes}dk)"
            for t in self.state.tasks
        ) or "  (gorev yok)"

        # Include recent check-in history for context
        history_str = ""
        recent = self.state.checkins[-5:]
        if recent:
            history_lines = []
            for ci in recent:
                line = f"  [{ci.score}/10]"
                if ci.task_title:
                    line += f" Gorev: {ci.task_title} -"
                if ci.progress:
                    line += f" {ci.progress}"
                if ci.blocker:
                    line += f" | Engel: {ci.blocker}"
                if ci.next_step:
                    line += f" | Sonraki: {ci.next_step}"
                if ci.mood:
                    line += f" ({ci.mood})"
                history_lines.append(line)
            history_str = "\n\nSon check-in gecmisi:\n" + "\n".join(history_lines)

        return SYSTEM_PROMPT.format(
            tasks=tasks_str,
            elapsed=self.state.get_elapsed_str(),
            completed=self.state.get_completed_count(),
            total=len(self.state.tasks),
        ) + history_str

    def _run_claude(self, prompt: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        # Check if session exists (resume) or needs to be created
        session_file = self._get_session_file()
        if session_file and session_file.exists():
            cmd = [
                self.claude_path, "-p", prompt,
                "--resume", self.session_id,
                "--model", self.state.model,
                "--output-format", "json",
            ]
        else:
            cmd = [
                self.claude_path, "-p", prompt,
                "--session-id", self.session_id,
                "--system-prompt", self._build_system_prompt(),
                "--model", self.state.model,
                "--output-format", "json",
                "--name", self.SESSION_NAME,
            ]
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8",
        )

    def _get_session_file(self) -> Optional[Path]:
        """Find the JSONL file for our session in Claude's project dirs."""
        try:
            for d in self.SESSIONS_DIR.iterdir():
                candidate = d / f"{self.session_id}.jsonl"
                if candidate.exists():
                    return candidate
        except (OSError, StopIteration):
            pass
        return None

    def send_message(self, user_text: str, root: tk.Tk,
                     callback: Callable[[str, int], None]) -> None:
        """Send message to Claude CLI, parse response, callback on main thread."""
        def worker() -> None:
            try:
                result = self._run_claude(user_text)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr[:200])
                feedback, score = self._parse_response(result.stdout.strip())
            except Exception:
                feedback, score = self._get_fallback(user_text)
            root.after(0, callback, feedback, score)
        threading.Thread(target=worker, daemon=True).start()

    def _parse_response(self, raw: str) -> tuple[str, int]:
        # --output-format json wraps in {"type":"result","result":"..."}
        try:
            outer = json.loads(raw)
            if isinstance(outer, dict) and "result" in outer:
                raw = outer["result"]
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to extract our JSON scoring format
        match = re.search(r'\{[^}]+\}', raw)
        if match:
            try:
                data = json.loads(match.group())
                feedback = str(data.get("feedback", raw))
                score = max(0, min(10, int(data.get("score", 5))))
                return feedback, score
            except (json.JSONDecodeError, ValueError):
                pass
        return raw[:300], 5

    def _get_fallback(self, user_text: str) -> tuple[str, int]:
        text_lower = user_text.lower().strip()
        done_kw = ["bitirdim", "tamamladim", "yaptim", "hallettim", "bitti"]
        work_kw = ["calisiyorum", "devam", "ilerliyorum", "uzerinde", "yapiyorum"]
        waste_kw = ["youtube", "twitter", "instagram", "tiktok", "oyun", "dizi",
                     "film", "reddit", "bos", "hicbir", "yapmadim"]

        if any(k in text_lower for k in done_kw):
            cat, score = "praise", random.randint(8, 10)
        elif any(k in text_lower for k in work_kw):
            cat, score = "encourage", random.randint(5, 7)
        elif any(k in text_lower for k in waste_kw) or not text_lower:
            cat, score = "warn", random.randint(0, 2)
        else:
            cat, score = "motivate", random.randint(3, 4)

        available = [m for m in FALLBACK_MESSAGES[cat] if m not in self.state.used_messages]
        if not available:
            self.state.used_messages = [m for m in self.state.used_messages
                                        if m not in FALLBACK_MESSAGES[cat]]
            available = FALLBACK_MESSAGES[cat]
        msg = random.choice(available)
        self.state.used_messages.append(msg)
        return msg, score

    def get_chat_history(self) -> list[dict[str, str]]:
        """Read chat messages from Claude CLI's session storage."""
        messages: list[dict[str, str]] = []
        # Find session jsonl file
        session_file = None
        for d in self.SESSIONS_DIR.iterdir():
            candidate = d / f"{self.session_id}.jsonl"
            if candidate.exists():
                session_file = candidate
                break
        if not session_file:
            return messages
        try:
            for line in session_file.read_text(encoding="utf-8").splitlines():
                msg = json.loads(line)
                msg_type = msg.get("type", "")
                if msg_type == "user":
                    content = msg.get("message", {}).get("content", "")
                    if isinstance(content, str) and content:
                        messages.append({"role": "user", "text": content})
                elif msg_type == "assistant":
                    content = msg.get("message", {}).get("content", "")
                    if isinstance(content, dict) and content.get("type") == "text":
                        messages.append({"role": "ai", "text": content["text"]})
                    elif isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                messages.append({"role": "ai", "text": c["text"]})
        except Exception:
            pass
        return messages

    def test_connection(self, callback: Callable[[bool, str], None], root: tk.Tk) -> None:
        def worker() -> None:
            try:
                result = subprocess.run(
                    [self.claude_path, "-p", "Sadece 'Merhaba!' yaz.", "--model", "haiku"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8",
                )
                if result.returncode == 0:
                    root.after(0, callback, True, result.stdout.strip()[:80])
                else:
                    root.after(0, callback, False, result.stderr.strip()[:80])
            except Exception as e:
                root.after(0, callback, False, str(e))
        threading.Thread(target=worker, daemon=True).start()


# ============================================================================
# CHECK-IN POPUP (CHAT MODE)
# ============================================================================

class CheckInPopup:
    def __init__(self, root: tk.Tk, state: StateManager, ai: AIManager,
                 on_done: Callable[..., None],
                 on_skip: Callable[[], None],
                 is_continuation: bool = False) -> None:
        self.root = root
        self.state = state
        self.ai = ai
        self.on_done = on_done
        self.on_skip = on_skip
        self.window: Optional[tk.Toplevel] = None
        self.timeout_id: Optional[str] = None
        self.first_response: Optional[str] = None
        self.last_feedback: str = ""
        self.last_score: int = 5
        self.is_continuation = is_continuation
        self.message_count: int = 0

    def show(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

        self.window = tk.Toplevel(self.root)
        self.window.title(TR["checkin_title"])
        self.window.configure(bg=COLORS["bg"])
        self.window.attributes("-topmost", True)
        self.window.resizable(True, True)

        w, h = 520, 520
        sx = self.window.winfo_screenwidth()
        sy = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sx-w)//2}+{(sy-h)//2}")
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        frame = tk.Frame(self.window, bg=COLORS["bg"], padx=20, pady=10)
        frame.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(frame, bg=COLORS["bg"])
        header.pack(fill="x")
        tk.Label(header, text="⏰ " + TR["checkin_title"],
                 font=("Segoe UI", 16, "bold"), fg=COLORS["accent"],
                 bg=COLORS["bg"]).pack(side="left")
        tk.Label(header, text=self.state.get_elapsed_str(),
                 font=("Segoe UI", 10), fg=COLORS["text_dim"],
                 bg=COLORS["bg"]).pack(side="right")

        active = self.state.get_active_task()
        if active:
            tk.Label(frame, text=f"Aktif gorev: {active.title} ({active.estimated_minutes}dk)",
                     font=("Segoe UI", 10), fg=COLORS["yellow"],
                     bg=COLORS["bg"]).pack(anchor="w")

        # Chat area
        self.chat_frame = tk.Frame(frame, bg=COLORS["bg_light"])
        self.chat_frame.pack(fill="both", expand=True, pady=8)

        self.chat_canvas = tk.Canvas(self.chat_frame, bg=COLORS["bg_light"],
                                     highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.chat_frame, orient="vertical",
                                  command=self.chat_canvas.yview)
        self.chat_inner = tk.Frame(self.chat_canvas, bg=COLORS["bg_light"])
        self.chat_inner.bind("<Configure>",
                             lambda _e: self.chat_canvas.configure(
                                 scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.create_window((0, 0), window=self.chat_inner,
                                       anchor="nw", width=460)
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)

        # Load previous chat messages from Claude CLI session
        prev_messages = self.ai.get_chat_history()
        if prev_messages:
            for msg in prev_messages[-10:]:  # Last 10 messages
                self._add_bubble(msg["text"], is_ai=(msg["role"] == "ai"))
            self._add_bubble("--- yeni check-in ---", is_ai=True)

        question = TR["checkin_question"].format(interval=self.state.checkin_interval)
        self._add_bubble(question, is_ai=True)

        # Input
        input_frame = tk.Frame(frame, bg=COLORS["bg"])
        input_frame.pack(fill="x", pady=(5, 0))
        self.text_input = tk.Text(input_frame, height=2,
                                  font=("Segoe UI", 11),
                                  bg=COLORS["input_bg"], fg=COLORS["text"],
                                  insertbackground=COLORS["text"],
                                  relief="flat", padx=8, pady=6)
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.text_input.focus_set()

        self.submit_btn = tk.Button(input_frame, text=TR["checkin_submit"],
                                    font=("Segoe UI", 11, "bold"),
                                    bg=COLORS["accent"], fg=COLORS["white"],
                                    activebackground=COLORS["accent_light"],
                                    relief="flat", padx=15, pady=6,
                                    command=self._on_submit)
        self.submit_btn.pack(side="left")

        # Bottom
        bottom = tk.Frame(frame, bg=COLORS["bg"])
        bottom.pack(fill="x", pady=(5, 0))
        tk.Button(bottom, text=TR["checkin_skip"], font=("Segoe UI", 10),
                  bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                  relief="flat", padx=15, pady=4,
                  command=self._on_skip).pack(side="left")
        self.done_btn = tk.Button(bottom, text="Tamam, kapat",
                                  font=("Segoe UI", 10),
                                  bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                                  relief="flat", padx=15, pady=4,
                                  command=self._on_close, state="disabled")
        self.done_btn.pack(side="right")

        self.window.bind("<Return>", lambda e: self._on_submit()
                         if not (int(e.state) & 0x1) else None)

        self.timeout_id = self.root.after(
            self.state.reminder_delay * 60 * 1000, self._on_timeout)

    def _add_bubble(self, text: str, is_ai: bool = False) -> None:
        bg = COLORS["bg_card"] if is_ai else "#1a4a2e"
        anchor = "w" if is_ai else "e"
        padx = (5, 40) if is_ai else (40, 5)
        bubble = tk.Label(self.chat_inner, text=text, font=("Segoe UI", 10),
                          fg=COLORS["text"], bg=bg, wraplength=380, justify="left",
                          padx=10, pady=6)
        bubble.pack(anchor=anchor, padx=padx, pady=3, fill="x" if is_ai else "none")
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _on_submit(self) -> None:
        text = self.text_input.get("1.0", "end").strip()
        if not text:
            return
        if self.first_response is None:
            self.first_response = text
        self._add_bubble(text, is_ai=False)
        self.text_input.delete("1.0", "end")
        self.submit_btn.configure(state="disabled")
        self._add_bubble(TR["ai_thinking"], is_ai=True)
        self.ai.send_message(text, self.root, self._on_ai_response)

    def _on_ai_response(self, feedback: str, score: int) -> None:
        self.last_feedback = feedback
        self.last_score = score
        children = self.chat_inner.winfo_children()
        if children:
            children[-1].destroy()
        self._add_bubble(feedback, is_ai=True)
        self.submit_btn.configure(state="normal")
        self.done_btn.configure(state="normal")
        self.text_input.focus_set()

    def _on_close(self) -> None:
        if self.timeout_id:
            self.root.after_cancel(self.timeout_id)
        if self.first_response is None:
            self.destroy()
            return
        # Ask Claude for a task-focused summary before closing
        self.submit_btn.configure(state="disabled")
        self.done_btn.configure(state="disabled")
        self._add_bubble("Ozet hazirlaniyor...", is_ai=True)

        active = self.state.get_active_task()
        task_context = ""
        if active:
            task_context = f"Aktif gorev: #{active.id} '{active.title}' ({active.estimated_minutes}dk). "

        self.ai.send_message(
            f'{task_context}Bu check-in sohbetini gorev bazli ozetle. '
            'Sadece JSON ver, baska bir sey yazma: '
            '{"task_id": gorev_numarasi_veya_null, '
            '"progress": "bu gorevde ne yapildi (kisa)", '
            '"blocker": "engel varsa yazin yoksa bos", '
            '"next_step": "siradaki adim", '
            '"mood": "iyi/orta/kotu", '
            '"score": 0-10, '
            '"summary": "1 cumle genel ozet"}',
            self.root, self._on_summary
        )

    def _on_summary(self, raw_feedback: str, raw_score: int) -> None:
        task_id = None
        task_title = ""
        progress = ""
        blocker = ""
        next_step = ""
        mood = ""
        summary = raw_feedback
        score = raw_score

        try:
            # Handle nested JSON from --output-format json
            match = re.search(r'\{[^}]+\}', raw_feedback)
            if match:
                data = json.loads(match.group())
                task_id = data.get("task_id")
                progress = data.get("progress", "")
                blocker = data.get("blocker", "")
                next_step = data.get("next_step", "")
                mood = data.get("mood", "")
                score = max(0, min(10, int(data.get("score", raw_score))))
                summary = data.get("summary", raw_feedback)
        except (json.JSONDecodeError, ValueError):
            pass

        # Resolve task title
        if task_id:
            for t in self.state.tasks:
                if t.id == task_id:
                    task_title = t.title
                    break

        self.destroy()
        self.on_done(task_id, task_title, progress, blocker, next_step, mood, summary, score)

    def _on_skip(self) -> None:
        if self.timeout_id:
            self.root.after_cancel(self.timeout_id)
        self.destroy()
        self.on_skip()

    def _on_timeout(self) -> None:
        self.timeout_id = None
        if self.window and self.window.winfo_exists():
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            self.window.attributes("-topmost", True)
            self.window.lift()
            self.window.focus_force()
            self._flash(0)
            self.timeout_id = self.root.after(
                self.state.reminder_delay * 60 * 1000, self._on_timeout)

    def _flash(self, count: int) -> None:
        if not self.window or not self.window.winfo_exists() or count >= 6:
            if self.window and self.window.winfo_exists():
                self.window.configure(bg=COLORS["bg"])
            return
        self.window.configure(bg=COLORS["red"] if count % 2 == 0 else COLORS["bg"])
        self.root.after(200, self._flash, count + 1)

    def destroy(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None


class SternWarning:
    def __init__(self, root: tk.Tk, message: str) -> None:
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.attributes("-topmost", True)
        self.window.attributes("-fullscreen", True)
        self.window.configure(bg="#CC0000")
        self.window.bind("<Escape>", lambda _e: self.dismiss())
        self.window.bind("<Button-1>", lambda _e: self.dismiss())
        frame = tk.Frame(self.window, bg="#CC0000")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(frame, text="UYARI", font=("Segoe UI", 48, "bold"),
                 fg="#FFFFFF", bg="#CC0000").pack(pady=20)
        tk.Label(frame, text=message, font=("Segoe UI", 24),
                 fg="#FFFFFF", bg="#CC0000", wraplength=800,
                 justify="center").pack(pady=20)
        tk.Label(frame, text="(Kapatmak icin tiklayin veya ESC basin)",
                 font=("Segoe UI", 14), fg="#FF9999", bg="#CC0000").pack(pady=30)
        winsound.MessageBeep(winsound.MB_ICONHAND)
        self.root.after(15000, self.dismiss)

    def dismiss(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.destroy()


# ============================================================================
# DASHBOARD
# ============================================================================

class Dashboard:
    def __init__(self, root: tk.Tk, state: StateManager, engine: 'Engine') -> None:
        self.root = root
        self.state = state
        self.engine = engine
        self.feedback_label: Optional[tk.Label] = None
        self._build_ui()
        self._start_clock()

    def _build_ui(self) -> None:
        self.root.title(TR["app_title"])
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("750x700")
        self.root.minsize(650, 550)

        self.main_frame = tk.Frame(self.root, bg=COLORS["bg"])
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self._build_add_task_frame()

        middle = tk.Frame(self.main_frame, bg=COLORS["bg"])
        middle.pack(fill="both", expand=True, pady=5)
        left = tk.Frame(middle, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right = tk.Frame(middle, bg=COLORS["bg"], width=220)
        right.pack(side="right", fill="y", padx=(5, 0))
        right.pack_propagate(False)

        self._build_task_list(left)
        self._build_stats(right)
        self._build_feedback_area()
        self._build_history()

    def _build_add_task_frame(self) -> None:
        frame = tk.Frame(self.main_frame, bg=COLORS["bg_card"], padx=12, pady=10)
        frame.pack(fill="x", pady=(0, 8))
        tk.Label(frame, text=TR["task_name"], font=("Segoe UI", 10),
                 fg=COLORS["text"], bg=COLORS["bg_card"]).pack(side="left")
        self.task_name_var = tk.StringVar()
        name_entry = tk.Entry(frame, textvariable=self.task_name_var,
                              font=("Segoe UI", 10), width=30,
                              bg=COLORS["input_bg"], fg=COLORS["text"],
                              insertbackground=COLORS["text"], relief="flat")
        name_entry.pack(side="left", padx=5)
        name_entry.bind("<Return>", lambda _e: self._add_task())
        tk.Label(frame, text=TR["task_duration"], font=("Segoe UI", 10),
                 fg=COLORS["text"], bg=COLORS["bg_card"]).pack(side="left", padx=(10, 0))
        self.task_dur_var = tk.StringVar(value="30")
        dur_entry = tk.Entry(frame, textvariable=self.task_dur_var,
                             font=("Segoe UI", 10), width=5,
                             bg=COLORS["input_bg"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        dur_entry.pack(side="left", padx=5)
        dur_entry.bind("<Return>", lambda _e: self._add_task())
        tk.Button(frame, text="+ " + TR["add_task"], font=("Segoe UI", 10, "bold"),
                  bg=COLORS["accent"], fg=COLORS["white"],
                  activebackground=COLORS["accent_light"],
                  relief="flat", padx=15, pady=3,
                  command=self._add_task).pack(side="left", padx=10)

    def _build_task_list(self, parent: tk.Frame) -> None:
        tk.Label(parent, text=TR["tasks_title"], font=("Segoe UI", 13, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
        self.task_container = tk.Frame(parent, bg=COLORS["bg_light"])
        self.task_container.pack(fill="both", expand=True, pady=5)
        self._render_tasks()

    def _build_stats(self, parent: tk.Frame) -> None:
        tk.Label(parent, text=TR["stats_title"], font=("Segoe UI", 13, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, 5))
        stats = tk.Frame(parent, bg=COLORS["bg_card"], padx=12, pady=10)
        stats.pack(fill="x")
        self.score_var = tk.StringVar(value="0.0")
        self._stat_row(stats, TR["score_label"], self.score_var, COLORS["accent"])
        self.efficiency_var = tk.StringVar(value="0%")
        self._stat_row(stats, TR["efficiency_label"], self.efficiency_var, COLORS["yellow"])
        self.completed_var = tk.StringVar(value="0/0")
        self._stat_row(stats, TR["completed_label"], self.completed_var, COLORS["green"])
        self.elapsed_var = tk.StringVar(value="0sa 0dk")
        self._stat_row(stats, TR["elapsed_label"], self.elapsed_var, COLORS["text_dim"])

        tk.Button(parent, text="💬 Claude ile Konus", font=("Segoe UI", 10, "bold"),
                  bg=COLORS["accent"], fg=COLORS["white"],
                  activebackground=COLORS["accent_light"], relief="flat", pady=5,
                  command=self._open_chat).pack(fill="x", pady=(10, 0))

        tk.Button(parent, text="⚙ " + TR["settings_title"], font=("Segoe UI", 10),
                  bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                  activebackground=COLORS["bg_light"], relief="flat", pady=5,
                  command=self._show_settings).pack(fill="x", pady=(5, 0))

    def _stat_row(self, parent: tk.Frame, label: str, var: tk.StringVar, color: str) -> None:
        row = tk.Frame(parent, bg=COLORS["bg_card"])
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=("Segoe UI", 10),
                 fg=COLORS["text_dim"], bg=COLORS["bg_card"]).pack(side="left")
        tk.Label(row, textvariable=var, font=("Segoe UI", 12, "bold"),
                 fg=color, bg=COLORS["bg_card"]).pack(side="right")

    def _build_feedback_area(self) -> None:
        self.feedback_label = tk.Label(self.main_frame, text="",
                                       font=("Segoe UI", 12),
                                       fg=COLORS["green"], bg=COLORS["bg"],
                                       wraplength=700, justify="center")
        self.feedback_label.pack(pady=5)

    def _build_history(self) -> None:
        tk.Label(self.main_frame, text=TR["history_title"],
                 font=("Segoe UI", 11, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
        self.history_container = tk.Frame(self.main_frame, bg=COLORS["bg_light"])
        self.history_container.pack(fill="x", pady=5)
        self._render_history()

    def _render_tasks(self) -> None:
        for w in self.task_container.winfo_children():
            w.destroy()
        if not self.state.tasks:
            tk.Label(self.task_container, text=TR["no_tasks"],
                     font=("Segoe UI", 10, "italic"),
                     fg=COLORS["text_dim"], bg=COLORS["bg_light"],
                     pady=20).pack()
            return
        for task in self.state.tasks:
            self._render_task_row(task)

    def _render_task_row(self, task: Task) -> None:
        if task.status == "bitti":
            bg, fg, indicator = "#1b3a1b", COLORS["green"], "✓"
        elif task.status == "devam":
            bg, fg, indicator = "#3a3a1b", COLORS["yellow"], "▶"
        else:
            bg, fg, indicator = COLORS["bg_light"], COLORS["text_dim"], "○"

        row = tk.Frame(self.task_container, bg=bg, padx=8, pady=6)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=f"{indicator} {task.id}.", font=("Segoe UI", 10, "bold"),
                 fg=fg, bg=bg).pack(side="left")
        title_font = ("Segoe UI", 10, "overstrike") if task.status == "bitti" else ("Segoe UI", 10)
        tk.Label(row, text=task.title, font=title_font, fg=fg, bg=bg).pack(side="left", padx=5)
        tk.Label(row, text=f"{task.estimated_minutes}{TR['minutes_short']}",
                 font=("Segoe UI", 9), fg=COLORS["text_dim"], bg=bg).pack(side="left", padx=5)

        # Delete button for all tasks
        tk.Button(row, text="✕", font=("Segoe UI", 9), bg=bg,
                  fg=COLORS["text_dim"], relief="flat", padx=4,
                  command=lambda t=task: self._delete_task(t)).pack(side="right", padx=2)

        if task.status == "bekliyor":
            tk.Button(row, text=TR["start_task"], font=("Segoe UI", 9),
                      bg=COLORS["yellow"], fg="#000", relief="flat", padx=8,
                      command=lambda t=task: self._start_task(t)).pack(side="right", padx=2)
        elif task.status == "devam":
            tk.Button(row, text=TR["complete_task"], font=("Segoe UI", 9),
                      bg=COLORS["green"], fg="#fff", relief="flat", padx=8,
                      command=lambda t=task: self._complete_task(t)).pack(side="right", padx=2)

    def _render_history(self) -> None:
        for w in self.history_container.winfo_children():
            w.destroy()
        recent = self.state.checkins[-5:][::-1]
        if not recent:
            tk.Label(self.history_container, text="Henuz check-in yok",
                     font=("Segoe UI", 9, "italic"), fg=COLORS["text_dim"],
                     bg=COLORS["bg_light"], pady=8).pack()
            return
        for ci in recent:
            row = tk.Frame(self.history_container, bg=COLORS["bg_light"], padx=8, pady=4)
            row.pack(fill="x", pady=1)
            try:
                t = datetime.fromisoformat(ci.timestamp).strftime("%H:%M")
            except ValueError:
                t = "??:??"
            sc_color = COLORS["green"] if ci.score >= 8 else COLORS["yellow"] if ci.score >= 5 else COLORS["red"]
            tk.Label(row, text=t, font=("Segoe UI", 9), fg=COLORS["text_dim"],
                     bg=COLORS["bg_light"]).pack(side="left")
            tk.Label(row, text=f"[{ci.score}/10]", font=("Segoe UI", 9, "bold"),
                     fg=sc_color, bg=COLORS["bg_light"]).pack(side="left", padx=5)
            # Show task + progress or summary
            display = ""
            if ci.task_title:
                display = f"{ci.task_title}: {ci.progress}" if ci.progress else ci.task_title
            elif ci.summary:
                display = ci.summary
            else:
                display = ci.progress or "(ozet yok)"
            short = display[:50] + ("..." if len(display) > 50 else "")
            tk.Label(row, text=short, font=("Segoe UI", 9), fg=COLORS["text"],
                     bg=COLORS["bg_light"]).pack(side="left", padx=5)

    def _add_task(self) -> None:
        name = self.task_name_var.get().strip()
        if not name:
            return
        try:
            dur = int(self.task_dur_var.get().strip())
        except ValueError:
            dur = 30
        self.state.tasks.append(Task(id=self.state.next_task_id(),
                                      title=name, estimated_minutes=max(1, dur)))
        self.state.save()
        self.task_name_var.set("")
        self.task_dur_var.set("30")
        self.refresh()

    def _start_task(self, task: Task) -> None:
        for t in self.state.tasks:
            if t.status == "devam" and t.id != task.id:
                t.status = "bekliyor"
                t.started_at = None
        task.status = "devam"
        task.started_at = datetime.now().isoformat()
        self.state.save()
        self.refresh()

    def _complete_task(self, task: Task) -> None:
        task.status = "bitti"
        task.completed_at = datetime.now().isoformat()
        self.state.save()
        self.refresh()

    def _delete_task(self, task: Task) -> None:
        self.state.tasks = [t for t in self.state.tasks if t.id != task.id]
        self.state.save()
        self.refresh()

    def _open_chat(self) -> None:
        """Open chat with Claude using --continue (continues last conversation)."""
        self.engine._trigger_chat()

    def _show_settings(self) -> None:
        SettingsDialog(self.root, self.state, self.engine)

    def show_feedback(self, text: str, score: int) -> None:
        color = COLORS["green"] if score >= 8 else COLORS["yellow"] if score >= 5 \
            else COLORS["accent"] if score >= 3 else COLORS["red"]
        if self.feedback_label:
            self.feedback_label.configure(text=text, fg=color)

    def refresh(self) -> None:
        self._render_tasks()
        self._render_history()
        self._update_stats()

    def _update_stats(self) -> None:
        self.score_var.set(f"{self.state.get_avg_score():.1f}/10")
        self.efficiency_var.set(f"{self.state.get_efficiency():.0f}%")
        self.completed_var.set(f"{self.state.get_completed_count()}/{len(self.state.tasks)}")
        self.elapsed_var.set(self.state.get_elapsed_str())

    def _start_clock(self) -> None:
        self._update_stats()
        self.root.after(30000, self._start_clock)


# ============================================================================
# SETTINGS DIALOG
# ============================================================================

class SettingsDialog:
    def __init__(self, root: tk.Tk, state: StateManager, engine: 'Engine') -> None:
        self.root = root
        self.state = state
        self.engine = engine

        self.window = tk.Toplevel(root)
        self.window.title(TR["settings_title"])
        self.window.configure(bg=COLORS["bg"])
        self.window.geometry("450x400")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.grab_set()

        frame = tk.Frame(self.window, bg=COLORS["bg"], padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        # Claude Model
        tk.Label(frame, text="Claude Model", font=("Segoe UI", 12, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, 5))

        self.model_var = tk.StringVar(value=self.state.model)
        models = [("Haiku (hizli, hafif)", "haiku"),
                  ("Sonnet (dengeli)", "sonnet"),
                  ("Opus (en akilli)", "opus")]
        for text, val in models:
            tk.Radiobutton(frame, text=text, variable=self.model_var, value=val,
                           font=("Segoe UI", 10), fg=COLORS["text"], bg=COLORS["bg"],
                           selectcolor=COLORS["bg_card"],
                           activebackground=COLORS["bg"]).pack(anchor="w")

        # Claude CLI status
        status_frame = tk.Frame(frame, bg=COLORS["bg"])
        status_frame.pack(fill="x", pady=(10, 0))
        tk.Button(status_frame, text="Baglantiyi Test Et", font=("Segoe UI", 10),
                  bg=COLORS["bg_card"], fg=COLORS["text"], relief="flat",
                  padx=15, pady=5, command=self._test).pack(side="left")
        self.test_label = tk.Label(status_frame, text="", font=("Segoe UI", 9),
                                   fg=COLORS["text_dim"], bg=COLORS["bg"])
        self.test_label.pack(side="left", padx=10)

        # Check-in interval
        tk.Label(frame, text="Check-in araligi (dakika):", font=("Segoe UI", 10),
                 fg=COLORS["text_dim"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 2))
        self.interval_var = tk.StringVar(value=str(self.state.checkin_interval))
        tk.Entry(frame, textvariable=self.interval_var, font=("Segoe UI", 10),
                 width=8, bg=COLORS["input_bg"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], relief="flat").pack(anchor="w")

        # Startup
        self.startup_var = tk.BooleanVar(value=self.state.startup_enabled)
        tk.Checkbutton(frame, text=TR["startup_option"], variable=self.startup_var,
                       font=("Segoe UI", 10), fg=COLORS["text"], bg=COLORS["bg"],
                       selectcolor=COLORS["bg_card"],
                       activebackground=COLORS["bg"]).pack(anchor="w", pady=(10, 5))

        # Save
        tk.Button(frame, text="Kaydet", font=("Segoe UI", 11, "bold"),
                  bg=COLORS["accent"], fg=COLORS["white"], relief="flat",
                  padx=25, pady=6, command=self._save).pack(pady=10)

    def _test(self) -> None:
        self.test_label.configure(text="Test ediliyor...", fg=COLORS["yellow"])
        self.state.model = self.model_var.get()
        ai = AIManager(self.state)
        ai.test_connection(self._on_test, self.root)

    def _on_test(self, success: bool, message: str) -> None:
        if success:
            self.test_label.configure(text=f"Basarili: {message[:60]}", fg=COLORS["green"])
        else:
            self.test_label.configure(text=f"Hata: {message[:60]}", fg=COLORS["red"])

    def _save(self) -> None:
        self.state.model = self.model_var.get()
        try:
            self.state.checkin_interval = max(1, int(self.interval_var.get().strip()))
        except ValueError:
            pass

        startup = self.startup_var.get()
        if startup != self.state.startup_enabled:
            self.state.startup_enabled = startup
            try:
                key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                     winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
                if startup:
                    script = str(Path(__file__).resolve())
                    winreg.SetValueEx(key, "AccountabilityBuddy", 0,
                                      winreg.REG_SZ, f'pythonw "{script}"')
                else:
                    try:
                        winreg.DeleteValue(key, "AccountabilityBuddy")
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(key)
            except OSError:
                pass

        self.state.save()
        self.engine.reschedule_checkin()
        self.window.destroy()


# ============================================================================
# SETUP WIZARD
# ============================================================================

class SetupWizard:
    def __init__(self, root: tk.Tk, state: StateManager,
                 on_done: Callable[[], None]) -> None:
        self.root = root
        self.state = state
        self.on_done = on_done

        self.window = tk.Toplevel(root)
        self.window.title("Hesap Arkadasi - Kurulum")
        self.window.configure(bg=COLORS["bg"])
        self.window.geometry("500x500")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self._finish)

        frame = tk.Frame(self.window, bg=COLORS["bg"], padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        # Welcome
        tk.Label(frame, text="Hosgeldin!",
                 font=("Segoe UI", 22, "bold"),
                 fg=COLORS["accent"], bg=COLORS["bg"]).pack(pady=(0, 5))
        tk.Label(frame, text="Hesap Arkadasi seni odakli tutacak.\n"
                 "Claude CLI ile calisiyor - aboneliginden dusuyor.",
                 font=("Segoe UI", 11), fg=COLORS["text"], bg=COLORS["bg"],
                 justify="center").pack(pady=(0, 15))

        # Step 1: Claude CLI check
        step1 = tk.LabelFrame(frame, text=" 1. Claude CLI Kontrolu ",
                               font=("Segoe UI", 11, "bold"),
                               fg=COLORS["accent"], bg=COLORS["bg_light"],
                               padx=15, pady=10)
        step1.pack(fill="x", pady=5)

        # Check if claude is available
        claude_exe = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
        try:
            _check = subprocess.run(
                [claude_exe, "--version"], capture_output=True, text=True, timeout=5, encoding="utf-8")
            cli_found = _check.returncode == 0
            cli_version = _check.stdout.strip()
        except Exception:
            cli_found = False
            cli_version = ""

        if cli_found:
            tk.Label(step1, text=f"Claude CLI bulundu: {cli_version}",
                     font=("Segoe UI", 10), fg=COLORS["green"],
                     bg=COLORS["bg_light"]).pack(anchor="w")
        else:
            tk.Label(step1, text="Claude CLI bulunamadi! Once yukleyin:",
                     font=("Segoe UI", 10), fg=COLORS["red"],
                     bg=COLORS["bg_light"]).pack(anchor="w")
            link = tk.Label(step1, text="  -> Claude Code Yukle",
                            font=("Segoe UI", 10, "underline"),
                            fg="#5dade2", bg=COLORS["bg_light"], cursor="hand2")
            link.pack(anchor="w")
            link.bind("<Button-1>", lambda _e: webbrowser.open(
                "https://docs.anthropic.com/en/docs/claude-code"))

        test_row = tk.Frame(step1, bg=COLORS["bg_light"])
        test_row.pack(fill="x", pady=(5, 0))
        tk.Button(test_row, text="Baglantiyi Test Et", font=("Segoe UI", 9, "bold"),
                  bg=COLORS["bg_card"], fg=COLORS["text"], relief="flat",
                  padx=12, pady=3, command=self._test).pack(side="left")
        self.test_label = tk.Label(test_row, text="", font=("Segoe UI", 9),
                                   fg=COLORS["text_dim"], bg=COLORS["bg_light"])
        self.test_label.pack(side="left", padx=10)

        # Step 2: Model
        step2 = tk.LabelFrame(frame, text=" 2. Model Sec ",
                               font=("Segoe UI", 11, "bold"),
                               fg=COLORS["accent"], bg=COLORS["bg_light"],
                               padx=15, pady=10)
        step2.pack(fill="x", pady=5)

        self.model_var = tk.StringVar(value="sonnet")
        models = [("Haiku - hizli, hafif", "haiku"),
                  ("Sonnet - dengeli (onerilen)", "sonnet"),
                  ("Opus - en akilli", "opus")]
        for text, val in models:
            tk.Radiobutton(step2, text=text, variable=self.model_var, value=val,
                           font=("Segoe UI", 10), fg=COLORS["text"],
                           bg=COLORS["bg_light"], selectcolor=COLORS["bg_card"],
                           activebackground=COLORS["bg_light"]).pack(anchor="w")

        # Step 3: Interval
        step3 = tk.LabelFrame(frame, text=" 3. Check-in Araligi ",
                               font=("Segoe UI", 11, "bold"),
                               fg=COLORS["accent"], bg=COLORS["bg_light"],
                               padx=15, pady=10)
        step3.pack(fill="x", pady=5)

        interval_row = tk.Frame(step3, bg=COLORS["bg_light"])
        interval_row.pack(fill="x")
        tk.Label(interval_row, text="Kac dakikada bir sorayim?",
                 font=("Segoe UI", 10), fg=COLORS["text"],
                 bg=COLORS["bg_light"]).pack(side="left")
        self.interval_var = tk.StringVar(value="30")
        tk.Entry(interval_row, textvariable=self.interval_var,
                 font=("Segoe UI", 10), width=5, bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"],
                 relief="flat").pack(side="left", padx=8)
        tk.Label(interval_row, text="dakika", font=("Segoe UI", 10),
                 fg=COLORS["text_dim"], bg=COLORS["bg_light"]).pack(side="left")

        # Start
        tk.Button(frame, text="Basla!", font=("Segoe UI", 14, "bold"),
                  bg=COLORS["accent"], fg=COLORS["white"],
                  activebackground=COLORS["accent_light"],
                  relief="flat", padx=40, pady=10,
                  command=self._finish).pack(pady=15)

    def _test(self) -> None:
        self.test_label.configure(text="Test ediliyor...", fg=COLORS["yellow"])
        ai = AIManager(self.state)
        ai.test_connection(self._on_test, self.root)

    def _on_test(self, success: bool, message: str) -> None:
        if success:
            self.test_label.configure(text=f"Basarili: {message[:60]}", fg=COLORS["green"])
        else:
            self.test_label.configure(text=f"Hata: {message[:60]}", fg=COLORS["red"])

    def _finish(self) -> None:
        self.state.model = self.model_var.get()
        try:
            self.state.checkin_interval = max(1, int(self.interval_var.get().strip()))
        except ValueError:
            pass
        self.state.save()
        self.window.destroy()
        self.on_done()


# ============================================================================
# ENGINE, TRAY, APP
# ============================================================================

class TrayManager:
    def __init__(self, root: tk.Tk, on_show: Callable[[], None],
                 on_checkin: Callable[[], None],
                 on_quit: Callable[[], None]) -> None:
        self.root = root
        self.on_show = on_show
        self.on_checkin = on_checkin
        self.on_quit = on_quit
        self.icon: Any = None

    def start(self) -> None:
        if not HAS_TRAY:
            return
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill="#2196F3")
        draw.line([(18, 34), (28, 44), (46, 22)], fill="white", width=4)
        menu = pystray.Menu(
            pystray.MenuItem(TR["tray_show"], lambda: self.root.after(0, self.on_show), default=True),
            pystray.MenuItem(TR["tray_checkin"], lambda: self.root.after(0, self.on_checkin)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(TR["tray_quit"], lambda: self.root.after(0, self.on_quit)),
        )
        self.icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self) -> None:
        if self.icon:
            self.icon.stop()


class Engine:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.state = StateManager()
        self.is_first_run = not STATE_FILE.exists()
        self.state.load()
        self.ai = AIManager(self.state)
        self.dashboard = Dashboard(root, self.state, self)
        self.tray = TrayManager(root, self._show_dashboard,
                                self._trigger_checkin, self._quit)
        self.popup: Optional[CheckInPopup] = None
        self.checkin_after_id: Optional[str] = None

    def start(self) -> None:
        self.tray.start()
        if self.is_first_run:
            SetupWizard(self.root, self.state, self._after_setup)
        else:
            self._show_dashboard()
            self._schedule_checkin()

    def _after_setup(self) -> None:
        self.ai = AIManager(self.state)
        self._show_dashboard()
        self._schedule_checkin()

    def _schedule_checkin(self) -> None:
        if self.checkin_after_id:
            self.root.after_cancel(self.checkin_after_id)
        ms = self.state.checkin_interval * 60 * 1000
        self.checkin_after_id = self.root.after(ms, self._trigger_checkin)

    def reschedule_checkin(self) -> None:
        self._schedule_checkin()

    def _trigger_checkin(self) -> None:
        self.checkin_after_id = None
        if self.popup and self.popup.window and self.popup.window.winfo_exists():
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            self.popup.window.lift()
            self.popup.window.focus_force()
            return
        self.popup = CheckInPopup(self.root, self.state, self.ai,
                                  self._on_checkin_done, self._on_checkin_skip)
        self.popup.show()

    def _trigger_chat(self) -> None:
        """Open chat popup with --continue (continues last Claude conversation)."""
        if self.popup and self.popup.window and self.popup.window.winfo_exists():
            self.popup.window.lift()
            self.popup.window.focus_force()
            return
        self.popup = CheckInPopup(self.root, self.state, self.ai,
                                  self._on_checkin_done, self._on_checkin_skip,
                                  is_continuation=True)
        self.popup.show()

    def _on_checkin_done(self, task_id: Optional[int], task_title: str,
                         progress: str, blocker: str, next_step: str,
                         mood: str, summary: str, score: int) -> None:
        checkin = CheckIn(
            timestamp=datetime.now().isoformat(),
            score=score, task_id=task_id, task_title=task_title,
            progress=progress, blocker=blocker, next_step=next_step,
            mood=mood, summary=summary,
        )
        self.state.checkins.append(checkin)
        self.state.save()
        self.dashboard.show_feedback(summary, score)
        self.dashboard.refresh()
        self._schedule_checkin()

        # Auto-complete task if high score and progress indicates done
        if score >= 8 and task_id:
            for t in self.state.tasks:
                if t.id == task_id and t.status == "devam":
                    done_kw = ["tamamlandi", "bitti", "bitirdi", "halletti"]
                    if any(k in progress.lower() for k in done_kw):
                        t.status = "bitti"
                        t.completed_at = datetime.now().isoformat()
                        self.state.save()
                        self.dashboard.refresh()
                    break

        if score <= 2:
            SternWarning(self.root, summary)

    def _on_checkin_skip(self) -> None:
        self.state.checkins.append(CheckIn(
            timestamp=datetime.now().isoformat(), summary="(atlanmis)", score=0))
        self.state.save()
        self.dashboard.refresh()
        if self.checkin_after_id:
            self.root.after_cancel(self.checkin_after_id)
        self.checkin_after_id = self.root.after(
            self.state.reminder_delay * 60 * 1000, self._trigger_checkin)

    def _show_dashboard(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.dashboard.refresh()

    def _hide_to_tray(self) -> None:
        self.root.withdraw()

    def _quit(self) -> None:
        self.state.save()
        self.tray.stop()
        self.root.quit()
        self.root.destroy()


class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.engine = Engine(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.engine._hide_to_tray)

    def run(self) -> None:
        self.engine.start()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
