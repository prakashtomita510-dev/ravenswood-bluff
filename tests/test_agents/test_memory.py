"""Phase 2 测试 - 记忆系统与社交图谱"""

import pytest
import json
from src.agents.memory.working_memory import WorkingMemory, Observation
from src.agents.memory.episodic_memory import EpisodicMemory, Episode
from src.agents.memory.social_graph import SocialGraph, PlayerProfile
from src.state.game_state import GamePhase


def test_working_memory():
    wm = WorkingMemory()
    assert wm.is_empty
    
    obs = Observation(
        observation_id="msg_1",
        content="玩家A发言了",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1
    )
    wm.add_observation(obs)
    wm.add_thought("A看起来像是个好人")
    
    assert not wm.is_empty
    
    context = wm.get_recent_context()
    assert "玩家A发言了" in context
    assert "内部推理" in context
    assert "A看起来像是个好人" in context
    
    wm.clear()
    assert wm.is_empty


def test_working_memory_clear_transient_preserves_impressions():
    wm = WorkingMemory()
    wm.add_observation(
        Observation(
            observation_id="msg_2",
            content="玩家B发言了",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1,
        )
    )
    wm.add_thought("B 有点可疑")
    wm.add_impression("B 喜欢回避问题")
    wm.remember_fact("Alice 昨天公开跳了预言家")
    wm.remember_private_info("night_info", "你昨晚查出 Bob 不是恶魔", day_number=1, round_number=1)

    wm.clear_transient()

    assert wm.is_empty
    assert wm.impressions == ["B 喜欢回避问题"]
    assert wm.anchor_facts == ["Alice 昨天公开跳了预言家"]
    assert wm.get_private_memory_summaries("night_info") == ["你昨晚查出 Bob 不是恶魔"]


def test_episodic_memory():
    em = EpisodicMemory()
    summary = em.get_summary()
    assert "还没有过去的记忆" in summary
    
    ep = Episode(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        day_number=1,
        summary="第一天大家都在划水"
    )
    ep.key_events.append("A提名了B")
    em.add_episode(ep)
    
    summary = em.get_summary()
    assert ">> 第1天 白天" in summary
    assert "第一天大家都在划水" in summary
    assert "A提名了B" in summary


def test_social_graph():
    sg = SocialGraph(my_player_id="p0")
    sg.init_player("p1", "Alice")
    sg.init_player("p2", "Bob")
    sg.init_player("p0", "Me (Should be ignored)") # 自己的不初始化到他人列表
    
    assert sg.get_profile("p0") is None
    
    # 增加信任
    sg.update_trust("p1", 0.5)
    assert sg.get_profile("p1").trust_score == 0.5
    
    # 减少信任
    sg.update_trust("p1", -0.2)
    assert sg.get_profile("p1").trust_score == 0.3
    
    # 界限限制
    sg.update_trust("p1", 5.0)
    assert sg.get_profile("p1").trust_score == 1.0
    sg.update_trust("p2", -2.0)
    assert sg.get_profile("p2").trust_score == -1.0
    
    # 笔记
    sg.add_note("p1", "像洗衣妇")
    sg.record_claim("p1", "fortune_teller", "self_claim", day_number=1, round_number=1, speaker_name="Alice")
    sg.record_claim("p1", "fortune_teller", "denial", day_number=2, round_number=2, speaker_name="Alice")
    assert "像洗衣妇" in sg.get_profile("p1").notes
    assert sg.get_profile("p1").claimed_role_id is None
    assert len(sg.get_profile("p1").claim_history) == 2
    
    summary = sg.get_graph_summary()
    assert "Alice (信任+1.0)" in summary
    assert "Bob (怀疑-1.0)" in summary
    assert "关于 Alice 的分析" in summary
    assert "明确否认自己是: fortune_teller" in summary
    assert "身份发言记录" in summary
    
    # JSON 导出
    data = json.loads(sg.dump_json())
    assert "p1" in data
    assert data["p1"]["trust_score"] == 1.0
    assert data["p1"]["claim_history_count"] == 2
    assert data["p1"]["recent_claims"]
    assert sg.claim_conflict_count("p1") == 1
    claim_signals = sg.claim_signal_summary("p1")
    assert claim_signals["self_claim"] == 1
    assert claim_signals["denial"] == 1
    assert claim_signals["conflicts"] == 1


def test_social_graph_freeze_thaw_and_claim_dedup():
    sg = SocialGraph(my_player_id="p0")
    sg.init_player("p1", "Alice")

    # 漏洞修复：freeze/thaw 不应因 logger 未定义而抛错
    sg.freeze_player("p1", "已确认死亡并归档")
    assert sg.get_profile("p1").is_frozen is True
    sg.thaw_player("p1", "出现新证据")
    assert sg.get_profile("p1").is_frozen is False

    # 最小一致性修补：同轮次同内容重复自报不应重复写入
    sg.record_claim("p1", "fortune_teller", "self_claim", day_number=1, round_number=1, source_text="我跳占卜师")
    sg.record_claim("p1", "fortune_teller", "self_claim", day_number=1, round_number=1, source_text="我跳占卜师")
    assert len(sg.get_profile("p1").claim_history) == 1


def test_social_graph_conflict_count_resets_after_denial():
    sg = SocialGraph(my_player_id="p0")
    sg.init_player("p1", "Alice")

    sg.record_claim("p1", "fortune_teller", "self_claim", day_number=1, round_number=1)
    sg.record_claim("p1", "fortune_teller", "denial", day_number=2, round_number=1)
    sg.record_claim("p1", "fortune_teller", "self_claim", day_number=3, round_number=1)

    # 否认会结束上一段声明链，后续重新自报同身份不应被额外算作改口冲突
    assert sg.claim_conflict_count("p1") == 1


def test_working_memory_private_info_has_priority_lane():
    wm = WorkingMemory()
    wm.remember_fact("Bob 公开跳了预言家")
    wm.remember_objective_info("evil_teammates", "你的邪恶队友是：Player 2", day_number=1, round_number=1)
    wm.remember_objective_info("evil_bluffs", "说书人给邪恶阵营的 bluff 是：洗衣妇, 图书馆员", day_number=1, round_number=1)
    wm.remember_private_info("night_info", "你昨晚查出 Bob 不是恶魔", day_number=1, round_number=1)
    wm.remember_public_info("role_claim", "Bob 公开跳了预言家", day_number=1, round_number=1)

    context = wm.get_recent_context()
    assert "你确认掌握的绝对客观事实" in context
    assert "你的邪恶队友是：Player 2" in context
    assert "说书人给邪恶阵营的 bluff 是：洗衣妇, 图书馆员" in context
    assert "你确认掌握的高可信私密信息" in context
    assert "你昨晚查出 Bob 不是恶魔" in context
    assert "公开场上的普通信息" in context
    assert "Bob 公开跳了预言家" in context
    assert wm.get_public_memory_summaries("role_claim") == ["Bob 公开跳了预言家"]


def test_working_memory_clear_transient_preserves_all_memory_tiers():
    wm = WorkingMemory()
    wm.add_observation(
        Observation(
            observation_id="evt-1",
            content="今天有人提名了 Bob",
            phase=GamePhase.NOMINATION,
            round_number=2,
        )
    )
    wm.add_thought("Bob 可能有问题。")
    wm.remember_objective_info("death", "Alice 死亡，原因：execution", day_number=2, round_number=2)
    wm.remember_private_info("undertaker_info", "送葬者信息: 今天被处决的玩家身份是：小恶魔。", day_number=2, round_number=2)
    wm.remember_public_info("role_claim", "Charlie 公开跳身份为 预言家", day_number=2, round_number=2)

    wm.clear_transient()

    assert wm.is_empty
    assert wm.get_objective_memory_summaries("death") == ["Alice 死亡，原因：execution"]
    assert wm.get_private_memory_summaries("undertaker_info") == ["送葬者信息: 今天被处决的玩家身份是：小恶魔。"]
    assert wm.get_public_memory_summaries("role_claim") == ["Charlie 公开跳身份为 预言家"]


def test_working_memory_multi_day_archives_preserve_private_and_public_layers():
    wm = WorkingMemory()

    wm.remember_private_info("investigator_info", "调查员信息: Bob 和 Charlie 中有一名爪牙。", day_number=1, round_number=1)
    wm.remember_public_info("role_claim", "Bob 公开跳身份为 洗衣妇", day_number=2, round_number=1)
    wm.clear_transient()
    wm.remember_public_info("public_fact", "Bob 明确否认自己是 洗衣妇", day_number=3, round_number=1)
    wm.clear_transient()

    context = wm.get_recent_context()
    assert "你确认掌握的高可信私密信息" in context
    assert "调查员信息: Bob 和 Charlie 中有一名爪牙。" in context
    assert "公开场上的普通信息" in context
    assert "Bob 公开跳身份为 洗衣妇" in context
    assert "Bob 明确否认自己是 洗衣妇" in context


def test_working_memory_tracks_failed_kill_targets_in_objective_lane():
    wm = WorkingMemory()

    wm.remember_objective_info(
        "failed_kill_target",
        "Bob 是高风险刀人失败目标：已连续失败 2 次（原因: protected）。",
        day_number=2,
        round_number=2,
        source="night_kill_result",
    )
    wm.clear_transient()

    summaries = wm.get_objective_memory_summaries("failed_kill_target")
    assert summaries == ["Bob 是高风险刀人失败目标：已连续失败 2 次（原因: protected）。"]
