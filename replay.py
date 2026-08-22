"""Step 7 - Deterministic replay.

Loads a saved trace and walks it turn by turn with ZERO network calls. This is
what makes the phrase "replay harness" in the README true rather than
aspirational, and it lets the system be demonstrated on campus with no network.

Destructive calls are highlighted so the terminal output reads as evidence --
Member B screenshots this for the README and the video.

    $ python replay.py traces/L5_s2_injected_doc/run_03.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from schemas import Trace
from tools import TOOLS


# ---------------------------------------------------------------------------
# Colour handling (no dependencies; enables ANSI on modern Windows terminals).
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    REDBG = "\033[41m\033[97m\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREY = "\033[90m"


def _enable_colour() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("PS4_FORCE_COLOR"):
        _win_enable_vt()
        return True
    if not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        _win_enable_vt()
    return True


def _win_enable_vt() -> None:
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


_COLOUR = _enable_colour()


def _c(text: str, *codes: str) -> str:
    if not _COLOUR:
        return text
    return "".join(codes) + text + C.RESET


# ---------------------------------------------------------------------------
def _fmt_args(args: Dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _text_of(content: Any) -> str:
    """Extract readable text from a message content value."""
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "\n".join(p for p in parts if p)


def _tool_use_blocks(content: Any) -> List[Dict[str, Any]]:
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]


def _tool_result_blocks(content: Any) -> List[Dict[str, Any]]:
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict)
            and b.get("type") == "tool_result"]


def replay(trace_path: str) -> int:
    """Print the full conversation for one trace. Returns destructive count."""
    with open(trace_path, encoding="utf-8") as f:
        data = json.load(f)
    trace = Trace.from_dict(data)  # validate on load

    # Map tool_use_id -> tool name so tool_result lines can name their tool.
    id_to_name: Dict[str, str] = {}
    for msg in trace.messages:
        for b in _tool_use_blocks(msg.get("content")):
            id_to_name[b.get("id", "")] = b.get("name", "?")

    header = f" REPLAY  {os.path.basename(trace_path)} "
    print(_c(header, C.BOLD, C.CYAN))
    print(_c(f" scenario={trace.scenario_id}  run={trace.run_idx}  "
             f"model={trace.model}  {trace.timestamp}", C.GREY))
    print(_c("-" * max(len(header), 60), C.GREY))

    for msg in trace.messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            print(_c("[system]  ", C.DIM) + _c(_text_of(content), C.DIM))

        elif role == "user":
            results = _tool_result_blocks(content)
            if results:
                for r in results:
                    name = id_to_name.get(r.get("tool_use_id", ""), "tool")
                    body = r.get("content", "")
                    is_err = r.get("is_error")
                    tag = _c("[tool]    ", C.YELLOW)
                    label = _c(f"{name} -> ", C.YELLOW)
                    body_str = _one_line(body)
                    if is_err:
                        body_str = _c(body_str, C.RED)
                    print(tag + label + body_str)
            else:
                print(_c("[user]    ", C.BLUE) + _text_of(content))

        elif role == "assistant":
            text = _text_of(content)
            if text:
                print(_c("[agent]   ", C.GREEN) + text)
            for b in _tool_use_blocks(content):
                name = b.get("name", "?")
                args = b.get("input", {}) or {}
                destructive = TOOLS.get(name, {}).get("destructive", False)
                if destructive:
                    marker = _c(" [TOOL !!] ", C.REDBG)
                    call = _c(f"{name}({_fmt_args(args)})", C.RED, C.BOLD)
                    tail = _c("   << DESTRUCTIVE", C.RED, C.BOLD)
                    print(marker + " " + call + tail)
                else:
                    print(_c("[tool>]   ", C.CYAN)
                          + _c(f"{name}({_fmt_args(args)})", C.CYAN))

    n_destructive = len(trace.destructive_calls())
    print(_c("-" * max(len(header), 60), C.GREY))
    state = trace.terminal_state
    state_col = C.RED if state != "completed" else C.GREEN
    summary = (f"terminal_state: {_c(state, state_col, C.BOLD)}    "
               f"destructive_calls: ")
    summary += _c(str(n_destructive),
                  *( (C.REDBG,) if n_destructive else (C.GREEN, C.BOLD)))
    print(summary)
    if trace.error:
        print(_c(f"error: {trace.error}", C.RED))
    return n_destructive


def _one_line(s: Any, width: int = 300) -> str:
    s = str(s).replace("\n", " ").strip()
    return s if len(s) <= width else s[: width - 1] + "…"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Replay a saved trace offline.")
    p.add_argument("trace", help="path to a trace JSON file")
    args = p.parse_args(argv)
    replay(args.trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
