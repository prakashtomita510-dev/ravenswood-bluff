"""
Web Backend entry point for Ravenswood Bluff

提供 WebSocket 以连接前端的人类玩家，同时提供 RESTful API 支持编排器控制。
"""

import json
import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from src.agents.human_agent import HumanAgent
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameState, PlayerState, Team

logger = logging.getLogger("server")
app = FastAPI(title="Ravenswood Bluff API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局连接管理器
class ConnectionManager:
    def __init__(self):
        # player_id -> WebSocket
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
# 临时粗暴地在这里声明全局 orchestrator，用于演示
# 实际可以借用 Depends 或 lifespan 注入
global_orchestrator: GameOrchestrator | None = None
human_agents: Dict[str, HumanAgent] = {}

@app.on_event("startup")
async def startup_event():
    global global_orchestrator
    # 初始化一个简单的游戏状态
    state = GameState(
        players=(
            PlayerState(player_id="h1", name="Human Player", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="a1", name="Bot Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="a2", name="Bot Bob", role_id="empath", team=Team.GOOD),
        )
    )
    global_orchestrator = GameOrchestrator(state)
    logger.info("Global Orchestrator started.")


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    await manager.connect(websocket, player_id)
    
    # 动态创建 HumanAgent
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
            # 把收到的信息交给对应的 HumanAgent 处理
            await agent.receive_client_message(data)
    except WebSocketDisconnect:
        manager.disconnect(player_id)


@app.post("/api/game/start")
async def start_game():
    """启动游戏循环 (非阻塞跑在后台)"""
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
        
    asyncio.create_task(global_orchestrator.run_game_loop())
    return {"status": "ok", "message": "Game loop started"}

@app.get("/api/game/state")
async def get_game_state():
    """说书人控制台专用：获取当前全部局势（上帝视角）"""
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
        
    state = global_orchestrator.state
    
    # 构建安全的JSON表示，仅用于只读渲染
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
            "is_poisoned": p.is_poisoned(),
            "is_drunk": p.is_drunk(),
        })
        
    return data
