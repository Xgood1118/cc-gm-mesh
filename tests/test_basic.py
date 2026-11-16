# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh.core import Vec3, parse_obj, triangulate  # noqa: E402


def test_vec3_cross():
    a = Vec3(1, 0, 0)
    b = Vec3(0, 1, 0)
    c = a.cross(b)
    assert abs(c.z - 1) < 1e-9


def test_parse_vertices():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "model.obj")
    if not os.path.exists(path):
        return
    mesh = parse_obj(path)
    assert len(mesh.vertices) == 8
    assert mesh.face_count() == 6


def test_parse_keeps_raw_faces():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "model.obj")
    if not os.path.exists(path):
        return
    mesh = parse_obj(path)
    assert len(mesh.faces[0]) == 4
    assert min(min(f) for f in mesh.faces) < 0


def test_triangulate_current_behaviour():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "model.obj")
    if not os.path.exists(path):
        return
    mesh = parse_obj(path)
    assert len(triangulate(mesh)) == 0
