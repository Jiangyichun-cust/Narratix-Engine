from __future__ import annotations
import sys
import csv
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pygame

from csv_utils import open_text_csv
from gameengine import GameEngine, OutputEvent

def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE_DIR = app_dir()

STORY_FILE = BASE_DIR / "story.csv"
SAVE_DIR = BASE_DIR / "saves"
SAVE_SLOT_COUNT = 3
ASSETS_DIR = BASE_DIR / "assets"

WINDOW_SIZE = (1366, 768)
MIN_WINDOW_SIZE = (1100, 620)
CHAPTER = "chapter_1"
TITLE = "CSV Game Engine"

COLORS = {
    "paper": (223, 211, 184),
    "ink": (238, 232, 214),
    "muted": (174, 165, 143),
    "gold": (208, 166, 82),
    "red": (135, 48, 44),
    "green": (70, 130, 96),
    "bg": (12, 14, 15),
    "panel": (23, 25, 25),
    "panel_dark": (15, 17, 18),
    "line": (93, 77, 48),
    "button": (38, 42, 43),
    "button_hover": (56, 61, 62),
}

VARIABLE_COMMANDS = {"SET", "ADD", "CALC"}

@dataclass
class Button:
    rect: pygame.Rect
    label: str
    key: str = ""


@dataclass
class StoryEntry:
    speaker: str
    text: str
    color: tuple[int, int, int]
    event_type: str


class PygameStoryGame:
    def __init__(
        self,
        story_path: str = STORY_FILE,
        chapter: str = CHAPTER,
        start_label: str = "start",
    ) -> None:
        pygame.init()
        self.audio_enabled = True
        try:
            pygame.mixer.init()
        except pygame.error:
            self.audio_enabled = False
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.story_path = Path(story_path)
        self.chapter = chapter
        self.start_label = start_label
        self.assets_dir = BASE_DIR / "assets" / "images"
        self.portrait_dir = BASE_DIR / "assets" / "portraits"
        self.audio_dir = BASE_DIR / "assets" / "audio"
        self.ui_meta = self._load_script_metadata()
        self.profile_portrait_path = self._resolve_portrait_path(self.ui_meta.get("profile_portrait", ""))
        pygame.display.set_caption(self.ui_meta.get("ui_title", TITLE))

        self.font_title = self._font(34, bold=True)
        self.font_ui = self._font(18)
        self.font_ui_bold = self._font(19, bold=True)
        self.font_body = self._font(24)
        self.font_body_bold = self._font(25, bold=True)
        self.font_small = self._font(16)
        self.font_tiny = self._font(14)

        self.engine = GameEngine()
        self.stat_names = self._load_stat_names()
        self.current_event: OutputEvent | None = None
        self.pending_event: OutputEvent | None = None
        self.current_cg = ""
        self.current_bgm = ""
        self.cg_cache: dict[str, pygame.Surface] = {}
        self.portrait_cache: dict[str, pygame.Surface] = {}
        self.choice_buttons: list[Button] = []
        self.action_buttons: list[Button] = []
        self.dialog_buttons: list[Button] = []
        self.slot_dialog_mode: str | None = None
        self.story_entries: list[StoryEntry] = []
        self.text_reveal = 0.0
        self.history_scroll = 0
        self.max_history_scroll = 0
        self.auto_scroll = True
        self.status_message = ""
        self.status_message_timer = 0.0
        self.active_save_slot = 1
        self.running = True
        self.ended = False

        self._new_game()

    def _font(self, size: int, bold: bool = False) -> pygame.font.Font:
        names = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
        return pygame.font.SysFont(names, size, bold=bold) or pygame.font.Font(None, size)

    def _new_game(self) -> None:
        self.engine = GameEngine()
        self.engine.load_csv(str(self.story_path), self.chapter)
        pygame.display.set_caption(self._meta("ui_title", TITLE))
        self.engine.start(self.start_label)
        self.current_event = None
        self.pending_event = None
        self.current_cg = ""
        self.current_bgm = ""
        self.choice_buttons.clear()
        self.action_buttons.clear()
        self.dialog_buttons.clear()
        self.slot_dialog_mode = None
        self.story_entries.clear()
        self.text_reveal = 0.0
        self.history_scroll = 0
        self.max_history_scroll = 0
        self.auto_scroll = True
        self.status_message = ""
        self.status_message_timer = 0.0
        self.ended = False
        self._play_bgm(self._meta("initial_bgm", ""))
        self._advance()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                size = (max(event.w, MIN_WINDOW_SIZE[0]), max(event.h, MIN_WINDOW_SIZE[1]))
                self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key, event.unicode)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_scroll(event.y)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_key(self, key: int, text: str) -> None:
        if key == pygame.K_ESCAPE:
            if self.slot_dialog_mode:
                self._close_slot_dialog()
                return
            self.running = False
            return
        if key == pygame.K_r and self.ended:
            self._new_game()
            return
        if key == pygame.K_F5:
            self._save_game()
            return
        if key == pygame.K_F9:
            self._load_game()
            return
        if key in {pygame.K_PAGEUP, pygame.K_UP}:
            self._handle_scroll(3)
            return
        if key in {pygame.K_PAGEDOWN, pygame.K_DOWN}:
            self._handle_scroll(-3)
            return
        if self.current_event and self.current_event.event_type == "choice":
            choice = text.strip().upper()
            if choice:
                self._choose(choice)
            return
        if key in {pygame.K_SPACE, pygame.K_RETURN}:
            self._advance_or_reveal()

    def _handle_scroll(self, amount: int) -> None:
        if self.max_history_scroll <= 0:
            return
        self.history_scroll = max(0, min(self.max_history_scroll, self.history_scroll + amount * 56))
        self.auto_scroll = self.history_scroll == 0

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.slot_dialog_mode:
            for button in self.dialog_buttons:
                if button.rect.collidepoint(pos):
                    if button.key == "DIALOG_CLOSE":
                        self._close_slot_dialog()
                    elif button.key.startswith("DIALOG_SAVE_"):
                        self._save_game(self._button_slot(button.key))
                        self._close_slot_dialog()
                    elif button.key.startswith("DIALOG_LOAD_"):
                        self._load_game(self._button_slot(button.key))
                        self._close_slot_dialog()
                    return
            self._close_slot_dialog()
            return

        for button in self.choice_buttons:
            if button.rect.collidepoint(pos):
                self._choose(button.key)
                return
        for button in self.action_buttons:
            if button.rect.collidepoint(pos):
                if button.key == "QUIT":
                    self.running = False
                elif button.key == "SAVE":
                    self._open_slot_dialog("save")
                elif button.key == "LOAD":
                    self._open_slot_dialog("load")
                elif button.key.startswith("SAVE_"):
                    self._save_game(self._button_slot(button.key))
                elif button.key.startswith("LOAD_"):
                    self._load_game(self._button_slot(button.key))
                return
        if self.current_event and self.current_event.event_type == "choice":
            if self.text_reveal < len(self._event_text(self.current_event)):
                self._advance_or_reveal()
            return
        if self.current_event and not self.ended:
            self._advance_or_reveal()

    def _update(self, dt: float) -> None:
        if not self.current_event:
            return
        text = self._event_text(self.current_event)
        duration = max(self.current_event.text_animation_duration, 0.45)
        speed = max(len(text) / duration, 32)
        self.text_reveal = min(len(text), self.text_reveal + speed * dt)
        self.status_message_timer = max(0.0, self.status_message_timer - dt)

    def _advance_or_reveal(self) -> None:
        if not self.current_event:
            self._advance()
            return
        text = self._event_text(self.current_event)
        if self.text_reveal < len(text):
            self.text_reveal = float(len(text))
            return
        if self.current_event.event_type != "choice":
            self._advance()

    def _advance(self) -> None:
        self.current_event = self.pending_event or self.engine.next_event()
        self.pending_event = None
        self.text_reveal = 0.0
        self.choice_buttons.clear()
        self.action_buttons.clear()

        if self.current_event.image_update and self.current_event.image_path:
            self.current_cg = self.current_event.image_path
        if self.current_event.bgm_update and self.current_event.bgm_path:
            self._play_bgm(self.current_event.bgm_path)

        if self.current_event.event_type == "end":
            self.ended = True
        self._append_current_entry()

    def _append_current_entry(self) -> None:
        if not self.current_event:
            return
        text = self._event_text(self.current_event)
        if not text:
            return
        speaker = self.current_event.speaker or ("决策" if self.current_event.event_type == "choice" else "")
        self.story_entries.append(StoryEntry(speaker, text, self._effect_color(self.current_event), self.current_event.event_type))
        if self.auto_scroll:
            self.history_scroll = 0

    def _choose(self, key: str) -> None:
        if not self.current_event or self.current_event.event_type != "choice":
            return
        valid = {choice["key"].upper() for choice in self.current_event.options or []}
        if key not in valid:
            return
        self.pending_event = self.engine.choose(key)
        self._advance()

    def _open_slot_dialog(self, mode: str) -> None:
        self.slot_dialog_mode = mode if mode in {"save", "load"} else None
        self.dialog_buttons.clear()

    def _close_slot_dialog(self) -> None:
        self.slot_dialog_mode = None
        self.dialog_buttons.clear()

    def _button_slot(self, key: str) -> int:
        try:
            slot = int(key.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            return self.active_save_slot
        return max(1, min(SAVE_SLOT_COUNT, slot))

    def _save_file(self, slot: int) -> Path:
        return SAVE_DIR / f"save_slot_{slot}.json"

    def _save_game(self, slot: int | None = None) -> None:
        if not self.current_event:
            return
        slot = max(1, min(SAVE_SLOT_COUNT, slot or self.active_save_slot))
        self.active_save_slot = slot
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "slot": slot,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "story_path": str(self.story_path),
            "chapter": self.chapter,
            "start_label": self.start_label,
            "engine": self.engine.get_state(),
            "current_event": self.current_event.to_dict(),
            "pending_event": self.pending_event.to_dict() if self.pending_event else None,
            "current_cg": self.current_cg,
            "current_bgm": self.current_bgm,
            "story_entries": [asdict(entry) for entry in self.story_entries],
            "text_reveal": self.text_reveal,
            "history_scroll": self.history_scroll,
            "auto_scroll": self.auto_scroll,
            "ended": self.ended,
        }
        self._save_file(slot).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._set_status(f"已存入档位 {slot}")

    def _load_game(self, slot: int | None = None) -> None:
        slot = max(1, min(SAVE_SLOT_COUNT, slot or self.active_save_slot))
        self.active_save_slot = slot
        save_file = self._save_file(slot)
        if not save_file.exists():
            self._set_status(f"档位 {slot} 为空")
            return
        payload = json.loads(save_file.read_text(encoding="utf-8"))
        self.chapter = payload.get("chapter", self.chapter)
        self.start_label = payload.get("start_label", self.start_label)
        self.ui_meta = self._load_script_metadata()
        self.stat_names = self._load_stat_names()

        self.engine = GameEngine()
        self.engine.load_csv(str(self.story_path), self.chapter)
        self.engine.load_state(payload.get("engine", {}))

        self.current_event = OutputEvent(**payload["current_event"])
        pending = payload.get("pending_event")
        self.pending_event = OutputEvent(**pending) if pending else None
        self.current_cg = payload.get("current_cg", "")
        self.current_bgm = payload.get("current_bgm", "")
        self._play_bgm(self.current_bgm, force=True)
        self.story_entries = [
            StoryEntry(
                speaker=entry.get("speaker", ""),
                text=entry.get("text", ""),
                color=tuple(entry.get("color", COLORS["ink"])),
                event_type=entry.get("event_type", "text"),
            )
            for entry in payload.get("story_entries", [])
        ]
        self.text_reveal = float(payload.get("text_reveal", len(self._event_text(self.current_event))))
        self.history_scroll = int(payload.get("history_scroll", 0))
        self.auto_scroll = bool(payload.get("auto_scroll", True))
        self.ended = bool(payload.get("ended", False))
        self.choice_buttons.clear()
        self.action_buttons.clear()
        pygame.display.set_caption(self._meta("ui_title", TITLE))
        self._set_status(f"已读取档位 {slot}")

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.status_message_timer = 2.0

    def _play_bgm(self, bgm_path: str, force: bool = False) -> None:
        if not bgm_path:
            return
        path = self._resolve_audio_path(bgm_path)
        if not path.exists():
            self._set_status(f"找不到音乐: {path.name}")
            return
        path_text = str(path)
        if not force and path_text == self.current_bgm:
            return
        self.current_bgm = path_text
        if not self.audio_enabled:
            return
        try:
            pygame.mixer.music.load(path_text)
            pygame.mixer.music.play(-1)
        except pygame.error as exc:
            self.audio_enabled = False
            self._set_status(f"音乐播放失败: {exc}")

    def _resolve_audio_path(self, filename: str) -> Path:
        path = Path(filename)
        if path.exists():
            return path
        base_relative = BASE_DIR / path
        if base_relative.exists():
            return base_relative
        if filename:
            return self.audio_dir / filename
        return self.audio_dir

    def _draw(self) -> None:
        width, height = self.screen.get_size()
        self.screen.fill(COLORS["bg"])

        margin = 20
        gap = 18
        left_w = 278
        right_w = 386
        center_w = width - margin * 2 - gap * 2 - left_w - right_w
        left = pygame.Rect(margin, margin, left_w, height - margin * 2)
        center = pygame.Rect(left.right + gap, margin, center_w, height - margin * 2)
        right = pygame.Rect(center.right + gap, margin, right_w, height - margin * 2)

        self._draw_profile_column(left)
        self._draw_cg_column(center)
        self._draw_text_column(right)
        self._draw_slot_dialog()
        pygame.display.flip()

    def _draw_profile_column(self, rect: pygame.Rect) -> None:
        self._panel(rect)
        title = self._meta("ui_title", TITLE)
        self.screen.blit(self.font_title.render(title, True, COLORS["ink"]), (rect.x + 18, rect.y + 18))
        subtitle = self.font_ui.render(self._meta("ui_subtitle", ""), True, COLORS["gold"])
        self.screen.blit(subtitle, (rect.x + 20, rect.y + 60))

        portrait_rect = pygame.Rect(rect.x + 20, rect.y + 94, rect.width - 40, 250)
        self._draw_large_portrait(portrait_rect)

        name = self.font_body_bold.render(self._meta("profile_name", "主角"), True, COLORS["paper"])
        self.screen.blit(name, (rect.x + 20, portrait_rect.bottom + 18))
        meta = self.font_ui.render(self._meta("profile_status", ""), True, COLORS["muted"])
        self.screen.blit(meta, (rect.x + 20, portrait_rect.bottom + 44))

        variables = self.current_event.variables if self.current_event else self.engine.variables
        hidden_stats = self._hidden_stat_names()
        active_stats = [name for name in self.stat_names if name not in hidden_stats]

        y = portrait_rect.bottom + 74
        bottom_limit = rect.bottom - 18
        row_height = max(17, min(29, (bottom_limit - y) // max(len(active_stats), 1)))
        compact = row_height < 24

        old_clip = self.screen.get_clip()
        stat_clip = pygame.Rect(rect.x + 12, y - 2, rect.width - 24, bottom_limit - y + 4)
        self.screen.set_clip(stat_clip)
        for stat in active_stats:
            raw_value = variables.get(stat)
            value = int(raw_value) if raw_value is not None else None
            self._draw_stat(stat, value, pygame.Rect(rect.x + 20, y, rect.width - 40, row_height), compact)
            y += row_height
        self.screen.set_clip(old_clip)

    def _draw_large_portrait(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, COLORS["panel_dark"], rect, border_radius=4)
        pygame.draw.rect(self.screen, COLORS["line"], rect, width=1, border_radius=4)
        self.profile_portrait_path = self._resolve_portrait_path(self._meta("profile_portrait", ""))
        portrait = self._load_portrait(self.profile_portrait_path)
        if portrait:
            scaled = self._cover_scale(portrait, rect.width, rect.height)
            self._blit_clipped(scaled, scaled.get_rect(center=rect.center), rect)
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (0, 0, 0, 72), shade.get_rect())
        self.screen.blit(shade, rect)
        pygame.draw.rect(self.screen, COLORS["gold"], rect, width=2, border_radius=4)

    def _draw_stat(self, name: str, value: int | None, rect: pygame.Rect, compact: bool = False) -> None:
        label = f"{name}  {value}" if value is not None else f"{name}  --"
        color = COLORS["ink"] if value is not None else COLORS["muted"]
        font = self.font_tiny if compact else self.font_small
        self.screen.blit(font.render(label, True, color), (rect.x, rect.y))
        bar_y = rect.y + (15 if compact else 21)
        bar_h = 4 if compact else 6
        bar = pygame.Rect(rect.x, bar_y, rect.width, bar_h)
        pygame.draw.rect(self.screen, (65, 65, 61), bar, border_radius=3)
        if value is None:
            return
        fill_w = max(0, min(rect.width, round(rect.width * value / 100)))
        fill = COLORS["red"] if value < 35 else COLORS["green"] if value >= 65 else COLORS["gold"]
        pygame.draw.rect(self.screen, fill, (bar.x, bar.y, fill_w, bar.height), border_radius=3)

    def _load_stat_names(self) -> list[str]:
        names: list[str] = []
        if not self.story_path.exists():
            return names
        with open_text_csv(self.story_path) as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("chapter", "").strip() != self.chapter:
                    continue
                command = row.get("command", "").strip().upper()
                target = row.get("target", "").strip()
                if command in VARIABLE_COMMANDS and target and target not in names:
                    names.append(target)
        return names

    def _draw_cg_column(self, rect: pygame.Rect) -> None:
        self._panel(rect)
        header = pygame.Rect(rect.x, rect.y, rect.width, 54)
        pygame.draw.rect(self.screen, COLORS["panel_dark"], header)
        scene_title = self._scene_title()
        self.screen.blit(self.font_ui_bold.render(scene_title, True, COLORS["gold"]), (header.x + 18, header.y + 17))

        controls_height = 72
        image_rect = pygame.Rect(rect.x + 16, rect.y + 70, rect.width - 32, rect.height - 86 - controls_height)
        pygame.draw.rect(self.screen, (8, 9, 10), image_rect)
        cg = self._load_cg(self.current_cg)
        if cg:
            scaled = self._contain_scale(cg, image_rect.width, image_rect.height)
            self._blit_clipped(scaled, scaled.get_rect(center=image_rect.center), image_rect)
        pygame.draw.rect(self.screen, COLORS["line"], image_rect, width=2)
        self._draw_actions(rect)

    def _draw_text_column(self, rect: pygame.Rect) -> None:
        self._panel(rect)
        event = self.current_event
        if not event:
            return

        speaker = event.speaker or ("决策" if event.event_type == "choice" else "")
        self.screen.blit(self.font_body_bold.render("档案记录", True, COLORS["gold"]), (rect.x + 24, rect.y + 20))
        active = self.font_small.render(f"当前：{speaker}", True, COLORS["muted"])
        self.screen.blit(active, (rect.x + 24, rect.y + 56))
        self._draw_current_avatar(event, pygame.Rect(rect.right - 152, rect.y + 16, 128, 128))
        pygame.draw.line(self.screen, COLORS["line"], (rect.x + 24, rect.y + 160), (rect.right - 24, rect.y + 160), 1)

        history_y = rect.y + 180
        history_bottom = rect.bottom - 24
        if event.event_type == "choice" and self.text_reveal >= len(self._event_text(event)):
            history_bottom -= self._choice_block_height(rect) + 14
        history_rect = pygame.Rect(rect.x + 24, history_y, rect.width - 48, max(150, history_bottom - history_y))
        self._draw_history(history_rect)

        if event.event_type == "choice" and self.text_reveal >= len(self._event_text(event)):
            self._draw_choices(rect)

    def _draw_current_avatar(self, event: OutputEvent, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, COLORS["panel_dark"], rect, border_radius=4)
        portrait = self._load_portrait(event.portrait_path)
        if portrait:
            scaled = self._cover_scale(portrait, rect.width, rect.height)
            self._blit_clipped(scaled, scaled.get_rect(center=rect.center), rect)
        pygame.draw.rect(self.screen, COLORS["gold"], rect, width=1, border_radius=4)

    def _draw_history(self, rect: pygame.Rect) -> None:
        old_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        rows: list[tuple[str, pygame.font.Font, tuple[int, int, int], int]] = []

        for index, entry in enumerate(self.story_entries):
            rows.append((entry.speaker, self.font_ui_bold, COLORS["gold"], 28))
            text = entry.text
            if index == len(self.story_entries) - 1:
                text = text[: int(self.text_reveal)]
            for line in wrap_text(text, self.font_body, rect.width - 10):
                rows.append((line, self.font_body, entry.color, 34))
            rows.append(("", self.font_small, COLORS["muted"], 16))

        total_height = sum(row[3] for row in rows)
        self.max_history_scroll = max(0, total_height - rect.height)
        if self.auto_scroll:
            self.history_scroll = 0

        y = rect.y + rect.height - total_height + self.history_scroll
        for text, font, color, line_height in rows:
            if y + line_height >= rect.y and y <= rect.bottom:
                self.screen.blit(font.render(text, True, color), (rect.x, y))
            y += line_height
        self.screen.set_clip(old_clip)

        if self.max_history_scroll > 0:
            track = pygame.Rect(rect.right - 4, rect.y, 3, rect.height)
            pygame.draw.rect(self.screen, (63, 61, 55), track, border_radius=2)
            thumb_h = max(34, int(rect.height * rect.height / (rect.height + self.max_history_scroll)))
            travel = rect.height - thumb_h
            ratio = (self.max_history_scroll - self.history_scroll) / self.max_history_scroll
            thumb_y = rect.y + int(ratio * travel)
            pygame.draw.rect(self.screen, COLORS["gold"], (track.x, thumb_y, track.width, thumb_h), border_radius=2)

    def _draw_choices(self, rect: pygame.Rect) -> None:
        event = self.current_event
        if not event:
            return
        self.choice_buttons.clear()

        options = event.options or []
        block_h = self._choice_block_height(rect)
        action_top = rect.bottom - 24
        block_top = action_top - block_h
        option_gap = 8
        button_height = max(30, min(42, (block_h - option_gap * (len(options) - 1)) // max(len(options), 1)))
        total_height = button_height * len(options) + option_gap * max(len(options) - 1, 0)
        y = block_top + (block_h - total_height) // 2

        for option in options:
            button_rect = pygame.Rect(rect.x + 24, y, rect.width - 48, button_height)
            self.choice_buttons.append(Button(button_rect, option["text"], option["key"]))
            self._draw_button(button_rect, f"{option['key']}  {option['text']}")
            y += button_height + option_gap

    def _choice_block_height(self, rect: pygame.Rect) -> int:
        event = self.current_event
        option_count = len(event.options or []) if event else 0
        if option_count <= 0:
            return 0
        option_gap = 8
        ideal = option_count * 42 + option_gap * max(option_count - 1, 0)
        return min(max(ideal, 50), max(96, rect.height // 3))

    def _draw_actions(self, rect: pygame.Rect) -> None:
        self.action_buttons.clear()
        controls_top = rect.bottom - 54
        message_y = controls_top - 24
        button_h = 34
        gap = 8
        main_button_w = 104
        save_rect = pygame.Rect(0, controls_top, main_button_w, button_h)
        load_rect = pygame.Rect(0, controls_top, main_button_w, button_h)
        quit_rect = pygame.Rect(0, controls_top, main_button_w, button_h)
        row_buttons = [Button(save_rect, "存档", "SAVE"), Button(load_rect, "读档", "LOAD"), Button(quit_rect, "退出", "QUIT")]

        total_row_w = sum(button.rect.width for button in row_buttons) + gap * max(len(row_buttons) - 1, 0)
        x = rect.x + (rect.width - total_row_w) // 2
        for button in row_buttons:
            button.rect.x = x
            button.rect.y = controls_top
            self.action_buttons.append(button)
            self._draw_button(button.rect, button.label, compact=True)
            x += button.rect.width + gap

        if self.current_event and self.current_event.event_type == "choice":
            hint = "点击选项或按 A/B/C/D，F5/F9 使用当前档位"
        elif self.ended:
            hint = "Esc 退出，F5/F9 使用当前档位"
        else:
            hint = "点击屏幕推进，F5/F9 使用当前档位"

        message = self.status_message if self.status_message_timer > 0 else hint
        self.screen.blit(self.font_small.render(message, True, COLORS["muted"]), (rect.x + 18, message_y))

    def _draw_slot_dialog(self) -> None:
        if not self.slot_dialog_mode:
            return
        self.dialog_buttons.clear()
        width, height = self.screen.get_size()
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        self.screen.blit(shade, (0, 0))

        dialog_w = min(460, width - 80)
        dialog_h = 282
        rect = pygame.Rect((width - dialog_w) // 2, (height - dialog_h) // 2, dialog_w, dialog_h)
        pygame.draw.rect(self.screen, COLORS["panel"], rect, border_radius=4)
        pygame.draw.rect(self.screen, COLORS["gold"], rect, width=2, border_radius=4)

        title = "选择存档档位" if self.slot_dialog_mode == "save" else "选择读档档位"
        self.screen.blit(self.font_body_bold.render(title, True, COLORS["gold"]), (rect.x + 24, rect.y + 20))
        close_rect = pygame.Rect(rect.right - 56, rect.y + 18, 32, 32)
        self.dialog_buttons.append(Button(close_rect, "X", "DIALOG_CLOSE"))
        self._draw_button(close_rect, "X", compact=True)

        y = rect.y + 72
        button_h = 44
        for slot in range(1, SAVE_SLOT_COUNT + 1):
            key = f"DIALOG_{self.slot_dialog_mode.upper()}_{slot}"
            button_rect = pygame.Rect(rect.x + 28, y, rect.width - 56, button_h)
            label = f"档位 {slot}  {self._slot_summary(slot)}"
            self.dialog_buttons.append(Button(button_rect, label, key))
            self._draw_button(button_rect, label)
            y += button_h + 12

        hint = "点击空白处或 Esc 关闭"
        self.screen.blit(self.font_small.render(hint, True, COLORS["muted"]), (rect.x + 28, rect.bottom - 34))

    def _slot_summary(self, slot: int) -> str:
        save_file = self._save_file(slot)
        if not save_file.exists():
            return "空"
        try:
            payload = json.loads(save_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "无法读取"
        saved_at = str(payload.get("saved_at", "")).replace("T", " ")
        return saved_at or "已有存档"

    def _draw_button(self, rect: pygame.Rect, label: str, compact: bool = False) -> None:
        hover = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, COLORS["button_hover"] if hover else COLORS["button"], rect, border_radius=3)
        pygame.draw.rect(self.screen, COLORS["gold"], rect, width=1, border_radius=3)
        font = self.font_ui_bold if compact else self.font_ui
        lines = wrap_text(label, font, rect.width - 22)
        y = rect.centery - len(lines[:2]) * font.get_height() // 2
        for line in lines[:2]:
            self.screen.blit(font.render(line, True, COLORS["ink"]), (rect.x + 12, y))
            y += font.get_height()

    def _panel(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, COLORS["panel"], rect)
        pygame.draw.rect(self.screen, COLORS["line"], rect, width=1)

    def _load_cg(self, path_text: str) -> pygame.Surface | None:
        if not path_text:
            return None
        path = Path(path_text)
        if not path.exists():
            path = self.assets_dir / path.name
        key = str(path)
        if key in self.cg_cache:
            return self.cg_cache[key]
        if not path.exists():
            return None
        image = pygame.image.load(str(path)).convert()
        self.cg_cache[key] = image
        return image

    def _load_portrait(self, portrait_path: str | Path) -> pygame.Surface | None:
        if not portrait_path:
            return None
        path = self._resolve_portrait_path(str(portrait_path))
        key = str(path)
        if key in self.portrait_cache:
            return self.portrait_cache[key]
        if not path.exists():
            return None
        image = pygame.image.load(str(path)).convert_alpha()
        self.portrait_cache[key] = image
        return image

    def _meta(self, key: str, default: str = "") -> str:
        if hasattr(self, "engine") and self.engine.metadata.get(key):
            return self.engine.metadata[key]
        return self.ui_meta.get(key, default)

    def _hidden_stat_names(self) -> set[str]:
        raw_value = self._meta("hidden_stats", "")
        return {item.strip() for item in re.split(r"[,，;；|、\s]+", raw_value) if item.strip()}

    def _load_script_metadata(self) -> dict[str, str]:
        metadata: dict[str, str] = {}
        if not self.story_path.exists():
            return metadata
        with open_text_csv(self.story_path) as file:
            reader = csv.DictReader(file)
            seen_content = False
            for row in reader:
                if row.get("chapter", "").strip() != self.chapter:
                    continue
                command = row.get("command", "").strip().upper()
                if command != "META":
                    seen_content = True
                    continue
                if seen_content:
                    continue
                key = row.get("target", "").strip()
                value = (
                    row.get("text", "").strip()
                    or row.get("expression", "").strip()
                    or row.get("image_filename", "").strip()
                )
                if key:
                    metadata[key] = value
        return metadata

    def _resolve_portrait_path(self, filename: str) -> Path:
        if not filename:
            return self.portrait_dir / ""
        path = Path(filename)
        if path.exists():
            return path
        if filename:
            return self.portrait_dir / filename
        return self.portrait_dir / ""

    def _cover_scale(self, surface: pygame.Surface, width: int, height: int) -> pygame.Surface:
        source_w, source_h = surface.get_size()
        scale = max(width / source_w, height / source_h)
        return pygame.transform.smoothscale(surface, (math.ceil(source_w * scale), math.ceil(source_h * scale)))

    def _contain_scale(self, surface: pygame.Surface, width: int, height: int) -> pygame.Surface:
        source_w, source_h = surface.get_size()
        scale = min(width / source_w, height / source_h)
        return pygame.transform.smoothscale(surface, (math.floor(source_w * scale), math.floor(source_h * scale)))

    def _blit_clipped(self, surface: pygame.Surface, dest: pygame.Rect, clip_rect: pygame.Rect) -> None:
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)
        self.screen.blit(surface, dest)
        self.screen.set_clip(old_clip)

    def _scene_title(self) -> str:
        if not self.current_cg:
            return ""
        filename = Path(self.current_cg).stem
        return filename

    def _event_text(self, event: OutputEvent) -> str:
        if event.event_type == "choice":
            return event.text or "请选择接下来的行动。"
        if event.event_type == "end":
            return event.text or "剧情结束。"
        return event.text or ""

    def _effect_color(self, event: OutputEvent) -> tuple[int, int, int]:
        if event.text_effect == "color" and event.text_effect_param.startswith("#"):
            try:
                value = event.text_effect_param.lstrip("#")
                return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
            except ValueError:
                return COLORS["ink"]
        return COLORS["ink"]


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + char
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char.lstrip()
    if current:
        lines.append(current)
    return lines or [""]


def run_pygame_game() -> None:
    PygameStoryGame().run()


if __name__ == "__main__":
    try:
        run_pygame_game()
    except Exception:
        pygame.quit()
        raise
