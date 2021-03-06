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
           "blender": (3, 0, 0),
           "location": "Object Properties Panel",
           "description": "Display wireframes on selected geometry",
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

class WIREVIS_Scene_Settings(PropertyGroup):
    wv_display: BoolProperty(name = '', default = False, description = 'Display wire')
    update: BoolProperty(name = '', default = False, description = 'Update wire')

class WIREVIS_Object_Settings(PropertyGroup):
    wv_bool: BoolProperty(name = '', default = False, description = 'Display wire')
    wv_colour: FloatVectorProperty(size = 4, name = "", attr = "Colour", default = [0.0, 0.0, 0.0, 1.0], subtype = 'COLOR', min = 0, max = 1, update = wire_update) 
    wv_extend: FloatProperty(name = "", description = "Wire extension", default = 0, min = 0, max = 1, update = wire_update) 
    wv_angle: FloatProperty(name = "", description = "Wire angle", default = 45, min = 0, max = 180, update = wire_update) 
    wv_material: BoolProperty(name = '', default = False, description = 'Material boundary')
    wv_dia: FloatProperty(name = "mm", description = "Wire diameter", default = 20, min = 0.1, max = 1000, update = wire_update) 
    wv_seg: IntProperty(name = "", description = "Wire segments", default = 3, min = 3, max = 12, update = wire_update) 

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
            newrow(layout,  'Extend:',  ots,  "wv_extend")
            newrow(layout,  'Colour:',  ots,  "wv_colour")
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
#        self.draw_handle_wv = SpaceView3D.draw_handler_add(self.draw_wv, (self, context), "WINDOW", "POST_VIEW")
        context.window_manager.modal_handler_add(self)
        wvp.wv_display = 1
        wvp.update = 1
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        scene = context.scene
        wvp = scene.wv_params
        
        if not wvp.wv_display:
            return {'FINISHED'}

        dp = context.evaluated_depsgraph_get()

        if wvp.update:
            bm = bmesh.new()
            
            for ob in [ob.evaluated_get(dp) for ob in scene.objects if ob.wirevis_settings.wv_bool]:  
                ows = ob.wirevis_settings
                obbm = bmesh.new()
                obbm.from_mesh(ob.data)
                obbm.transform(ob.matrix_world)
                ecoords = [[v.co for v in e.verts] for e in obbm.edges if e.calc_face_angle(0.1) * 180/pi > ob.wirevis_settings.wv_angle or ows.wv_material and len(e.link_faces) == 2 and len(set([f.material_index for f in e.link_faces])) == 2]                
                ecentres = [(e[0] + e[1]) * 0.5 for e in ecoords]

                for ei, ec in enumerate(ecentres):
                    length = (ecoords[ei][0] - ecoords[ei][1]).length
                    mat_trans = mathutils.Matrix.Translation(ec)
                    mat_rot = mathutils.Vector((0, 0, 1)).rotation_difference(ecoords[ei][1] - ec).to_matrix().to_4x4()
                    print('start', datetime.datetime.now())
                    wire_verts = bmesh.ops.create_cone(bm, cap_ends = 1, cap_tris = 1, segments = ows.wv_seg, radius1 = ows.wv_dia * 0.001, radius2 = ows.wv_dia * 0.001, depth = length, matrix = mat_trans@mat_rot)['verts']
                    print('end', datetime.datetime.now())
                    
                    if ows.wv_extend > 0:
                        wire_verts[0].co += (wire_verts[0].co - ec).normalized() * ows.wv_extend
                        wire_verts[1].co += (wire_verts[1].co - ec).normalized() * ows.wv_extend
                    
                
                obbm.free()

            try:
                wire_object = bpy.data.objects['wire_object']
                bm.transform(wire_object.matrix_world.inverted())
                bm.to_mesh(wire_object.data)
            except:
                wire_mesh = bpy.data.meshes.new('wire_mesh')
                wire_object = bpy.data.objects.new("wire_object", wire_mesh)
                bm.transform(wire_object.matrix_world.inverted())
                bm.to_mesh(wire_mesh)
                bpy.context.collection.objects.link(wire_object)

            bm.free()
            wvp.update = 0
            return {'PASS_THROUGH'}
        else:
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