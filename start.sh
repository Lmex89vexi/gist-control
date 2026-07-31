#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$project_root/venv"
venv_python="$venv_dir/bin/python"

if [[ ! -x "$venv_python" ]]; then
    echo "Creating virtual environment at $venv_dir ..."
    python3 -m venv "$venv_dir"
    if [[ ! -x "$venv_python" ]]; then
        echo "Failed to create virtual environment executable: $venv_python" >&2
        exit 1
    fi
fi

if [[ ! -x "$venv_dir/bin/pip" ]]; then
    echo "pip is missing in the virtual environment" >&2
    exit 1
fi

pip="$venv_dir/bin/pip"
if [[ -f "$project_root/pyproject.toml" ]]; then
    echo "Installing project in editable mode ..."
    "$pip" install -q --upgrade pip
    "$pip" install -q -e "$project_root"
elif [[ -f "$project_root/requirements.pip" ]]; then
    echo "Installing requirements from requirements.pip ..."
    "$pip" install -q --upgrade pip
    "$pip" install -q -r "$project_root/requirements.pip"
else
    echo "No pyproject.toml or requirements.pip found; nothing to install." >&2
    exit 1
fi

cd "$project_root"
exec "$venv_python" -m gistman "$@"
