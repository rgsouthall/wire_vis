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

import bpy, gpu, bgl
from bpy.props import BoolProperty, PointerProperty, FloatVectorProperty
from bpy.types import Panel, PropertyGroup, Operator
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader

class WIREVIS_Object_Settings(PropertyGroup):
    wv_bool: BoolProperty(name = '', default = False, description = 'Display wire')
    wv_colour: FloatVectorProperty(size = 4, name = "", attr = "Colour", default = [0.0, 0.0, 0.0, 1.0], subtype = 'COLOR', min = 0, max = 1) 

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

class VIEW3D_OT_WireVis(Operator):
    bl_idname = "view3d.wirevis"
    bl_label = "Wire Vis"
    bl_description = "Display Wireframe"
    bl_register = True
    bl_undo = False

    def create_batch(self):
        wv_vertex_shader = '''
            uniform mat4 viewProjectionMatrix;
            uniform mat4 vw_matrix;
            uniform vec4 colour;
            in vec3 position;            
            out vec4 w_colour;
            
            void main()
            {
                w_colour = colour;
                gl_Position = viewProjectionMatrix * vw_matrix * vec4(position, 1.0f);
            }
        '''
        
        wv_fragment_shader = '''
            in vec4 w_colour;
            out vec4 FragColour;
 
            void main()
            {
                FragColour = w_colour;
            }
        '''

        self.wv_shader = GPUShader(wv_vertex_shader, wv_fragment_shader) 
        coords = self.ret_coords()
        self.wv_batch = batch_for_shader(self.sp_shader, 'LINE_STRIP', {"position": coords})

    def draw_wv(self, op, context):
        scene = context.scene
        try:
        # Draw lines
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            bgl.glDepthFunc(bgl.GL_LESS)
            bgl.glDepthMask(bgl.GL_FALSE)
            bgl.glEnable(bgl.GL_BLEND)            
            gpu.state.depth_test_set('LESS')
            gpu.state.depth_mask_set(False)
            gpu.state.blend_set('ALPHA')

            try:
                self.sp_shader.bind()
            except:
                self.create_batch()

            matrix = bpy.context.region_data.perspective_matrix

            for ob in [ob for ob in scene.objects if ob.wirevis_settings]:
                vw_matrix = ob.matrix_world
                self.sp_shader.uniform_float("viewProjectionMatrix", matrix)
                self.sp_shader.uniform_float("vw_matrix", vw_matrix)
                self.sp_shader.uniform_float("colour", ob.wirevis_settings.wv_colour)
        except:
            pass

def newrow(layout, s1, root, s2):
    row = layout.row()
    row.label(text=s1)
    row.prop(root, s2)

classes = (WIREVIS_PT_object, WIREVIS_Object_Settings)

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    bpy.types.Object.wirevis_settings = PointerProperty(type=WIREVIS_Object_Settings)

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)