# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {"name": "Wire Visualiser",
           "author": "Ryan Southall",
           "version": (0, 4, 0),
           "blender": (4, 2, 0),
           "location": "Object Properties Panel",
           "description": "Display wire frames on specified geometry",
           "warning": "",
           "wiki_url": "tba",
           "tracker_url": "",
           "category": "Object"}

import bpy, gpu, bmesh, mathutils, datetime, random
from math import pi, radians
from bpy.props import BoolProperty, PointerProperty, FloatVectorProperty, FloatProperty, IntProperty, EnumProperty
from bpy.types import Panel, PropertyGroup, Operator, SpaceView3D
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


def wire_update(self, context):
    context.scene.wv_params.update = 1

    for area in bpy.context.window.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def wc_update(self, context):
    context.scene.wv_params.cupdate = 1

    for area in bpy.context.window.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def get_all_children(col):
    yield col
    for child in col.children:
        yield from get_all_children(child)


class WIREVIS_Scene_Settings(PropertyGroup):
    wv_display: BoolProperty(name='', default=False, description='Display wire')
    update: BoolProperty(name='', default=False, description='Update wire')
    cupdate: BoolProperty(name='', default=False, description='Update wire colour')
    wv_override: BoolProperty(name='', default=False, description='Wire override', update=wire_update)
    wv_colour: FloatVectorProperty(size=4, name="", attr="Colour", default=[0.0, 0.0, 0.0, 1.0], subtype='COLOR', min=0, max=1, update=wc_update)
    wv_extend: FloatProperty(name="", description="Wire extension", default=0, min=0, max=1, update=wire_update)
    wv_extend_type: EnumProperty(name='', items=[('0', 'Relative', 'Relative extend'), ('1', 'Absolute', 'Absolute extend')], description='Type pf wire extend', default='0', update=wire_update)
    wv_angle: FloatProperty(name="", description="Wire angle", default=45, min=0, max=180, update=wire_update)
    wv_material: BoolProperty(name='', default=False, description='Material boundary', update=wire_update)
    wv_dia: FloatProperty(name="mm", description="Wire diameter", default=20, min=0.1, max=1000, update=wire_update)
    wv_seg: IntProperty(name="", description="Wire segments", default=3, min=3, max=12, update=wire_update)
    wv_le: BoolProperty(name='', default=False, description='Lone edges', update=wire_update)
    wv_len: FloatProperty(name="mm", description="Wire length cutoff", default=10, min=0.0, update=wire_update)
    wv_rotate: FloatProperty(name="", description="Twist angle", default=0, min=0, max=360, update=wire_update)
    wv_jitter: FloatProperty(name='', description='Random jitter', default=0, min=0, precision=4, update=wire_update)
    wv_jitter_type: EnumProperty(name='', items=[('0', 'Edge', 'Edge jitter'), ('1', 'Vertex', 'Vertex')], description='Type of jitter', default='0', update=wire_update)


class WIREVIS_Object_Settings(PropertyGroup):
    wv_bool: BoolProperty(name='', default=False, description='Display wire', update=wire_update)
    wv_colour: FloatVectorProperty(size=4, name="", attr="Colour", default=[0.0, 0.0, 0.0, 1.0], subtype='COLOR', min=0, max=1, update=wc_update)
    wv_extend: FloatProperty(name="", description="Wire extension", default=0, min=0, max=1, update=wire_update)
    wv_extend_type: EnumProperty(name='', items=[('0', 'Relative', 'Relative extend'), ('1', 'Absolute', 'Absolute extend')], description='Type of wire extend', default='0', update=wire_update)
    wv_angle: FloatProperty(name="", description="Wire angle", default=45, min=0, max=180, update=wire_update)
    wv_material: BoolProperty(name='', default=False, description='Material boundary', update=wire_update)
    wv_dia: FloatProperty(name="mm", description="Wire diameter", default=20, min=0.1, max=1000, update=wire_update)
    wv_seg: IntProperty(name="", description="Wire segments", default=3, min=3, max=12, update=wire_update)
    wv_le: BoolProperty(name='', default=False, description='Lone edges', update=wire_update)
    wv_len: FloatProperty(name="mm", description="Wire length cutoff", default=10, min=0.0, update=wire_update)
    wv_rotate: FloatProperty(name="", description="Twist angle", default=0, min=0, max=360, update=wire_update)
    wv_jitter: FloatProperty(name='', description='Random jitter', default=0, min=0, precision=4, update=wire_update)
    wv_jitter_type: EnumProperty(name='', items=[('0', 'Edge', 'Edge jitter'), ('1', 'Vertex', 'Vertex')], description='Type of jitter', default='0', update=wire_update)


class WIREVIS_PT_scene(Panel):
    '''WireVis 3D view panel'''
    bl_label = "Wire"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WireVis"

    def draw(self, context):
        scene = context.scene
        swv = scene.wv_params
        layout = self.layout
        newrow(layout, 'Override:', swv, "wv_override")

        if swv.wv_override:
            newrow(layout, 'Colour:', swv, "wv_colour")
            newrow(layout, 'Angle:', swv, "wv_angle")
            newrow(layout, 'Material boundary:', swv, "wv_material")
            newrow(layout, 'Cutoff length:', swv, "wv_len")
            newrow(layout, 'Lone edges:', swv, "wv_le")
            newrow(layout, 'Extend:', swv, "wv_extend")

            if swv.wv_extend:
                newrow(layout,  'Extend type:',  swv,  "wv_extend_type")

            newrow(layout, 'Twist:', swv, "wv_rotate")   
            newrow(layout, 'Jitter level:', swv, "wv_jitter")

            if swv.wv_jitter:
                newrow(layout, 'Jitter type:', swv, "wv_jitter_type")

            newrow(layout, 'Segments:', swv, "wv_seg")
            newrow(layout, 'Diameter:', swv, "wv_dia")

        row = layout.row()

        if not swv.wv_display:
            row.operator("view3d.wirevis", text="Display")
        else:
            row.operator("view3d.wirecancel", text="Cancel")


class WIREVIS_PT_object(Panel):
    bl_label = "WireVis"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        if context.object.type == 'MESH':
            return True

    def draw(self, context):
        ob = context.object
        owv = ob.wirevis_settings
        layout = self.layout
        newrow(layout,  'Display:',  owv,  "wv_bool")

        if owv.wv_bool:
            newrow(layout, 'Colour:',  owv,  "wv_colour")
            newrow(layout, 'Angle:',  owv,  "wv_angle")
            newrow(layout, 'Material boundary:',  owv,  "wv_material")
            newrow(layout, 'Cutoff length:',  owv,  "wv_len")
            newrow(layout, 'Lone edges:',  owv,  "wv_le")
            newrow(layout, 'Extend:',  owv,  "wv_extend")

            if owv.wv_extend:
                newrow(layout, 'Extend type:',  owv,  "wv_extend_type")
            
            newrow(layout, 'Twist:',  owv,  "wv_rotate")
            newrow(layout, 'Jitter level:', owv, "wv_jitter")

            if owv.wv_jitter:
                newrow(layout, 'Jitter type:', owv, "wv_jitter_type")

            newrow(layout, 'Segments:',  owv,  "wv_seg")
            newrow(layout, 'Diameter:',  owv,  "wv_dia")


class VIEW3D_OT_WireVis(Operator):
    bl_idname = "view3d.wirevis"
    bl_label = "Wire Vis"
    bl_description = "Display Wireframe"
    bl_register = True
    bl_undo = False

    def invoke(self, context, event):
        wm = context.window_manager
        scene = context.scene
        wvp = scene.wv_params
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        wvp.wv_display = 1
        wvp.update = 1
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        scene = context.scene
        swv = scene.wv_params
        dp = context.evaluated_depsgraph_get()
        vl_colls = get_all_children(context.view_layer.layer_collection)
        wv_obs = [ob for ob in scene.objects if ob.wirevis_settings.wv_bool]
        vl_colls = [v for v in vl_colls]
        vl_coll_names = [v.name for v in vl_colls]
        wv_obs = [ob for ob in wv_obs if any([not vl_colls[vl_coll_names.index(c.name)].exclude for c in ob.users_collection if c.name in vl_coll_names]) or all([c == scene.collection for c in ob.users_collection])]
        verts_out, faces_out, mis_out = [], [], []

        if not swv.wv_display:
            return {'FINISHED'}

        if swv.update:
            if not wv_obs:
                self.report({'ERROR'}, 'No objects with the wire_vis display property turned on')
                return {'CANCELLED'}

            if swv.wv_override:
                wbm = bmesh.new()
                bmesh.ops.create_cone(wbm, cap_ends=1, cap_tris=1, depth=1, segments=swv.wv_seg, radius1=swv.wv_dia * 0.001, radius2=swv.wv_dia * 0.001)
                ows = swv
                wbm.verts.ensure_lookup_table()
                low_z = wbm.verts[0].co[2]
                hi_z = wbm.verts[1].co[2]

            for oi, ob in enumerate(wv_obs):
                if not swv.wv_override:
                    ows = ob.wirevis_settings
                    wbm = bmesh.new()
                    bmesh.ops.create_cone(wbm, cap_ends=1, cap_tris=1, depth=1, segments=ows.wv_seg, radius1=ows.wv_dia * 0.001, radius2=ows.wv_dia * 0.001)
                
                wbm.verts.ensure_lookup_table()
                low_z = wbm.verts[0].co[2]
                hi_z = wbm.verts[1].co[2]
                obbm = bmesh.new()
                obbm.from_object(ob, dp)
                obbm.transform(ob.matrix_world)
                valid_edges = [e for e in obbm.edges if (e.calc_face_angle(0.1) * 180/pi >= ows.wv_angle or
                           (ows.wv_material and len(e.link_faces) == 2 and len(set(f.material_index for f in e.link_faces)) == 2) or
                           (ows.wv_le and len(e.link_faces) == 1)) and e.calc_length()*1000 > ows.wv_len]

                ecoords = [[v.co for v in e.verts] for e in valid_edges]
                ecentres = [(e[0] + e[1]) * 0.5 for e in ecoords]
                enormals = [sum((f.normal for f in e.link_faces), Vector()).normalized() for e in valid_edges]
                e_lens = [(e[0] - e[1]).length for e in ecoords]
                lvo = len(verts_out)

                for ei, ec in enumerate(ecentres):
                    mat_trans = mathutils.Matrix.Translation(ec)
                    mat_rot = mathutils.Vector((0, 0, 1)).rotation_difference(ecoords[ei][1] - ec).to_matrix().to_4x4()
                    mr = mat_rot@mathutils.Vector((0, 1, 0))
                    mat_rot2 = mr.rotation_difference(enormals[ei]).to_matrix().to_4x4()
                    nbm = wbm.copy()
                    nbm.verts.ensure_lookup_table()

                    if ows.wv_jitter and ows.wv_jitter_type == '0':
                        rand1 = random.uniform(-ows.wv_jitter * 0.01, ows.wv_jitter * 0.01)
                        rand2 = random.uniform(-ows.wv_jitter * 0.01, ows.wv_jitter * 0.01)

                    if ows.wv_rotate > 0:
                        bmesh.ops.rotate(nbm, cent=nbm.verts[1].co, matrix=mathutils.Matrix.Rotation(radians(ows.wv_rotate), 4, 'Z'), verts=[v for v in nbm.verts if v.co[2] == hi_z])

                    for v in nbm.verts:
                        if v.co[2] == low_z:
                            v.co[2] = -e_lens[ei] * 0.5

                            if ows.wv_jitter and ows.wv_jitter_type == '0':
                                v.co[0] += rand1
                                v.co[1] += rand1
                            elif ows.wv_jitter:
                                v.co[0] += random.uniform(-ows.wv_jitter * 0.01, ows.wv_jitter * 0.01)
                                v.co[1] += random.uniform(-ows.wv_jitter * 0.01, ows.wv_jitter * 0.01)

                        elif v.co[2] == hi_z:
                            v.co[2] = e_lens[ei] * 0.5

                            if ows.wv_jitter and ows.wv_jitter_type == '0':
                                v.co[0] += rand2
                                v.co[1] += rand2
                            elif ows.wv_jitter:
                                v.co[0] += random.uniform(-ows.wv_jitter * 0.01, ows.wv_jitter * 0.01)
                                v.co[1] += random.uniform(-ows.wv_jitter * 0.01, ows.wv_jitter * 0.01)

                    if ows.wv_extend > 0:
                        if ows.wv_extend_type == '0':
                            nbm.verts[0].co += mathutils.Vector((0, 0, -1)) * ows.wv_extend * e_lens[ei]**0.5
                            nbm.verts[1].co += mathutils.Vector((0, 0, 1)) * ows.wv_extend * e_lens[ei]**0.5
                        else:
                            nbm.verts[0].co += mathutils.Vector((0, 0, -1)) * ows.wv_extend
                            nbm.verts[1].co += mathutils.Vector((0, 0, 1)) * ows.wv_extend
                    
                    bmesh.ops.transform(nbm, matrix=mat_trans@mat_rot2@mat_rot, verts=nbm.verts)
                    verts_out += [v.co.to_tuple() for v in nbm.verts]
                    faces_out += [[lvo + j.index + ei * len(nbm.verts) for j in i.verts] for i in nbm.faces]
                    mis_out += [oi for f in nbm.faces]
                    nbm.free()
                
                if not swv.wv_override:
                    wbm.free()

                    try:
                        wire_material = bpy.data.materials[f'wire_material-{oi}']
                    except Exception:
                        wire_material = bpy.data.materials.new(name=f'wire_material-{oi}')
                
                    wire_material.diffuse_color = ows.wv_colour
                
                obbm.free()

            if swv.wv_override:
                wbm.free()
                
                try:
                    wire_material = bpy.data.materials[f'wire_material-0']
                except Exception:
                    wire_material = bpy.data.materials.new(name=f'wire_material-0')

            try:
                wire_object = bpy.data.objects['wire_object']
                wire_object.data.clear_geometry()
                wire_object.data.from_pydata(verts_out, [], faces_out)
                
                if swv.wv_override:
                    wire_object.data.polygons.foreach_set('material_index', [0 for mo in mis_out])
                else:
                    wire_object.data.polygons.foreach_set('material_index', mis_out)

            except Exception:
                wire_mesh = bpy.data.meshes.new('wire_mesh')
                wire_mesh.from_pydata(verts_out, [], faces_out)
                
                if swv.wv_override:
                    wire_mesh.polygons.foreach_set('material_index', [0 for mo in mis_out])
                else:
                    wire_mesh.polygons.foreach_set('material_index', mis_out)

                wire_object = bpy.data.objects.new("wire_object", wire_mesh)
                bpy.context.collection.objects.link(wire_object)
                wire_object.display.show_shadows = False

            for i in range(oi + 1):
                if not swv.wv_override:
                    while i >= len(wire_object.material_slots):
                        wire_object.data.materials.append(bpy.data.materials[f'wire_material-{i}'])
                else:
                    if 'wire_material-0' not in wire_object.data.materials:
                        wire_object.data.materials.append(bpy.data.materials['wire_material-0'])

            swv.update = 0

            for area in context.window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        elif swv.cupdate:
            wire_object = bpy.data.objects['wire_object']
            swv.cupdate = 0

            for oi, ob in enumerate(wv_obs):
                colour = swv.wv_colour if swv.wv_override else ob.wirevis_settings.wv_colour
                wire_object.material_slots[oi].material.diffuse_color = colour

        return {'PASS_THROUGH'}


class VIEW3D_OT_WireCancel(Operator):
    bl_idname = "view3d.wirecancel"
    bl_label = "Wire Cancel"
    bl_description = "Cancel wireframe"
    bl_register = True
    bl_undo = False

    def execute(self, context):
        context.scene.wv_params.wv_display = 0
        return {'FINISHED'}


def newrow(layout, s1, root, s2):
    row = layout.row()
    row.label(text=s1)
    row.prop(root, s2)


classes = (WIREVIS_PT_object, WIREVIS_Object_Settings, WIREVIS_Scene_Settings, VIEW3D_OT_WireVis, WIREVIS_PT_scene, VIEW3D_OT_WireCancel)


def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    bpy.types.Scene.wv_params = PointerProperty(type=WIREVIS_Scene_Settings)
    bpy.types.Object.wirevis_settings = PointerProperty(type=WIREVIS_Object_Settings)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
