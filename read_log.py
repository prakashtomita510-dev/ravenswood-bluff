import os
import sys

log_path = r"d:\鸦木布拉夫小镇\simulation_trace.log"
with open(log_path, "rb") as f:
    data = f.read()

for enc in ['utf-16', 'utf-16-le', 'utf-8']:
    try:
        text = data.decode(enc)
        if "night_action" in text or "Night 2" in text or "night" in text.lower():
            print(f"--- Search Results ({enc}) ---")
            lines = text.splitlines()
            for line in lines[-100:]: # Show last 100 lines
                if "night" in line.lower() or "speak" in line.lower() or "round" in line.lower():
                    print(line)
        break
    except Exception:
        continue
