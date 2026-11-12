#!/usr/bin/env python3
"""Prompt Builder — a desktop window for promptgen.

Fill in the task (and any optional details), press Generate, then Copy or Save.
Launch it from the app launcher, or run:  python3 promptgen_gui.py
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import promptgen as pg  # noqa: E402

APP_ID = "local.promptgen.PromptBuilder"
OUTDIR = HERE / "prompts"
TYPE_CHOICES = ["auto"] + list(pg.TYPES)
LENGTH_CHOICES = ["", "short", "medium", "long"]
MODELS = pg.MODELS


def nice(kind: str) -> str:
    return pg.TYPES[kind]["name"]


class TextArea(Gtk.Box):
    """A labelled, multi-line text field."""

    def __init__(self, title: str, hint: str = "", lines: int = 3):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=12)
        self.title = Gtk.Label(label=title, xalign=0, css_classes=["heading"])
        self.hint = Gtk.Label(label=hint, xalign=0, wrap=True, css_classes=["dim-label", "caption"])
        self.view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False,
                                 top_margin=8, bottom_margin=8, left_margin=10, right_margin=10)
        height = 22 * lines + 16
        scroller = Gtk.ScrolledWindow(child=self.view, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=height, max_content_height=height * 3,
                                      propagate_natural_height=True)
        frame = Gtk.Frame(child=scroller, margin_top=4)
        self.append(self.title)
        self.append(self.hint)
        self.append(frame)
        self.hint.set_visible(bool(hint))

    @property
    def buffer(self) -> Gtk.TextBuffer:
        return self.view.get_buffer()

    @property
    def text(self) -> str:
        b = self.buffer
        return b.get_text(b.get_start_iter(), b.get_end_iter(), False)

    def set_labels(self, title: str, hint: str = "") -> None:
        self.title.set_label(title)
        self.hint.set_label(hint)
        self.hint.set_visible(bool(hint))


class Window(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Prompt Builder", default_width=1180, default_height=800)
        self.busy = False
        self.last_task = ""

        # ---- header bar ---------------------------------------------------
        header = Adw.HeaderBar()
        self.generate_btn = Gtk.Button(css_classes=["suggested-action"], tooltip_text="Generate (Ctrl+Enter)",
                                       child=Adw.ButtonContent(icon_name="media-playback-start-symbolic",
                                                               label="Generate"))
        self.generate_btn.connect("clicked", self.on_generate)
        header.pack_end(self.generate_btn)
        clear_btn = Gtk.Button(icon_name="edit-clear-all-symbolic", tooltip_text="Clear all fields")
        clear_btn.connect("clicked", self.on_clear)
        header.pack_start(clear_btn)

        # ---- form (left) --------------------------------------------------
        form = Adw.PreferencesPage()
        form.set_size_request(400, -1)

        g_task = Adw.PreferencesGroup(title="What should the AI do?",
                                      description="Describe the job in a sentence or two. This is the only required field.")
        self.task = TextArea("Task", lines=3)
        self.task.title.set_visible(False)
        self.task.set_margin_top(0)
        self.task.buffer.connect("changed", lambda *_: self.refresh_type())
        g_task.add(self.task)
        form.add(g_task)
        g_type = Adw.PreferencesGroup()
        types_model = Gtk.StringList.new(["Auto-detect"] + [nice(t) for t in pg.TYPES])
        self.type_row = Adw.ComboRow(title="Prompt type", model=types_model)
        self.type_row.connect("notify::selected", lambda *_: self.refresh_type())
        g_type.add(self.type_row)
        form.add(g_type)

        g_details = Adw.PreferencesGroup(title="Details", description="All optional. Fill in whatever matters.")
        self.goal = Adw.EntryRow(title="Goal: why you need this")
        self.audience = Adw.EntryRow(title="Audience: who it's for")
        self.tone = Adw.EntryRow()
        self.length = Adw.ComboRow(title="Length", model=Gtk.StringList.new(["Any", "Short", "Medium", "Long"]))
        self.fmt = Adw.EntryRow()
        self.fmt.connect("changed", lambda *_: self.refresh_type())
        self.role = Adw.EntryRow(title="Role for the AI (blank uses the type's default)")
        for row in (self.goal, self.audience, self.tone, self.length, self.fmt, self.role):
            g_details.add(row)
        form.add(g_details)

        g_more = Adw.PreferencesGroup(title="Background and rules")
        self.context = TextArea("", lines=3)
        self.rules = TextArea("", lines=3)
        self.example = TextArea("Example of what you want", "Optional. Used as a guide to style and structure.", lines=3)
        self.context.set_margin_top(0)
        for area in (self.context, self.rules, self.example):
            g_more.add(area)
        form.add(g_more)

        g_opts = Adw.PreferencesGroup(title="Options")
        self.input_slot = Adw.SwitchRow(title="Add a paste-your-input placeholder",
                                        subtitle="Adds {{PASTE YOUR INPUT HERE}} so you can reuse the prompt")
        self.polish_row = Adw.SwitchRow(title="Polish with Claude",
                                        subtitle="Claude rewrites the draft to make it clearer. Uses your API key.")
        self.model_row = Adw.ComboRow(title="Model", model=Gtk.StringList.new(MODELS))
        self.key_row = Adw.PasswordEntryRow(show_apply_button=True)
        self.key_row.connect("apply", self.on_save_key)
        for row in (self.input_slot, self.polish_row, self.model_row, self.key_row):
            g_opts.add(row)
        self.polish_row.connect("notify::active", lambda *_: self.refresh_polish())
        form.add(g_opts)

        # ---- output (right) -----------------------------------------------
        self.output = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, monospace=True,
                                   top_margin=18, bottom_margin=18, left_margin=20, right_margin=20)
        out_scroll = Gtk.ScrolledWindow(child=self.output, vexpand=True, hexpand=True)
        empty = Adw.StatusPage(icon_name="document-edit-symbolic", title="No prompt yet",
                               description="Describe the task on the left, then press Generate.")
        busy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                       valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        busy.append(Gtk.Spinner(spinning=True, width_request=48, height_request=48))
        self.busy_label = Gtk.Label(label="Polishing with Claude…", css_classes=["dim-label"])
        busy.append(self.busy_label)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True)
        self.stack.add_named(empty, "empty")
        self.stack.add_named(out_scroll, "output")
        self.stack.add_named(busy, "busy")

        actions = Gtk.ActionBar()
        self.status = Gtk.Label(css_classes=["dim-label"], ellipsize=3)
        actions.pack_start(self.status)
        self.save_btn = Gtk.Button(child=Adw.ButtonContent(icon_name="document-save-symbolic", label="Save"),
                                   tooltip_text=f"Save to {OUTDIR}")
        self.copy_btn = Gtk.Button(child=Adw.ButtonContent(icon_name="edit-copy-symbolic", label="Copy"),
                                   css_classes=["suggested-action"])
        self.save_btn.connect("clicked", self.on_save)
        self.copy_btn.connect("clicked", self.on_copy)
        actions.pack_end(self.copy_btn)
        actions.pack_end(self.save_btn)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.set_size_request(380, -1)
        right.append(self.stack)
        right.append(actions)

        paned = Gtk.Paned(start_child=form, end_child=right, position=520,
                          shrink_start_child=False, shrink_end_child=False)
        self.toasts = Adw.ToastOverlay(child=paned)
        toolbar = Adw.ToolbarView(content=self.toasts)
        toolbar.add_top_bar(header)
        self.set_content(toolbar)

        # Ctrl+Enter generates from anywhere in the window.
        shortcuts = Gtk.ShortcutController(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        shortcuts.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("<Control>Return"),
                                            action=Gtk.CallbackAction.new(lambda *_: self.on_generate() or True)))
        self.add_controller(shortcuts)

        self.refresh_type()
        self.refresh_polish()
        self.set_has_output(False)
        self.task.view.grab_focus()

    # ---- helpers ----------------------------------------------------------
    def current_type(self) -> tuple[str, bool]:
        """(type, was_auto_detected)"""
        choice = TYPE_CHOICES[self.type_row.get_selected()]
        if choice != "auto":
            return choice, False
        text = f"{self.task.text} {self.fmt.get_text()}".strip()
        return (pg.guess_type(text) if text else "general"), True

    def refresh_type(self) -> None:
        kind, auto = self.current_type()
        self.type_row.set_subtitle(f"Detected: {nice(kind)}" if auto and self.task.text.strip() else "")
        spec = pg.TYPES[kind]
        labels = {**pg.TEMPLATES["default_labels"], **spec.get("labels", {})}
        hidden = set(spec.get("hide", []))
        rows = {"goal": self.goal, "audience": self.audience, "tone": self.tone, "length": self.length,
                "format": self.fmt, "role": self.role, "input_slot": self.input_slot, "example": self.example}
        for name, widget in rows.items():
            widget.set_visible(name not in hidden)
        for name in ("goal", "audience", "tone", "format", "role"):
            rows[name].set_title(labels[name])
        for name, area in (("context", self.context), ("rules", self.rules), ("example", self.example)):
            area.set_labels(*labels[name])

    def refresh_polish(self) -> None:
        if not pg.polish_available():
            self.polish_row.set_active(False)
            self.polish_row.set_sensitive(False)
            self.polish_row.set_subtitle("Unavailable: the 'anthropic' package isn't installed (see README)")
        on = self.polish_row.get_active()
        self.model_row.set_visible(on)
        self.key_row.set_visible(on)
        has_key = pg.load_api_key() is not None
        self.key_row.set_title("Anthropic API key (saved)" if has_key else "Anthropic API key: paste, then press ✓")

    def set_has_output(self, has: bool) -> None:
        self.copy_btn.set_sensitive(has)
        self.save_btn.set_sensitive(has)

    def toast(self, text: str, timeout: int = 3, button: str | None = None, on_click=None) -> None:
        t = Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout)
        if button and on_click:
            t.set_button_label(button)
            t.connect("button-clicked", lambda *_: on_click())
        self.toasts.add_toast(t)

    def output_text(self) -> str:
        b = self.output.get_buffer()
        return b.get_text(b.get_start_iter(), b.get_end_iter(), False)

    def collect(self) -> dict | None:
        task = self.task.text.strip()
        if not task:
            self.toast("Describe the task first.")
            self.task.view.grab_focus()
            return None
        kind, _ = self.current_type()
        return {
            "task": task,
            "type": kind,
            "goal": self.goal.get_text(),
            "audience": self.audience.get_text(),
            "context": self.context.text,
            "tone": self.tone.get_text(),
            "length": LENGTH_CHOICES[self.length.get_selected()],
            "format": self.fmt.get_text(),
            "role": self.role.get_text(),
            "constraints": [ln.strip(" \t-•*") for ln in self.rules.text.splitlines() if ln.strip(" \t-•*")],
            "example": self.example.text,
            "input_slot": self.input_slot.get_active(),
        }

    # ---- actions ----------------------------------------------------------
    def on_generate(self, *_):
        if self.busy:
            return
        opts = self.collect()
        if not opts:
            return
        draft = pg.build_prompt(opts)
        label = f"{nice(opts['type'])} prompt"

        if not (self.polish_row.get_active() and self.polish_row.get_sensitive()):
            self.show_result(draft, label, None, opts["task"])
            return

        model = MODELS[self.model_row.get_selected()]
        self.set_busy(True, f"Polishing with {model}…")

        def work():
            try:
                text, err = pg.polish(draft, opts["type"], model), None
            except pg.PolishError as e:
                text, err = draft, str(e)
            except Exception as e:  # never leave the window stuck on the spinner
                text, err = draft, f"unexpected error: {e}"
            final_label = label if err else f"{label} · polished by {model}"
            GLib.idle_add(self.show_result, text, final_label, err, opts["task"])

        threading.Thread(target=work, daemon=True).start()

    def set_busy(self, busy: bool, message: str = "") -> None:
        self.busy = busy
        self.generate_btn.set_sensitive(not busy)
        if busy:
            self.busy_label.set_label(message)
            self.stack.set_visible_child_name("busy")
            self.set_has_output(False)

    def show_result(self, text: str, label: str, error: str | None, task: str) -> bool:
        self.set_busy(False)
        self.output.get_buffer().set_text(text.rstrip("\n"))
        self.stack.set_visible_child_name("output")
        self.status.set_label(label)
        self.last_task = task
        self.set_has_output(True)
        if error:
            self.toast(f"Couldn't polish: {error} Showing the unpolished prompt.", timeout=8)
        return False  # for GLib.idle_add

    def on_copy(self, *_):
        data = GLib.Bytes.new(self.output_text().encode())
        self.get_clipboard().set_content(Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", data))
        self.toast("Copied to clipboard")

    def on_save(self, *_):
        try:
            path = pg.save(self.output_text() + "\n", self.last_task or "prompt", OUTDIR)
        except OSError as e:
            self.toast(f"Couldn't save: {e}", timeout=6)
            return
        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(path)))
        self.toast(f"Saved {path.name}", timeout=5, button="Show",
                   on_click=lambda: launcher.open_containing_folder(self, None, None))

    def on_save_key(self, row: Adw.PasswordEntryRow):
        key = row.get_text().strip()
        if not key:
            return
        try:
            pg.save_api_key(key)
        except OSError as e:
            self.toast(f"Couldn't save the key: {e}", timeout=6)
            return
        row.set_text("")
        self.refresh_polish()
        self.toast("API key saved")

    def on_clear(self, *_):
        for area in (self.task, self.context, self.rules, self.example):
            area.buffer.set_text("")
        for row in (self.goal, self.audience, self.tone, self.fmt, self.role):
            row.set_text("")
        self.type_row.set_selected(0)
        self.length.set_selected(0)
        self.input_slot.set_active(False)
        self.task.view.grab_focus()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        (self.props.active_window or Window(self)).present()


def main() -> int:
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
