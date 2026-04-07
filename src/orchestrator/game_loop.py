"""
游戏主循环 (Game Orchestrator)

驱动整个游戏进行的顶层控制器。
"""

from __future__ import annotations

import asyncio
import logging

from src.agents.base_agent import BaseAgent
from src.engine.phase_manager import PhaseManager
from src.engine.nomination import NominationManager
from src.engine.roles.base_role import get_role_class
from src.engine.victory_checker import VictoryChecker
from src.orchestrator.event_bus import EventBus
from src.orchestrator.information_broker import InformationBroker
from src.state.event_log import EventLog
from src.state.game_state import GameEvent, GamePhase, GameState, Visibility, Team, PlayerStatus, PlayerState
from src.state.snapshot import SnapshotManager

logger = logging.getLogger(__name__)


class GameOrchestrator:
    """顶级容器，协调 Engine(规则), Agent(玩家), 和 State(数据)"""

    def __init__(self, initial_state: GameState):
        self.state = initial_state
        self.phase_manager = PhaseManager()
        self.event_bus = EventBus()
        self.event_log = EventLog()
        self.snapshot_manager = SnapshotManager()
        self.broker = InformationBroker()
        
        # 记录每回合的获胜队伍
        self.winner: Team | None = None

        # 监听所有事件并录入日志和广播
        self.event_bus.subscribe("*", self._on_any_event, priority=0)

    def register_agent(self, agent: BaseAgent) -> None:
        """注册玩家代理"""
        self.broker.register_agent(agent)
        # 同步初始角色和阵营
        player_state = self.state.get_player(agent.player_id)
        if player_state:
            agent.synchronize_role(player_state)

    async def _on_any_event(self, event: GameEvent) -> None:
        """中心事件分发与记录"""
        self.event_log.append(event)
        # 通过 Broker 路由事件视野
        await self.broker.broadcast_event(event, self.state)

    async def run_setup(self, player_count: int, host_id: str):
        """由外部(API)调用，完成准备并启动"""
        if self.phase_manager.current_phase != GamePhase.SETUP:
            return
        
        logger.info(f"开始配置游戏: {player_count} 人局")
        from src.engine.scripts import SCRIPTS, distribute_roles
        script = SCRIPTS["trouble_brewing"]
        
        # 1. 分配角色
        role_ids = distribute_roles(script, player_count)
        
        # 2. 初始化玩家列表
        new_players = []
        # 保留已连接的人类玩家(虽然目前只有一个 h1)
        human_p = self.state.get_player(host_id)
        
        for i in range(player_count):
            p_id = f"p{i+1}"
            role_id = role_ids[i]
            
            # 判断阵营
            from src.engine.roles.base_role import get_role_class
            from src.state.game_state import RoleType
            cls = get_role_class(role_id)
            team = cls.get_definition().team if cls else Team.GOOD
            
            p_name = f"Player {i+1}"
            if p_id == host_id and human_p:
                p_name = human_p.name
                
            # 处理酒鬼 (Drunken)
            fake_role = None
            is_drunk = False
            if role_id == "drunken":
                is_drunk = True
                # 随机选一个不在场上的村民
                import random
                in_play = set(role_ids)
                townsfolk_pool = [r for r in script.roles if get_role_class(r).get_definition().role_type == RoleType.TOWNSFOLK and r not in in_play]
                fake_role = random.choice(townsfolk_pool) if townsfolk_pool else "washerwoman"
            
            new_players.append(PlayerState(
                player_id=p_id,
                name=p_name,
                role_id=role_id,
                team=team,
                fake_role=fake_role,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.DRUNK) if is_drunk else (PlayerStatus.ALIVE,)
            ))
            
        from src.state.game_state import GameConfig
        self.state = self.state.with_update(
            players=tuple(new_players),
            config=GameConfig(player_count=player_count)
        )
        self._update_grimoire()
        
        # 3. 注册 AI 代理 (为非人类玩家)
        from src.agents.ai_agent import AIAgent, Persona
        from src.llm.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        
        for p in self.state.players:
            if p.player_id not in self.broker.agents:
                # 随机生成个性
                agent = AIAgent(p.player_id, p.name, backend, Persona("普通的村民", "比较安静观察"))
                self.register_agent(agent)
                
        # 4. 标志准备完成，由 run_game_loop 继续
        self._setup_done.set_result(True)

    async def run_game_loop(self) -> Team:
        """
        运行完整游戏主循环直到分出胜负
        """
        self._setup_done = asyncio.get_running_loop().create_future()
        logger.info("=== 游戏开始 ===")
        # 保存初始快照
        self.snapshot_manager.take_snapshot(self.state)

        # 进入准备阶段
        await self._transition_and_run(GamePhase.SETUP)
        
        while not self.winner:
            # 胜负判定
            self.winner = VictoryChecker.check_victory(self.state)
            if self.winner:
                logger.info(f"=== 游戏结束: {self.winner.value} 获胜 ===")
                break
                
            current_phase = self.phase_manager.current_phase
            
            if current_phase == GamePhase.SETUP:
                # 等待外部调用 run_setup
                await self._setup_done
                await self._transition_and_run(GamePhase.FIRST_NIGHT)
            elif current_phase == GamePhase.FIRST_NIGHT or current_phase == GamePhase.NIGHT:
                await self._transition_and_run(GamePhase.DAY_DISCUSSION)
            elif current_phase == GamePhase.DAY_DISCUSSION:
                await self._transition_and_run(GamePhase.NOMINATION)
            elif current_phase == GamePhase.NOMINATION:
                if self.state.current_nominee:
                    await self._transition_and_run(GamePhase.VOTING)
                else:
                    await self._transition_and_run(GamePhase.NIGHT)
            elif current_phase == GamePhase.VOTING:
                await self._transition_and_run(GamePhase.EXECUTION)
            elif current_phase == GamePhase.EXECUTION:
                await self._transition_and_run(GamePhase.NIGHT)
            else:
                break
                
        return self.winner

    async def _transition_and_run(self, target_phase: GamePhase) -> None:
        """转变阶段并运行该阶段的主逻辑"""
        print(f"\n>>> [系统] 转变阶段至: {target_phase.value} (第 {self.phase_manager.round_number} 轮)")
        self.phase_manager.transition_to(target_phase)
        self.state = self.state.with_update(
            phase=target_phase,
            round_number=self.phase_manager.round_number,
            day_number=self.phase_manager.day_number
        )
        
        # 给玩家一点反应时间
        import asyncio
        if target_phase != GamePhase.SETUP:
            await asyncio.sleep(2)
        
        # 宣布阶段变更 (公开事件)
        phase_event = GameEvent(
            event_type="phase_change",
            phase=target_phase,
            round_number=self.phase_manager.round_number,
            visibility=Visibility.PUBLIC,
            payload={"day_number": self.phase_manager.day_number}
        )
        await self.event_bus.publish(phase_event)
        self.state = self.state.with_event(phase_event)
        self.snapshot_manager.take_snapshot(self.state)
        
        # 执行具体阶段的协调逻辑
        if target_phase == GamePhase.SETUP:
            await self._run_setup_phase()
        elif target_phase == GamePhase.FIRST_NIGHT:
            await self._run_first_night()
        elif target_phase == GamePhase.NIGHT:
            await self._run_night()
        elif target_phase == GamePhase.DAY_DISCUSSION:
            await self._run_day_discussion()
        elif target_phase == GamePhase.NOMINATION:
            await self._run_nomination_phase()
        elif target_phase == GamePhase.VOTING:
            await self._run_voting_phase()
        elif target_phase == GamePhase.EXECUTION:
            await self._run_execution_phase()

    # --------------- 具体阶段逻辑 ---------------
    
    async def _run_setup_phase(self) -> None:
        """准备阶段：系统在此等待 Host 通过 API 调用 run_setup"""
        logger.info("等说书人(h1)配置游戏人数...")
        # 此时 UI 呈现遮罩层，后端 run_game_loop 在等待 _setup_done 这个 Future
        pass

    async def _run_first_night(self) -> None:
        """首夜逻辑：身份告知、邪恶阵营互相认识及首夜信息分发"""
        logger.info("=== 第一夜开始 ===")
        self._update_grimoire()

        # 1. 邪恶阵营互相认识
        evil_players = [p for p in self.state.players if p.team == Team.EVIL]
        for ep in evil_players:
            teammates = [p.name for p in evil_players if p.player_id != ep.player_id]
            e = GameEvent(
                event_type="evil_reveal",
                phase=GamePhase.FIRST_NIGHT,
                round_number=self.state.round_number,
                target=ep.player_id,
                visibility=Visibility.PRIVATE,
                payload={"teammates": teammates}
            )
            await self.event_bus.publish(e)
            self.state = self.state.with_event(e)

        # 2. 分发初始信息 (洗衣妇、图书馆员等)
        await self._distribute_night_info()

        # 3. 执行首夜特定行动
        await self._execute_night_actions(GamePhase.FIRST_NIGHT)
        
        # 首夜结束后的 Grimoire 更新
        self._update_grimoire()

    def _update_grimoire(self) -> None:
        """生成最新的魔典视图供说书人使用"""
        from src.state.game_state import GrimoireInfo, PlayerGrimoireInfo
        grimoire_players = []
        for p in self.state.players:
            grimoire_players.append(PlayerGrimoireInfo(
                player_id=p.player_id,
                name=p.name,
                role_id=p.role_id,
                fake_role=p.fake_role,
                team=p.team,
                is_alive=p.is_alive,
                is_poisoned=p.is_poisoned,
                is_drunk=p.is_drunk
            ))
        self.state = self.state.with_update(
            grimoire=GrimoireInfo(players=tuple(grimoire_players))
        )

    async def _run_night(self) -> None:
        """普通夜晚：技能释放"""
        logger.info(f"=== 第 {self.state.round_number} 夜开始 ===")
        
        # 1. 分发信息
        await self._distribute_night_info()
        
        # 2. 执行行动
        await self._execute_night_actions(GamePhase.NIGHT)

    async def _execute_night_actions(self, phase: GamePhase) -> None:
        """执行当前相位的所有合法行动"""
        players_to_act = []
        for p in self.state.get_alive_players():
            role_cls = get_role_class(p.role_id)
            if role_cls:
                role_inst = role_cls()
                if role_inst.can_act_at_phase(self.state, phase):
                    players_to_act.append((p, role_inst))
        
        # 排序
        players_to_act.sort(key=lambda x: x[1].get_definition().ability.night_order if x[1].get_definition().ability else 99)

        for p, role_inst in players_to_act:
            if p.player_id in self.broker.agents:
                agent = self.broker.agents[p.player_id]
                logger.info(f"[{phase.value}] 请求玩家 {agent.name}({agent.player_id}) 执行行动: night_action")
                try:
                    action = await agent.act(self.state, "night_action")
                    logger.info(f"[{phase.value}] 玩家 {agent.name} 返回行动: {action}")
                except Exception as e:
                    logger.error(f"[{phase.value}] 玩家 {agent.player_id} 行动执行异常: {e}", exc_info=True)
                    continue
                
                if action.get("action") == "night_action" and action.get("target"):
                    target = action["target"]
                    try:
                        for e in events:
                            await self.event_bus.publish(e)
                            self.state = self.state.with_event(e)
                    except Exception as e:
                        logger.warning(f"夜晚行动效果结算失败: {e}")

    async def _distribute_night_info(self) -> None:
        """给需要获取信息的角色分发信息事件"""
        for p in self.state.get_alive_players():
            role_cls = get_role_class(p.role_id)
            if role_cls:
                info = role_cls().get_night_info(self.state, p)
                if info:
                    e = GameEvent(
                        event_type="night_info",
                        phase=self.phase_manager.current_phase,
                        round_number=self.phase_manager.round_number,
                        target=p.player_id,
                        visibility=Visibility.PRIVATE,
                        payload=info
                    )
                    await self.event_bus.publish(e)
                    self.state = self.state.with_event(e)

    async def _run_day_discussion(self) -> None:
        """白天自由讨论环节 — 支持多轮"""
        print(">>> [白天讨论] 讨论环节开始")
        
        # 每日开始时重置状态
        self.state = self.state.with_update(
            nominations_today=(),
            nominees_today=(),
            votes_today={},
            current_nominee=None,
            current_nominator=None
        )

        max_rounds = 3
        current_round = 0
        should_skip = False

        while current_round < max_rounds and not should_skip:
            current_round += 1
            print(f">>> [白天讨论] 第 {current_round} 轮发言开始")
            
            for p in self.state.players:
                if p.player_id in self.broker.agents:
                    agent = self.broker.agents[p.player_id]
                    # logger.info(f"[白天讨论] 等待玩家 {agent.name}({agent.player_id}) 发言...")
                    try:
                        action = await agent.act(self.state, "speak")
                        
                        if action.get("action") == "skip_discussion":
                            logger.info(f"玩家 {agent.name} 请求结束讨论。")
                            should_skip = True
                            break

                        if action.get("action") == "speak" and action.get("content"):
                            e = GameEvent(
                                event_type="player_speaks",
                                phase=GamePhase.DAY_DISCUSSION,
                                round_number=self.state.round_number,
                                actor=p.player_id,
                                visibility=Visibility.PUBLIC,
                                payload={
                                    "content": action["content"], 
                                    "tone": action.get("tone", "calm"),
                                    "round": current_round
                                }
                            )
                            await self.event_bus.publish(e)
                            self.state = self.state.with_event(e)
                    except Exception as e:
                        logger.error(f"[白天讨论] 玩家 {agent.player_id} 发言异常: {e}")
                        continue
            
            if should_skip: break
            # 轮次间稍微停顿
            await asyncio.sleep(0.5)

        print(">>> [白天讨论] 讨论环节结束")

    async def _run_nomination_phase(self) -> None:
        """提名环节。由于这里没人干预，我们可以让Agent轮流决定是否提名"""
        print(">>> [提名阶段] 环节开始")
        for nominator_p in self.state.get_alive_players():
            if nominator_p.player_id in self.broker.agents:
                agent = self.broker.agents[nominator_p.player_id]
                print(f">>> [提名阶段] 正在请求 {agent.name}({agent.player_id}) 进行提名决策...")
                action = await agent.act(self.state, "nominate")
                print(f">>> [提名阶段] {agent.name} 返回: {action}")
                
                # 如果决定提名
                if action.get("action") == "nominate" and action.get("target"):
                    target = action["target"]
                    try:
                        new_state, events = NominationManager.nominate(
                            self.state, nominator_p.player_id, target
                        )
                        self.state = new_state
                        for e in events:
                            await self.event_bus.publish(e)
                            self.state = self.state.with_event(e)
                        # 一旦有人发起提名并成功，就直接进入投票阶段循环
                        return
                    except Exception as e:
                        logger.warning(f"无效提名: {e}")

    async def _run_voting_phase(self) -> None:
        """依次进行拉票和投票"""
        if not self.state.current_nominee:
            return

        nominee = self.state.get_player(self.state.current_nominee)
        if nominee and nominee.player_id in self.broker.agents:
            agent = self.broker.agents[nominee.player_id]
            # 这里可以让被提名者做遗言辩护
            action = await agent.act(self.state, "defense_speech")
            if action.get("action") == "speak":
                e = GameEvent(
                    event_type="player_speaks",
                    phase=GamePhase.VOTING,
                    round_number=self.state.round_number,
                    actor=nominee.player_id,
                    visibility=Visibility.PUBLIC,
                    payload={"content": action["content"], "is_defense": True}
                )
                await self.event_bus.publish(e)
                self.state = self.state.with_event(e)

        # 收集投票
        for voter in self.state.players:
            if not voter.can_vote: continue
            
            if voter.player_id in self.broker.agents:
                agent = self.broker.agents[voter.player_id]
                action = await agent.act(self.state, "vote")
                
                vote_decision = action.get("decision", False)
                try:
                    new_state, events = NominationManager.cast_vote(
                        self.state, voter.player_id, vote_decision
                    )
                    self.state = new_state
                    for e in events:
                        await self.event_bus.publish(e)
                        self.state = self.state.with_event(e)
                except Exception as e:
                    logger.warning(f"投票无效: {e}")

        # 决算
        new_state, events = NominationManager.resolve_voting_round(self.state)
        self.state = new_state
        for e in events:
            await self.event_bus.publish(e)
            self.state = self.state.with_event(e)
            
    async def _run_execution_phase(self) -> None:
        """处决判定阶段"""
        # (简化) 查看事件里有没有达到处决标准的
        passed_events = [
            e for e in self.event_log.get_events_by_type("voting_result")
            if e.round_number == self.state.round_number and e.payload.get("passed")
        ]
        
        if passed_events:
            # 取得票数最高的那个 (这里简化假设只有一次提名的结果在事件里，或者取最后一个/票数最多的)
            # 假定最后一个 passed 的就是被处决的
            last_passed = passed_events[-1]
            target_id = last_passed.target
            if target_id:
                # 执行处决
                e = GameEvent(
                    event_type="player_death",
                    phase=GamePhase.EXECUTION,
                    round_number=self.state.round_number,
                    target=target_id,
                    actor="system",
                    visibility=Visibility.PUBLIC,
                    payload={"reason": "execution"}
                )
                await self.event_bus.publish(e)
                self.state = self.state.with_event(e)
                self.state = self.state.with_player_update(target_id, is_alive=False)

    def export_game_record(self, export_dir: str) -> None:
        """持久化输出事件日志和系统快照到外部文件系统，用于前端回放或调试"""
        import os
        import json
        
        os.makedirs(export_dir, exist_ok=True)
        # 导出快照
        snapshot_path = os.path.join(export_dir, "snapshots.json")
        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(self.snapshot_manager.export_to_json())
            
        # 导出事件
        event_path = os.path.join(export_dir, "events.json")
        events_data = [e.model_dump(mode="json") for e in self.event_log.events]
        with open(event_path, "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"游戏记录已持久化到目录: {export_dir}")
