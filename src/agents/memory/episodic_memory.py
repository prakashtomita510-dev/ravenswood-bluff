"""
情节记忆 (Episodic Memory)

存储过去每个阶段的结构化摘要，类似于短期记忆，可以跨越多个轮次保留。
"""

from __future__ import annotations

from src.state.game_state import GamePhase


class Episode:
    """
    一个情景单元，例如"第一天的白天讨论"的摘要
    """
    def __init__(
        self,
        phase: GamePhase,
        round_number: int,
        day_number: int,
        summary: str,
    ):
        self.phase = phase
        self.round_number = round_number
        self.day_number = day_number
        self.summary = summary
        self.key_events: list[str] = []  # 关键事件（如某人提名，某人死亡等）


class EpisodicMemory:
    """
    情节记忆管理器
    
    在工作记忆因阶段转变而被清空之前，Agent会将工作记忆中的内容总结为一个情景单元(Episode)
    存入此处，以便需要时回顾过去发生了什么。
    """

    def __init__(self) -> None:
        self.episodes: list[Episode] = []

    def add_episode(self, episode: Episode) -> None:
        """添加一个记忆片段"""
        self.episodes.append(episode)

    def get_summary(self, max_episodes: int = 5) -> str:
        """
        获取过去的情节摘要，提供给LLM作为历史背景
        """
        if not self.episodes:
            return "游戏才刚刚开始，你还没有过去的记忆。"

        recent = self.episodes[-max_episodes:]
        text_blocks = []
        text_blocks.append("【往期回忆摘要】")
        for ep in recent:
            if ep.phase in (GamePhase.DAY_DISCUSSION, GamePhase.NOMINATION, GamePhase.VOTING):
                title = f">> 第{ep.day_number}天 白天"
            else:
                title = f">> 第{ep.round_number}天 夜晚"
                
            text_blocks.append(title)
            text_blocks.append(ep.summary)
            if ep.key_events:
                for event in ep.key_events:
                    text_blocks.append(f"  * {event}")
        
        return "\n".join(text_blocks)
