"""Generate deterministic demo reports and SVG portfolio assets from the real engine."""

from __future__ import annotations

import json
from pathlib import Path

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.reporting.charts import architecture_svg, coverage_availability_svg
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import run_lab, write_run_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    run = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE))
    demo = root / "artifacts" / "demo"
    images = root / "docs" / "images"
    images.mkdir(parents=True, exist_ok=True)
    write_run_artifacts(run, demo)
    (demo / "environment-manifest.json").write_text(
        json.dumps(run.aggregate["environment"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (images / "architecture.svg").write_text(
        architecture_svg() + "\n", encoding="utf-8", newline="\n"
    )
    (images / "worked-result.svg").write_text(
        coverage_availability_svg(run.aggregate["method_metrics"]) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"replay_hash={run.replay_hash}")
    print(f"wall_seconds={run.runtime_diagnostics['wall_seconds']:.6f}")


if __name__ == "__main__":
    main()
