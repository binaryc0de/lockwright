"""Small applied-mesh primitives, triangulation, and UV helpers."""
import bpy
import bmesh
from mathutils import Vector


def mesh_object(name, vertices, faces, mat, location=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    if mat:
        mesh.materials.append(mat)
    return obj


def active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def box(name, dimensions, mat, location=(0, 0, 0), bevel=0, segments=3):
    x, y, z = (d / 2 for d in dimensions)
    vertices = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = mesh_object(name, vertices, faces, mat, location)
    if bevel:
        active(obj)
        modifier = obj.modifiers.new('edge_radius', 'BEVEL')
        modifier.width = bevel
        modifier.segments = segments
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        # Mark bevel faces smooth but keep planar faces flat.
        for face in obj.data.polygons:
            face.use_smooth = max(abs(n) for n in face.normal) < 0.999
        normal = obj.modifiers.new('weighted_normals', 'WEIGHTED_NORMAL')
        normal.keep_sharp = True
        normal.weight = 50
        bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def uv_front(obj, front_rect, other_rect=(0.02, 0.02, 0.06, 0.06), width=None, height=None):
    """+Y front; -X is screen-right when viewed from the front (no mirrored text)."""
    uv = obj.data.uv_layers.new(name='UVMap')
    width = width or obj.dimensions.x
    height = height or obj.dimensions.z
    for polygon in obj.data.polygons:
        rect = front_rect if polygon.normal.y > 0.999 else other_rect
        u0, v0, u1, v1 = rect
        for loop in polygon.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv = (u0 + (0.5 - vertex.x / width) * (u1 - u0),
                                v0 + (0.5 + vertex.z / height) * (v1 - v0))


def join_static(objects, name, origin=(0, 0, 0)):
    active(objects[0])
    for obj in objects:
        obj.select_set(True)
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    delta = obj.location - Vector(origin)
    for vertex in obj.data.vertices:
        vertex.co += delta
    obj.location = origin
    obj.name = name
    obj.data.name = name
    return obj


def triangulate(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    if obj.modifiers:
        raise RuntimeError(f'Unapplied modifiers on {obj.name}')
