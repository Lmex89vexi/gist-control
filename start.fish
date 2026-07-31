#!/usr/bin/env fish

set -l script_path (status --current-filename)
set -l project_root (path dirname (path resolve $script_path))
set -l venv_dir "$project_root/venv"
set -l venv_python "$venv_dir/bin/python"

if not test -x "$venv_python"
    echo "Creating virtual environment at $venv_dir ..."
    python3 -m venv "$venv_dir"
    if not test -x "$venv_python"
        echo "Failed to create virtual environment executable: $venv_python" >&2
        exit 1
    end
end

if not test -x "$venv_dir/bin/pip"
    echo "pip is missing in the virtual environment" >&2
    exit 1
end

# Install / upgrade dependencies in editable mode
set -l pip "$venv_dir/bin/pip"
if test -f "$project_root/pyproject.toml"
    echo "Installing project in editable mode ..."
    "$pip" install -q --upgrade pip
    "$pip" install -q -e "$project_root"
else if test -f "$project_root/requirements.pip"
    echo "Installing requirements from requirements.pip ..."
    "$pip" install -q --upgrade pip
    "$pip" install -q -r "$project_root/requirements.pip"
else
    echo "No pyproject.toml or requirements.pip found; nothing to install." >&2
    exit 1
end

cd "$project_root"; or begin
    echo "Cannot change directory to $project_root" >&2
    exit 1
end

exec "$venv_python" -m gistman $argv
