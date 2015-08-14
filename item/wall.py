import bmesh
from base import getLevelLocation, xAxis, yAxis, zAxis, zero
from blender_util import *


def getWallFromEmpty(context, op, empty, end=False):
    # The end==True means empty must be at either open end of the wall
    # check validity of empty
    if not (empty and empty.type == "EMPTY" and (not end or "e" in empty)):
        return None
    wall = Wall(context, op, False)
    wall.init(empty.parent)
    return wall


def addTransformsVariable(driver, name, id0, transform_type):
    v = driver.driver.variables.new()
    v.name = name
    v.type = "TRANSFORMS"
    v.targets[0].id = id0
    v.targets[0].transform_type = transform_type
    v.targets[0].transform_space = "LOCAL_SPACE"


def addSinglePropVariable(driver, name, id0, data_path):
    v = driver.driver.variables.new()
    v.name = name
    v.type = "SINGLE_PROP"
    v.targets[0].id = id0
    v.targets[0].data_path = data_path


def addLocDiffVariable(driver, name, id0, id1):
        v = driver.driver.variables.new()
        v.name = name
        v.type = "LOC_DIFF"
        v.targets[0].id = id0
        v.targets[0].transform_space = "LOCAL_SPACE"
        v.targets[1].id = id1
        v.targets[1].transform_space = "LOCAL_SPACE"


def getFaceFortVerts(verts1, verts2):
    # find the common face for both verts1 and verts2
    for face in verts1[0].link_faces:
        if face in verts2[0].link_faces and face in verts2[1].link_faces:
            return face


class Wall:
    
    emptyProperties = {'empty_draw_type':'CUBE', 'empty_draw_size':0.02}
    
    def __init__(self, context, op, create):
        self.context = context
        self.op = op
        if create:
            self.create()
    
    def init(self, parent):
        self.parent = parent
        # getting mesh object
        for obj in parent.children:
            if obj.type == "MESH":
                self.mesh = obj
                break
    
    def create(self, locEnd=None):
        context = self.context
        op = self.op
        loc = getLevelLocation(context)
        
        h = op.height
        w = op.width
        
        # the initial wall segment is oriented along Y-axis by default
        alongX = False
        # check if the initial wall segment should be oriented along X-axis or along Y-axis
        if locEnd:
            dx = locEnd.x-loc.x
            dy = locEnd.y-loc.y
            if abs(dx) > abs(dy):
                alongX = True
                l = dx
            else:
                l = dy
        else:
            l = op.length
        
        # parent one vert mesh
        parent = createOneVertObject("Wall", loc)
        parent.dupli_type = "VERTS"
        parent.hide_select = True
        
        obj = createMeshObject("wall_mesh")
        obj["counter"] = 1
        obj["height"] = h
        obj["start"] = "0"
        obj["end"] = "1"
        obj.hide_select = True
        
        bm = getBmesh(obj)
        # vertex groups are in the deform layer, create one before any operation with bmesh:
        layer = bm.verts.layers.deform.new()
        
        # verts
        v = [
            (0., 0., 0.), (0., -w, 0.), (l, -w, 0.), (l, 0., 0.),
            (0., 0., h), (0., -w, h), (l, -w, h), (l, 0., h)
        ] if alongX else [
            (0., 0., 0.), (w, 0., 0.), (w, l, 0.), (0, l, 0.),
            (0., 0., h), (w, 0., h), (w, l, h), (0., l, h)
        ]
        
        # create verts
        for i in range(len(v)):
            v[i] = bm.verts.new(v[i])
        
        # create faces
        # bottom face
        bm.faces.new((v[0], v[3], v[2], v[1]))
        # top face
        bm.faces.new((v[4], v[5], v[6], v[7]))
        # left face
        bm.faces.new((v[0], v[4], v[7], v[3]))
        # right face
        bm.faces.new((v[1], v[2], v[6], v[5]))
        # front face
        bm.faces.new((v[0], v[1], v[5], v[4]))
        # back face
        bm.faces.new((v[3], v[7], v[6], v[2]))
        
        # create vertex groups for each vertical wall edge and empty object as a wall controller
        # for the wall origin
        # left
        assignGroupToVerts(obj, layer, "l0", v[0], v[4])
        assignGroupToVerts(obj, layer, "r0", v[1], v[5])
        # for the wall end
        assignGroupToVerts(obj, layer, "l1", v[3], v[7])
        assignGroupToVerts(obj, layer, "r1", v[2], v[6])
        
        bm.to_mesh(obj.data)
        bm.free()
        
        # l means left
        # e means end: e==0 for the start, e==1 for the end
        # n means next
        # p means previous
        # g means group to identify the related modifier and vertex group
        # w means width
        l0 = self.createEmptyObject("l0", (0., 0., 0.), False)
        setCustomAttributes(l0, l=1, e=0, g="0", w=w, n="1")
        r0 = self.createEmptyObject("r0", (0., -w, 0.) if alongX else (w, 0., 0.), True)
        setCustomAttributes(r0, l=0, e=0, g="0", w=w, n="1")
        l1 = self.createEmptyObject("l1", (l, 0., 0.) if alongX else (0., l, 0.), False)
        setCustomAttributes(l1, l=1, e=1, g="1", w=w, p="0")
        r1 = self.createEmptyObject("r1", (l, -w, 0.) if alongX else (w, l, 0.), True)
        setCustomAttributes(r1, l=0, e=1, g="1", w=w, p="0")
        
        # without scene.update() parenting and hook modifiers will not work correctly
        context.scene.update()
        
        # perform parenting
        parent_set((obj, l0, r0, l1, r1), parent)
        
        # without scene.update() parenting and hook modifiers will not work correctly
        # this step is probably optional here, however it's required in self.extend(..)
        context.scene.update()
        
        # add hook modifiers
        addHookModifier(obj, "l0", l0, "l0")
        addHookModifier(obj, "r0", r0, "r0")
        addHookModifier(obj, "l1", l1, "l1")
        addHookModifier(obj, "r1", r1, "r1")
        
        # add drivers
        self.addEndEdgeDrivers(r0, l0, l1, False)
        self.addEndEdgeDrivers(r1, l0, l1, True)
        
        bpy.ops.object.select_all(action="DESELECT")
        l1.select = True
        context.scene.objects.active = l1
        
        return (alongX, not alongX, False)
    
    def extend(self, empty1, locEnd = None):
        
        alongX = False
        alongY = False
        
        if locEnd:
            # convert the end location to the coordinate system of the wall
            locEnd = self.parent.matrix_world.inverted() * locEnd
            
        
        empty2 = self.getNeighbor(empty1)
        context = self.context
        op = self.op
        mesh = self.mesh
        counter = mesh["counter"] + 1
        group = str(counter)
        # are we at the end (1) or at the start (0)
        end = empty1["e"]
        h = mesh["height"]
        # the width of the new wall segment
        w = empty1["w"]
        
        bm = getBmesh(mesh)
        # All vertex groups are in the deform layer.
        # There can be only one deform layer
        layer = bm.verts.layers.deform[0]
        
        left = empty1["l"]
        prefix1 = "l" if left else "r"
        group1 = prefix1 + group
        # prefix for the neighbor verts located to the left or to the right
        prefix2 = "r" if left else "l"
        group2 = prefix2 + group
        # delete the face at the open end of the wall, defined by the related vertex groups
        verts1 = self.getVertsForVertexGroup(bm, prefix1+empty1["g"])
        verts2 = self.getVertsForVertexGroup(bm, prefix2+empty1["g"])
        bmesh.ops.delete(
            bm,
            geom=(getFaceFortVerts(verts1, verts2),),
            context=3
        )
        # continuation of the vertex controlled by empty1, a Blender empty object
        # normal to the open edge ending by empty1
        n = (
                empty1.location - self.getPrevious(empty1).location if end else self.getNext(empty1).location - empty1.location
            ).cross(zAxis).normalized()
        if locEnd:
            # check if n is oriented along X-axis or Y-axis
            if abs(n[0])<zero:
                alongY = True
                n = yAxis
                l = locEnd.y - empty1.location.y
            elif abs(n[1])<zero:
                alongX = True
                n = xAxis
                l = locEnd.x - empty1.location.x
            else:
                l = op.length
        else:
            l = op.length
        
        loc = empty1.location + l*n
        e1 = self.createEmptyObject(group1, loc, False)
        setCustomAttributes(e1, l=1, e=end, g=group, w=w)
        if end:
            setCustomAttributes(e1, p=empty1["g"])
            setCustomAttributes(empty1, n=group)
        else:
            setCustomAttributes(e1, n=empty1["g"])
            setCustomAttributes(empty1, p=group)
        del empty1["e"]
        # create also the accompanying verts
        v1_1 = bm.verts.new(e1.location)
        v1_2 = bm.verts.new(v1_1.co + h*zAxis)
        # neighbor of e1
        # normal to the line between empty1.location and e1.location
        n = n.cross(zAxis)
        if not end:
            n = -n
        e2 = self.createEmptyObject(group2, loc + w*n, True)
        setCustomAttributes(e2, l=0, e=1, g=group, w=w, p=empty1["g"])
        if end:
            setCustomAttributes(e2, p=empty1["g"])
            setCustomAttributes(empty2, n=group)
        else:
            setCustomAttributes(e2, n=empty1["g"])
            setCustomAttributes(empty2, p=group)
        del empty2["e"]
        # create also the accompanying verts
        v2_1 = bm.verts.new(e2.location)
        v2_2 = bm.verts.new(v2_1.co + h*zAxis)
        
        # update the location of empty2
        #empty2.location = self.inset(
        #    empty1.location, w, w, n,
        #    (empty1.location-self.getPrevious(empty1).location).normalized(),
        #    (e1.location-empty1.location).normalized()
        #)
        #empty2.location = self.inset(
        #    empty1.location, w, w,
        #    self.getPrevious(empty1).location,
        #    empty1.location,
        #    e1.location
        #)
        if end:
            self.addInternalEdgeDrivers(empty2, self.getPrevious(empty1), empty1, e1, end)
        else:
            self.addInternalEdgeDrivers(empty2, e1, empty1, self.getNext(empty1), end)
        
        # create all necessary faces
        bm.faces.new( (verts1[0], verts1[1], v1_2, v1_1) if end else (v1_1, v1_2, verts1[1], verts1[0]) )
        bm.faces.new( (v1_1, v1_2, v2_2, v2_1) if end else (v2_1, v2_2, v1_2, v1_1) )
        bm.faces.new((v2_1, v2_2, verts2[1], verts2[0]) if end else (verts2[0], verts2[1], v2_2, v2_1) )
        bm.faces.new((verts1[1], verts2[1], v2_2, v1_2) if end else (v1_2, v2_2, verts2[1], verts1[1]) )
        bm.faces.new((v1_1, v2_1, verts2[0], verts1[0]) if end else (verts1[0], verts2[0], v2_1, v1_1) )
        
        assignGroupToVerts(mesh, layer, group1, v1_1, v1_2)
        assignGroupToVerts(mesh, layer, group2, v2_1, v2_2)
        
        mesh["counter"] = counter
        if end:
            mesh["end"] = group
        else:
            mesh["start"] = group
        bm.to_mesh(mesh.data)
        bm.free()
        
        # without scene.update() parenting and hook modifiers will not work correctly
        # this step is probably optional here, however it's required in self.create()
        context.scene.update()
        
        # perform parenting
        parent_set((e1, e2), self.parent)
        
        # without scene.update() parenting and hook modifiers will not work correctly
        context.scene.update()
        
        # add hook modifiers
        addHookModifier(mesh, group1, e1, group1)
        addHookModifier(mesh, group2, e2, group2)
        
        # add drivers
        if end:
            self.addEndEdgeDrivers(e2, empty1, e1, True)
        else:
            self.addEndEdgeDrivers(e2, e1, empty1, False)
        
        bpy.ops.object.select_all(action="DESELECT")
        e1.select = True
        context.scene.objects.active = e1
        
        return (alongX, alongY, False)
    
    def complete(self, left):
        mesh = self.mesh
        start = self.getStart(left)
        end = self.getEnd(left)
        
        bm = getBmesh(mesh)
        
        prefix1 = "l" if left else "r"
        # prefix for the neighbor verts located to the left or to the right
        prefix2 = "r" if left else "l"
        
        # delete the faces at the open ends of the wall, defined by the related vertex groups
        # for empty1
        verts1_1 = self.getVertsForVertexGroup(bm, prefix1+start["g"])
        verts1_2 = self.getVertsForVertexGroup(bm, prefix2+start["g"])
        # for empty2
        verts2_1 = self.getVertsForVertexGroup(bm, prefix1+end["g"])
        verts2_2 = self.getVertsForVertexGroup(bm, prefix2+end["g"])
        bmesh.ops.delete(
            bm,
            geom=( getFaceFortVerts(verts1_1, verts1_2), getFaceFortVerts(verts2_1, verts2_2) ),
            context=3
        )
        
        # create faces
        # top and bottom
        bm.faces.new((verts2_1[1], verts2_2[1], verts1_2[1], verts1_1[1]))
        bm.faces.new((verts1_1[0], verts1_2[0], verts2_2[0], verts2_1[0]))
        # front and back
        bm.faces.new((verts2_1[0], verts2_1[1], verts1_1[1], verts1_1[0]))
        bm.faces.new((verts1_2[0], verts1_2[1], verts2_2[1], verts2_2[0]))
        
        end["n"] = start["g"]
        start["p"] = end["g"]
        del start["e"], end["e"], mesh["start"], mesh["end"]
        
        bm.to_mesh(self.mesh.data)
        bm.free()
        
        # without scene.update() parenting and hook modifiers will not work correctly
        self.context.scene.update()
        
        self.addInternalEdgeDrivers(self.getNeighbor(start), end, start, self.getNext(start), 0)
        self.addInternalEdgeDrivers(self.getNeighbor(end), self.getPrevious(end), end, start, 1)

    def getNeighbor(self, o):
        prefix = "r" if o["l"] else "l"
        return self.mesh.modifiers[prefix+o["g"]].object
    
    def getNext(self, o):
        if "e" in o and o["e"]:
            return None
        prefix = "l" if o["l"] else "r"
        return self.mesh.modifiers[prefix+o["n"]].object

    def getPrevious(self, o):
        if "e" in o and not o["e"]:
            return None
        prefix = "l" if o["l"] else "r"
        return self.mesh.modifiers[prefix+o["p"]].object
    
    def getStart(self, left):
        return None if self.isClosed() else self.getEmpty(self.mesh["start"], left)
        
    def getEnd(self, left):
        return None if self.isClosed() else self.getEmpty(self.mesh["end"], left)
    
    def getEmpty(self, group, left):
        prefix = "l" if left else "r"
        return self.mesh.modifiers[prefix+group].object
    
    def isClosed(self):
        return not "end" in self.mesh
    
    def createEmptyObject(self, name, location, hide):
        empty = createEmptyObject(name, location, hide, **self.emptyProperties)
        empty.lock_location[2] = True
        return empty
    
    def getVertsForVertexGroup(self, bm, group):
        """
        Gets verts for the vertex group and rearranges them if necessary
        """
        verts = getVertsForVertexGroup(self.mesh, bm, group)
        # rearrange verts if necessary
        if verts[0].co.z>verts[1].co.z:
            verts[0], verts[1] = verts[1], verts[0]
        
        return verts
    
    def inset0(self, location, w1, w2, n2, vec1, vec2):
        zero = 0.000001
        # cross product between edge1 and edge1
        cross = vec1.cross(vec2)
        # To check if have a concave (>180) or convex angle (<180) between edge1 and edge2
        # we calculate dot product between cross and axis
        # If the dot product is positive, we have a convex angle (<180), otherwise concave (>180)
        dot = cross.dot(zAxis)
        convex = True if dot>0 else False
        # sine of the angle between -self.edge1.vec and self.edge2.vec
        sin = cross.length
        isLine = True if sin<zero and convex else False
        if not isLine:
            #sin = sin if convex else -sin
            # cosine of the angle between -self.edge1.vec and self.edge2.vec
            cos = -(vec1.dot(vec2))
        
        return location + w2*n2 + (w1+w2*cos)/sin*vec2

    def inset(self, location, w1, w2, p0, p1, p2):
        import math
        zero = 0.000001
        x0 = p0.x
        y0 = p0.y
        
        x1 = p1.x
        y1 = p1.y
        
        x2 = p2.x
        y2 = p2.y
        
        d1 = math.sqrt((x1-x0)*(x1-x0)+(y1-y0)*(y1-y0))
        d2 = math.sqrt((x2-x1)*(x2-x1)+(y2-y1)*(y2-y1))
        
        # cross product between edge1 and edge1
        #cross = vec1.cross(vec2)
        cross = ((x1-x0)*(y2-y1) - (y1-y0)*(x2-x1)) / (d1*d2)
        n2x = (y2-y1)/d2
        n2y = (x1-x2)/d2
        # To check if have a concave (>180) or convex angle (<180) between edge1 and edge2
        # we calculate dot product between cross and axis
        # If the dot product is positive, we have a convex angle (<180), otherwise concave (>180)
        #dot = cross.dot(zAxis)
        #convex = True if dot>0 else False
        # sine of the angle between -self.edge1.vec and self.edge2.vec
        sin = -cross
        #isLine = True if sin<zero and convex else False
        #if not isLine:
            #sin = sin if convex else -sin
            # cosine of the angle between -self.edge1.vec and self.edge2.vec
            #cos = -(vec1.dot(vec2))
        cos = -((x1-x0)*(x2-x1)+(y1-y0)*(y2-y1))
        
        return (
            location.x + w2*(y2-y1)/d2 - (w1-w2*((x1-x0)*(x2-x1)+(y1-y0)*(y2-y1))) *(x2-x1) / ((x1-x0)*(y2-y1) - (y1-y0)*(x2-x1)) * d1,
            location.y + w2*(x1-x2)/d2 - (w1-w2*((x1-x0)*(x2-x1)+(y1-y0)*(y2-y1))) *(y2-y1) / ((x1-x0)*(y2-y1) - (y1-y0)*(x2-x1)) * d1,
            location.z
        )

    def addEndEdgeDrivers(self, slave, m0, m1, end):
        """
        Adds drivers for an end vertical edge (a slave edge) of the wall
        
        Args:
            slave: A Blender empty object that controls the slave open vertical edge of the wall
            m0: A Blender empty object that defines the start of the master horizontal edge of the wall
            m1: A Blender empty object that defines the end of the master horizontal edge of the wall
            end (bool): Defines which of m0 (False) and m1 (True) controls the master open vertical edge of the wall
        """
        master = m1 if end else m0
        
        # add driver for slave.location.x
        x = slave.driver_add("location", 0)
        # x
        addTransformsVariable(x, "x", master, "LOC_X")
        # y0 or y1
        addTransformsVariable(x, "y0" if end else "y1", m0, "LOC_Y")
        # y1 or y2
        addTransformsVariable(x, "y1" if end else "y2", m1, "LOC_Y")
        # d1 or d2: distance between m0 and m1
        addLocDiffVariable(x, "d1" if end else "d2", m0, m1)
        # w1 or w2: width
        addSinglePropVariable(x, "w1" if end else "w2", m1, "[\"w\"]")
        # expression
        x.driver.expression = "x + w1*(y1-y0)/max(d1, 0.001)" if end else "x + w2*(y2-y1)/max(d2, 0.001)"
        
        # add driver for x r1.location.y
        y = slave.driver_add("location", 1)
        # y
        addTransformsVariable(y, "y", master, "LOC_Y")
        # x0 or x1
        addTransformsVariable(y, "x0" if end else "x1", m0, "LOC_X")
        # x1 or x2
        addTransformsVariable(y, "x1" if end else "x2", m1, "LOC_X")
        # d1 or d2: distance between m0 and m1
        addLocDiffVariable(y, "d1" if end else "d2", m0, m1)
        # w1 or w2: width
        addSinglePropVariable(y, "w1" if end else "w2", m1, "[\"w\"]")
        # expression
        y.driver.expression = "y + w1*(x0-x1)/max(d1, 0.001)" if end else "y + w2*(x1-x2)/max(d2, 0.001)"

    def addInternalEdgeDrivers(self, slave, m0, m1, m2, end):
        # update the driver for slave.location.x
        x = slave.animation_data.drivers[0]
        # x0
        addTransformsVariable(x, "x0", m0, "LOC_X")
        # x1
        addTransformsVariable(x, "x1", m1, "LOC_X")
        # x2
        addTransformsVariable(x, "x2", m2, "LOC_X")
        # y2 or y0
        addTransformsVariable(x, "y2" if end else "y0", m2 if end else m0, "LOC_Y")
        # d2 or d1: distance between m1 and m2 or m1 and m0
        addLocDiffVariable(x, "d2" if end else "d1", m1, m2 if end else m0)
        # w2 or w1: width
        addSinglePropVariable(x, "w2" if end else "w1", m2 if end else m1, "[\"w\"]")
        # expression
        x.driver.expression = "x + w2*(y2-y1)/max(d2,0.001) - (w1-w2*((x1-x0)*(x2-x1)+(y1-y0)*(y2-y1))/max(d1,0.001)/max(d2,0.001)) * (x2-x1) * d1 / ((x1-x0)*(y2-y1)-(y1-y0)*(x2-x1) if abs((x1-x0)*(y2-y1)-(y1-y0)*(x2-x1))>0.001 else 0.001)"

        # update the driver for slave.location.y
        y = slave.animation_data.drivers[1]
        # x2 or x0
        addTransformsVariable(y, "x2" if end else "x0", m2 if end else m0, "LOC_X")
        # y0
        addTransformsVariable(y, "y0", m0, "LOC_Y")
        # y1
        addTransformsVariable(y, "y1", m1, "LOC_Y")
        # y2
        addTransformsVariable(y, "y2", m2, "LOC_Y")
        # d2 or d1: distance between m1 and m2 or m1 and m0
        addLocDiffVariable(y, "d2" if end else "d1", m1, m2 if end else m0)
        # w2 or w1: width
        addSinglePropVariable(y, "w2" if end else "w1", m2 if end else m1, "[\"w\"]")
        # expression
        y.driver.expression = "y + w2*(x1-x2)/max(d2,0.001) - (w1-w2*((x1-x0)*(x2-x1)+(y1-y0)*(y2-y1))/max(d1,0.001)/max(d2,0.001)) * (y2-y1) * d1 / ((x1-x0)*(y2-y1)-(y1-y0)*(x2-x1) if abs((x1-x0)*(y2-y1)-(y1-y0)*(x2-x1))>0.001 else 0.001)"