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
           "blender": (3, 3, 0),
           "location": "Object Properties Panel",
           "description": "Display wireframes on specified geometry",
           "warning": "",
           "wiki_url": "tba",
           "tracker_url": "",
           "category": "Object"}

import bpy, gpu, bgl, bmesh, mathutils, datetime
from math import pi
from bpy.props import BoolProperty, PointerProperty, FloatVectorProperty, FloatProperty, IntProperty
from bpy.types import Panel, PropertyGroup, Operator, SpaceView3D
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader


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


class WIREVIS_Scene_Settings(PropertyGroup):
    wv_display: BoolProperty(name='', default=False, description='Display wire')
    update: BoolProperty(name='', default=False, description='Update wire')
    cupdate: BoolProperty(name='', default=False, description='Update wire colour')

class WIREVIS_Object_Settings(PropertyGroup):
    wv_bool: BoolProperty(name='', default=False, description='Display wire', update=wire_update)
    wv_colour: FloatVectorProperty(size=4, name="", attr="Colour", default=[0.0, 0.0, 0.0, 1.0], subtype='COLOR', min=0, max=1, update=wc_update)
    wv_extend: FloatProperty(name="", description="Wire extension", default=0, min=0, max=1, update=wire_update)
    wv_angle: FloatProperty(name="", description="Wire angle", default=45, min=0, max=180, update=wire_update)
    wv_material: BoolProperty(name='', default=False, description='Material boundary', update=wire_update)
    wv_dia: FloatProperty(name="mm", description="Wire diameter", default=20, min=0.1, max=1000, update=wire_update)
    wv_seg: IntProperty(name="", description="Wire segments", default=3, min=3, max=12, update=wire_update)
    wv_le: BoolProperty(name='', default=False, description='Lone edges', update=wire_update)
    wv_len: FloatProperty(name="mm", description="Wire length cutoff", default=10, min = 0.0, update=wire_update)


class WIREVIS_PT_scene(Panel):
    '''WireVis 3D view panel'''
    bl_label = "Wire"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WireVis"

    def draw(self, context):
        layout = self.layout
        row = layout.row()

        if not context.scene.wv_params.wv_display:
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
        ots = ob.wirevis_settings
        layout = self.layout
        newrow(layout,  'Display:',  ots,  "wv_bool")

        if ots.wv_bool:
            newrow(layout,  'Colour:',  ots,  "wv_colour")
            newrow(layout,  'Angle:',  ots,  "wv_angle")
            newrow(layout,  'Material boundary:',  ots,  "wv_material")
            newrow(layout,  'Cutoff length:',  ots,  "wv_len")
            newrow(layout,  'Lone edges:',  ots,  "wv_le")
            newrow(layout,  'Extend:',  ots,  "wv_extend")
            newrow(layout,  'Segments:',  ots,  "wv_seg")
            newrow(layout,  'Diameter:',  ots,  "wv_dia")


class VIEW3D_OT_WireVis(Operator):
    bl_idname = "view3d.wirevis"
    bl_label = "Wire Vis"
    bl_description = "Display Wireframe"
    bl_register = True
    bl_undo = False

    def invoke(self, context, event):
        scene = context.scene
        wvp = scene.wv_params
        # self.draw_handle_wv = SpaceView3D.draw_handler_add(self.draw_wv, (self, context), "WINDOW", "POST_VIEW")
        context.window_manager.modal_handler_add(self)
        wvp.wv_display = 1
        wvp.update = 1
        return {'RUNNING_MODAL'}


    def modal(self, context, event):
        scene = context.scene
        wvp = scene.wv_params
        dp = context.evaluated_depsgraph_get()
        wv_obs = [ob for ob in scene.objects if ob.wirevis_settings.wv_bool]

        if not wvp.wv_display:
            return {'FINISHED'}

        if wvp.update:
            bm = bmesh.new()
            
            if not wv_obs:
                self.report({'ERROR'}, 'No objects with the wire_vis display property turned on')
                return {'CANCELLED'}

            for oi, ob in enumerate(wv_obs):
                ows = ob.wirevis_settings
                obbm = bmesh.new()
                obbm.from_object(ob, dp)
                obbm.transform(ob.matrix_world)
                ecoords = [[v.co for v in e.verts] for e in obbm.edges if (e.calc_face_angle(0.1) * 180/pi > ows.wv_angle or
                           (ows.wv_material and len(e.link_faces) == 2 and len(set(f.material_index for f in e.link_faces)) == 2) or 
                           (ows.wv_le and len(e.link_faces) == 1)) and e.calc_length()*1000 > ows.wv_len]
                ecentres = [(e[0] + e[1]) * 0.5 for e in ecoords]

                for ei, ec in enumerate(ecentres):
                    length = (ecoords[ei][0] - ecoords[ei][1]).length
                    mat_trans = mathutils.Matrix.Translation(ec)
                    mat_rot = mathutils.Vector((0, 0, 1)).rotation_difference(ecoords[ei][1] - ec).to_matrix().to_4x4()
                    wire_verts = bmesh.ops.create_cone(bm, cap_ends=1, cap_tris=1, segments=ows.wv_seg, radius1=ows.wv_dia * 0.001, radius2=ows.wv_dia * 0.001, depth=length, matrix=mat_trans@mat_rot)['verts']
                    
                    for v in wire_verts:
                        for f in v.link_faces:
                            f.material_index = oi


                    if ows.wv_extend > 0:
                        wire_verts[0].co += (wire_verts[0].co - ec).normalized() * ows.wv_extend
                        wire_verts[1].co += (wire_verts[1].co - ec).normalized() * ows.wv_extend

                obbm.free()

                try:
                    wire_material = bpy.data.materials[f'wire_material-{oi}']
                except:
                    wire_material = bpy.data.materials.new(name=f'wire_material-{oi}')

                wire_material.diffuse_color = ows.wv_colour

            try:
                wire_object = bpy.data.objects['wire_object']
            
            except Exception as e:
                wire_mesh = bpy.data.meshes.new('wire_mesh')
                wire_object = bpy.data.objects.new("wire_object", wire_mesh)
                bpy.context.collection.objects.link(wire_object)
                wire_object.display.show_shadows = False
                
            bm.transform(wire_object.matrix_world.inverted())
            bm.to_mesh(wire_object.data)

            for i in range(oi + 1):
                while i >= len(wire_object.material_slots):
                    wire_object.data.materials.append(bpy.data.materials[f'wire_material-{i}'])
                

            bm.free()
            wvp.update = 0

            for area in context.window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        
        elif wvp.cupdate:
            wire_object = bpy.data.objects['wire_object']
            wvp.cupdate = 0
            
            for oi, ob in enumerate(wv_obs):
                wire_object.material_slots[oi].material.diffuse_color = ob.wirevis_settings.wv_colour
            
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