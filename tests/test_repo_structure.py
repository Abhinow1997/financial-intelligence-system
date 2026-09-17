# Meta test: the skeleton keeps its shape. Good first 'green build' for the git lab.
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "services/gateway",
    "services/backend",
    "services/frontend",
    "services/ingestion",
    "services/integration",
    "services/analytics",
    "services/rag",
    "services/agents",
    "services/evaluation",
    "services/security",
    "services/platform",
    "libs/fin_common",
    "docs/labs/lab00_git_workflow.md",
    "docker-compose.yml",
    "CONTRIBUTING.md",
]


def test_required_paths_exist():
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    assert not missing, f"missing: {missing}"
