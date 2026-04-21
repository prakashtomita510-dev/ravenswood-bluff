"""
验收测试 (Acceptance Gate): AI 玩家视角边界隔离 (Wave 3-A)
断言：如果 AI 玩家扮演了被隐藏状态污染的角色（如“酒鬼”或被“下毒”），其底层 AI Agent 及 Prompt 中绝不可以有对真相字段（如 true_role_id = drunken 或 is_poisoned = True）的直接感知。
"""

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GamePhase, Team, PlayerState, PlayerStatus

async def main() -> None:
    print("Running Player Knowledge Isolation Acceptance Gate...")
    
    from src.state.game_state import GameState
    orch = GameOrchestrator(initial_state=GameState())
    orch.state = orch.state.with_update(phase=GamePhase.SETUP)
    players = (
        PlayerState(
            player_id="p1",
            name="Alice",
            role_id="drunken",
            perceived_role_id="washerwoman",
            team=Team.GOOD,
            current_team=Team.GOOD,
        ),
        PlayerState(
            player_id="p2",
            name="Bob",
            role_id="chef",
            perceived_role_id="chef",
            team=Team.GOOD,
            current_team=Team.GOOD,
            statuses=(PlayerStatus.ALIVE, PlayerStatus.POISONED)
        ),
    )
    orch.state = orch.state.with_update(
        players=players,
        seat_order=("p1", "p2"),
        player_count=2,
        alive_count=2
    )

    from src.agents.ai_agent import AIAgent, Persona
    from src.llm.mock_backend import MockBackend

    agent_p1 = AIAgent("p1", "Alice", MockBackend(), Persona("测试", "安静", "voice", "social"))
    agent_p2 = AIAgent("p2", "Bob", MockBackend(), Persona("测试", "安静", "voice", "social"))

    orch.register_agent(agent_p1)
    orch.register_agent(agent_p2)

    assert not hasattr(agent_p1.private_view, "true_role_id")
    assert getattr(agent_p1, "true_role_id", None) is None
    assert agent_p1.private_view.perceived_role_id == "washerwoman"
    assert not hasattr(agent_p1.private_view, "is_poisoned")
    assert agent_p1.role_id == "washerwoman"
    prompt_p1 = agent_p1._build_persona_prompt_block("speak")
    assert "drunken" not in prompt_p1.lower()
    assert "酒鬼" not in prompt_p1

    assert not hasattr(agent_p2.private_view, "is_poisoned")
    assert agent_p2.private_view.perceived_role_id == "chef"
    assert agent_p2.role_id == "chef"
    prompt_p2 = agent_p2._build_persona_prompt_block("speak")
    assert "poison" not in prompt_p2.lower()
    assert "中毒" not in prompt_p2

    print("player knowledge acceptance: ok")


if __name__ == "__main__":
    asyncio.run(main())
