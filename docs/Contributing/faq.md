# FAQ and Troubleshooting

> Mainly for VS Code and pyright users

## Conflicting stubs with VS Code extension

While we don't use Pyright in CI, if you are using Pylance/PyRight in your IDE, you may want to remove the django-stubs provided by the extension, as they collide with django-stubs.

E.g. for Mac: `rm -r ~/.vscode/extensions/ms-python.vscode-pylance-20*/dist/bundled/stubs/django-stubs`

You will need to restart VS Code.

> If a better method that outright deleting the stubs (after each update of the extension...) exists, please open an issue or PR.

## Ignore specific linting errors

We actively use `ruff`'s `# noqa: <code>` and `mypy`'s `# type: ignore[<code>]` to ignore type errors.

Pylint ignore codes are accepted, but rules re-implemented by `ruff` should be disabled in `pyproject.toml` instead.

We accept ignores for pyright, with inline comments `# pyright: ignore[<code>]`.

Ignore flags should include a specific code, and not be too broad.

## Mypy crashes

Mypy may crash because of cache issues. You can try to delete the cache folder `rm -rf .mypy_cache`, or use the `--no-incremental` flag.
