from __future__ import annotations

import json
from pathlib import Path

from skillevolbench.components import TrajectoryExtractor


def test_opencode_atif_tools_record_only_skills_the_agent_used(
    tmp_path: Path,
) -> None:
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(
        json.dumps(
            {
                "schema_version": "ATIF-v1.0",
                "steps": [
                    {
                        "source": "user",
                        "message": "Try /root/.agents/skills/not-actually-used/SKILL.md",
                    },
                    {
                        "source": "agent",
                        "tool_calls": [
                            {
                                "function_name": "read",
                                "arguments": {
                                    "filePath": (
                                        "/root/.agents/skills/read-by-opencode/"
                                        "SKILL.md"
                                    )
                                },
                            },
                            {
                                "function_name": "bash",
                                "arguments": {
                                    "command": (
                                        "sed -n '1,80p' "
                                        "/root/.agents/skills/shelled-by-opencode/"
                                        "SKILL.md"
                                    )
                                },
                            },
                            {
                                "function_name": "skill",
                                "arguments": {"name": "invoked-by-opencode"},
                            },
                        ],
                    },
                ],
            }
        )
    )

    assert TrajectoryExtractor().extract_skills_used(trajectory) == [
        "invoked-by-opencode",
        "read-by-opencode",
        "shelled-by-opencode",
    ]
