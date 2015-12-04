from .wall.ops import *
from .window.ops import *
from .door.ops import *
from .floor.ops import *


def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)