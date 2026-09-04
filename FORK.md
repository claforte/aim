# claforte/aim fork

This fork is the AIM distribution used by `claforte/hshf`. It keeps the Python
backend and TypeScript UI changes together, including video/media support,
live-run indexing fixes, denser media layouts, image zoom, and robust media
blob loading.

Do not install `aim` or `aim-ui` from PyPI. The stock packages can satisfy the
same version constraints while serving an upstream UI that lacks this fork's
Media/Videos support.

## Local source install

Prerequisites:

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js and npm (the fork is currently developed with Node 22)

Clone this repository beside the consuming repository:

```text
~/git/
├── aim/
└── hshf/
```

Build the UI after cloning or pulling UI changes:

```bash
cd ~/git/aim/aim/web/ui
npm ci
npm run build
```

Git ignores the generated `aim/web/ui/build` tree. For a standalone checkout,
install both local distributions together into a dedicated environment:

```bash
cd ~/git/aim
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./aim/web/ui .
```

The two local paths in the last command are required. Installing only the root
package allows its `aim-ui` dependency to resolve to PyPI.

Consumer projects should likewise source both distributions from this checkout:

```toml
[project]
dependencies = [
    "aim>=3.29",
    "aim-ui==3.29.1",
]

[tool.uv.sources]
aim = { path = "../../../aim", editable = true }
aim-ui = { path = "../../../aim/aim/web/ui", editable = true }
```

The relative paths above are correct for a consumer at
`~/git/hshf/packages/<package>`. Adjust them for other layouts, then run
`uv sync` in the consuming project.

Verify that both distributions resolve to this checkout:

```bash
uv pip show aim aim-ui
```

Both entries should report an `Editable project location` under `~/git/aim`.

## Run the UI

Point AIM at an experiment repository from the consuming environment:

```bash
uv run aim up --repo /path/to/aim/repo --host 127.0.0.1 --port 43800
```

After pulling new commits from this fork, rerun `npm ci && npm run build` when
`aim/web/ui` changed, then rerun `uv sync` in each consuming environment.
