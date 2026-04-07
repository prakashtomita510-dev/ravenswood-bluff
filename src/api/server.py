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
from src.state.game_state import GameState, PlayerState, Team

# Configure logging
# Moved to top level

# Global variables
global_orchestrator: GameOrchestrator | None = None
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
        from src.agents.ai_agent import AIAgent, Persona
        from src.llm.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        
        state = GameState(
            players=(
                PlayerState(player_id="h1", name="Human Player", role_id="imp", team=Team.EVIL),
                PlayerState(player_id="a1", name="Bot Alice", role_id="washerwoman", team=Team.GOOD),
                PlayerState(player_id="a2", name="Bot Bob", role_id="empath", team=Team.GOOD),
                PlayerState(player_id="a3", name="Bot Charlie", role_id="poisoner", team=Team.EVIL),
            )
        )
        global_orchestrator = GameOrchestrator(state)
        
        a1_agent = AIAgent("a1", "Bot Alice", backend, Persona("普通的洗衣妇", "多嘴且热心"))
        a2_agent = AIAgent("a2", "Bot Bob", backend, Persona("同情心泛滥的村民", "犹豫不决"))
        a3_agent = AIAgent("a3", "Bot Charlie", backend, Persona("险恶的投毒者", "狡诈，喜欢带节奏"))
        
        global_orchestrator.register_agent(a1_agent)
        global_orchestrator.register_agent(a2_agent)
        global_orchestrator.register_agent(a3_agent)
        
        logger.info("Global Orchestrator started with AI Agents.")
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
            send_message_callback=lambda msg: manager.send_personal_message(msg, player_id)
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

@app.post("/api/game/start")
async def start_game():
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    asyncio.create_task(run_game_loop_safe())
    return {"status": "ok", "message": "Game loop started"}

@app.get("/api/game/state")
async def get_game_state():
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    state = global_orchestrator.state
    data = {
        "round_number": state.round_number,
        "phase": state.phase.value,
        "alive_count": state.alive_count,
        "current_nominee": state.current_nominee,
        "players": []
    }
    for p in state.players:
        data["players"].append({
            "player_id": p.player_id,
            "name": p.name,
            "role_id": p.role_id,
            "team": p.team.value,
            "is_alive": p.is_alive,
            "is_poisoned": p.is_poisoned,
            "is_drunk": p.is_drunk,
        })
    return data

if __name__ == "__main__":
    import uvicorn
    # 使用 app 对象而不是字符串，确保在同一个进程中运行且日志配置生效
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
