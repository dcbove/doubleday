# Doubleday — Claude Code Guidelines

## Docstrings

Every Python module and every public function/class/method must have a docstring.
Use Google-style docstrings. This is enforced by Ruff (`D` rules, `convention = "google"`).

## Linting

Run `ruff check` before committing. Fix any violations — do not suppress with `noqa` unless discussed.
