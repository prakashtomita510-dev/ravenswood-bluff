import os
import json
import argparse
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def export_all_assets(game_id: str, output_dir: str = "data/exports"):
    """
    一键导出指定 game_id 的所有关联资产：
    1. 对局历史 (GameRecordStore)
    2. AI 行为日志 (GameDataCollector)
    3. 说书人裁量记录 (StorytellerAgent via GameRecordStore)
    """
    try:
        from src.state.game_record import GameRecordStore
        from src.state.game_data_collector import GameDataCollector
        
        # 确保输出目录存在
        target_dir = Path(output_dir) / game_id
        target_dir.mkdir(parents=True, exist_ok=True)
        
        record_store = GameRecordStore()
        collector = GameDataCollector()
        
        logger.info(f"正在为对局 {game_id} 聚合资产...")
        
        # 1. 导出对局详情
        record = await record_store.export_history_detail(game_id)
        if record:
            with open(target_dir / "game_history.json", "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            logger.info(f"已导出对局历史: {target_dir / 'game_history.json'}")
        else:
            logger.warning(f"未找到对局历史记录: {game_id}")

        # 2. 导出 AI 行为快照
        traces = collector.export_ai_traces(game_id)
        if traces:
            with open(target_dir / "ai_traces.jsonl", "w", encoding="utf-8") as f:
                for trace in traces:
                    f.write(json.dumps(trace, ensure_ascii=False) + "\n")
            logger.info(f"已导出 AI 行为轨迹: {target_dir / 'ai_traces.jsonl'}")
        else:
            logger.warning(f"未找到 AI 行为轨迹: {game_id}")

        # 3. 导出说书人裁量记录 (从历史详情中提取)
        if record and "storyteller_judgements" in record:
            with open(target_dir / "storyteller_judgements.json", "w", encoding="utf-8") as f:
                json.dump(record["storyteller_judgements"], f, ensure_ascii=False, indent=2)
            logger.info(f"已从历史中分离说书人裁量记录: {target_dir / 'storyteller_judgements.json'}")

        # 4. 生成打包说明
        manifest = {
            "game_id": game_id,
            "export_time": datetime.now().isoformat(),
            "assets": [
                "game_history.json",
                "ai_traces.jsonl",
                "storyteller_judgements.json"
            ]
        }
        with open(target_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        
        logger.info(f"对局 {game_id} 的所有资产已成功导出至: {target_dir}")
        return True

    except Exception as e:
        logger.error(f"导出失败: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键导出对局全量资产")
    parser.add_argument("game_id", help="要导出的 game_id")
    parser.add_argument("--output", default="data/exports", help="输出根目录")
    
    args = parser.parse_args()
    
    asyncio.run(export_all_assets(args.game_id, args.output))
