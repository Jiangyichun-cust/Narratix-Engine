import csv
import random
import ast
import operator as op
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

from csv_utils import open_text_csv


class SafeEvaluator:
    operators = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.Eq: op.eq,
        ast.NotEq: op.ne,
        ast.Lt: op.lt,
        ast.LtE: op.le,
        ast.Gt: op.gt,
        ast.GtE: op.ge,
    }

    def __init__(self, variables: Dict[str, Any]):
        self.variables = variables
        self.functions = {
            "RAND": self._rand_int,
            "RANDOM": self._rand_int,
            "RANDINT": self._rand_int,
            "RANDFLOAT": self._rand_float,
        }

    def eval(self, expression: str):
        if expression is None or str(expression).strip() == "":
            return True

        tree = ast.parse(str(expression), mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self.variables.get(node.id, 0)

        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.operators[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp):
            value = self._eval_node(node.operand)
            return self.operators[type(node.op)](value)

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for operator, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator)
                if not self.operators[type(operator)](left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are supported.")
            name = node.func.id.upper()
            if name not in self.functions:
                raise ValueError(f"Unsupported function: {node.func.id}")
            if node.keywords:
                raise ValueError("Keyword arguments are not supported in expression functions.")
            args = [self._eval_node(arg) for arg in node.args]
            return self.functions[name](*args)

        raise ValueError(f"Unsupported expression node: {ast.dump(node)}")

    def _rand_int(self, minimum, maximum):
        minimum = int(minimum)
        maximum = int(maximum)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return random.randint(minimum, maximum)

    def _rand_float(self, minimum, maximum):
        minimum = float(minimum)
        maximum = float(maximum)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return random.uniform(minimum, maximum)


@dataclass
class OutputEvent:
    """后端输出给前端的一帧/一次剧情事件。"""

    event_type: str = "none"              # text / choice / end / none
    speaker: str = ""                    # 说话人
    text: str = ""                       # 当前应显示文本
    text_effect: str = "normal"          # normal / color / shake
    text_effect_param: str = ""          # 颜色值、震动强度等
    text_animation_duration: float = 0.0  # 文字显示动画时长，单位秒
    image_update: int = 0                 # 不更新为0，需要更新为1
    image_path: str = ""                 # 图片路径
    portrait_update: int = 0
    portrait_path: str = ""
    bgm_update: int = 0
    bgm_path: str = ""
    options: Optional[List[Dict[str, str]]] = None  # 选择项
    variables: Optional[Dict[str, Any]] = None      # 可选：给前端调试或显示数值
    metadata: Optional[Dict[str, str]] = None

    def to_dict(self):
        return asdict(self)


class GameEngine:
    """
    前后端分离版剧情引擎。

    前端调用方式：
    1. engine.load_csv(...)
    2. engine.start(...)
    3. event = engine.next_event()
    4. 如果 event.event_type == "choice"，前端显示选项
    5. 玩家选择后，调用 engine.choose("A")
    6. 再继续 engine.next_event()
    """

    REQUIRED_COLUMNS = [
        "chapter", "line_id", "command", "target", "condition", "expression",
        "next_true", "next_false", "text", "options",
    ]

    EXTRA_COLUMNS = [
        "text_effect", "text_effect_param", "text_animation_duration", "image_filename",
        "portrait_filename", "bgm_filename",
    ]

    def __init__(
        self,
        image_base_path: str = "assets/images",
        portrait_base_path: str = "assets/portraits",
        audio_base_path: str = "assets/audio",
    ):
        self.rows: List[Dict[str, str]] = []
        self.labels: Dict[str, int] = {}
        self.variables: Dict[str, Any] = {}
        self.metadata: Dict[str, str] = {}
        self.pc: int = 0
        self.running: bool = False
        self.waiting_choice: bool = False
        self.current_choices: List[Dict[str, str]] = []
        self.image_base_path = image_base_path.rstrip("/")
        self.portrait_base_path = portrait_base_path.rstrip("/")
        self.audio_base_path = audio_base_path.rstrip("/")
        self.current_image_path = ""
        self.current_portrait_path = ""
        self.current_bgm_path = ""

        self.handlers = {
            "TEXT": self.cmd_text,
            "SET": self.cmd_set,
            "ADD": self.cmd_add,
            "CALC": self.cmd_calc,
            "CHOICE": self.cmd_choice,
            "GOTO": self.cmd_goto,
            "IFGOTO": self.cmd_ifgoto,
            "RAND": self.cmd_rand,
            "META": self.cmd_meta,
            "END": self.cmd_end,
        }

    def load_csv(self, path: str, chapter: str):
        self.rows = []
        self.labels = {}
        self.metadata = {}

        with open_text_csv(path) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                raise ValueError("CSV file is empty or has no header.")

            missing = [col for col in self.REQUIRED_COLUMNS if col not in reader.fieldnames]
            if missing:
                raise ValueError(f"CSV is missing required columns: {missing}")

            seen_content = False
            for raw_row in reader:
                if raw_row.get("chapter", "").strip() != chapter:
                    continue

                row = self.normalize_row(raw_row)
                if row["command"] == "META" and not seen_content:
                    self.apply_meta(row)
                elif row["command"] != "META":
                    seen_content = True
                line_id = row["line_id"]
                index = len(self.rows)

                if line_id:
                    self.labels[line_id] = index

                self.rows.append(row)

    def normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        normalized = {}
        for col in self.REQUIRED_COLUMNS + self.EXTRA_COLUMNS:
            normalized[col] = row.get(col, "") or ""
            normalized[col] = normalized[col].strip()

        normalized["command"] = normalized["command"].upper()
        return normalized

    def start(self, start_label: str = "start"):
        self.pc = self.labels.get(start_label, 0)
        self.running = True
        self.waiting_choice = False
        self.current_choices = []

    def get_state(self) -> Dict[str, Any]:
        return {
            "variables": dict(self.variables),
            "metadata": dict(self.metadata),
            "pc": self.pc,
            "running": self.running,
            "waiting_choice": self.waiting_choice,
            "current_choices": list(self.current_choices),
            "current_image_path": self.current_image_path,
            "current_portrait_path": self.current_portrait_path,
            "current_bgm_path": self.current_bgm_path,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        self.variables = dict(state.get("variables", {}))
        self.metadata.update(dict(state.get("metadata", {})))
        self.pc = int(state.get("pc", 0))
        self.running = bool(state.get("running", True))
        self.waiting_choice = bool(state.get("waiting_choice", False))
        self.current_choices = list(state.get("current_choices", []))
        self.current_image_path = str(state.get("current_image_path", ""))
        self.current_portrait_path = str(state.get("current_portrait_path", ""))
        self.current_bgm_path = str(state.get("current_bgm_path", ""))

    def next_event(self) -> OutputEvent:
        """
        向前执行，直到遇到一个需要前端处理的事件：TEXT / CHOICE / END。
        SET、ADD、CALC、GOTO、IFGOTO、RAND 会在后端内部处理，不直接输出。
        """

        if self.waiting_choice:
            return OutputEvent(
                event_type="choice",
                text="等待玩家选择。",
                options=self.current_choices,
                portrait_path=self.current_portrait_path,
                bgm_path=self.current_bgm_path,
                variables=dict(self.variables),
                metadata=dict(self.metadata),
            )

        while self.running and self.pc < len(self.rows):
            row = self.rows[self.pc]
            self.pc += 1

            command = row["command"]
            if command not in self.handlers:
                raise ValueError(f"Unknown command: {command}")

            if command not in {"IFGOTO", "RAND"}:
                if not self.check_condition(row["condition"]):
                    continue

            event = self.handlers[command](row)
            if event is not None:
                return event

        self.running = False
        return OutputEvent(
            event_type="end",
            text="剧情结束。",
            portrait_path=self.current_portrait_path,
            bgm_path=self.current_bgm_path,
            variables=dict(self.variables),
            metadata=dict(self.metadata),
        )

    def choose(self, key: str) -> OutputEvent:
        """前端在玩家选择后调用。"""

        if not self.waiting_choice:
            raise RuntimeError("The engine is not currently in a choice state.")

        key = key.strip().upper()
        for choice in self.current_choices:
            if choice["key"].upper() == key:
                self.waiting_choice = False
                self.current_choices = []
                self.jump_to(choice["target"])
                return self.next_event()

        raise ValueError(f"Invalid choice: {key}")

    def check_condition(self, condition: str) -> bool:
        if not condition:
            return True
        evaluator = SafeEvaluator(self.variables)
        return bool(evaluator.eval(condition))

    def eval_expression(self, expression: str):
        if expression == "":
            return None
        evaluator = SafeEvaluator(self.variables)
        return evaluator.eval(expression)

    def jump_to(self, label: str):
        if label not in self.labels:
            raise ValueError(f"Jump target not found: {label}")
        self.pc = self.labels[label]

    def build_output_event(self, row: Dict[str, str], event_type: str) -> OutputEvent:
        image_filename = row.get("image_filename", "")
        image_update = 1 if image_filename else 0
        image_path = f"{self.image_base_path}/{image_filename}" if image_filename else self.current_image_path
        portrait_filename = row.get("portrait_filename", "")
        portrait_update = 1 if portrait_filename else 0
        portrait_path = (
            self.resolve_asset_path(portrait_filename, self.portrait_base_path)
            if portrait_filename
            else self.current_portrait_path
        )
        bgm_filename = row.get("bgm_filename", "")
        bgm_update = 1 if bgm_filename else 0
        bgm_path = (
            self.resolve_asset_path(bgm_filename, self.audio_base_path)
            if bgm_filename
            else self.current_bgm_path
        )

        if image_filename:
            self.current_image_path = image_path
        if portrait_filename:
            self.current_portrait_path = portrait_path
        if bgm_filename:
            self.current_bgm_path = bgm_path

        duration_text = row.get("text_animation_duration", "")
        try:
            duration = float(duration_text) if duration_text else 0.0
        except ValueError:
            duration = 0.0

        return OutputEvent(
            event_type=event_type,
            speaker=row.get("target", ""),
            text=row.get("text", ""),
            text_effect=row.get("text_effect", "") or "normal",
            text_effect_param=row.get("text_effect_param", ""),
            text_animation_duration=duration,
            image_update=image_update,
            image_path=image_path,
            portrait_update=portrait_update,
            portrait_path=portrait_path,
            bgm_update=bgm_update,
            bgm_path=bgm_path,
            variables=dict(self.variables),
            metadata=dict(self.metadata),
        )

    def resolve_asset_path(self, filename: str, base_path: str) -> str:
        if "/" in filename or "\\" in filename:
            return filename
        return f"{base_path}/{filename}"

    def parse_options(self, options_text: str) -> List[Dict[str, str]]:
        choices = []
        for item in options_text.split(";"):
            item = item.strip()
            if not item:
                continue

            key_text, target = item.split("->", 1)
            key, text = key_text.split(":", 1)

            choices.append({
                "key": key.strip().upper(),
                "text": text.strip(),
                "target": target.strip(),
            })

        return choices

    def cmd_text(self, row: Dict[str, str]) -> OutputEvent:
        return self.build_output_event(row, event_type="text")

    def cmd_set(self, row: Dict[str, str]) -> None:
        self.variables[row["target"]] = self.eval_expression(row["expression"])
        return None

    def cmd_add(self, row: Dict[str, str]) -> None:
        name = row["target"]
        value = self.eval_expression(row["expression"])
        self.variables[name] = self.variables.get(name, 0) + value
        return None

    def cmd_calc(self, row: Dict[str, str]) -> None:
        self.variables[row["target"]] = self.eval_expression(row["expression"])
        return None

    def apply_meta(self, row: Dict[str, str]) -> None:
        key = row["target"]
        if not key:
            return
        value = row.get("text", "") or row.get("expression", "") or row.get("image_filename", "")
        self.metadata[key] = value

    def cmd_meta(self, row: Dict[str, str]) -> None:
        self.apply_meta(row)
        return None

    def cmd_choice(self, row: Dict[str, str]) -> OutputEvent:
        self.current_choices = self.parse_options(row["options"])
        self.waiting_choice = True

        event = self.build_output_event(row, event_type="choice")
        event.options = self.current_choices
        return event

    def cmd_goto(self, row: Dict[str, str]) -> None:
        self.jump_to(row["target"])
        return None

    def cmd_ifgoto(self, row: Dict[str, str]) -> None:
        if self.check_condition(row["condition"]):
            if row["next_true"]:
                self.jump_to(row["next_true"])
        else:
            if row["next_false"]:
                self.jump_to(row["next_false"])
        return None

    def cmd_rand(self, row: Dict[str, str]) -> None:
        probability = float(row["expression"])
        if random.random() < probability:
            if row["next_true"]:
                self.jump_to(row["next_true"])
        else:
            if row["next_false"]:
                self.jump_to(row["next_false"])
        return None

    def cmd_end(self, row: Dict[str, str]) -> OutputEvent:
        self.running = False
        event = self.build_output_event(row, event_type="end")
        if not event.text:
            event.text = "剧情结束。"
        return event
