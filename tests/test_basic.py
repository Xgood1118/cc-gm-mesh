# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh.core import (  # noqa: E402
    Mesh,
    Vec3,
    compute_normals,
    merge_duplicate_vertices,
    parse_obj,
    triangulate,
    write_obj,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "data", "model.obj")


def test_vec3_cross():
    a = Vec3(1, 0, 0)
    b = Vec3(0, 1, 0)
    c = a.cross(b)
    assert abs(c.z - 1) < 1e-9


def test_parse_vertices():
    mesh = parse_obj(MODEL)
    assert len(mesh.vertices) == 8
    assert mesh.face_count() == 6


def test_negative_indices_resolved():
    """负索引按 OBJ 规范折算：-1 指向最后一个顶点。"""
    mesh = parse_obj(MODEL)
    assert mesh.faces[1] == [5, 6, 7, 8]  # 文件中的 f -4 -3 -2 -1
    assert min(min(f) for f in mesh.faces) >= 1


def test_out_of_bounds_reports_line(tmp_path):
    bad = tmp_path / "bad.obj"
    bad.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        parse_obj(str(bad))
    assert "4" in str(exc.value)  # 出错面在第 4 行

    bad_neg = tmp_path / "bad_neg.obj"
    bad_neg.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 -4\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc2:
        parse_obj(str(bad_neg))
    assert "4" in str(exc2.value)


def test_quad_triangulation_count():
    """6 个四边形 -> 12 个三角形，满足 sum(n-2)。"""
    mesh = parse_obj(MODEL)
    tris = triangulate(mesh)
    assert len(tris) == 12
    assert len(tris) == sum(len(f) - 2 for f in mesh.faces)
    assert all(len(t) == 3 for t in tris)


def test_concave_polygon_triangulation():
    """凹五边形：耳切法拆出的三角形必须全部落在多边形内（面积守恒）。"""
    mesh = Mesh()
    for x, y in [(0, 0), (4, 0), (4, 4), (2, 1), (0, 4)]:
        mesh.vertices.append(Vec3(x, y, 0))
    mesh.faces.append([1, 2, 3, 4, 5])
    tris = triangulate(mesh)
    assert len(tris) == 3  # n - 2
    area = 0.0
    for t in tris:
        a, b, c = (mesh.vertices[i - 1] for i in t)
        area += b.sub(a).cross(c.sub(a)).length() / 2.0
    assert abs(area - 10.0) < 1e-9  # 多边形面积 16 - 6 = 10


def test_normals_unit_length():
    mesh = parse_obj(MODEL)
    normals = compute_normals(mesh)
    assert len(normals) == len(mesh.vertices)
    for n in normals:
        assert abs(n.length() - 1.0) < 1e-6


def test_normals_area_weighted():
    """共享顶点处，大面的法线方向应占主导。"""
    mesh = Mesh()
    mesh.vertices = [
        Vec3(0, 0, 0), Vec3(2, 0, 0), Vec3(0, 2, 0),  # 大三角形，法线 +z
        Vec3(0, 0.01, 0), Vec3(0, 0, 0.01),            # 小三角形，法线 +x
    ]
    mesh.faces = [[1, 2, 3], [1, 4, 5]]
    normals = compute_normals(mesh)
    n = normals[0]
    assert n.z > 0.99  # 几乎完全由大面决定


def test_normals_inconsistent_winding_not_cancelled():
    """绕序相反的两个相邻三角形，统一绕序后法线不应抵消。"""
    mesh = Mesh()
    mesh.vertices = [Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0)]
    mesh.faces = [[1, 2, 3], [1, 4, 3]]  # 第二个面绕序与第一个冲突
    normals = compute_normals(mesh)
    for n in normals:
        assert n.z > 0.99  # 全部朝 +z，而不是抵消成 0


def test_merge_duplicate_vertices():
    mesh = Mesh()
    mesh.vertices = [Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 0, 0), Vec3(0, 1, 0)]
    mesh.faces = [[1, 2, 4], [2, 3, 4]]
    before = sorted((v.x, v.y, v.z) for v in mesh.vertices)
    removed = merge_duplicate_vertices(mesh)
    assert removed == 1
    assert len(mesh.vertices) == 3
    assert mesh.faces == [[1, 2, 3], [2, 1, 3]]
    # 外形不变：合并后顶点位置集合是原集合的子集，且每个被引用的位置都在
    after = sorted(set((v.x, v.y, v.z) for v in mesh.vertices))
    assert after == sorted(set(before))
    assert max(max(f) for f in mesh.faces) <= len(mesh.vertices)


def test_roundtrip(tmp_path):
    """写出的 OBJ 能被 parse_obj 读回，顶点数与三角形数一致。"""
    mesh = parse_obj(MODEL)
    merge_duplicate_vertices(mesh)
    compute_normals(mesh)
    tris = triangulate(mesh)
    mesh.faces = [list(t) for t in tris]
    out = tmp_path / "out.obj"
    write_obj(mesh, str(out))

    back = parse_obj(str(out))
    assert len(back.vertices) == len(mesh.vertices)
    assert len(back.faces) == len(tris)


def test_output_deterministic(tmp_path):
    """连续两次运行输出逐字节相同。"""
    paths = []
    for name in ("a.obj", "b.obj"):
        mesh = parse_obj(MODEL)
        merge_duplicate_vertices(mesh)
        compute_normals(mesh)
        mesh.faces = [list(t) for t in triangulate(mesh)]
        p = tmp_path / name
        write_obj(mesh, str(p))
        paths.append(p)
    assert paths[0].read_bytes() == paths[1].read_bytes()
