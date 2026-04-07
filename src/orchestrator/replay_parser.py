"""
游戏回放系统 (Replay Parser)

解析之前导出的 events.json 和 snapshots.json 记录文件，
提供复盘解析和控制台输出能力。
"""

import json
import os
import logging
from typing import Any

logger = logging.getLogger("replay")

class ReplayParser:
    def __init__(self, export_dir: str):
        self.export_dir = export_dir
        self.events: list[dict[str, Any]] = []
        self.snapshots: list[dict[str, Any]] = []

    def load(self):
        """加载历史记录"""
        event_path = os.path.join(self.export_dir, "events.json")
        snapshot_path = os.path.join(self.export_dir, "snapshots.json")
        
        if os.path.exists(event_path):
            with open(event_path, "r", encoding="utf-8") as f:
                self.events = json.load(f)
                
        if os.path.exists(snapshot_path):
            with open(snapshot_path, "r", encoding="utf-8") as f:
                self.snapshots = json.load(f)

    def print_text_replay(self):
        """在控制台打印文字回放"""
        print(f"=== 游戏回放开始 (日志数量: {len(self.events)}) ===")
        current_round = -1
        current_phase = ""
        
        for e in self.events:
            if e["round_number"] != current_round or e.get("phase") != current_phase:
                current_round = e["round_number"]
                current_phase = e.get("phase", "")
                print(f"\n--- 第 {current_round} 轮 | {current_phase} ---")
                
            etype = e["event_type"]
            vis = e["visibility"]
            
            if vis == "public":
                vis_tag = "[全服可见]"
            elif vis == "private":
                vis_tag = f"[私密 -> {e.get('target')}]"
            elif vis == "team_evil":
                vis_tag = "[恶魔阵营]"
            else:
                vis_tag = "[上帝视角]"
                
            payload_str = json.dumps(e.get("payload", {}), ensure_ascii=False)
            
            content = f"{vis_tag} {etype}"
            if e.get("actor"):
                content += f" | 发动者: {e['actor']}"
            if e.get("target"):
                content += f" | 目标: {e['target']}"
                
            print(f"- {content} | 细节: {payload_str}")
            
        print("\n=== 回放结束 ===")

if __name__ == "__main__":
    # 用法：python -m src.orchestrator.replay_parser <目录>
    import sys
    if len(sys.argv) > 1:
        parser = ReplayParser(sys.argv[1])
        parser.load()
        parser.print_text_replay()
    else:
        print("请提供带有 events.json 和 snapshots.json 的文件夹路径。")
