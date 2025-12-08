import sys
try:
    with open('execution_v2.log', 'r', encoding='utf-16-le', errors='ignore') as f:
        content = f.read()
        print(content)
except Exception as e:
    print(f"Error reading utf-16: {e}")
    try:
        with open('execution_v2.log', 'r', encoding='utf-8', errors='ignore') as f:
            print(f.read())
    except Exception as e2:
        print(f"Error reading utf-8: {e2}")
