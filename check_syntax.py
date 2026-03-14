import ast
import sys

try:
    with open(r'C:\Users\Administrator\Desktop\TraceBack\backend\app\api\config_api.py', 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print('语法正确')
except SyntaxError as e:
    print(f'语法错误: {e}')
    sys.exit(1)
