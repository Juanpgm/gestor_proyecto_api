import re

src = open("api/routers/unidades_proyecto.py", "r", encoding="utf-8").read()
matches = []
i = 0
while True:
    m = re.search(r"@router\.(get|post|put|delete|patch)\(", src[i:])
    if not m:
        break
    start = i + m.start()
    depth = 0
    pos = i + m.end() - 1
    end = None
    while pos < len(src):
        c = src[pos]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                end = pos
                break
        pos += 1
    matches.append(src[start : end + 1])
    i = end + 1
total = len(matches)
missing = [b for b in matches if "dependencies=" not in b]
print(f"Total: {total}")
print(f"Missing deps: {len(missing)}")
for b in missing:
    head = b.splitlines()[1] if len(b.splitlines()) > 1 else b[:80]
    print("-", head.strip())
