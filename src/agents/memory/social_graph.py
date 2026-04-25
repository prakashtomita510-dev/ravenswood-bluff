"""
社交图谱 (Social Graph)

维护Agent对其他玩家的信任度、身份推理和阵营推测。
这是社交推理能力的核心数据结构。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional


logger = logging.getLogger(__name__)


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
    # 身份相关声明历史
    claim_history: list[ClaimRecord] = field(default_factory=list)
    # 当前自报的身份 (取代 claimed_role_id)
    current_self_claim: Optional[str] = None
    # 关于其他玩家的声明: subject_player_id -> list[ClaimRecord]
    claims_about_others: dict[str, list[ClaimRecord]] = field(default_factory=dict)
    # 发言冲突记录
    claim_conflicts: list[str] = field(default_factory=list)
    
    # [Task D] 记忆冻结状态：如果为 True，在摘要中将只显示极简总结，以节省空间
    is_frozen: bool = False
    frozen_summary: str = ""

    @property
    def claimed_role_id(self) -> Optional[str]:
        """兼容旧读取口径，等价于 current_self_claim。"""
        return self.current_self_claim


class SocialGraph:
    """
    社交推理图谱
    """

    def __init__(
        self,
        my_player_id: str,
        note_limit: int = 30,
        claim_limit: int = 20,
        summary_note_limit: int = 5,
        summary_claim_limit: int = 4
    ) -> None:
        self.my_player_id = my_player_id
        self.note_limit = note_limit
        self.claim_limit = claim_limit
        self.summary_note_limit = summary_note_limit
        self.summary_claim_limit = summary_claim_limit
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
            # 如果信任度发生剧烈波动，自动解冻以重新审视
            if abs(delta) > 0.3 and profile.is_frozen:
                self.thaw_player(player_id, "信任度剧烈波动")

    def freeze_player(self, player_id: str, summary: str) -> None:
        """冻结玩家记忆，转为摘要模式"""
        profile = self.get_profile(player_id)
        if profile:
            profile.is_frozen = True
            profile.frozen_summary = summary
            logger.info(f"Memory for player {player_id} is now FROZEN.")

    def thaw_player(self, player_id: str, reason: str = "") -> None:
        """解除冻结，恢复详细展示"""
        profile = self.get_profile(player_id)
        if profile:
            profile.is_frozen = False
            logger.info(f"Memory for player {player_id} is THAWED. Reason: {reason}")

    def add_note(self, player_id: str, note: str) -> None:
        """添加观察笔记"""
        profile = self.get_profile(player_id)
        if profile:
            profile.notes.append(note)
            profile.notes = profile.notes[-self.note_limit:]

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
            previous_claim = profile.current_self_claim
            previous_record = profile.claim_history[-1] if profile.claim_history else None
            if (
                previous_record
                and previous_record.role_id == role_id
                and previous_record.claim_type == claim_type
                and previous_record.day_number == day_number
                and previous_record.round_number == round_number
                and previous_record.source_text == source_text
            ):
                return
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
            profile.claim_history = profile.claim_history[-self.claim_limit:]
            if claim_type == "self_claim":
                if previous_claim and previous_claim != role_id:
                    profile.notes.append(f"公开身份从 {previous_claim} 改成 {role_id}，存在改口/冲突")
                    profile.claim_conflicts.append(f"D{day_number}R{round_number}: {previous_claim} -> {role_id}")
                profile.current_self_claim = role_id
            elif claim_type == "denial" and profile.current_self_claim == role_id:
                profile.current_self_claim = None
                profile.notes.append(f"明确否认自己是 {role_id}")
            profile.notes = profile.notes[-self.note_limit:]

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
                previous_self_claim = None
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

    def get_all_self_claims(self) -> dict[str, str]:
        """获取所有已知的玩家自报身份。"""
        return {
            pid: profile.current_self_claim
            for pid, profile in self.profiles.items()
            if profile.current_self_claim
        }

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
            if prof.is_frozen:
                # 冻结模式：只输出一行摘要
                status = " (已冻结/由于死亡或身份确认为已知)"
                summary.append(f"- 【{prof.name}】{status}: {prof.frozen_summary or '该玩家信息已归档。'}")
                continue

            if prof.current_self_claim:
                summary.append(f"- {prof.name} 公开跳身份为: {prof.current_self_claim}")
            elif prof.claim_history:
                latest_claim = prof.claim_history[-1]
                if latest_claim.claim_type == "denial":
                    summary.append(f"- {prof.name} 明确否认自己是: {latest_claim.role_id}")
            if prof.claim_history:
                recent_claims = prof.claim_history[-self.summary_claim_limit:]
                claim_text = "; ".join(self._format_claim_record(record) for record in recent_claims)
                summary.append(f"- {prof.name} 的身份发言记录: {claim_text}")
            if prof.notes:
                # 只取最近几条笔记
                recent_notes = prof.notes[-self.summary_note_limit:]
                notes_text = "; ".join(recent_notes)
                if len(notes_text) > 80:
                    notes_text = notes_text[:80] + "..."
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
                "current_self_claim": prof.current_self_claim,
                "claim_history_count": len(prof.claim_history),
                "recent_claims": [self._format_claim_record(record) for record in prof.claim_history[-3:]],
            }
        return json.dumps(data, ensure_ascii=False)
