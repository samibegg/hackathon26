from pathlib import Path

import yaml

TEMPLATE_DIR = Path(__file__).resolve().parents[1]


def test_agent_yaml_lists_hitl_on_agent_sandbox() -> None:
    config = yaml.safe_load((TEMPLATE_DIR / "agent.yaml").read_text())
    agent_tools = config["sandboxes"]["agent"]["tools"]
    assert "approve_discovery_completeness" in agent_tools
    assert "execute_migration_pipeline" in config["sandboxes"]["tool"]["tools"]
