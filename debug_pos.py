
import os

file_path = r'd:\Project\Workouts\AgencySalesPro-Replit\templates\pos\sale.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_index = content.find('let rawProducts')
if start_index != -1:
    print("Found rawProducts block:")
    print(content[start_index:start_index+500])
else:
    print("rawProducts block not found")
