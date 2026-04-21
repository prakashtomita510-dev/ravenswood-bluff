import ast
import traceback
import sys

try:
    path = r'd:\鸦木布拉夫小镇\src\engine\roles\townsfolk.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    print("File read successfully")
    ast.parse(content)
    print("Syntax is clean!")
except SyntaxError as e:
    print(f"Syntax Error at line {e.lineno}, offset {e.offset}")
    print(f"Line content: {e.text}")
    sys.exit(1)
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
