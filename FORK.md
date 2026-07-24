# claforte/aim fork

This fork is the AIM distribution used by `claforte/hshf`. It keeps the Python
backend and TypeScript UI changes together, including video/media support,
live-run indexing fixes, denser media layouts, image zoom, and robust media
blob loading.

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

The generated `aim/web/ui/build` tree is intentionally not committed. Python
consumers should install both local distributions so they do not mix the forked
backend with the stock `aim-ui` wheel:

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
