#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def resolve_venv_python(project_root: Path) -> Path:
	python3_path = project_root / "venv" / "bin" / "python3"
	if python3_path.is_file() and os.access(python3_path, os.X_OK):
		return python3_path

	python_path = project_root / "venv" / "bin" / "python"
	if python_path.is_file() and os.access(python_path, os.X_OK):
		return python_path

	raise FileNotFoundError(
		"Missing virtual environment executable. Create it first with: "
		"python3 -m venv venv"
	)


def main(argv: list[str] | None = None) -> int:
	args = sys.argv[1:] if argv is None else argv
	project_root = Path(__file__).resolve().parent

	try:
		venv_python = resolve_venv_python(project_root)
	except FileNotFoundError as error:
		print(error, file=sys.stderr)
		return 1

	run_result = subprocess.run(
		[str(venv_python), "-m", "gistman", *args],
		cwd=project_root,
		check=False,
	)
	return run_result.returncode


if __name__ == "__main__":
	raise SystemExit(main())
