# -*- coding: utf-8 -*-
"""生成一个四边形面构成的小立方体，混入负索引。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

BODY = """# cube with quad faces and negative indices
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
v 1 0 1
v 1 1 1
v 0 1 1
f 1 2 3 4
f -4 -3 -2 -1
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


def main():
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "model.obj")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(BODY)
    print("已生成", path)


if __name__ == "__main__":
    main()
