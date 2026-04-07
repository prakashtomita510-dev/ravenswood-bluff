"""
社交图谱 (Social Graph)

维护Agent对其他玩家的信任度、身份推理和阵营推测。
这是社交推理能力的核心数据结构。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerProfile:
    """Agent心中对某个特定玩家的侧写"""
    player_id: str
    name: str
    
    # 信任度：-1.0 (绝对是坏人) 到 1.0 (绝对是好人)
    # 初始倾向为 0.0（中立）
    trust_score: float = 0.0
    
    # 身份推测字典: role_id -> 概率 (0.0~1.0)
    # 例如可能觉得某人是洗衣妇的概率有 0.8
    role_beliefs: dict[str, float] = field(default_factory=dict)
    
    # 阵营推测: "good" -> % , "evil" -> %
    alignment_beliefs: dict[str, float] = field(default_factory=lambda: {"good": 0.5, "evil": 0.5})
    
    # 对玩家历史发言一致性/疑点的文字记录
    notes: list[str] = field(default_factory=list)


class SocialGraph:
    """
    社交推理图谱
    """

    def __init__(self, my_player_id: str) -> None:
        self.my_player_id = my_player_id
        self.profiles: dict[str, PlayerProfile] = {}

    def init_player(self, player_id: str, name: str) -> None:
        """初始化一个玩家画像"""
        if player_id not in self.profiles and player_id != self.my_player_id:
            self.profiles[player_id] = PlayerProfile(player_id=player_id, name=name)

    def get_profile(self, player_id: str) -> Optional[PlayerProfile]:
        return self.profiles.get(player_id)

    def update_trust(self, player_id: str, delta: float) -> None:
        """更新信任度分值，限制在 [-1.0, 1.0]"""
        profile = self.get_profile(player_id)
        if profile:
            profile.trust_score = max(-1.0, min(1.0, profile.trust_score + delta))

    def add_note(self, player_id: str, note: str) -> None:
        """添加观察笔记"""
        profile = self.get_profile(player_id)
        if profile:
            profile.notes.append(note)

    def get_graph_summary(self) -> str:
        """输出社交图谱的文字摘要，给 LLM 参考"""
        if not self.profiles:
            return "你目前对其他人没有任何了解或信任偏好。"
            
        summary = ["【你心中的社交图谱】"]
        
        # 将信任度分为几个梯队
        trusted = []
        neutral = []
        suspicious = []
        
        for pid, prof in self.profiles.items():
            if prof.trust_score >= 0.4:
                trusted.append(f"{prof.name} (信任+{prof.trust_score:.1f})")
            elif prof.trust_score <= -0.4:
                suspicious.append(f"{prof.name} (怀疑{prof.trust_score:.1f})")
            else:
                neutral.append(f"{prof.name} (中立)")
                
        if trusted:
            summary.append(f"🟢 你比较信任的人: {', '.join(trusted)}")
        if suspicious:
            summary.append(f"🔴 你高度怀疑的人: {', '.join(suspicious)}")
        if neutral:
            summary.append(f"⚪ 你持保留态度的人: {', '.join(neutral)}")
            
        # 加上最近的推理笔记
        for pid, prof in self.profiles.items():
            if prof.notes:
                # 只取最近2条笔记
                recent_notes = prof.notes[-2:]
                notes_text = "; ".join(recent_notes)
                if len(notes_text) > 50:
                    notes_text = notes_text[:50] + "..."
                summary.append(f"- 关于 {prof.name} 的分析: {notes_text}")

        return "\n".join(summary)

    def dump_json(self) -> str:
        """导出 JSON 用于持久化/调试"""
        data = {}
        for pid, prof in self.profiles.items():
            data[pid] = {
                "name": prof.name,
                "trust_score": prof.trust_score,
                "notes_count": len(prof.notes)
            }
        return json.dumps(data, ensure_ascii=False)
