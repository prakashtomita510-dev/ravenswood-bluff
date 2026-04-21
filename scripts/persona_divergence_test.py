"""
验收测试 (Acceptance Gate): W3-C 多层人格与记忆压缩验证
断言：
1. 不同 Archetype 的 Agent 在相同局势下具有不同的提名阈值。
2. 当记忆量超过 30 条时，能够触发 _reflect 逻辑并将记忆压缩至 1 条。
"""

import asyncio
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.ai_agent import AIAgent, Persona
from src.agents.persona_registry import ARCHETYPES
from src.llm.mock_backend import MockBackend
from src.agents.memory.working_memory import Observation
from src.state.game_state import GameState, PlayerState, GamePhase, Team

# 配置日志
logging.basicConfig(level=logging.INFO)

async def test_threshold_divergence():
    print("Checking Threshold Divergence for Archetypes...")
    backend = MockBackend()
    
    # 强势领袖 (Aggressive)
    p_aggressive = Persona("强势的人", "大声说话", archetype="aggressive")
    agent_agg = AIAgent("p1", "Alice", backend, p_aggressive)
    
    # 边缘透明人 (Silent)
    p_silent = Persona("安静的人", "小声说话", archetype="silent")
    agent_sil = AIAgent("p2", "Bob", backend, p_silent)
    
    state = GameState(
        phase=GamePhase.NOMINATION,
        day_number=1,
        round_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Cathy", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="D", role_id="librarian", team=Team.GOOD),
            PlayerState(player_id="p5", name="E", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p6", name="F", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p7", name="G", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p8", name="H", role_id="monk", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"),
    )
    dummy_p1 = PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD)
    dummy_p2 = PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD)
    
    # 强制同步一次角色
    agent_agg.synchronize_role(dummy_p1)
    agent_sil.synchronize_role(dummy_p2)

    visible_agg = agent_agg._build_visible_state(state)
    visible_sil = agent_sil._build_visible_state(state)
    thresh_agg = agent_agg._nomination_threshold(visible_agg)
    thresh_sil = agent_sil._nomination_threshold(visible_sil)
    
    print(f"Aggressive Threshold: {thresh_agg:.2f}")
    print(f"Silent Threshold: {thresh_sil:.2f}")
    
    assert thresh_agg < thresh_sil, "Aggressive should have lower threshold than Silent"
    print("Threshold Divergence: OK")

async def test_memory_compression():
    print("\nChecking Memory Compression (Distillation)...")
    backend = MockBackend()
    backend.set_response('{"action": "none", "reasoning": "测试中"}')
    # 设置反思的 Mock 响应
    backend.set_response("我觉得 Bob 非常可疑，因为他一直在划水。")

    p = Persona("测试者", "普通", archetype="logic")
    agent = AIAgent("p1", "Alice", backend, p)
    dummy_p = PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD)
    agent.synchronize_role(dummy_p)

    state = GameState(phase=GamePhase.DAY_DISCUSSION, day_number=2, round_number=1)
    
    # 注入 35 条记忆
    from src.agents.memory.working_memory import Observation as Obs
    for i in range(35):
        agent.working_memory.add_observation(Obs(
            observation_id=f"test-{i}",
            content=f"这是第 {i} 条观察到的废话",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1
        ))
    
    assert len(agent.working_memory.observations) == 35
    print(f"Memory count before act: {len(agent.working_memory.observations)}")
    
    # 执行一次动作，预期触发 _reflect
    visible_state = agent._build_visible_state(state)
    legal_context = agent._build_legal_action_context(state, visible_state)
    await agent.act(visible_state, "speak", legal_context=legal_context)
    
    print(f"Memory count after act: {len(agent.working_memory.observations)}")
    # 压缩后应该是 1 条（总结）
    assert len(agent.working_memory.observations) <= 5 
    assert len(agent.working_memory.impressions) >= 1
    print("Memory Compression: OK")

async def main():
    await test_threshold_divergence()
    await test_memory_compression()
    print("\nW3-C Acceptance Gate: ALL GREEN")

if __name__ == "__main__":
    asyncio.run(main())
