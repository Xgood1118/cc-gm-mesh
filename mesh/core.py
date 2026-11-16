# -*- coding: utf-8 -*-
"""OBJ 解析、修复与法线重建。

流水线：parse_obj -> merge_duplicate_vertices -> compute_normals（内部统一绕序）
-> triangulate -> write_obj。

约定：mesh.faces 中存放的是 1 基索引（与 OBJ 文件一致），解析阶段已把负索引
按 OBJ 规范折算成正索引。
"""


class Vec3(object):
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def sub(self, o):
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def cross(self, o):
        return Vec3(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z,
                    self.x * o.y - self.y * o.x)

    def length(self):
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5

    def normalized(self):
        n = self.length()
        if n == 0:
            return Vec3(0, 0, 0)
        return Vec3(self.x / n, self.y / n, self.z / n)

    def __repr__(self):
        return "Vec3(%.4f, %.4f, %.4f)" % (self.x, self.y, self.z)


class Mesh(object):
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.normals = []

    def face_count(self):
        return len(self.faces)


def parse_obj(path):
    """解析 OBJ。

    - 正索引：1 基，直接引用已读入的顶点。
    - 负索引：按 OBJ 规范，-1 指向当前已读入的最后一个顶点，依此类推。
    - 索引为 0 或越界时抛出 ValueError，消息里带上面所在的行号。
    解析后 mesh.faces 中全部是 1 基正索引。
    """
    mesh = Mesh()
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "v":
                mesh.vertices.append(Vec3(float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == "f":
                n = len(mesh.vertices)
                idx = []
                for p in parts[1:]:
                    raw = int(p.split("/")[0])
                    if raw > 0:
                        i = raw
                    elif raw < 0:
                        i = n + raw + 1
                    else:
                        raise ValueError(
                            "第 %d 行：OBJ 索引从 1 开始，不允许 0" % lineno)
                    if i < 1 or i > n:
                        raise ValueError(
                            "第 %d 行：面索引 %d 越界（当前已读入顶点数 %d）"
                            % (lineno, raw, n))
                    idx.append(i)
                if len(idx) < 3:
                    raise ValueError("第 %d 行：面至少需要 3 个顶点" % lineno)
                mesh.faces.append(idx)
    return mesh


def merge_duplicate_vertices(mesh):
    """合并位置完全相同的顶点，同步重写面索引。返回合并掉的顶点数。

    只按 (x, y, z) 精确判等，保留首次出现的副本，因此合并前后网格外形不变。
    """
    key_to_new = {}
    remap = []
    new_vertices = []
    for v in mesh.vertices:
        key = (v.x, v.y, v.z)
        slot = key_to_new.get(key)
        if slot is None:
            slot = len(new_vertices) + 1
            key_to_new[key] = slot
            new_vertices.append(v)
        remap.append(slot)
    removed = len(mesh.vertices) - len(new_vertices)
    mesh.vertices = new_vertices
    mesh.faces = [[remap[i - 1] for i in face] for face in mesh.faces]
    return removed


def _newell_normal(points):
    """Newell 法求多边形法线，模长正比于面积（平面多边形时为 2 倍面积）。"""
    nx = ny = nz = 0.0
    m = len(points)
    for k in range(m):
        a = points[k]
        b = points[(k + 1) % m]
        nx += (a.y - b.y) * (a.z + b.z)
        ny += (a.z - b.z) * (a.x + b.x)
        nz += (a.x - b.x) * (a.y + b.y)
    return Vec3(nx, ny, nz)


def _unify_winding(mesh):
    """统一绕序：沿共享边 BFS，把与邻接面绕序冲突的面整体翻转。

    之后按有向体积判断整体朝向，体积为负说明整体朝内，把所有面再翻一次，
    使封闭网格的法线朝外。非封闭网格保持 BFS 结果。
    """
    faces = mesh.faces
    n_faces = len(faces)
    edge_to_faces = {}
    for fi, face in enumerate(faces):
        m = len(face)
        for k in range(m):
            a, b = face[k], face[(k + 1) % m]
            key = (a, b) if a < b else (b, a)
            edge_to_faces.setdefault(key, []).append((fi, a, b))

    visited = [False] * n_faces
    for seed in range(n_faces):
        if visited[seed]:
            continue
        visited[seed] = True
        stack = [seed]
        while stack:
            fi = stack.pop()
            face = faces[fi]
            m = len(face)
            for k in range(m):
                a, b = face[k], face[(k + 1) % m]
                key = (a, b) if a < b else (b, a)
                for fj, c, d in edge_to_faces.get(key, ()):
                    if visited[fj]:
                        continue
                    # 一致的绕序下，相邻面沿共享边的走向应当相反；
                    # 走向相同说明 fj 绕序冲突，翻转之。
                    if (c, d) == (a, b):
                        faces[fj] = list(reversed(faces[fj]))
                    visited[fj] = True
                    stack.append(fj)

    volume = 0.0
    for face in faces:
        a0 = mesh.vertices[face[0] - 1]
        for k in range(1, len(face) - 1):
            b = mesh.vertices[face[k] - 1]
            c = mesh.vertices[face[k + 1] - 1]
            cr = b.cross(c)
            volume += a0.x * cr.x + a0.y * cr.y + a0.z * cr.z
    if volume < 0:
        mesh.faces = [list(reversed(face)) for face in faces]


def compute_normals(mesh):
    """面积加权顶点法线，结果为单位向量。

    先统一绕序（避免相邻面法线互相抵消），再按 Newell 法线累加——Newell
    法线的模长正比于面面积，天然就是面积加权——最后归一化。
    """
    _unify_winding(mesh)
    acc = [Vec3(0, 0, 0) for _ in mesh.vertices]
    for face in mesh.faces:
        points = [mesh.vertices[i - 1] for i in face]
        n = _newell_normal(points)
        for i in face:
            p = acc[i - 1]
            acc[i - 1] = Vec3(p.x + n.x, p.y + n.y, p.z + n.z)
    mesh.normals = [v.normalized() for v in acc]
    return mesh.normals


def _cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_tri_strict(p, a, b, c, eps=1e-12):
    """p 是否严格位于 CCW 三角形 abc 内部（边上不算）。"""
    return (_cross2(a, b, p) > eps and _cross2(b, c, p) > eps
            and _cross2(c, a, p) > eps)


def _triangulate_face(vertices, face):
    """耳切法拆分单个多边形，凹多边形也不会拆出网格外的三角形。"""
    if len(face) == 3:
        return [tuple(face)]
    points3 = [vertices[i - 1] for i in face]
    normal = _newell_normal(points3)
    comps = (normal.x, normal.y, normal.z)
    drop = max(range(3), key=lambda k: abs(comps[k]))
    pts = [tuple(c for k, c in enumerate((v.x, v.y, v.z)) if k != drop)
           for v in points3]

    m = len(pts)
    area2 = 0.0
    for k in range(m):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % m]
        area2 += x1 * y2 - x2 * y1
    order = list(range(m))
    if area2 < 0:
        order.reverse()

    tris = []
    while len(order) > 3:
        ear_found = False
        size = len(order)
        for k in range(size):
            i0 = order[k - 1]
            i1 = order[k]
            i2 = order[(k + 1) % size]
            if _cross2(pts[i0], pts[i1], pts[i2]) <= 1e-12:
                continue  # 凹顶点或退化，不是耳朵
            inside = False
            for j in order:
                if j in (i0, i1, i2):
                    continue
                if _point_in_tri_strict(pts[j], pts[i0], pts[i1], pts[i2]):
                    inside = True
                    break
            if inside:
                continue
            tris.append((face[i0], face[i1], face[i2]))
            order.pop(k)
            ear_found = True
            break
        if not ear_found:
            # 退化多边形（共线、自交等）兜底：扇形拆分，保证数量守恒。
            for k in range(1, len(order) - 1):
                tris.append((face[order[0]], face[order[k]], face[order[k + 1]]))
            return tris
    tris.append((face[order[0]], face[order[1]], face[order[2]]))
    return tris


def triangulate(mesh):
    """把所有面拆成三角形。n 边面拆出 n-2 个三角形，索引保持 1 基。"""
    tris = []
    for face in mesh.faces:
        tris.extend(_triangulate_face(mesh.vertices, face))
    return tris


def write_obj(mesh, path, with_normals=True):
    lines = ["# rebuilt mesh"]
    for v in mesh.vertices:
        lines.append("v %.6f %.6f %.6f" % (v.x, v.y, v.z))
    if with_normals:
        for n in mesh.normals:
            lines.append("vn %.6f %.6f %.6f" % (n.x, n.y, n.z))
    for face in mesh.faces:
        if with_normals:
            lines.append("f " + " ".join("%d//%d" % (i, i) for i in face))
        else:
            lines.append("f " + " ".join(str(i) for i in face))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="mesh")
    ap.add_argument("obj")
    ap.add_argument("--out", default="out.obj")
    args = ap.parse_args(argv)

    mesh = parse_obj(args.obj)
    merged = merge_duplicate_vertices(mesh)
    normals = compute_normals(mesh)
    tris = triangulate(mesh)
    mesh.faces = [list(t) for t in tris]
    write_obj(mesh, args.out)

    lengths = [n.length() for n in normals]
    print("顶点 %d，三角形 %d，合并重复顶点 %d" % (
        len(mesh.vertices), len(tris), merged))
    if lengths:
        print("法线长度 min %.9f，max %.9f" % (min(lengths), max(lengths)))
    print("已写出 %s" % args.out)
    return 0
