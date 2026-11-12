#!/usr/bin/env python3
"""promptgen — turn a few basic inputs into a well-structured prompt.

Usage:
  ./promptgen.py                      # interactive: answers a few questions
  ./promptgen.py "summarize this report for execs" -t writing -a "busy executives"
  ./promptgen.py --help

The finished prompt is printed, copied to the clipboard (if wl-copy/xclip is
available), and saved under ./prompts/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Prompt types, labels and detection rules live in templates.js, which the web
# app, the desktop app and this script all share. Its body is strict JSON.
# ---------------------------------------------------------------------------
TEMPLATES_FILE = Path(__file__).resolve().parent / "templates.js"


def _load_templates() -> dict:
    text = TEMPLATES_FILE.read_text(encoding="utf-8")
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


TEMPLATES = _load_templates()
TYPES: dict[str, dict] = TEMPLATES["types"]
LENGTHS: dict[str, str] = TEMPLATES["lengths"]
MODELS: list[str] = TEMPLATES["models"]
POLISH_SYSTEM: str = TEMPLATES["polish_system"]


# ---------------------------------------------------------------------------
# Building the prompt
# ---------------------------------------------------------------------------
def build_prompt(o: dict) -> str:
    """Assemble the prompt text from the collected options."""
    kind = o["type"]
    task = o["task"].strip()
    o = {**o, "task": task[:1].upper() + task[1:]}
    if TYPES[kind].get("image"):
        return build_image_prompt(o)

    preset = TYPES[kind]
    role = o.get("role") or preset["role"]
    parts: list[str] = [f"You are {role}."]

    # The task, with goal and audience woven in.
    task_lines = [o["task"].strip().rstrip(".") + "."]
    if o.get("goal"):
        task_lines.append(f"The goal is: {o['goal'].strip().rstrip('.')}.")
    if o.get("audience"):
        task_lines.append(f"The audience is {o['audience'].strip().rstrip('.')}.")
    parts.append(section("task", " ".join(task_lines)))

    if o.get("context"):
        tag = preset.get("context_tag", "context")
        parts.append(section(tag, o["context"].strip()))

    guidelines = list(preset["guidelines"])
    if o.get("tone"):
        guidelines.append(preset.get("tone_line", "Use a {tone} tone.").replace("{tone}", o["tone"].strip()))
    if o.get("length"):
        guidelines.append(LENGTHS.get(o["length"], o["length"]))
    guidelines += [c.strip() for c in o.get("constraints", []) if c.strip()]
    if guidelines:
        parts.append(section("guidelines", "\n".join(f"- {g}" for g in guidelines)))

    if o.get("example"):
        parts.append(section("example", o["example"].strip()
                             + "\n\nUse this as a guide to style and structure, not content to copy."))

    parts.append(section("output_format", (o.get("format") or preset["format"]).strip()))

    if o.get("input_slot"):
        parts.append(section("input", "{{PASTE YOUR INPUT HERE}}"))

    return "\n\n".join(parts) + "\n"


def build_image_prompt(o: dict) -> str:
    bits = [o["task"].strip().rstrip(".")]
    if o.get("context"):
        bits.append(o["context"].strip().rstrip("."))
    if o.get("tone"):
        bits.append(f"{o['tone'].strip()} atmosphere")
    if o.get("format"):
        bits.append(o["format"].strip().rstrip("."))
    else:
        bits.append("highly detailed, balanced composition, natural lighting")
    text = ", ".join(bits) + "."
    neg = [c.strip() for c in o.get("constraints", []) if c.strip()]
    if neg:
        text += "\n\nAvoid: " + ", ".join(neg) + "."
    return text + "\n"


def section(tag: str, body: str) -> str:
    return f"<{tag}>\n{body}\n</{tag}>"


# ---------------------------------------------------------------------------
# Optional: have Claude polish the draft (needs `pip install anthropic` and an
# API key in ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------
DEFAULT_MODEL = MODELS[0]
KEY_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "promptgen" / "api_key"


def polish_available() -> bool:
    return importlib.util.find_spec("anthropic") is not None


def load_api_key() -> str | None:
    """ANTHROPIC_API_KEY from the environment, else the key saved by the GUI."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        return KEY_FILE.read_text().strip() or None
    except OSError:
        return None


def save_api_key(key: str) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key.strip() + "\n")
    os.chmod(KEY_FILE, 0o600)


class PolishError(Exception):
    pass


def polish(draft: str, kind: str, model: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise PolishError("the 'anthropic' package isn't installed. Run:  pip install anthropic") from None

    try:
        key = load_api_key()
        client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # If the model declines, let the API retry on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=POLISH_SYSTEM,
            messages=[{"role": "user", "content": f"Prompt type: {kind}\n\n<draft_prompt>\n{draft}</draft_prompt>"}],
        )
    except anthropic.AuthenticationError:
        raise PolishError("the API key was rejected. Check ANTHROPIC_API_KEY.") from None
    except anthropic.NotFoundError:
        raise PolishError(f"model '{model}' wasn't found.") from None
    except anthropic.RateLimitError:
        raise PolishError("rate limited by the API. Try again in a minute.") from None
    except anthropic.APIStatusError as e:
        raise PolishError(f"API error {e.status_code}: {e.message}") from None
    except anthropic.APIConnectionError:
        raise PolishError("couldn't reach the API. Check your internet connection.") from None
    except TypeError as e:  # raised when no credentials can be found
        if "auth" in str(e).lower() or "api_key" in str(e).lower():
            raise PolishError("no API key found. Set ANTHROPIC_API_KEY "
                              "(get one at https://console.anthropic.com/).") from None
        raise

    if response.stop_reason == "refusal":
        raise PolishError("Claude declined to polish this prompt.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise PolishError("Claude returned an empty response.")
    if response.stop_reason == "max_tokens":
        raise PolishError("the response was cut off before it finished.")
    return text + "\n"


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------
def ask(question: str, default: str | None = None, required: bool = False) -> str:
    hint = f" [{default}]" if default else (" (required)" if required else " (Enter to skip)")
    while True:
        try:
            ans = input(f"{question}{hint}: ").strip()
        except EOFError:
            ans = ""
        if ans:
            return ans
        if default is not None:
            return default
        if not required:
            return ""
        print("  This one is needed.")


def interactive() -> dict:
    print("promptgen — answer a few questions. Only the first is required.\n")
    o: dict = {}
    o["task"] = ask("1. What should the AI do?", required=True)
    o["type"] = ask(f"2. Type ({', '.join(TYPES)})", default=guess_type(o["task"]))
    while o["type"] not in TYPES:
        o["type"] = ask(f"   Pick one of: {', '.join(TYPES)}", default="general")

    if o["type"] == "image":
        o["context"] = ask("3. Subject details / setting")
        o["tone"] = ask("4. Mood")
        o["format"] = ask("5. Style (e.g. watercolor, 35mm photo, isometric 3D)")
        cons = ask("6. Things to avoid (comma-separated)")
    else:
        o["goal"] = ask("3. Why? What's the end goal")
        o["audience"] = ask("4. Who is it for")
        o["context"] = ask("5. Background the AI should know")
        o["tone"] = ask("6. Tone (e.g. friendly, formal, blunt)")
        o["length"] = ask("7. Length (short / medium / long)")
        o["format"] = ask("8. Output format (Enter for the type's default)")
        cons = ask("9. Rules or constraints (separate with ';')")
        o["role"] = ask("10. Role for the AI (Enter for the type's default)")
        o["input_slot"] = ask("11. Add a placeholder to paste your own input? (y/n)", default="n").lower().startswith("y")
    o["polish"] = ask("Have Claude polish the result? (y/n)", default="n").lower().startswith("y")
    o["constraints"] = [c for c in re.split(r"[;,]" if o["type"] == "image" else r";", cons) if c.strip()]
    return o


def guess_type(task: str) -> str:
    t = task.lower()
    for kind, pattern in TEMPLATES["detect"]:
        if re.search(pattern, t):
            return kind
    return "general"


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def copy_to_clipboard(text: str) -> bool:
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"], ["pbcopy"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode(), check=True, timeout=5)
                return True
            except (subprocess.SubprocessError, OSError):
                continue
    return False


def save(text: str, task: str, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", task.lower()).strip("-")[:40] or "prompt"
    path = outdir / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{slug}.txt"
    path.write_text(text)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Turn a few basic inputs into a well-structured prompt.",
        epilog="Run with no arguments for interactive mode.",
    )
    p.add_argument("task", nargs="?", help="what the AI should do")
    p.add_argument("-t", "--type", choices=list(TYPES), help="prompt type (guessed from the task if omitted)")
    p.add_argument("-g", "--goal", help="why / the end goal")
    p.add_argument("-a", "--audience", help="who the output is for")
    p.add_argument("-c", "--context", help="background the AI should know")
    p.add_argument("--tone", help="e.g. friendly, formal, blunt")
    p.add_argument("-l", "--length", help="short, medium, long, or your own wording")
    p.add_argument("-f", "--format", help="desired output format (or image style)")
    p.add_argument("-r", "--role", help="role for the AI (overrides the type's default)")
    p.add_argument("-x", "--constraint", action="append", default=[], dest="constraints",
                   help="a rule to follow; repeat for several")
    p.add_argument("-e", "--example", help="an example of the desired output")
    p.add_argument("-i", "--input-slot", action="store_true", help="add a {{PASTE YOUR INPUT HERE}} placeholder")
    p.add_argument("-p", "--polish", action="store_true",
                   help="have Claude improve the prompt (needs the anthropic package and ANTHROPIC_API_KEY)")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Claude model for --polish (default: {DEFAULT_MODEL})")
    p.add_argument("-o", "--outdir", default=str(Path(__file__).resolve().parent / "prompts"),
                   help="where to save prompts (default: ./prompts)")
    p.add_argument("--no-save", action="store_true", help="don't save to a file")
    p.add_argument("--no-copy", action="store_true", help="don't copy to the clipboard")
    args = p.parse_args(argv)

    if args.task:
        opts = vars(args).copy()
        opts["type"] = args.type or guess_type(f"{args.task} {args.format or ''}")
    else:
        if not sys.stdin.isatty():
            p.error("give a task argument when not running interactively")
        try:
            opts = interactive()
        except KeyboardInterrupt:
            print()
            return 130

    prompt = build_prompt(opts)
    label = f"{opts['type']} prompt"

    if args.polish or opts.get("polish"):
        print(f"\nPolishing with {args.model}…", file=sys.stderr)
        try:
            prompt = polish(prompt, opts["type"], args.model)
            label += f" (polished by {args.model})"
        except PolishError as e:
            print(f"⚠ Couldn't polish: {e}\n  Showing the unpolished prompt instead.", file=sys.stderr)

    print("\n" + "─" * 60 + f"\n  {label}\n" + "─" * 60)
    print(prompt)
    print("─" * 60)
    notes = []
    if not args.no_copy and copy_to_clipboard(prompt):
        notes.append("copied to clipboard")
    if not args.no_save:
        notes.append(f"saved to {save(prompt, opts['task'], Path(args.outdir))}")
    if notes:
        print("✓ " + "; ".join(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
