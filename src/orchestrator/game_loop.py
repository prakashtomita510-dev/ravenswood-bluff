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
from src.state.game_state import GameEvent, GamePhase, GameState, Visibility, Team
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

    async def run_game_loop(self) -> Team:
        """
        运行完整游戏主循环直到分出胜负
        """
        logger.info("=== 游戏开始 ===")
        # 保存初始快照
        self.snapshot_manager.take_snapshot(self.state)

        # 进入第一夜
        await self._transition_and_run(GamePhase.FIRST_NIGHT)
        
        while not self.winner:
            # 胜负判定
            self.winner = VictoryChecker.check_victory(self.state)
            if self.winner:
                logger.info(f"=== 游戏结束: {self.winner.value} 获胜 ===")
                break
                
            current_phase = self.phase_manager.current_phase
            
            if current_phase == GamePhase.FIRST_NIGHT or current_phase == GamePhase.NIGHT:
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
        self.phase_manager.transition_to(target_phase)
        self.state = self.state.with_update(
            phase=target_phase,
            round_number=self.phase_manager.round_number
        )
        
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
        if target_phase == GamePhase.FIRST_NIGHT:
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
    
    async def _run_first_night(self) -> None:
        """第一夜：发身份，邪恶阵营互相认识，无刀"""
        # 发身份和给信息的逻辑
        
        # 在这里简化演示：找能发信息的角色（比如洗衣妇）发信息
        await self._distribute_night_info()

    async def _run_night(self) -> None:
        """普通夜晚：技能释放"""
        # 按夜晚行动顺序调用（需支持根据剧本排序）
        # 这里简化：我们遍历所有存活且有行动技能的角色
        
        # 先发信息
        await self._distribute_night_info()
        
        # 接收行动 (比如投毒，杀人)
        # 这里应该以严格的行动顺序(night_order)请求
        for p in self.state.get_alive_players():
            role_cls = get_role_class(p.role_id)
            if not role_cls: continue
            
            # 在真实逻辑中，我们会请求 Agent 行动
            if p.player_id in self.broker.agents:
                agent = self.broker.agents[p.player_id]
                action = await agent.act(self.state, "night_action")
                
                if action.get("action") == "night_action" and action.get("target"):
                    target = action["target"]
                    try:
                        role_inst = role_cls()
                        # 执行技能并更新状态
                        new_state, events = role_inst.execute_ability(
                            self.state, p, target=target
                        )
                        self.state = new_state
                        for e in events:
                            await self.event_bus.publish(e)
                            self.state = self.state.with_event(e)
                    except Exception as e:
                        logger.warning(f"夜晚行动失败: {e}")

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
        """白天自由讨论环节"""
        # 让每个存活玩家或者死人进行发言
        # 在AI驱动的纯文字版中，可以用按座次发言的方式，多轮循环直到大家都不想说了
        # 或者简化为每人发一轮言
        for p in self.state.players:
            if p.player_id in self.broker.agents:
                agent = self.broker.agents[p.player_id]
                action = await agent.act(self.state, "speak")
                if action.get("action") == "speak" and action.get("content"):
                    e = GameEvent(
                        event_type="player_speaks",
                        phase=GamePhase.DAY_DISCUSSION,
                        round_number=self.state.round_number,
                        actor=p.player_id,
                        visibility=Visibility.PUBLIC,
                        payload={"content": action["content"], "tone": action.get("tone", "calm")}
                    )
                    await self.event_bus.publish(e)
                    self.state = self.state.with_event(e)

    async def _run_nomination_phase(self) -> None:
        """提名环节。由于这里没人干预，我们可以让Agent轮流决定是否提名"""
        for nominator_p in self.state.get_alive_players():
            if nominator_p.player_id in self.broker.agents:
                agent = self.broker.agents[nominator_p.player_id]
                action = await agent.act(self.state, "nominate")
                
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
