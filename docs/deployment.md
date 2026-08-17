# Deployment for version 0.2.1

The verified public application is available at
[inferential-safety-lab.streamlit.app](https://inferential-safety-lab.streamlit.app/).

## Local Python

Create a Python 3.12 environment, install the ordinary runtime, then run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Windows users can run `scripts/launch-windows.ps1` after installation.

## Streamlit Community Cloud

Use `streamlit_app.py` as the entry point and Python 3.12. The app needs no
secret, database, remote API, model download, R runtime, or persistent volume.
Public deployment must remain synthetic-only.

The Community Cloud deployment uses the public
`aldaqrouqtaysir/inferential-safety-lab` repository, branch `main`, Python 3.12,
and no secrets. Updates to `main` trigger the hosted application to redeploy.

The application uses top navigation with `Understand` at `/`, `Experiment` at
`/experiment`, and `Results` at `/results`. It is intentionally light under both
light and dark operating-system preferences. Streamlit's toolbar mode is set to
`minimal`.

## GitHub Pages

`artifacts/demo/inferential-safety-card.html` is self-contained and suitable as
a static result page. `docs/images/` contains static screenshots and SVGs that
can support a static documentation or result gallery.

## Dependency installation

`pyproject.toml` provides compatible ranges. `requirements-lock.txt` records
the exact full local development environment for audit and reproduction. The
hosted runtime path uses only `[project].dependencies`: NumPy, pandas, and
Streamlit. It does not require pytest, coverage, mypy, Ruff, Playwright, or
package-build tooling. After runtime dependencies are installed, simulation and
report generation require no network access.

The deployment requires no runtime credential, user account, upload, telemetry,
or persistent user-data store.
