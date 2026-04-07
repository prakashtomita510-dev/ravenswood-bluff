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
    assert "像洗衣妇" in sg.get_profile("p1").notes
    
    summary = sg.get_graph_summary()
    assert "Alice (信任+1.0)" in summary
    assert "Bob (怀疑-1.0)" in summary
    assert "关于 Alice 的分析" in summary
    
    # JSON 导出
    data = json.loads(sg.dump_json())
    assert "p1" in data
    assert data["p1"]["trust_score"] == 1.0
