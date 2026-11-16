import sys, re
s = sys.stdin.read()
m = re.search(r'joint name=\W*gripper\W.*?</joint>', s, re.S)
l = re.search(r'<limit[^>]*>', m.group(0)) if m else None
print('limite pinza en robot_description:', l.group(0).replace('\\"', '"') if l else 'NO ENCONTRADO')
