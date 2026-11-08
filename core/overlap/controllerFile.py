from maya import cmds
from maya import mel


class SHAPES:
    class CUBE:
        points = [
            [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5], [-0.5, -0.5, -0.5],
            [-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5],
            [0.5, -0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5]
        ]
        knots = list(range(16))

    class SPHERE:
        points = [
            [0, 0.5, 0], [0, 0.46194, 0.191341], [0, 0.353554, 0.353554], [0, 0.191341, 0.46194],
            [0, 0, 0.5], [0, -0.191341, 0.46194], [0, -0.353554, 0.353554], [0, -0.46194, 0.191341],
            [0, -0.5, 0], [0, -0.46194, -0.191341], [0, -0.353554, -0.353554], [0, -0.191341, -0.46194],
            [0, 0, -0.5], [0, 0.191341, -0.46194], [0, 0.353554, -0.353554], [0, 0.46194, -0.191341],
            [0, 0.5, 0], [0.191341, 0.46194, 0], [0.353554, 0.353554, 0], [0.46194, 0.191341, 0],
            [0.5, 0, 0], [0.46194, -0.191341, 0], [0.353554, -0.353554, 0], [0.191341, -0.46194, 0],
            [0, -0.5, 0], [-0.191341, -0.46194, 0], [-0.353554, -0.353554, 0], [-0.46194, -0.191341, 0],
            [-0.5, 0, 0], [-0.46194, 0.191341, 0], [-0.353554, 0.353554, 0], [-0.191341, 0.46194, 0],
            [0, 0.5, 0], [0, 0.46194, -0.191341], [0, 0.353554, -0.353554], [0, 0.191341, -0.46194],
            [0, 0, -0.5], [-0.191341, 0, -0.46194], [-0.353554, 0, -0.353554], [-0.46194, 0, -0.191341],
            [-0.5, 0, 0], [-0.46194, 0, 0.191341], [-0.353554, 0, 0.353554], [-0.191341, 0, 0.46194],
            [0, 0, 0.5], [0.191341, 0, 0.46194], [0.353554, 0, 0.353554], [0.46194, 0, 0.191341],
            [0.5, 0, 0], [0.46194, 0, -0.191341], [0.353554, 0, -0.353554], [0.191341, 0, -0.46194], [0, 0, -0.5]
        ]
        knots = list(range(53))


class create_control:
    def __init__(self):
        self.world = 0
        self.crv = 1
        self.scale = 1
        self.controllerName = None

    def run_sel(self):
        objects = cmds.ls(sl=True, o=True)
        if objects:
            surface = objects[0]
            sel_comps = cmds.ls(os=True, fl=True)
            vertices = [c for c in sel_comps if '.vtx' in c]
            if vertices:
                target_vtx = vertices[0]
                result = self.run_vtx(target_vtx, surface)
                soft_mod = result[0]
                ctrl_node = result[1]
                
                if len(sel_comps) >= 2:
                    cmds.setAttr(f'{soft_mod}.falloffRadius', 5000)
                    self.floodReplace(sel_comps, soft_mod)
                    
                if self.world:
                    parent_grp = cmds.listRelatives(ctrl_node, p=True)[0]
                    temp_loc = cmds.spaceLocator()[0]
                    constraint = cmds.orientConstraint(temp_loc, parent_grp)
                    cmds.delete(constraint, temp_loc)
                    
                cmds.select(ctrl_node)
                return result
        return 0

    def getNumber(self, geo):
        existing = cmds.ls(f'{geo}_*_OH')
        if existing:
            numbers = []
            for item in existing:
                try:
                    num = int(item.split(f'{geo}_')[1].split('_')[0])
                    numbers.append(num)
                except ValueError:
                    pass
            return max(numbers) + 1 if numbers else 1
        return 1

    def run_vtx(self, vtx, surf):
        sm_nodes = self.stickyMod(surf)
        soft_mod, handle, out_geo = sm_nodes
        
        rivet_grp = self.rivet(vtx, surf, out_geo)
        pt_name = self.getName('Overlap_Helper_point_')
        helper_grp = cmds.group(em=True, n=pt_name)
        cmds.makeIdentity(helper_grp, apply=True, t=1, r=1, s=1)
        
        temp_cn = cmds.parentConstraint(rivet_grp, helper_grp)
        cmds.delete(temp_cn)
        cmds.parent(helper_grp, rivet_grp)
        cmds.makeIdentity(helper_grp, apply=True, t=1, r=1, s=1)
        
        inf_name = self.getName('INF_')
        inf_node = cmds.createNode('transform', n=inf_name, p=rivet_grp)
        cmds.setAttr(f'{inf_node}.hiddenInOutliner', 1)
        cmds.setAttr(f'{inf_node}.inheritsTransform', 0)
        
        cmds.pointConstraint(helper_grp, inf_node)
        cmds.connectAttr(f'{inf_node}.t', f'{soft_mod}.falloffCenter', force=True)
        
        for attr in ('sx', 'sy', 'sz', 'v'):
            cmds.setAttr(f'{helper_grp}.{attr}', 1, lock=True, keyable=False)
            
        cmds.parent(handle, helper_grp, relative=True)
        cmds.connectAttr(f'{handle}.pim', f'{soft_mod}.bindPreMatrix', force=True)
        
        for attr in ('tx', 'ty', 'tz'):
            cmds.setAttr(f'{helper_grp}.{attr}', lock=True, keyable=False)
            
        return self.finalize([soft_mod, handle], surf)

    def stickyMod(self, surf):
        mod_name = self.getName('osm_')
        soft_mod, handle = cmds.softMod(surf, n=mod_name)
        child = cmds.listRelatives(handle, c=True)[0]
        cmds.setAttr(f'{child}.visibility', 0)
        cmds.setAttr(f'{handle}.visibility', 1, lock=True, keyable=False)
        cmds.setAttr(f'{handle}.rp', 0, 0, 0)
        cmds.setAttr(f'{handle}.sp', 0, 0, 0)
        
        cmds.setAttr(f'{soft_mod}.falloffAroundSelection', 0)
        cmds.setAttr(f'{soft_mod}.falloffRadius', 1, lock=True, keyable=False)
        cmds.setAttr(f'{handle}.displayHandle', 1)
        
        cmds.connectAttr(f'{surf}.worldMatrix', f'{soft_mod}.geomMatrix[0]')
        out_geo = cmds.listConnections(f'{soft_mod}.input[0].inputGeometry', plugs=True)[0]
        
        for attr in ('fcx', 'fcy', 'fcz', 'fix', 'fiy', 'fiz', 'fas', 'fm', 'en'):
            cmds.setAttr(f'{soft_mod}.{attr}', lock=True, keyable=False)
            
        cmds.setAttr(f'{soft_mod}.falloffMode', 1)
        return soft_mod, handle, out_geo

    def rivet(self, vtx, surf, outGeo):
        vtx_idx = vtx.split('[')[1].split(']')[0]
        edge_info = cmds.polyInfo(vtx, vertexToEdge=True)[0].split(':')[1].split()
        edges = [int(e) for e in edge_info if e.isdigit()]
        
        curve_node = cmds.createNode('curveFromMeshEdge', n=f'{surf}_edge_{edges[1]}_OH')
        cmds.setAttr(f'{curve_node}.edgeIndex[0]', edges[1])
        
        if outGeo:
            cmds.connectAttr(outGeo, f'{curve_node}.inputMesh')
        else:
            cmds.connectAttr(f'{surf}.worldMesh', f'{curve_node}.inputMesh')
            
        poc_node = cmds.createNode('pointOnCurveInfo', n=f'{surf}_e{edges[1]}_v{vtx_idx}_POC')
        cmds.setAttr(f'{poc_node}.turnOnPercentage', 1)
        cmds.connectAttr(f'{curve_node}.outputCurve', f'{poc_node}.inputCurve')
        
        grp_name = self.getName('Overlap_Helper_Control_Group_')
        ctrl_grp = cmds.createNode('transform', n=grp_name)
        cmds.setAttr(f'{ctrl_grp}.hiddenInOutliner', 1)
        cmds.connectAttr(f'{poc_node}.result.position', f'{ctrl_grp}.translate')
        
        norm_cn = cmds.normalConstraint(surf, ctrl_grp, n=self.getName('nrmlCN_'), aim=[0, 1, 0], u=[1, 0, 0])[0]
        if outGeo:
            target_plug = cmds.listConnections(f'{norm_cn}.target[0].targetGeometry', d=False, p=True)[0]
            cmds.disconnectAttr(target_plug, f'{norm_cn}.target[0].targetGeometry')
            cmds.connectAttr(outGeo, f'{norm_cn}.target[0].targetGeometry')
            
        cmds.connectAttr(f'{poc_node}.tangent', f'{norm_cn}.worldUpVector')
        cmds.setAttr(f'{norm_cn}.hiddenInOutliner', 1)
        return ctrl_grp

    def floodReplace(self, comps, sm_dfrm):
        geo = str(comps[0]).split('.')[0]
        cmds.hilite(geo, replace=True)
        cmds.select(comps)
        mel.eval(f'artSetToolAndSelectAttr("artAttrCtx", "softMod.{sm_dfrm}.weights");')
        mel.eval('artAttrInitPaintableAttr;')
        mel.eval('artAttrValues artAttrContext;')
        mel.eval('artAttrPaintOperation artAttrCtx Replace;')
        mel.eval('artAttrCtx -e -opacity 1 `currentCtx`;')
        mel.eval('artAttrCtx -e -value 0 `currentCtx`;')
        cmds.select(comps)
        mel.eval('invertSelection;')
        mel.eval('artAttrCtx -e -clear `currentCtx`;')
        mel.eval('artAttrPaintOperation artAttrCtx Smooth;')
        mel.eval('artAttrCtx -e -opacity 1 `currentCtx`;')
        cmds.select(f'{geo}.vtx[*]')
        mel.eval('artAttrCtx -e -clear `currentCtx`;')
        cmds.select(geo)
        mel.eval('SelectTool;')

    def finalize(self, sm, surf):
        soft_mod, handle = sm
        parent_pt = cmds.listRelatives(handle, p=True)[0]
        ctrl_grp = cmds.listRelatives(parent_pt, p=True)[0]
        surf_name = cmds.listRelatives(surf, p=True)[0]
        if ':' in surf_name:
            surf_name = surf_name.split(':')[1]
            
        ctrl_name = self.getName('control_')
        if self.crv:
            crv = cmds.curve(n=ctrl_name, d=1, p=SHAPES.SPHERE.points, k=SHAPES.SPHERE.knots)
        else:
            crv = cmds.curve(n=ctrl_name, d=1, p=SHAPES.CUBE.points, k=SHAPES.CUBE.knots)
            
        crv_shape = cmds.listRelatives(crv, s=True)[0]
        for attr in ('sx', 'sy', 'sz'):
            cmds.setAttr(f'{crv}.{attr}', 0.4 * self.scale)
        cmds.makeIdentity(crv, apply=True, s=True)
        
        cmds.parent(crv, parent_pt)
        for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
            cmds.setAttr(f'{crv}.{attr}', 0)
        for attr in ('sx', 'sy', 'sz'):
            cmds.setAttr(f'{crv}.{attr}', 1)
            
        cmds.parent(crv_shape, handle, r=True, s=True, add=True)
        cmds.delete(crv)
        
        cmds.addAttr(handle, ln='visualizationMode', at='enum', en='Handle:Nurbs Curve', dv=1)
        cmds.setAttr(f'{handle}.visualizationMode', cb=True)
        cmds.connectAttr(f'{handle}.visualizationMode', f'{crv_shape}.v')
        
        rev_node = cmds.createNode('reverse', n=f'{handle}_OHrev')
        cmds.setAttr(f'{rev_node}.ihi', 0)
        cmds.connectAttr(f'{handle}.visualizationMode', f'{rev_node}.inputX')
        cmds.connectAttr(f'{rev_node}.outputX', f'{handle}.displayHandle')
        
        cmds.setAttr(f'{handle}.overrideEnabled', 1)
        cmds.setAttr(f'{handle}.overrideColor', 22)
        
        main_grp = cmds.ls('Overlap_Helper', '*:Overlap_Helper')
        if main_grp:
            cmds.parent(ctrl_grp, main_grp[0])
        else:
            cmds.group(n='Overlap_Helper', em=True, w=True)
            cmds.parent(ctrl_grp, 'Overlap_Helper')
            
        if self.controllerName:
            newName = self.getName(self.controllerName)
            handle = cmds.rename(handle, newName)
        else:
            idx = self.getNumber(surf_name)
            handle = cmds.rename(handle, f'{surf_name}_{idx}_OH')
            
        sm_node = f'{handle}SoftMod'
        cmds.addAttr(handle, ln='size', at='double', dv=self.scale)
        cmds.select(handle)
        return sm_node, handle

    def getName(self, name):
        count = 1
        while True:
            target_name = f'{name}{count}'
            if not cmds.objExists(target_name):
                return target_name
            count += 1

    def dialoge(self, msg):
        cmds.warning(msg)

    def change(self, type, weight=1.0, envelope=1.0, falloffMode=1, falloffCurve=1, shapeChange=0, scaleChange=1.0, rename=''):
        selection = cmds.ls(sl=True)
        valid_ctrls = []
        for obj in selection:
            parent = cmds.listRelatives(obj, p=True)
            if parent and 'Overlap' in parent[0] and 'Helper' in parent[0]:
                valid_ctrls.append(obj)
                
        if not valid_ctrls:
            self.dialoge('This is not an Overlap Helper control')
            return

        for ctrl in valid_ctrls:
            soft_mod = cmds.listConnections(ctrl, type='softMod')[0]
            if type == 'reweight':
                if cmds.getAttr(f'{soft_mod}.falloffRadius') == 5000:
                    self.dialoge('This is not weightable, use paint instead')
                else:
                    cmds.setAttr(f'{soft_mod}.falloffRadius', weight)
            elif type == 'envelope':
                cmds.setAttr(f'{soft_mod}.envelope', envelope)
            elif type == 'falloffMode':
                cmds.setAttr(f'{soft_mod}.falloffMode', falloffMode)
            elif type == 'falloffCurve':
                cmds.setAttr(f'{soft_mod}.falloffCurve[0].falloffCurve_Interp', falloffCurve)
            elif type == 'rename' and rename:
                new_name = self.getName(rename)
                cmds.rename(ctrl, new_name)