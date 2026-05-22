from __future__ import annotations

import gemma_worker
from gemma_worker import run


def test_version():
    assert gemma_worker.__version__ == "0.1.0"


def test_parse_args_defaults():
    ns = run.parse_args(["find unused"])
    assert ns.task == "find unused"
    assert ns.playbook == "auto"
    assert ns.output == "json"
    assert ns.max_iterations == 3
    assert ns.priority == "normal"


def test_parse_args_explicit():
    ns = run.parse_args(
        ["scan repo", "--playbook", "deadcode", "--output", "text", "--max-iterations", "5"]
    )
    assert ns.playbook == "deadcode"
    assert ns.output == "text"
    assert ns.max_iterations == 5
