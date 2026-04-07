"""
Web Backend entry point for Ravenswood Bluff
"""

import json
import logging
import asyncio
import sys
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

# Configure logging
fh = logging.FileHandler("orchestrator_run.log", encoding="utf-8")
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True
)
logging.getLogger("src").setLevel(logging.INFO)
logging.getLogger("src").addHandler(fh)
logger = logging.getLogger("server")
logger.addHandler(fh)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.agents.human_agent import HumanAgent
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameState, PlayerState, Team, GamePhase

# Configure logging
# Moved to top level

# Global variables
from src.agents.storyteller_agent import StorytellerAgent
global_orchestrator: GameOrchestrator | None = None
global_storyteller: StorytellerAgent | None = None
human_agents: Dict[str, HumanAgent] = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.active_connections[player_id] = websocket
        logger.info(f"玩家已连接 - WebSocket: {player_id}")

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]
            logger.info(f"玩家断开连接: {player_id}")

    async def send_personal_message(self, message: str, player_id: str):
        if player_id in self.active_connections:
            ws = self.active_connections[player_id]
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.error(f"发往 {player_id} 的消息失败: {e}")

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_orchestrator
    try:
        from src.llm.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        global_storyteller = StorytellerAgent(backend)
        
        # 初始状态只有一个待定玩家
        state = GameState(
            phase=GamePhase.SETUP,
            players=(
                PlayerState(player_id="h1", name="Host", role_id="washerwoman", team=Team.GOOD),
            )
        )
        global_orchestrator = GameOrchestrator(state)
        global_orchestrator.storyteller_agent = global_storyteller
        
        # 自动启动游戏循环任务
        asyncio.create_task(run_game_loop_safe())
        
        logger.info("Global Orchestrator started in SETUP phase.")
    except Exception as e:
        logger.error(f"Failed to startup: {e}", exc_info=True)
    yield

app = FastAPI(title="Ravenswood Bluff API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public")
if os.path.exists(public_dir):
    app.mount("/ui", StaticFiles(directory=public_dir, html=True), name="ui")

async def run_game_loop_safe():
    try:
        logger.info("Starting safe game loop background task...")
        await global_orchestrator.run_game_loop()
    except Exception as e:
        logger.error(f"Game loop crashed: {e}", exc_info=True)

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/ui/index.html")

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    await manager.connect(websocket, player_id)
    if player_id not in human_agents:
        agent = HumanAgent(
            player_id=player_id, 
            name=f"Human_{player_id}", 
            send_message_callback=lambda msg: manager.send_personal_message(msg, player_id),
            chat_callback=global_orchestrator.handle_chat if global_orchestrator else None
        )
        human_agents[player_id] = agent
        if global_orchestrator:
            global_orchestrator.register_agent(agent)
    agent = human_agents[player_id]
    try:
        while True:
            data = await websocket.receive_text()
            await agent.receive_client_message(data)
    except WebSocketDisconnect:
        manager.disconnect(player_id)

@app.post("/api/game/setup")
async def setup_game(data: Dict[str, Any]):
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    
    player_count = data.get("player_count", 5)
    host_id = data.get("host_id", "h1")
    is_human = data.get("is_human_participant", True)
    
    if player_count < 5 or player_count > 15:
        return {"status": "error", "message": "Player count must be between 5 and 15"}

    # 异步触发准备完成
    asyncio.create_task(global_orchestrator.run_setup(player_count, host_id, is_human))
    return {"status": "ok", "message": f"Game setup for {player_count} players started"}

@app.post("/api/game/start")
async def start_game():
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    asyncio.create_task(run_game_loop_safe())
    return {"status": "ok", "message": "Game loop started"}

@app.get("/api/game/state")
async def get_game_state(player_id: str = None):
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    state = global_orchestrator.state
    is_observer = player_id not in state.config.human_player_ids if state.config else False
    
    data = {
        "round_number": state.round_number,
        "day_number": state.day_number,
        "phase": state.phase.value,
        "alive_count": state.alive_count,
        "current_nominee": state.current_nominee,
        "is_observer": is_observer,
        "players": []
    }
    for p in state.players:
        p_info = {
            "player_id": p.player_id,
            "name": p.name,
            "is_alive": p.is_alive,
        }
        # 仅在请求者是该玩家本人时，返回角色信息
        if player_id == p.player_id:
            # 如果是该玩家本人且有虚假身份(如酒鬼)，则返回虚假身份供其展示
            display_role = p.role_id
            if p.fake_role:
                display_role = p.fake_role
                
            p_info.update({
                "role_id": display_role,
                "team": p.team.value,
                "is_poisoned": p.is_poisoned,
                "is_drunk": p.is_drunk,
            })
        
        # 说书人(h1)可以额外看到一些状态标记，但角色身份建议只在 Grimoire 中查看
        if player_id == "h1":
             p_info.update({
                "fake_role": p.fake_role,
                "is_poisoned": p.is_poisoned,
                "is_drunk": p.is_drunk,
            })
        
        data["players"].append(p_info)
    return data

@app.get("/api/game/grimoire")
async def get_grimoire():
    """获取说书人专用魔典信息"""
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    
    grimoire = global_orchestrator.state.grimoire
    if not grimoire:
        return {"players": []}
        
    return grimoire.model_dump()

if __name__ == "__main__":
    import uvicorn
    # 使用 app 对象而不是字符串，确保在同一个进程中运行且日志配置生效
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
