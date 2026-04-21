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
class ClaimRecord:
    """对公开身份相关发言的结构化记录。"""
    role_id: str
    claim_type: str
    source_text: str = ""
    round_number: int | None = None
    day_number: int | None = None
    speaker_id: str | None = None
    speaker_name: str | None = None


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
    # 公开宣称身份
    claimed_role_id: Optional[str] = None
    claim_history: list[ClaimRecord] = field(default_factory=list)


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
            profile.notes = profile.notes[-12:]

    def record_claim(
        self,
        player_id: str,
        role_id: str,
        claim_type: str,
        *,
        source_text: str = "",
        round_number: int | None = None,
        day_number: int | None = None,
        speaker_id: str | None = None,
        speaker_name: str | None = None,
    ) -> None:
        """记录某玩家的公开身份相关发言。"""
        profile = self.get_profile(player_id)
        if profile:
            previous_claim = profile.claimed_role_id
            record = ClaimRecord(
                role_id=role_id,
                claim_type=claim_type,
                source_text=source_text,
                round_number=round_number,
                day_number=day_number,
                speaker_id=speaker_id,
                speaker_name=speaker_name,
            )
            profile.claim_history.append(record)
            profile.claim_history = profile.claim_history[-12:]
            if claim_type == "self_claim":
                if previous_claim and previous_claim != role_id:
                    profile.notes.append(f"公开身份从 {previous_claim} 改成 {role_id}，存在改口/冲突")
                profile.claimed_role_id = role_id
            elif claim_type == "denial" and profile.claimed_role_id == role_id:
                profile.claimed_role_id = None
                profile.notes.append(f"明确否认自己是 {role_id}")
            profile.notes = profile.notes[-12:]

    def _format_claim_record(self, record: ClaimRecord) -> str:
        marker = f"D{record.day_number or '-'}R{record.round_number or '-'}"
        if record.claim_type == "self_claim":
            return f"{marker} 自报 {record.role_id}"
        if record.claim_type == "denial":
            return f"{marker} 否认 {record.role_id}"
        if record.claim_type == "question":
            speaker = record.speaker_name or record.speaker_id or "有人"
            return f"{marker} {speaker} 质疑其像 {record.role_id}"
        if record.claim_type == "accusation":
            speaker = record.speaker_name or record.speaker_id or "有人"
            return f"{marker} {speaker} 指认为 {record.role_id}"
        return f"{marker} {record.claim_type} {record.role_id}"

    def update_claim(self, player_id: str, role_id: str) -> None:
        """兼容旧接口，默认按自报处理。"""
        self.record_claim(player_id, role_id, "self_claim")

    def claim_conflict_count(self, player_id: str) -> int:
        profile = self.get_profile(player_id)
        if not profile or len(profile.claim_history) < 2:
            return 0
        conflicts = 0
        previous_self_claim: str | None = None
        for record in profile.claim_history:
            if record.claim_type == "self_claim":
                if previous_self_claim and previous_self_claim != record.role_id:
                    conflicts += 1
                previous_self_claim = record.role_id
            elif record.claim_type == "denial" and previous_self_claim == record.role_id:
                conflicts += 1
        return conflicts

    def claim_signal_summary(self, player_id: str) -> dict[str, int]:
        profile = self.get_profile(player_id)
        if not profile:
            return {"self_claim": 0, "denial": 0, "question": 0, "accusation": 0, "conflicts": 0}
        counts = {"self_claim": 0, "denial": 0, "question": 0, "accusation": 0}
        for record in profile.claim_history:
            if record.claim_type in counts:
                counts[record.claim_type] += 1
        counts["conflicts"] = self.claim_conflict_count(player_id)
        return counts

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
            if prof.claimed_role_id:
                summary.append(f"- {prof.name} 公开跳身份为: {prof.claimed_role_id}")
            elif prof.claim_history:
                latest_claim = prof.claim_history[-1]
                if latest_claim.claim_type == "denial":
                    summary.append(f"- {prof.name} 明确否认自己是: {latest_claim.role_id}")
            if prof.claim_history:
                recent_claims = prof.claim_history[-2:]
                claim_text = "; ".join(self._format_claim_record(record) for record in recent_claims)
                summary.append(f"- {prof.name} 的身份发言记录: {claim_text}")
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
                "notes_count": len(prof.notes),
                "claimed_role_id": prof.claimed_role_id,
                "claim_history_count": len(prof.claim_history),
                "recent_claims": [self._format_claim_record(record) for record in prof.claim_history[-3:]],
            }
        return json.dumps(data, ensure_ascii=False)
