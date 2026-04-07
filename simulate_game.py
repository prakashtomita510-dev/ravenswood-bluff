"""
Ravenswood Bluff - Automated Game Simulation Script
Runs a full game with 4 AI Agents to verify engine logic and LLM connectivity.
"""

import asyncio
import logging
import sys
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameState, PlayerState, Team, GamePhase
from src.agents.ai_agent import AIAgent, Persona
from src.llm.openai_backend import OpenAIBackend

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("simulation")

async def run_simulation():
    print("=== [开始全自动对局测试] ===")
    
    # 1. 初始化 LLM 后端
    backend = OpenAIBackend()
    
    # 2. 定义 4 个 AI 玩家
    players = (
        PlayerState(player_id="a1", name="Alice", role_id="imp", team=Team.EVIL),
        PlayerState(player_id="a2", name="Bob", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="a3", name="Charlie", role_id="empath", team=Team.GOOD),
        PlayerState(player_id="a4", name="David", role_id="poisoner", team=Team.EVIL),
    )
    
    state = GameState(players=players, phase=GamePhase.SETUP)
    orchestrator = GameOrchestrator(state)
    
    # 初始化说书人
    from src.agents.storyteller_agent import StorytellerAgent
    orchestrator.storyteller_agent = StorytellerAgent(backend)
    
    # 3. 注册代理
    agents = [
        AIAgent("a1", "Alice", backend, Persona("狡诈的多面手", "冷静且逻辑慎密")),
        AIAgent("a2", "Bob", backend, Persona("热心的村民", "多嘴，喜欢分享信息")),
        AIAgent("a3", "Charlie", backend, Persona("胆小的旁观者", "犹豫不决")),
        AIAgent("a4", "David", backend, Persona("险恶的投毒者", "低调，善于伪装")),
    ]
    
    for agent in agents:
        orchestrator.register_agent(agent)
    
    print(">>> 代理注册完毕，准备启动主循环...")
    
    # 4. 模拟外部触发 SETUP
    print(">>> 模拟说书人初始化对局...")
    # 这里我们直接手动设置 _setup_done，因为 players 已经手动定义了
    orchestrator._setup_done = asyncio.get_running_loop().create_future()
    orchestrator._setup_done.set_result(True)
    
    # 5. 运行游戏主循环
    try:
        winner = await orchestrator.run_game_loop()
        print(f"\n=== [对局结束] 胜方: {winner.value} ===")
    except Exception as e:
        import traceback
        logger.error(f"!!! 对局卡死或崩溃: {e}")
        traceback.print_exc()
        print("\n--- 调试信息 ---")
        print(f"当前阶段: {orchestrator.state.phase}")
        print(f"当前被提名者: {orchestrator.state.current_nominee}")

if __name__ == "__main__":
    asyncio.run(run_simulation())
