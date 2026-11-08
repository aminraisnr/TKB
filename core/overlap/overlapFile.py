from maya import cmds


class OVERLAP:
    def __init__(self):
        self.physics_on = 1
        self.translate = 0
        self.stiffness = 3
        self.timeScale = 0.3
        self.Scale_ = 3
        self.smoothness = 10
        self.weight = 0.9
        self.specific_axis_state = 0
        self.tx = self.ty = self.tz = 1
        self.loop = 0
        self.dont_use_first_ctrl = 0
        self.bake_on_layer = 1
        self.cleanWhenStart()

    def overlap_dialog(self, msg):
        cmds.warning(f"Overlap Helper: {msg}")

    def cleanWhenStart(self):
        if cmds.objExists('OverlapHelperLogic_*'):
            cmds.delete('OverlapHelperLogic_*')
        if cmds.objExists('nucleus1'):
            cmds.delete('nucleus1')

    def clean(self, obj, copy_animation):
        try:
            if self.physics_on:
                nodes_to_del = [n for n in [getattr(self, 'particle', None), 'nucleus1', obj, getattr(self, 'loc_for_connect_to_particle', None), getattr(self, 'loc_for_particle_and_goal_OR_offset', None)] if n and cmds.objExists(n)]
                if nodes_to_del:
                    cmds.delete(nodes_to_del)
            else:
                nodes_to_del = [n for n in [obj, getattr(self, 'loc_for_particle_and_goal_OR_offset', None)] if n and cmds.objExists(n)]
                if nodes_to_del:
                    cmds.delete(nodes_to_del)
            if copy_animation and cmds.objExists(copy_animation):
                cmds.delete(copy_animation)
        except Exception as e:
            print(f"Clean warning: {e}")

    def get_lock_state(self, obj):
        attr = 'translate' if self.translate else 'rotate'
        self.lockX = cmds.getAttr(f'{obj}.{attr}X', lock=True)
        self.lockY = cmds.getAttr(f'{obj}.{attr}Y', lock=True)
        self.lockZ = cmds.getAttr(f'{obj}.{attr}Z', lock=True)

    def create_chain(self):
        self.locs = [cmds.spaceLocator(n=f'OverlapHelperLogic_chain_{i + 1}')[0] for i in range(len(self.sel) + 1)]
        for loc in self.locs:
            cmds.setAttr(f'{loc}.v', 0)
            
        for i in range(len(self.locs) - 1):
            cmds.parent(self.locs[i + 1], self.locs[i])
            
        for i in range(len(self.sel)):
            cmds.matchTransform(self.locs[i], self.sel[i], pos=True)
            if i != len(self.sel) - 1:
                aim_cn = cmds.aimConstraint(self.sel[i + 1], self.locs[i], aim=[0, 1, 0], u=[0, 0, 1], wut='vector', wu=[0, 1, 0])
                cmds.delete(aim_cn)

    def math(self):
        ty_vals = [cmds.getAttr(f'{loc}.ty') for loc in self.locs[1:]]
        if ty_vals:
            self.ty = sum(ty_vals) / len(ty_vals)
        else:
            self.ty = 1.0
        cmds.setAttr(f'{self.locs[-1]}.ty', self.ty)

    def parent_chain_to_controls(self):
        for i in range(len(self.sel)):
            cmds.parentConstraint(self.sel[i], self.locs[i], mo=True)

    def physics_on_logic(self, idx):
        self.loc_for_particle_and_goal_OR_offset = cmds.spaceLocator(n='OverlapHelperLogic_loc_goal')[0]
        cmds.setAttr(f'{self.loc_for_particle_and_goal_OR_offset}.v', 0)
        cmds.matchTransform(self.loc_for_particle_and_goal_OR_offset, self.locs[idx], pos=True, rot=True)
        cmds.move(0, (self.ty / max(0.001, self.Scale_)) * 5, 0, self.loc_for_particle_and_goal_OR_offset, r=True, os=True, ls=True)
        cmds.parentConstraint(self.locs[idx], self.loc_for_particle_and_goal_OR_offset, mo=True)
        
        pos = cmds.xform(self.loc_for_particle_and_goal_OR_offset, q=True, ws=True, t=True)
        self.particle = cmds.nParticle(p=pos, n='OverlapHelperLogic_particle')
        cmds.goal(self.particle[0], g=self.loc_for_particle_and_goal_OR_offset, w=0.5)
        
        self.loc_for_connect_to_particle = cmds.spaceLocator(n='OverlapHelperLogic_loc_particle')[0]
        cmds.connectAttr(f'{self.particle[0]}.center', f'{self.loc_for_connect_to_particle}.translate', force=True)
        
        if cmds.objExists('nucleus1'):
            cmds.setAttr('nucleus1.startFrame', self.min_time)
            cmds.setAttr('nucleus1.timeScale', self.timeScale)
            
        if len(self.particle) > 1 and cmds.objExists(self.particle[1]):
            if cmds.attributeQuery('goalSmoothness', n=self.particle[1], exists=True):
                cmds.setAttr(f'{self.particle[1]}.goalSmoothness', self.smoothness)
            if cmds.attributeQuery('goalWeight', n=self.particle[1], exists=True):
                cmds.setAttr(f'{self.particle[1]}.goalWeight[0]', self.weight)

    def physics_off_logic(self, idx):
        cmds.currentTime(self.min_time)
        self.loc_for_particle_and_goal_OR_offset = cmds.spaceLocator(n='OverlapHelperLogic_loc_offset')[0]
        cmds.setAttr(f'{self.loc_for_particle_and_goal_OR_offset}.v', 0)
        cmds.matchTransform(self.loc_for_particle_and_goal_OR_offset, self.locs[idx], pos=True, rot=True)
        cmds.move(0, (self.ty / max(0.001, self.Scale_)) * 5, 0, self.loc_for_particle_and_goal_OR_offset, r=True, os=True, ls=True)
        cmds.parentConstraint(self.locs[idx], self.loc_for_particle_and_goal_OR_offset, mo=True)
        
        cmds.setKeyframe(self.sel[idx], time=self.min_time, at=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'])
        cmds.bakeResults(self.loc_for_particle_and_goal_OR_offset, t=(self.min_time, self.max_time), simulation=True, shape=False)
        
        cn = cmds.listConnections(self.loc_for_particle_and_goal_OR_offset, type='parentConstraint')
        if cn:
            cmds.delete(cn)
            
        shift = int(self.stiffness)
        cmds.keyframe(self.loc_for_particle_and_goal_OR_offset, edit=True, relative=True, timeChange=shift)

    def bake_on_layer_logic(self, num, layer_name, obj):
        attrs = ['translateX', 'translateY', 'translateZ'] if self.translate else ['rotateX', 'rotateY', 'rotateZ']
        plugs = [f'{self.sel[num]}.{a}' for a in attrs]
        
        cmds.select(cl=True)
        cmds.animLayer(layer_name, edit=True, attribute=plugs)
        cmds.copyKey(obj, attribute=attrs)
        cmds.pasteKey(self.sel[num], option='replace', animLayer=layer_name, attribute=attrs)

    def overlap(self):
        self.create_chain()
        self.math()
        self.parent_chain_to_controls()
        
        self.final_layer_name = ''
        if self.bake_on_layer:
            self.final_layer_name = cmds.animLayer('OverlapHelper#', override=True)
            
        auto_key_state = cmds.autoKeyframe(q=True, state=True)
        cmds.autoKeyframe(state=False)
        
        try:
            for i in range(len(self.sel)):
                if self.dont_use_first_ctrl and i == 0:
                    continue
                    
                self.get_lock_state(self.sel[i])
                
                if self.physics_on:
                    self.physics_on_logic(i)
                    target_loc = self.loc_for_connect_to_particle
                    is_sim = True
                else:
                    self.physics_off_logic(i)
                    target_loc = self.loc_for_particle_and_goal_OR_offset
                    is_sim = False
                    
                if not self.translate:
                    obj_grp = cmds.spaceLocator(n='OverlapHelperLogic_rotHelper')[0]
                    cmds.parentConstraint(self.locs[i], obj_grp)
                    aim_node = cmds.spaceLocator(n='OverlapHelperLogic_aim')[0]
                    cmds.parent(aim_node, obj_grp)
                    cmds.aimConstraint(target_loc, aim_node, aim=[0, 1, 0], u=[0, 1, 0], wut='vector', wu=[0, 1, 0])
                    target_loc = aim_node

                dup_obj = cmds.duplicate(self.sel[i], parentOnly=True, n='OverlapHelperLogic_dup')[0]
                
                attrs = ['translateX', 'translateY', 'translateZ'] if self.translate else ['rotateX', 'rotateY', 'rotateZ']
                
                if self.translate:
                    cmds.parentConstraint(target_loc, dup_obj, mo=True)
                else:
                    cmds.orientConstraint(target_loc, dup_obj, mo=True)
                    
                cmds.bakeResults(
                    dup_obj, 
                    t=(self.min_time, self.max_time), 
                    simulation=is_sim, 
                    sampleBy=1, 
                    disableImplicitControl=True,
                    preserveOutsideKeys=True,
                    sparseAnimCurveBake=False,
                    at=attrs
                )
                    
                if self.bake_on_layer:
                    self.bake_on_layer_logic(i, self.final_layer_name, dup_obj)
                else:
                    cmds.copyKey(dup_obj, attribute=attrs)
                    cmds.pasteKey(self.sel[i], option='replace', attribute=attrs)
                    
                self.clean(target_loc, dup_obj)

            if hasattr(self, 'locs') and self.locs:
                cmds.delete(self.locs)
        finally:
            cmds.autoKeyframe(state=auto_key_state)

    def get_time_slider(self):
        self.min_time = cmds.playbackOptions(q=True, min=True)
        self.max_time = cmds.playbackOptions(q=True, max=True)
        self.current_time = cmds.currentTime(q=True)

    def start(self):
        self.cleanWhenStart()
        self.get_time_slider()
        self.selection = cmds.ls(sl=True)
        
        if not self.selection:
            self.overlap_dialog('Tidak ada kontroler/joint yang dipilih!')
            return

        if len(self.selection) < 2 and not self.specific_axis_state:
            self.overlap_dialog('Pilih minimal 2 objek berurutan!')
            return

        self.sel = list(self.selection)
        
        cmds.undoInfo(openChunk=True, chunkName="OverlapHelperBake")
        try:
            cmds.refresh(suspend=True)
            self.overlap()
        except Exception as e:
            self.overlap_dialog(f"Gagal memproses overlap: {e}")
        finally:
            cmds.refresh(suspend=False)
            self.cleanWhenStart()
            cmds.currentTime(self.current_time)
            cmds.undoInfo(closeChunk=True)