# -*- coding: utf-8 -*-
"""OBJ 解析与法线重建骨架。

当前解析器只认 v 与 f，负索引不作处理，四边形面在三角化时被整段丢掉，
法线按面累加后不做归一。
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
    """解析 OBJ。负索引原样保留，多边形面原样保留。"""
    mesh = Mesh()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "v":
                mesh.vertices.append(Vec3(float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == "f":
                idx = [int(p.split("/")[0]) for p in parts[1:]]
                mesh.faces.append(idx)
    return mesh


def triangulate(mesh):
    """把面拆成三角形。当前只接受三顶点面，其余整段丢弃。"""
    tris = []
    for face in mesh.faces:
        if len(face) == 3:
            tris.append(tuple(face))
    return tris


def compute_normals(mesh):
    """按面法线累加到顶点，累加后不归一。"""
    acc = [Vec3(0, 0, 0) for _ in mesh.vertices]
    for face in mesh.faces:
        if len(face) < 3:
            continue
        try:
            a = mesh.vertices[face[0] - 1]
            b = mesh.vertices[face[1] - 1]
            c = mesh.vertices[face[2] - 1]
        except IndexError:
            continue
        n = b.sub(a).cross(c.sub(a))
        for i in face:
            try:
                acc[i - 1] = Vec3(acc[i - 1].x + n.x, acc[i - 1].y + n.y, acc[i - 1].z + n.z)
            except IndexError:
                pass
    mesh.normals = acc
    return acc


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
    tris = triangulate(mesh)
    normals = compute_normals(mesh)
    write_obj(mesh, args.out)
    print("顶点 %d，面 %d，三角形 %d，法线 %d" % (
        len(mesh.vertices), mesh.face_count(), len(tris), len(normals)))
    return 0
