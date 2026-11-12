"""Напоминание и гимнастика для глаз в течение дня.

Запуск: «Запустить гимнастику.bat» или
    pyw -3 eye_gym.py

Крестик сворачивает окно, напоминания продолжаются.
Галочка «Запускать вместе с Windows» кладёт скрытый ярлык в автозагрузку.
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import shutil
import sys
import time
import tkinter as tk
import traceback
import winsound
from tkinter import messagebox
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pictures import draw_picture

BG = "#f3efe7"
PANEL = "#fffdf9"
TEXT = "#211c18"
MUTED = "#4a433c"
LINE = "#e3d9cc"
ACCENT = "#1a6b73"
ACCENT_DARK = "#14555c"
BTN = "#efe8dc"
OK = "#246b45"

APP_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = APP_DIR / "settings.json"
JOURNAL_PATH = APP_DIR / "journal.json"
ERROR_LOG = APP_DIR / "error.log"
STARTUP_NAME = "Гимнастика для глаз.vbs"
MUTEX_NAME = "Local\\EyeGymMutex"
EVENT_NAME = "Local\\EyeGymShow"
INTRO_SECONDS = 4
DEFAULTS = {
    "interval_min": 60,
    "day_start": "09:00",
    "day_end": "19:00",
    "sound": True,
    "next_at": None,
}
INTERVALS = (30, 45, 60, 90, 120)


@dataclass(frozen=True)
class Exercise:
    title: str
    text: str
    seconds: int
    kind: str


# Без давления на веки и без сильного зажмуривания: при ангиопатии это лишнее.
# text остаётся в данных, на экране зарядки его нет: схему видно без чтения.
EXERCISES = (
    Exercise(
        "Моргание",
        "Моргайте мягко и часто, как будто смахиваете пыль. Не зажмуривайтесь и не двигайте головой.",
        20,
        "blink",
    ),
    Exercise(
        "Вверх и вниз",
        "Медленно переводите взгляд вверх и вниз. Голова неподвижна. Дышите ровно, без усилия.",
        20,
        "vertical",
    ),
    Exercise(
        "Влево и вправо",
        "Медленно смотрите влево и вправо, как можно дальше. Голову не поворачивайте.",
        20,
        "horizontal",
    ),
    Exercise(
        "Диагонали",
        "Взгляд из правого верхнего угла в левый нижний, затем из левого верхнего в правый нижний.",
        24,
        "diagonal",
    ),
    Exercise(
        "Круги",
        "Медленный круг глазами по часовой стрелке, затем против. По 3–4 круга. Без рывков и без боли.",
        30,
        "circle",
    ),
    Exercise(
        "Восьмёрка",
        "Взглядом рисуйте лежащую восьмёрку. Голова остаётся на месте, движение только глаз.",
        24,
        "eight",
    ),
    Exercise(
        "Близко и далеко",
        "Палец на 25–30 см. Несколько секунд смотрите на него, затем вдаль, лучше в окно. Чередуйте.",
        30,
        "nearfar",
    ),
    Exercise(
        "Пальминг",
        "Закройте глаза и накройте их ладонями, не давя на веки. Локти обоприте. Тепло, темнота, спокойный выдох.",
        40,
        "palming",
    ),
)


def parse_hhmm(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.strip().split(":")
    hour, minute = int(hour_text), int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(value)
    return hour, minute


def format_hhmm(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def minutes_of(now: datetime) -> int:
    return now.hour * 60 + now.minute


def within_window(now: datetime, start: str, end: str) -> bool:
    start_min = _hhmm_minutes(start)
    end_min = _hhmm_minutes(end)
    return start_min <= minutes_of(now) <= end_min


def _hhmm_minutes(value: str) -> int:
    hour, minute = parse_hhmm(value)
    return hour * 60 + minute


def compute_next(after: datetime, start: str, end: str, interval_min: int) -> datetime:
    """Следующее напоминание не раньше чем через interval и только внутри окна."""
    start_min = _hhmm_minutes(start)
    end_min = _hhmm_minutes(end)
    if end_min <= start_min:
        raise ValueError("конец дня должен быть позже начала")
    candidate = after + timedelta(minutes=interval_min)
    for _ in range(10):
        day_minutes = minutes_of(candidate)
        day_start = candidate.replace(
            hour=start_min // 60, minute=start_min % 60, second=0, microsecond=0
        )
        if day_minutes < start_min:
            return day_start
        if day_minutes <= end_min:
            return candidate.replace(second=0, microsecond=0)
        candidate = day_start + timedelta(days=1)
    return candidate


def clamp_to_window(target: datetime, start: str, end: str) -> datetime:
    if within_window(target, start, end):
        return target.replace(second=0, microsecond=0)
    start_min = _hhmm_minutes(start)
    day_start = target.replace(
        hour=start_min // 60, minute=start_min % 60, second=0, microsecond=0
    )
    if minutes_of(target) < start_min:
        return day_start
    return day_start + timedelta(days=1)


def initial_next(
    saved: datetime | None,
    now: datetime,
    start: str,
    end: str,
    interval_min: int,
) -> datetime:
    if saved is not None and saved > now:
        return saved
    if saved is not None and within_window(now, start, end):
        return (now + timedelta(seconds=45)).replace(microsecond=0)
    return compute_next(now, start, end, interval_min)


def plural(count: int, one: str, few: str, many: str) -> str:
    number = abs(count) % 100
    if 11 <= number <= 14:
        return many
    tail = number % 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


def format_remain(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "сейчас"
    if seconds < 60:
        return f"через {seconds} {plural(seconds, 'секунду', 'секунды', 'секунд')}"
    minutes, _rest = divmod(seconds, 60)
    if minutes < 60:
        return f"через {minutes} {plural(minutes, 'минуту', 'минуты', 'минут')}"
    hours, minutes = divmod(minutes, 60)
    hour_word = plural(hours, "час", "часа", "часов")
    if minutes == 0:
        return f"через {hours} {hour_word}"
    minute_word = plural(minutes, "минуту", "минуты", "минут")
    return f"через {hours} {hour_word} {minutes} {minute_word}"


def format_when(moment: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    clock = moment.strftime("%H:%M")
    if moment.date() == now.date():
        return f"сегодня в {clock}"
    if moment.date() == now.date() + timedelta(days=1):
        return f"завтра в {clock}"
    weekday = "пн вт ср чт пт сб вс".split()[moment.weekday()]
    return f"{weekday} {moment.day:02d}.{moment.month:02d} в {clock}"


def format_clock(seconds: float) -> str:
    total = max(0, math.ceil(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def session_seconds() -> int:
    return INTRO_SECONDS + sum(item.seconds for item in EXERCISES)


def format_session_length() -> str:
    total = session_seconds()
    minutes = total / 60
    if abs(minutes - round(minutes)) < 0.05:
        whole = int(round(minutes))
        return f"{whole} {plural(whole, 'минуту', 'минуты', 'минут')}"
    text = f"{minutes:.1f}".replace(".", ",")
    return f"{text} минуты"


def load_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def log_error(error: BaseException) -> None:
    try:
        with ERROR_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---\n")
            traceback.print_exception(type(error), error, error.__traceback__, file=handle)
    except OSError:
        pass


def pythonw_path() -> Path:
    executable = Path(sys.executable)
    if executable.name.lower() in {"python.exe", "pythonw.exe"}:
        sibling = executable.with_name("pythonw.exe")
        if sibling.exists():
            return sibling
        return executable
    found = shutil.which("pythonw") or shutil.which("pyw")
    if found:
        return Path(found)
    return executable


def launch_command() -> str:
    executable = str(pythonw_path())
    script = str(APP_DIR / "eye_gym.py")
    return f'"{executable}" "{script}" --background'


def startup_path() -> Path:
    appdata = Path(os.environ["APPDATA"])
    return appdata / "Microsoft/Windows/Start Menu/Programs/Startup" / STARTUP_NAME


def autostart_script() -> str:
    command = launch_command().replace('"', '""')
    work = str(APP_DIR).replace('"', '""')
    return (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.CurrentDirectory = "{work}"\r\n'
        f'sh.Run "{command}", 0, False\r\n'
    )


def autostart_enabled() -> bool:
    return startup_path().exists()


def set_autostart(enabled: bool) -> None:
    path = startup_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(autostart_script(), encoding="utf-8")


class SingleInstance:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateEventW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.OpenEventW.restype = ctypes.c_void_p
        kernel32.SetEvent.argtypes = [ctypes.c_void_p]
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32 = kernel32
        self.mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        self.already = ctypes.get_last_error() == 183
        self.event = None
        if self.already:
            if self.mutex:
                kernel32.CloseHandle(self.mutex)
                self.mutex = None
            event = kernel32.OpenEventW(0x0002, False, EVENT_NAME)
            if event:
                kernel32.SetEvent(event)
                kernel32.CloseHandle(event)
            return
        self.event = kernel32.CreateEventW(None, False, False, EVENT_NAME)

    def poll_show(self) -> bool:
        if not self.event:
            return False
        return self.kernel32.WaitForSingleObject(self.event, 0) == 0


class App:
    def __init__(
        self,
        root: tk.Tk,
        instance: SingleInstance | None = None,
        background: bool = False,
    ) -> None:
        self.root = root
        self.instance = instance
        self.mode = "home"
        self.step = -1
        self.done_steps = 0
        self.paused = False
        self.remaining = 0.0
        self.deadline = 0.0
        self.step_seconds = 1
        self.picture_kind = "ready"
        self.picture_elapsed = 0.0
        self._picture_mark = time.monotonic()
        self._count_cache: tuple[int, int] | None = None
        self.interval_buttons: dict[int, tk.Button] = {}
        self._load_settings()
        self._build()
        self._refresh_home()
        self.root.after(200, self._tick)
        self.root.after(40, self._animate)
        if background:
            self.root.after(100, self.root.iconify)

    def _load_settings(self) -> None:
        raw = load_json(SETTINGS_PATH, {})
        if not isinstance(raw, dict):
            raw = {}
        interval = raw.get("interval_min", DEFAULTS["interval_min"])
        self.interval = interval if interval in INTERVALS else DEFAULTS["interval_min"]
        self.day_start = self._valid_hhmm(raw.get("day_start"), DEFAULTS["day_start"])
        self.day_end = self._valid_hhmm(raw.get("day_end"), DEFAULTS["day_end"])
        if _hhmm_minutes(self.day_end) <= _hhmm_minutes(self.day_start):
            self.day_start = DEFAULTS["day_start"]
            self.day_end = DEFAULTS["day_end"]
        self.sound = bool(raw.get("sound", True))
        saved = self._parse_stamp(raw.get("next_at"))
        self.next_at = initial_next(
            saved, datetime.now(), self.day_start, self.day_end, self.interval
        )
        self._save_settings()

    @staticmethod
    def _valid_hhmm(value: object, fallback: str) -> str:
        if not isinstance(value, str):
            return fallback
        try:
            hour, minute = parse_hhmm(value)
        except ValueError:
            return fallback
        return format_hhmm(hour, minute)

    @staticmethod
    def _parse_stamp(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _save_settings(self) -> None:
        atomic_write(
            SETTINGS_PATH,
            {
                "interval_min": self.interval,
                "day_start": self.day_start,
                "day_end": self.day_end,
                "sound": self.sound,
                "next_at": self.next_at.isoformat(timespec="seconds"),
            },
        )

    def _build(self) -> None:
        root = self.root
        root.title("Гимнастика для глаз")
        root.configure(bg=BG)
        root.minsize(520, 480)
        root.protocol("WM_DELETE_WINDOW", self._minimize)

        self.home = self._frame()
        self.remind = self._frame()
        self.session = self._frame()
        self.done = self._frame()
        self._build_home()
        self._build_remind()
        self._build_session()
        self._build_done()
        self._show("home")
        self._fit()

    def _fit(self) -> None:
        self.root.update_idletasks()
        frames = (self.home, self.remind, self.session, self.done)
        width = max(600, *(frame.winfo_reqwidth() for frame in frames))
        height = max(frame.winfo_reqheight() for frame in frames)
        self._place(width, height)
        self.root.minsize(min(width, self.root.winfo_screenwidth() - 40), min(height, self.root.winfo_screenheight() - 80))

    def _place(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(width, screen_w - 40)
        height = min(height, screen_h - 80)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 24)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _frame(self) -> tk.Frame:
        frame = tk.Frame(self.root, bg=BG)
        return frame

    def _show(self, name: str) -> None:
        for frame in (self.home, self.remind, self.session, self.done):
            frame.pack_forget()
        {"home": self.home, "remind": self.remind, "session": self.session, "done": self.done}[
            name
        ].pack(fill="both", expand=True)

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        primary: bool = False,
        font_size: int = 13,
    ) -> tk.Button:
        background = ACCENT if primary else BTN
        foreground = "#ffffff" if primary else TEXT
        active = ACCENT_DARK if primary else "#e4d9c8"
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active,
            activeforeground=foreground,
            relief="flat",
            bd=0,
            font=("Segoe UI", font_size),
            padx=16,
            pady=10,
            cursor="hand2",
            highlightthickness=0,
        )
        return button

    def _build_home(self) -> None:
        pad = tk.Frame(self.home, bg=BG)
        pad.pack(fill="both", expand=True, padx=28, pady=22)
        tk.Label(
            pad, text="Гимнастика для глаз", bg=BG, fg=TEXT, font=("Segoe UI", 24)
        ).pack(anchor="w")
        tk.Label(
            pad,
            text=f"{len(EXERCISES)} упражнений · около {format_session_length()}",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 13),
        ).pack(anchor="w", pady=(2, 14))

        card = tk.Frame(pad, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="x", pady=(0, 14))
        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="x", padx=16, pady=12)
        tk.Label(
            inner, text="Следующее напоминание", bg=PANEL, fg=MUTED, font=("Segoe UI", 11)
        ).pack(anchor="w")
        self.when_lbl = tk.Label(inner, bg=PANEL, fg=TEXT, font=("Segoe UI", 20))
        self.when_lbl.pack(anchor="w")
        self.remain_lbl = tk.Label(inner, bg=PANEL, fg=ACCENT, font=("Segoe UI", 13))
        self.remain_lbl.pack(anchor="w")
        self.today_lbl = tk.Label(inner, bg=PANEL, fg=MUTED, font=("Segoe UI", 12))
        self.today_lbl.pack(anchor="w", pady=(6, 0))

        self._button(pad, "Начать сейчас", self._start_session, primary=True, font_size=16).pack(
            fill="x", pady=(0, 14)
        )

        tk.Label(pad, text="Как часто", bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        row = tk.Frame(pad, bg=BG)
        row.pack(fill="x", pady=(4, 12))
        for minutes in INTERVALS:
            button = self._button(row, f"{minutes} мин", lambda m=minutes: self._select_interval(m), font_size=12)
            button.pack(side="left", padx=(0, 6))
            self.interval_buttons[minutes] = button
        self._paint_intervals()

        hours = tk.Frame(pad, bg=BG)
        hours.pack(fill="x", pady=(0, 8))
        tk.Label(hours, text="С", bg=BG, fg=TEXT, font=("Segoe UI", 13)).pack(side="left")
        self.start_var = tk.StringVar(value=self.day_start)
        self.end_var = tk.StringVar(value=self.day_end)
        self._time_entry(hours, self.start_var).pack(side="left", padx=(8, 12))
        tk.Label(hours, text="до", bg=BG, fg=TEXT, font=("Segoe UI", 13)).pack(side="left")
        self._time_entry(hours, self.end_var).pack(side="left", padx=(8, 0))
        self.hint = tk.Label(pad, text="", bg=BG, fg="#8c3a32", font=("Segoe UI", 11))
        self.hint.pack(anchor="w")

        self.sound_var = tk.BooleanVar(value=self.sound)
        self.autostart_var = tk.BooleanVar(value=autostart_enabled())
        tk.Checkbutton(
            pad,
            text="Звук при смене упражнения",
            variable=self.sound_var,
            command=self._on_sound,
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=PANEL,
            font=("Segoe UI", 12),
            highlightthickness=0,
        ).pack(anchor="w", pady=(6, 0))
        tk.Checkbutton(
            pad,
            text="Запускать вместе с Windows",
            variable=self.autostart_var,
            command=self._on_autostart,
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=PANEL,
            font=("Segoe UI", 12),
            highlightthickness=0,
        ).pack(anchor="w")

        names = " · ".join(item.title.lower() for item in EXERCISES)
        tk.Label(
            pad,
            text=names.capitalize(),
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 11),
            wraplength=530,
            justify="left",
        ).pack(anchor="w", pady=(12, 4))
        tk.Label(
            pad,
            text=(
                "Гимнастика снимает усталость от экрана. Если левый глаз падает резко, "
                "появилась пелена, вспышки или боль — к офтальмологу сразу."
            ),
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 11),
            wraplength=530,
            justify="left",
        ).pack(anchor="w")

        bottom = tk.Frame(pad, bg=BG)
        bottom.pack(side="bottom", fill="x", pady=(16, 0))
        self._button(bottom, "Свернуть", self._minimize).pack(side="left")
        self._button(bottom, "Выход", self._quit).pack(side="right")
        tk.Label(
            bottom,
            text="Крестик сворачивает",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=12)

    def _time_entry(self, parent: tk.Widget, variable: tk.StringVar) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            width=6,
            justify="center",
            font=("Segoe UI", 14),
            bg=PANEL,
            fg=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=ACCENT,
        )
        entry.bind("<FocusOut>", lambda _event: self._commit_hours())
        entry.bind("<Return>", lambda _event: self._commit_hours())
        return entry

    def _build_remind(self) -> None:
        pad = tk.Frame(self.remind, bg=BG)
        pad.pack(fill="both", expand=True, padx=28, pady=36)
        tk.Label(pad, text="Пора дать глазам паузу", bg=BG, fg=TEXT, font=("Segoe UI", 24)).pack(
            anchor="w"
        )
        tk.Label(
            pad,
            text=f"{len(EXERCISES)} упражнений, около {format_session_length()}",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 14),
        ).pack(anchor="w", pady=(6, 22))
        self._button(pad, "Начать гимнастику", self._start_session, primary=True, font_size=16).pack(
            fill="x", pady=(0, 10)
        )
        row = tk.Frame(pad, bg=BG)
        row.pack(fill="x", pady=(0, 10))
        self._button(row, "Через 10 минут", lambda: self._postpone(10)).pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._button(row, "Через 30 минут", lambda: self._postpone(30)).pack(side="left", expand=True, fill="x")
        self._button(pad, "Пропустить", self._skip_reminder).pack(fill="x")

    def _build_session(self) -> None:
        pad = tk.Frame(self.session, bg=BG)
        pad.pack(fill="both", expand=True, padx=22, pady=16)
        header = tk.Frame(pad, bg=BG)
        header.pack(fill="x")
        self.step_lbl = tk.Label(header, bg=BG, fg=ACCENT, font=("Segoe UI", 14))
        self.step_lbl.pack(side="left")
        self.time_lbl = tk.Label(header, bg=BG, fg=TEXT, font=("Segoe UI", 32))
        self.time_lbl.pack(side="right")
        self.title_lbl = tk.Label(pad, bg=BG, fg=TEXT, font=("Segoe UI", 26), anchor="w")
        self.title_lbl.pack(fill="x", pady=(2, 8))
        self.picture = tk.Canvas(
            pad,
            height=360,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=LINE,
        )
        self.picture.pack(fill="both", expand=True, pady=(0, 10))
        self.picture.bind("<Configure>", self._on_picture_resize)
        self.bar = tk.Canvas(pad, height=12, bg=LINE, highlightthickness=0)
        self.bar.pack(fill="x", pady=(0, 12))
        self.bar_fill = self.bar.create_rectangle(0, 0, 0, 12, fill=ACCENT, width=0)
        row = tk.Frame(pad, bg=BG)
        row.pack(fill="x")
        self.pause_btn = self._button(row, "Пауза", self._toggle_pause)
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._button(row, "Дальше", self._skip_step).pack(side="left", expand=True, fill="x")
        self._button(pad, "Закончить", self._stop).pack(fill="x", pady=(10, 0))

    def _build_done(self) -> None:
        pad = tk.Frame(self.done, bg=BG)
        pad.pack(fill="both", expand=True, padx=28, pady=36)
        tk.Label(pad, text="Готово", bg=BG, fg=OK, font=("Segoe UI", 28)).pack(anchor="w")
        self.done_lbl = tk.Label(pad, bg=BG, fg=TEXT, font=("Segoe UI", 16), wraplength=530, justify="left")
        self.done_lbl.pack(anchor="w", pady=(10, 6))
        self.done_next_lbl = tk.Label(pad, bg=BG, fg=MUTED, font=("Segoe UI", 14))
        self.done_next_lbl.pack(anchor="w", pady=(0, 20))
        self._button(pad, "Свернуть", self._minimize, primary=True, font_size=15).pack(fill="x")

    def _paint_intervals(self) -> None:
        for minutes, button in self.interval_buttons.items():
            selected = minutes == self.interval
            background = ACCENT if selected else BTN
            foreground = "#ffffff" if selected else TEXT
            button.configure(bg=background, fg=foreground, activebackground=ACCENT_DARK if selected else "#e4d9c8")

    def _select_interval(self, minutes: int) -> None:
        self.interval = minutes
        self._paint_intervals()
        self.hint.configure(text="")
        self._reschedule_from_now()

    def _commit_hours(self) -> None:
        try:
            start = format_hhmm(*parse_hhmm(self.start_var.get()))
            end = format_hhmm(*parse_hhmm(self.end_var.get()))
            if _hhmm_minutes(end) <= _hhmm_minutes(start):
                raise ValueError
        except ValueError:
            self.start_var.set(self.day_start)
            self.end_var.set(self.day_end)
            self.hint.configure(text="Нужно время вроде 09:00 и 19:00, конец позже начала")
            return
        changed = start != self.day_start or end != self.day_end
        self.day_start = start
        self.day_end = end
        self.start_var.set(start)
        self.end_var.set(end)
        self.hint.configure(text="")
        if changed:
            self._reschedule_from_now()

    def _on_sound(self) -> None:
        self.sound = bool(self.sound_var.get())
        self._save_settings()

    def _on_autostart(self) -> None:
        try:
            set_autostart(bool(self.autostart_var.get()))
        except OSError as error:
            log_error(error)
            self.autostart_var.set(autostart_enabled())
            messagebox.showerror(
                "Гимнастика для глаз",
                "Не получилось изменить автозагрузку. Запускайте программу ярлыком вручную.",
            )

    def _reschedule_from_now(self) -> None:
        self.next_at = compute_next(datetime.now(), self.day_start, self.day_end, self.interval)
        self._save_settings()
        self._refresh_home()

    def _refresh_home(self) -> None:
        now = datetime.now()
        self.when_lbl.configure(text=format_when(self.next_at, now))
        self.remain_lbl.configure(text=format_remain(self.next_at - now))
        today, week = self._counts()
        if today == 0 and week == 0:
            summary = "Сегодня ещё не делали"
        elif today == 0:
            summary = (
                f"Сегодня ещё не делали · на этой неделе {week} "
                f"{plural(week, 'раз', 'раза', 'раз')}"
            )
        else:
            summary = (
                f"Сегодня {today} {plural(today, 'раз', 'раза', 'раз')} · "
                f"на этой неделе {week} {plural(week, 'раз', 'раза', 'раз')}"
            )
        self.today_lbl.configure(text=summary)

    def _counts(self) -> tuple[int, int]:
        if self._count_cache is not None:
            return self._count_cache
        self._count_cache = self._read_counts()
        return self._count_cache

    def _read_counts(self) -> tuple[int, int]:
        journal = load_json(JOURNAL_PATH, [])
        if not isinstance(journal, list):
            return 0, 0
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        done_today = 0
        done_week = 0
        for item in journal:
            if not isinstance(item, dict) or item.get("status") != "done":
                continue
            stamp = self._parse_stamp(item.get("at"))
            if stamp is None:
                continue
            if stamp.date() == today:
                done_today += 1
            if stamp.date() >= week_start:
                done_week += 1
        return done_today, done_week

    def _log(self, status: str, steps: int) -> None:
        journal = load_json(JOURNAL_PATH, [])
        if not isinstance(journal, list):
            journal = []
        journal.append(
            {
                "at": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "steps": steps,
                "total": len(EXERCISES),
            }
        )
        del journal[:-400]
        self._count_cache = None
        try:
            atomic_write(JOURNAL_PATH, journal)
        except OSError as error:
            log_error(error)

    def _chime(self, kind: str) -> None:
        if not self.sound:
            return
        try:
            if kind == "remind":
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif kind == "step":
                winsound.Beep(660, 80)
            elif kind == "done":
                winsound.Beep(523, 110)
                winsound.Beep(784, 150)
        except RuntimeError:
            pass

    def _tick(self) -> None:
        if not self.root.winfo_exists():
            return
        try:
            if self.instance and self.instance.poll_show():
                self._bring_up(steal=True)
                if self.mode not in {"session", "remind"}:
                    self.mode = "home"
                    self._show("home")
            if self.mode == "session":
                self._tick_session()
            elif self.mode != "remind" and datetime.now() >= self.next_at:
                self._show_reminder()
            elif self.mode == "home":
                self._refresh_home()
        except Exception as error:
            log_error(error)
        self.root.after(200, self._tick)

    def _show_reminder(self) -> None:
        self.mode = "remind"
        self._show("remind")
        self._chime("remind")
        self._bring_up(steal=True)

    def _bring_up(self, steal: bool) -> None:
        self.root.deiconify()
        self.root.lift()
        if steal:
            self.root.attributes("-topmost", True)
            self.root.after(800, lambda: self.root.attributes("-topmost", False))
            try:
                self.root.focus_force()
            except tk.TclError:
                pass

    def _start_session(self) -> None:
        self.mode = "session"
        self.step = -1
        self.done_steps = 0
        self._show("session")
        self.picture_kind = "ready"
        self.step_lbl.configure(text="")
        self.title_lbl.configure(text="Прямо")
        self._arm(INTRO_SECONDS)
        self._bring_up(steal=False)

    def _arm(self, seconds: int) -> None:
        self.paused = False
        self.step_seconds = max(1, seconds)
        self.deadline = time.monotonic() + seconds
        self.pause_btn.configure(text="Пауза")
        self.time_lbl.configure(text=format_clock(seconds))
        self.picture_elapsed = 0.0
        self._picture_mark = time.monotonic()
        self._draw_bar(0)
        self._draw_picture()

    def _tick_session(self) -> None:
        if self.paused:
            return
        left = self.deadline - time.monotonic()
        if left <= 0:
            self.time_lbl.configure(text="0:00")
            self._draw_bar(1)
            self._on_step_elapsed()
            return
        self.time_lbl.configure(text=format_clock(left))
        self._draw_bar(1 - left / self.step_seconds)

    def _on_step_elapsed(self) -> None:
        if self.mode != "session":
            return
        if self.step < 0:
            self.step = 0
            self._chime("step")
            self._show_exercise()
            return
        self.done_steps = self.step + 1
        if self.step + 1 >= len(EXERCISES):
            self._finish()
            return
        self.step += 1
        self._chime("step")
        self._show_exercise()

    def _show_exercise(self) -> None:
        exercise = EXERCISES[self.step]
        self.picture_kind = exercise.kind
        self.step_lbl.configure(text=f"{self.step + 1} из {len(EXERCISES)}")
        self.title_lbl.configure(text=exercise.title)
        self._arm(exercise.seconds)

    def _toggle_pause(self) -> None:
        if self.mode != "session":
            return
        if self.paused:
            self.deadline = time.monotonic() + self.remaining
            self._picture_mark = time.monotonic()
            self.paused = False
            self.pause_btn.configure(text="Пауза")
            return
        self.remaining = max(0.2, self.deadline - time.monotonic())
        self.picture_elapsed = self._picture_elapsed_now()
        self._picture_mark = time.monotonic()
        self.paused = True
        self.pause_btn.configure(text="Продолжить")

    def _skip_step(self) -> None:
        if self.mode != "session":
            return
        self.paused = False
        self._on_step_elapsed()

    def _stop(self) -> None:
        if self.done_steps > 0:
            self._log("stopped", self.done_steps)
        self._schedule_after_break()
        self.mode = "home"
        self._show("home")
        self._refresh_home()

    def _finish(self) -> None:
        if self.mode != "session":
            return
        self._chime("done")
        self._log("done", len(EXERCISES))
        self._schedule_after_break()
        self.mode = "done"
        self.done_lbl.configure(text=f"Все {len(EXERCISES)} упражнений.")
        self.done_next_lbl.configure(text=f"Дальше {format_when(self.next_at)}")
        self._show("done")
        self._bring_up(steal=False)

    def _schedule_after_break(self) -> None:
        self.next_at = compute_next(datetime.now(), self.day_start, self.day_end, self.interval)
        self._save_settings()

    def _postpone(self, minutes: int) -> None:
        target = datetime.now() + timedelta(minutes=minutes)
        self.next_at = clamp_to_window(target, self.day_start, self.day_end)
        self._save_settings()
        self.mode = "home"
        self._show("home")
        self._refresh_home()
        self._minimize()

    def _skip_reminder(self) -> None:
        self._schedule_after_break()
        self.mode = "home"
        self._show("home")
        self._refresh_home()
        self._minimize()

    def _picture_elapsed_now(self) -> float:
        if self.paused:
            return self.picture_elapsed
        return self.picture_elapsed + max(0.0, time.monotonic() - self._picture_mark)

    def _animate(self) -> None:
        try:
            if self.mode == "session" and not self.paused:
                self._draw_picture()
        except Exception as error:
            log_error(error)
        if self.root.winfo_exists():
            self.root.after(40, self._animate)

    def _on_picture_resize(self, _event: tk.Event) -> None:
        if self.mode == "session":
            self._draw_picture()

    def _draw_picture(self) -> None:
        if self.mode != "session":
            return
        width = self.picture.winfo_width()
        height = self.picture.winfo_height()
        if width < 80 or height < 80:
            return
        draw_picture(
            self.picture,
            self.picture_kind,
            self._picture_elapsed_now(),
            float(self.step_seconds),
            width,
            height,
        )

    def _draw_bar(self, ratio: float) -> None:
        self.bar.update_idletasks()
        width = max(1, self.bar.winfo_width())
        self.bar.coords(self.bar_fill, 0, 0, width * min(1, max(0, ratio)), 12)

    def _minimize(self) -> None:
        self.root.iconify()

    def _quit(self) -> None:
        self._save_settings()
        self.root.destroy()


def enable_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> None:
    enable_dpi()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EyeGym.Reminder")
    except Exception:
        pass
    instance = SingleInstance()
    if instance.already:
        sys.exit(0)
    root = tk.Tk()
    App(root, instance=instance, background="--background" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
