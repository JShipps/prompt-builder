#!/usr/bin/env bash
# Install the Prompt Builder desktop app on Linux.
#
#   ./install-linux.sh              set up and add Prompt Builder to your app launcher
#   ./install-linux.sh --uninstall  remove it from your app launcher
#
# Run it again after moving this folder, so the launcher points at the new place.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="local.promptgen.PromptBuilder"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$APPS/$APP_ID.desktop"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$DESKTOP_FILE"
    command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
    echo "Removed Prompt Builder from your app launcher."
    echo "To remove everything, delete this folder: $DIR"
    exit 0
fi

echo "Checking for Python with GTK 4 and libadwaita 1.4 or newer..."
if ! python3 - <<'PY' 2>/dev/null
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw
assert (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 4)
PY
then
    cat >&2 <<'MSG'
Prompt Builder needs Python's GTK 4 and libadwaita (1.4+) bindings. Install them with:

  Arch / Manjaro / CachyOS:  sudo pacman -S python-gobject gtk4 libadwaita
  Debian 13 / Ubuntu 24.04+: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-venv
  Fedora:                    sudo dnf install python3-gobject gtk4 libadwaita

then run this script again. (The web app and the command line work without them.)
MSG
    exit 1
fi

echo "Creating a Python environment in $DIR/.venv ..."
python3 -m venv --system-site-packages "$DIR/.venv"
if ! "$DIR/.venv/bin/pip" install --quiet --disable-pip-version-check -r "$DIR/requirements.txt"; then
    echo "Warning: couldn't install the 'anthropic' package, so 'Polish with Claude' will be unavailable." >&2
fi

mkdir -p "$APPS"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Prompt Builder
GenericName=AI Prompt Generator
Comment=Turn a few basic inputs into a well-structured AI prompt
Exec="$DIR/.venv/bin/python" "$DIR/promptgen_gui.py"
Icon=accessories-text-editor
Terminal=false
Categories=Utility;TextTools;
Keywords=prompt;ai;claude;llm;generator;
StartupWMClass=$APP_ID
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

echo
echo "Done. Open your app launcher and search for \"Prompt Builder\"."
