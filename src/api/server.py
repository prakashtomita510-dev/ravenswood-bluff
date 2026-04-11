"""
Web Backend entry point for Ravenswood Bluff
"""

import json
import logging
import asyncio
import sys
import os
from contextlib import asynccontextmanager
from contextlib import suppress
from datetime import datetime
from typing import Dict, Any

def _ensure_file_handler(logger_name: str, filename: str) -> logging.FileHandler:
    logger_obj = logging.getLogger(logger_name)
    abs_path = os.path.abspath(filename)
    for handler in logger_obj.handlers:
        if isinstance(handler, logging.FileHandler) and os.path.abspath(getattr(handler, "baseFilename", "")) == abs_path:
            return handler
    handler = logging.FileHandler(filename, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger_obj.addHandler(handler)
    return handler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True
)
logging.getLogger("src").setLevel(logging.INFO)
orchestrator_fh = _ensure_file_handler("src", "orchestrator_run.log")
storyteller_fh = _ensure_file_handler("storyteller", "storyteller_run.log")
logger = logging.getLogger("server")
logger.addHandler(orchestrator_fh)
logging.getLogger("storyteller").setLevel(logging.INFO)
logging.getLogger("storyteller").propagate = False

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.agents.human_agent import HumanAgent
from src.content.trouble_brewing_terms import get_role_name, get_role_term
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameState, PlayerState, Team, GamePhase

# Configure logging
# Moved to top level

# Global variables
from src.agents.storyteller_agent import StorytellerAgent
global_orchestrator: GameOrchestrator | None = None
global_storyteller: StorytellerAgent | None = None
global_game_loop_task: asyncio.Task | None = None
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


def build_backend(force_mode: str | None = None):
    from dotenv import load_dotenv

    load_dotenv()
    requested_mode = (force_mode or os.getenv("BOTC_BACKEND", "auto")).lower()

    if requested_mode == "mock":
        from src.llm.mock_backend import MockBackend
        backend = MockBackend()
    elif requested_mode == "live":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("BOTC-BACKEND: 已请求 live backend，但缺少 OPENAI_API_KEY")
        from src.llm.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
    else:
        if os.getenv("OPENAI_API_KEY"):
            from src.llm.openai_backend import OpenAIBackend
            backend = OpenAIBackend()
        else:
            from src.llm.mock_backend import MockBackend
            backend = MockBackend()

    logger.info(
        "Backend resolved: mode=%s type=%s model=%s api_key_present=%s base_url=%s",
        requested_mode,
        backend.__class__.__name__,
        backend.get_model_name(),
        bool(os.getenv("OPENAI_API_KEY")),
        os.getenv("OPENAI_BASE_URL"),
    )
    return backend, requested_mode


def build_fresh_orchestrator(force_backend_mode: str | None = None) -> GameOrchestrator:
    global global_storyteller

    backend, backend_mode = build_backend(force_backend_mode)
    global_storyteller = StorytellerAgent(backend)
    state = GameState(
        phase=GamePhase.SETUP,
        players=(
            PlayerState(player_id="h1", name="Host", role_id="washerwoman", team=Team.GOOD),
        )
    )
    orchestrator = GameOrchestrator(state)
    orchestrator.storyteller_agent = global_storyteller
    orchestrator.default_agent_backend = backend
    logger.info("Initialized orchestrator with backend_mode=%s", backend_mode)
    return orchestrator


async def stop_game_loop_task() -> None:
    global global_game_loop_task

    task = global_game_loop_task
    global_game_loop_task = None
    if task and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def ensure_game_loop_running() -> bool:
    global global_game_loop_task

    if global_game_loop_task and not global_game_loop_task.done():
        return False
    global_game_loop_task = asyncio.create_task(run_game_loop_safe())
    return True


def collect_metrics(orchestrator: GameOrchestrator) -> dict[str, Any]:
    state = orchestrator.state
    events = list(state.event_log)
    recent_events = [
        {
            "event_type": event.event_type,
            "actor": event.actor,
            "target": event.target,
            "trace_id": event.trace_id,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }
        for event in events[-10:]
    ]
    nomination_prompted = [
        e for e in events
        if e.event_type in {"nomination_prompted", "nomination_window_opened"}
    ]
    nomination_attempted = [e for e in events if e.event_type == "nomination_attempted"]
    nominations = [e for e in events if e.event_type == "nomination_started"]
    votes = [e for e in events if e.event_type == "vote_cast"]
    executions = [e for e in events if e.event_type == "execution_resolved"]
    last_execution = executions[-1].payload if executions else None
    last_phase_event = next((e for e in reversed(events) if e.event_type == "phase_changed"), None)
    phase_duration_seconds = None
    if last_phase_event:
        phase_duration_seconds = round((datetime.now() - last_phase_event.timestamp).total_seconds(), 2)

    backend = orchestrator.default_agent_backend
    return {
        "game_id": state.game_id,
        "backend": {
            "type": backend.__class__.__name__ if backend else None,
            "model": backend.get_model_name() if backend else None,
        },
        "loop_running": bool(global_game_loop_task and not global_game_loop_task.done()),
        "phase": state.phase.value,
        "day_number": state.day_number,
        "round_number": state.round_number,
        "alive_count": state.alive_count,
        "phase_duration_seconds": phase_duration_seconds,
        "recent_events": recent_events,
        "nomination_prompt_count": len(nomination_prompted),
        "nomination_attempt_count": len(nomination_attempted),
        "legal_nomination_count": len(nominations),
        "vote_count": len(votes),
        "execution_count": len(executions),
        "last_execution": last_execution,
        "recent_event": recent_events[-1]["event_type"] if recent_events else None,
        "nomination_attempts": len(nomination_attempted),
        "legal_nominations": len(nominations),
        "vote_counts": len(votes),
        "latest_execution": last_execution,
    }


def resolve_viewer_mode(orchestrator: GameOrchestrator, player_id: str | None) -> str:
    config = orchestrator.state.config
    if not config or not player_id:
        return "observer"
    if config.storyteller_client_id and player_id == config.storyteller_client_id:
        return "storyteller"
    if config.human_mode == "player" and config.human_client_id == player_id:
        return "player"
    return "observer"


def can_view_grimoire(orchestrator: GameOrchestrator, player_id: str | None) -> bool:
    return resolve_viewer_mode(orchestrator, player_id) == "storyteller"


def build_private_info_list(orchestrator: GameOrchestrator, player_id: str | None) -> list[dict[str, Any]]:
    if not player_id:
        return []
    messages = [
        {
            "trace_id": event.trace_id,
            "phase": event.phase.value,
            "round_number": event.round_number,
            "payload": event.payload,
        }
        for event in orchestrator.state.event_log
        if event.event_type == "private_info_delivered" and event.target == player_id
    ]
    return messages[-10:]


def build_nomination_state(orchestrator: GameOrchestrator) -> dict[str, Any]:
    state = orchestrator.state
    nomination_state = dict(state.payload.get("nomination_state", {}))
    nomination_state.setdefault("game_id", state.game_id)
    nomination_state.setdefault("stage", "idle")
    terminal_stage = nomination_state.get("stage", "idle") in {"executed", "no_nomination", "invalid_nomination"}
    terminal_result = nomination_state.get("result_phase") in {"execution_resolved", "no_nomination", "invalid_nomination"}
    if "result_phase" not in nomination_state:
        stage = nomination_state.get("stage", "idle")
        inferred_phase = {
            "no_nomination": "no_nomination",
            "invalid_nomination": "invalid_nomination",
            "resolved": "vote_resolved",
            "executed": "execution_resolved",
            "window_open": "window_open",
            "nomination": "nomination_started",
            "defense": "defense_started",
            "voting": "vote_resolved",
        }.get(stage)
        if inferred_phase:
            nomination_state["result_phase"] = inferred_phase
    if terminal_stage or terminal_result:
        nomination_state["current_nominator"] = None
        nomination_state["current_nominee"] = None
        nomination_state["votes_cast"] = 0
        nomination_state["yes_votes"] = 0
        nomination_state["votes"] = {}
    elif state.current_nominator is not None:
        nomination_state["current_nominator"] = state.current_nominator
    else:
        nomination_state.setdefault("current_nominator", None)
    if terminal_stage or terminal_result:
        nomination_state["current_nominee"] = None
    elif state.current_nominee is not None:
        nomination_state["current_nominee"] = state.current_nominee
    else:
        nomination_state.setdefault("current_nominee", None)
    if terminal_stage or terminal_result:
        nomination_state["votes_cast"] = 0
        nomination_state["yes_votes"] = 0
        nomination_state["votes"] = {}
    elif state.votes_today:
        nomination_state["votes_cast"] = len(state.votes_today)
        nomination_state["yes_votes"] = sum(1 for vote in state.votes_today.values() if vote)
        nomination_state["votes"] = dict(state.votes_today)
    else:
        nomination_state.setdefault("votes_cast", 0)
        nomination_state.setdefault("yes_votes", 0)
        nomination_state.setdefault("votes", {})
    history = list(state.payload.get("nomination_history", []))
    if not history:
        inferred_history: list[dict[str, Any]] = []
        for event in state.event_log:
            if event.event_type == "nomination_started":
                inferred_history.append(
                    {
                        "kind": "nomination_started",
                        "round": len([item for item in inferred_history if item.get("kind") == "nomination_started"]) + 1,
                        "nominator": event.actor,
                        "nominee": event.target,
                        "trace_id": event.trace_id,
                    }
                )
            elif event.event_type == "voting_resolved":
                inferred_history.append(
                    {
                        "kind": "voting_resolved",
                        "round": len([item for item in inferred_history if item.get("kind") == "voting_resolved"]) + 1,
                        "nominee": event.target,
                        "votes": event.payload.get("votes"),
                        "needed": event.payload.get("needed"),
                        "passed": event.payload.get("passed"),
                        "trace_id": event.trace_id,
                    }
                )
            elif event.event_type == "execution_resolved":
                inferred_history.append(
                    {
                        "kind": "execution_resolved",
                        "round": len([item for item in inferred_history if item.get("kind") == "execution_resolved"]) + 1,
                        "executed": event.payload.get("executed"),
                        "votes": event.payload.get("votes"),
                        "reason": event.payload.get("reason"),
                        "trace_id": event.trace_id,
                    }
                )
        history = inferred_history[-12:]
    nomination_state["history"] = history
    nomination_state["has_history"] = bool(history)
    is_terminal = terminal_stage or terminal_result
    nomination_state["has_current_round"] = bool(
        not is_terminal
        and (
            nomination_state.get("stage") in {"window_open", "nomination", "defense", "voting", "resolved"}
            or nomination_state.get("current_nominator")
            or nomination_state.get("current_nominee")
            or nomination_state.get("defense_text")
            or nomination_state.get("votes")
        )
    )
    nomination_state["is_terminal"] = is_terminal
    nomination_state["threshold"] = (state.alive_count // 2) + 1 if state.alive_count else 0
    return nomination_state


def decorate_ws_message_with_game_id(message: str, orchestrator: GameOrchestrator | None) -> str:
    if not orchestrator:
        return message
    try:
        payload = json.loads(message)
    except Exception:
        return message
    if not isinstance(payload, dict):
        return message
    payload["game_id"] = orchestrator.state.game_id
    return json.dumps(payload, ensure_ascii=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_orchestrator
    try:
        global_orchestrator = build_fresh_orchestrator()
        ensure_game_loop_running()
        logger.info("Global Orchestrator started in SETUP phase.")
    except Exception as e:
        logger.error(f"Failed to startup: {e}", exc_info=True)
    yield
    await stop_game_loop_task()

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
        orchestrator = global_orchestrator
        if not orchestrator:
            return
        logger.info("Starting safe game loop background task...")
        await orchestrator.run_game_loop()
    except asyncio.CancelledError:
        logger.info("Game loop background task cancelled.")
        raise
    except Exception as e:
        logger.error(f"Game loop crashed: {e}", exc_info=True)

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/ui/index.html")

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    await manager.connect(websocket, player_id)
    async def send_message_with_session(message: str) -> None:
        await manager.send_personal_message(decorate_ws_message_with_game_id(message, global_orchestrator), player_id)
    async def chat_callback(sender_id: str, content: str, is_private: bool) -> None:
        orchestrator = global_orchestrator
        if orchestrator:
            await orchestrator.handle_chat(sender_id, content, is_private)
    if player_id not in human_agents:
        agent = HumanAgent(
            player_id=player_id, 
            name=f"Human_{player_id}", 
            send_message_callback=send_message_with_session,
            chat_callback=chat_callback
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
    human_mode = data.get("human_mode", "player")
    human_client_id = data.get("human_client_id") or host_id
    storyteller_client_id = data.get("storyteller_client_id") or (human_client_id if human_mode == "storyteller" else None)
    is_human = human_mode == "player"
    discussion_rounds = data.get("discussion_rounds")
    audit_mode = bool(data.get("audit_mode", False))
    max_nomination_rounds = data.get("max_nomination_rounds")
    
    if player_count < 5 or player_count > 15:
        return {"status": "error", "message": "Player count must be between 5 and 15"}

    try:
        await global_orchestrator.run_setup_with_options(
            player_count=player_count,
            host_id=host_id,
            is_human=is_human,
            discussion_rounds=discussion_rounds,
            audit_mode=audit_mode,
            max_nomination_rounds=max_nomination_rounds,
            backend_mode=os.getenv("BOTC_BACKEND", "auto"),
            human_mode=human_mode,
            human_client_id=human_client_id,
            storyteller_client_id=storyteller_client_id,
        )
    except RuntimeError as exc:
        return {"status": "error", "message": str(exc)}
    return {
        "status": "ok",
        "message": f"Game setup for {player_count} players started",
        "human_mode": human_mode,
        "human_client_id": human_client_id if human_mode == "player" else None,
        "storyteller_client_id": storyteller_client_id,
    }

@app.post("/api/game/start")
async def start_game():
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    started = ensure_game_loop_running()
    return {
        "status": "ok",
        "message": "Game loop started" if started else "Game loop already running",
        "already_running": not started,
    }

@app.post("/api/game/reset")
async def reset_game(data: Dict[str, Any] | None = None):
    global global_orchestrator, human_agents
    logger.info("Resetting game orchestrator and sessions.")
    await stop_game_loop_task()
    backend_mode = data.get("backend_mode") if isinstance(data, dict) else None
    global_orchestrator = build_fresh_orchestrator(backend_mode)
    human_agents.clear()
    ensure_game_loop_running()
    return {"status": "ok", "message": "Game reset to SETUP phase"}

@app.get("/api/game/roles")
async def get_roles():
    """获取所有角色及其说明 (用于手册)"""
    from src.engine.roles.base_role import get_all_role_ids, get_role_class
    roles_info = []
    for rid in get_all_role_ids():
        cls = get_role_class(rid)
        if cls:
            defn = cls.get_definition()
            term = get_role_term(rid)
            roles_info.append({
                "role_id": rid,
                "name": term["zh_name"] if term else defn.name,
                "name_en": term["en_name"] if term else defn.name_en,
                "team": defn.team.value,
                "type": defn.role_type.value,
                "description": term["description"] if term else defn.ability.description,
                "trigger": defn.ability.trigger.value
            })
    return {"roles": roles_info}

@app.get("/api/game/state")
async def get_game_state(player_id: str = None):
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    orchestrator = global_orchestrator
    state = orchestrator.state
    viewer_mode = resolve_viewer_mode(orchestrator, player_id)
    is_observer = viewer_mode == "observer"
    
    data = {
        "game_id": state.game_id,
        "round_number": state.round_number,
        "day_number": state.day_number,
        "phase": state.phase.value,
        "alive_count": state.alive_count,
        "current_nominee": state.current_nominee,
        "current_nominator": state.current_nominator,
        "viewer_mode": viewer_mode,
        "human_mode": state.config.human_mode if state.config else "none",
        "is_observer": is_observer,
        "can_view_grimoire": can_view_grimoire(orchestrator, player_id),
        "nomination_state": build_nomination_state(orchestrator),
        "private_info": build_private_info_list(orchestrator, player_id) if viewer_mode == "player" else [],
        "players": []
    }
    
    # 按照座位顺序返回玩家列表
    ordered_ids = state.seat_order if state.seat_order else [p.player_id for p in state.players]
    player_map = {p.player_id: p for p in state.players}
    
    for pid in ordered_ids:
        p = player_map.get(pid)
        if not p: continue
        p_info = {
            "player_id": p.player_id,
            "name": p.name,
            "is_alive": p.is_alive,
        }
        # 仅玩家本人看到自己的角色与私密状态
        if viewer_mode == "player" and player_id == p.player_id:
            # 如果是该玩家本人且有虚假身份(如酒鬼)，则返回虚假身份供其展示
            display_role = p.perceived_role_id or p.fake_role or p.role_id
                
            p_info.update({
                "role_id": display_role,
                "team": (p.current_team or p.team).value,
                "is_poisoned": p.is_poisoned,
                "is_drunk": p.is_drunk,
            })
        
        if viewer_mode == "storyteller":
             p_info.update({
                "true_role_id": p.true_role_id,
                "perceived_role_id": p.perceived_role_id,
                "fake_role": p.fake_role,
                "team": (p.current_team or p.team).value,
                "is_poisoned": p.is_poisoned,
                "is_drunk": p.is_drunk,
            })
        
        data["players"].append(p_info)
    return data

@app.get("/api/game/grimoire")
async def get_grimoire(player_id: str | None = None, view: str = "full"):
    """获取说书人专用魔典信息"""
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    if not can_view_grimoire(global_orchestrator, player_id):
        raise HTTPException(status_code=403, detail="只有说书人可以查看魔典")
    
    grimoire = global_orchestrator.state.grimoire
    if not grimoire:
        return {"players": []}
        
    return grimoire.model_dump() if view == "full" else {"players": grimoire.players}

@app.get("/api/game/metrics")
async def get_game_metrics():
    if not global_orchestrator:
        return {"status": "error", "message": "Orchestrator not initialized"}
    return collect_metrics(global_orchestrator)

@app.post("/api/storyteller/night/next")
async def storyteller_night_next():
    if not global_orchestrator or not global_orchestrator.storyteller_agent:
        return {"status": "error", "message": "Storyteller not initialized"}
    phase = global_orchestrator.state.phase
    return await global_orchestrator.storyteller_agent.get_human_storyteller_step(global_orchestrator.state, phase)

@app.post("/api/storyteller/night/resolve")
async def storyteller_night_resolve(data: Dict[str, Any]):
    return {"status": "ok", "payload": data}

@app.post("/api/storyteller/info/confirm")
async def storyteller_info_confirm(data: Dict[str, Any]):
    return {"status": "ok", "payload": data}

if __name__ == "__main__":
    import uvicorn
    # 使用 app 对象而不是字符串，确保在同一个进程中运行且日志配置生效
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
