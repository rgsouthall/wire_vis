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
           "version": (0, 3, 0),
           "blender": (2, 93, 0),
           "location": "Object Properties Panel",
           "description": "Display wireframes on selected geometry",
           "warning": "",
           "wiki_url": "tba",
           "tracker_url": "",
           "category": "Object"}

import bpy, gpu, bgl, bmesh, mathutils
from math import pi
from bpy.props import BoolProperty, PointerProperty, FloatVectorProperty, FloatProperty, IntProperty
from bpy.types import Panel, PropertyGroup, Operator, SpaceView3D
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader

class WIREVIS_Scene_Settings(PropertyGroup):
    wv_display: BoolProperty(name = '', default = False, description = 'Display wire')

class WIREVIS_Object_Settings(PropertyGroup):
    wv_bool: BoolProperty(name = '', default = False, description = 'Display wire')
    wv_colour: FloatVectorProperty(size = 4, name = "", attr = "Colour", default = [0.0, 0.0, 0.0, 1.0], subtype = 'COLOR', min = 0, max = 1) 
    wv_extend: FloatProperty(name = "", description = "Wire extension", default = 0, min = 0, max = 1) 
    wv_angle: FloatProperty(name = "", description = "Wire angle", default = 0, min = 0, max = 180) 
    wv_dia: FloatProperty(name = "mm", description = "Wire diameter", default = 20, min = 0.1, max = 1000) 
    wv_seg: IntProperty(name = "", description = "Wire segments", default = 3, min = 3, max = 12) 

class WIREVIS_PT_scene(Panel):
    '''WireVis 3D view panel'''
    bl_label = "Wire"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WireVis"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("view3d.wirevis", text="WireVis Display") 

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

    def create_batch(self, scene):
        wv_vertex_shader = '''
            uniform mat4 viewProjectionMatrix;
//            uniform mat4 vw_matrix;            
//            uniform float extend;
            in vec3 position;   
            //in vec3 e_centre;         
            
            void main()
            {
                gl_Position = viewProjectionMatrix * (vec4(position, 1.0f));
            }
        '''
        wv_geometry_shader = '''
            layout (lines) in;
            layout (line_strip, max_vertices = 2) out;

            void main() 
            {    
                gl_Position = gl_in[0].gl_Position + vec4(-0.1, 0.0, 0.0, 0.0); 
                EmitVertex();

                gl_Position = gl_in[1].gl_Position + vec4(0.1, 0.0, 0.0, 0.0);
                EmitVertex();
    
                EndPrimitive();
            } 
        '''

        wv_fragment_shader = '''
            uniform vec4 colour;
            out vec4 FragColour;

            void main()
            {
                FragColour = colour;
            }
        '''
        self.wv_shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
#        self.wv_shader = GPUShader(wv_vertex_shader, wv_fragment_shader)#, geocode = wv_geometry_shader) 
#        ob = scene.active_object
#        coords = [v.co for v in ob.data.vertices]
#        self.wv_batch = batch_for_shader(self.wv_shader, 'LINE_STRIP', {"position": coords})

    def draw_wv(self, op, context):
#        dp = context.evaluated_depsgraph_get()
        scene = context.scene
        #try:
            # Draw lines
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glDepthFunc(bgl.GL_LESS)
        bgl.glDepthMask(bgl.GL_FALSE)
        bgl.glEnable(bgl.GL_BLEND)         
#            bgl.glLineWidth(1)   
        gpu.state.depth_test_set('LESS')
        gpu.state.depth_mask_set(False)
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(1)
        bgl.glHint(bgl.GL_POLYGON_SMOOTH_HINT, bgl.GL_NICEST)
        bgl.glEnable(bgl.GL_POLYGON_SMOOTH)            
        bgl.glEnable(bgl.GL_MULTISAMPLE)

        matrix = bpy.context.region_data.perspective_matrix

        try:
            self.wv_shader.bind()
        except Exception as e:
            print('e0', e)
            self.create_batch(scene)
        
        for ob in [ob for ob in scene.objects if ob.wirevis_settings.wv_bool]:
            bm = bmesh.new()
            obbm = bmesh.new()
            obbm.from_mesh(ob.data)
            obbm.transform(ob.matrix_world)
            ecoords = [[v.co for v in e.verts] for e in obbm.edges if e.calc_face_angle(0.1) * 180/pi > ob.wirevis_settings.wv_angle]
            obbm.free()
            ecentres = [(e[0] + e[1]) * 0.5 for e in ecoords]
#            fcoords = []

            for ei, ec in enumerate(ecentres):
#                    print(ec)
#                    bm = bmesh.new()
                mat_trans = mathutils.Matrix.Translation(ec)
#                    print(mathutils.Vector((0, 0, 1)).rotation_difference(ecoords[ei][0] - ec))
                mat_rot = mathutils.Vector((0, 0, 1)).rotation_difference(ecoords[ei][0] - ec).to_matrix().to_4x4()
                wire_verts = bmesh.ops.create_cone(bm, cap_ends = 1, cap_tris = 1, segments = ob.wirevis_settings.wv_seg, diameter1 = ob.wirevis_settings.wv_dia * 0.001, diameter2 = ob.wirevis_settings.wv_dia * 0.001, depth = (ecoords[ei][0] - ecoords[ei][1]).length, matrix = mat_trans@mat_rot)['verts']
#                    bmesh.ops.create_cone(bm, cap_ends = 1, cap_tris = 1, segments = 4, diameter1 = 0.1, diameter2 = 0.1, depth = (ecoords[ei][0] - ecoords[ei][1]).length)
#                    print([v.co for v in bm.verts])
                wire_verts[0].co += (wire_verts[0].co - ec).normalized() * ob.wirevis_settings.wv_extend
                wire_verts[1].co += (wire_verts[1].co - ec).normalized() * ob.wirevis_settings.wv_extend
#                    bm.verts.ensure_lookup_table()
#                    bm.verts[ei * (2 * ob.wirevis_settings.wv_seg + 2)].co += (bm.verts[ei * (2 * ob.wirevis_settings.wv_seg + 2)].co - ec).normalized() * ob.wirevis_settings.wv_extend
#                    bm.verts[ei * (2 * ob.wirevis_settings.wv_seg + 2) + 1].co += (bm.verts[ei * (2 * ob.wirevis_settings.wv_seg + 2) + 1].co - ec).normalized() * ob.wirevis_settings.wv_extend
            bmesh.ops.triangulate(bm, faces = bm.faces)
            vcoords = [v.co for v in bm.verts]
            indices = [[v.index for v in f.verts] for f in bm.faces]
#            fcoords = [[v.co for v in f.verts] for f in bm.faces]
            bm.free()
#                print(len(fcoords), len(ecentres))    
#            ecentres = [x for pair in zip(ecentres,ecentres) for x in pair]
#            coords = [item for sublist in fcoords for item in sublist]   
            print(len(vcoords))             
            self.wv_batch = batch_for_shader(self.wv_shader, 'TRIS', {"pos": vcoords}, indices = indices)
#            vw_matrix = ob.matrix_world
#            self.wv_shader.uniform_float("viewProjectionMatrix", matrix)
#            self.wv_shader.uniform_float("vw_matrix", vw_matrix)
            self.wv_shader.uniform_float("color", ob.wirevis_settings.wv_colour)
#                self.wv_shader.uniform_float("extend", ob.wirevis_settings.wv_extend)

        
        self.wv_batch.draw(self.wv_shader)
        bgl.glDisable(bgl.GL_MULTISAMPLE)
        bgl.glDisable(bgl.GL_POLYGON_SMOOTH)            
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glClear(bgl.GL_DEPTH_BUFFER_BIT)
        bgl.glDisable(bgl.GL_DEPTH_TEST) 
        bgl.glDepthMask(bgl.GL_TRUE)
        bgl.glPointSize(1)
            

#        except Exception as e:
#            print('e1', e)

    def invoke(self, context, event):
        scene = context.scene
        wvp = scene.wv_params
        self.draw_handle_wv = SpaceView3D.draw_handler_add(self.draw_wv, (self, context), "WINDOW", "POST_VIEW")
        context.window_manager.modal_handler_add(self)
        wvp.wv_display = 1
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        scene = context.scene
        wvp = scene.wv_params

        if context.area:
            context.area.tag_redraw()
            
        if wvp.wv_display == 0:
            try:
                SpaceView3D.draw_handler_remove(self.draw_handle_wv, "WINDOW")
            except:
                pass
                
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

def newrow(layout, s1, root, s2):
    row = layout.row()
    row.label(text=s1)
    row.prop(root, s2)

classes = (WIREVIS_PT_object, WIREVIS_Object_Settings, WIREVIS_Scene_Settings, VIEW3D_OT_WireVis, WIREVIS_PT_scene)

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    bpy.types.Scene.wv_params = PointerProperty(type=WIREVIS_Scene_Settings)
    bpy.types.Object.wirevis_settings = PointerProperty(type=WIREVIS_Object_Settings)

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)