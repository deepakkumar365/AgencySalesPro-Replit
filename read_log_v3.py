import sys
try:
    with open('execution_v5.log', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        print(content)
except Exception as e:
    print(f"Error reading log: {e}")
