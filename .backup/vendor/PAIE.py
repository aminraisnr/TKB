import maya.cmds as mc
import os, pickle

class PaieData(object):
    def __init__(self):
        self.header = {}
        self.data = {}

    def save(self, path):
        try:
            with open(path, 'wb') as f:
                pickle.dump(self.header, f)
                pickle.dump(self.data, f)
            return True
        except: return False

    def load(self, path):
        try:
            with open(path, 'rb') as f:
                self.header = pickle.load(f)
                self.data = pickle.load(f)
            return True
        except: return False

class PaieGUI(object):
    def __init__(self):
        self.name = "paieGUI_v3_FinalFix"
        self.title = "TKB Copy Manager v3.1 (Optimized)"
        self.path = os.path.join(mc.internalVar(upd=True), 'paie_data').replace('\\', '/')
        if not os.path.exists(self.path): os.makedirs(self.path)
        self.createUI()

    def createUI(self):
        if mc.window(self.name, exists=True): mc.deleteUI(self.name)
        self.window = mc.window(self.name, title=self.title, widthHeight=(350, 640))
        
        mc.columnLayout(adj=True, rs=4, co=['both', 5])
        mc.text(l="ANIMATION & POSE MANAGER", bgc=(0.15, 0.15, 0.15), h=35, fn="boldLabelFont")
        
        # --- FILE LIST ---
        self.fileList = mc.textScrollList(h=220, ams=False, sc=self.on_file_selected)
        self.refresh_list()
        
        mc.rowLayout(nc=2, ad2=True)
        mc.button(l="REFRESH LIST", c=lambda *x: self.refresh_list(), w=165, h=25)
        mc.button(l="DELETE FILE", bgc=(0.4, 0.2, 0.2), c=self.do_delete_file, w=165, h=25)
        mc.setParent('..')
        
        mc.button(l="SELECT CONTROLS FROM FILE", h=30, bgc=(0.3, 0.3, 0.3), c=self.do_select_from_file)
        
        mc.separator(h=10, st="doubleDash")
        
        # --- EXPORT SECTION ---
        mc.text(l="EXPORT SECTION", al="left", fn="boldLabelFont")
        self.mode_radio = mc.radioButtonGrp(labelArray2=['Pose Only', 'Animation'], nrb=2, sl=2)
        
        mc.rowLayout(nc=3, ad3=True)
        mc.text(l="Frame Range:")
        self.start_frame_field = mc.intField(v=int(mc.playbackOptions(q=True, min=True)))
        self.end_frame_field = mc.intField(v=int(mc.playbackOptions(q=True, max=True)))
        mc.setParent('..')

        mc.button(l="EXPORT SELECTED", h=40, bgc=(0.28, 0.38, 0.28), c=self.do_export)
        
        # --- IMPORT ---
        mc.text(l="IMPORT METHOD (To Selection Only)", al="left", fn="boldLabelFont")
        self.import_type = mc.radioButtonGrp(labelArray2=['Smart', 'Bake'], nrb=2, sl=1)
        mc.button(l="IMPORT TO SELECTED", h=45, bgc=(0.28, 0.28, 0.38), c=self.do_import)

        # --- PROGRESS ---
        mc.separator(h=5, st="none")
        self.status_text = mc.text(l="Ready", al="center", h=20, fn="smallObliqueLabelFont")
        self.progress_bar = mc.progressBar(maxValue=100, width=340)
        
        mc.showWindow(self.window)

    def on_file_selected(self):
        self.update_status("File selected. Ready to import.", 0)

    def refresh_list(self):
        mc.textScrollList(self.fileList, e=True, ra=True)
        if os.path.exists(self.path):
            files = sorted([f for f in os.listdir(self.path) if f.endswith('.paie')])
            mc.textScrollList(self.fileList, e=True, append=files)

    def do_delete_file(self, *args):
        sel_file = mc.textScrollList(self.fileList, q=True, si=True)
        if not sel_file: return
        if mc.confirmDialog(title='Delete', message=f'Hapus {sel_file[0]}?', button=['Yes','No'], db='No') == 'Yes':
            os.remove(os.path.join(self.path, sel_file[0]))
            self.refresh_list()

    def get_clean_name(self, node):
        return node.split(':')[-1]

    def update_status(self, message, progress):
        mc.text(self.status_text, e=True, l=message)
        mc.progressBar(self.progress_bar, e=True, pr=int(progress))

    def do_select_from_file(self, *args):
        sel_file = mc.textScrollList(self.fileList, q=True, si=True)
        if not sel_file: return
        
        curr_sel = mc.ls(sl=True)
        ns = ""
        if curr_sel and ":" in curr_sel[0]:
            ns = ":".join(curr_sel[0].split(":")[:-1]) + ":"
            
        data_obj = PaieData()
        if data_obj.load(os.path.join(self.path, sel_file[0])):
            to_select = [ns + name for name in data_obj.data.keys() if mc.objExists(ns + name)]
            
            if to_select:
                mc.select(to_select)
                self.update_status(f"Selected {len(to_select)} objects.", 100)
                mc.refresh()
            else:
                mc.warning("Tidak ditemukan objek yang cocok dengan namespace saat ini.")

    def do_export(self, *args):
        sel = mc.ls(sl=True)
        if not sel: return
        
        res = mc.promptDialog(title='Export', message='Filename:', button=['OK', 'Cancel'], db='OK')
        if res == 'OK':
            filename = mc.promptDialog(q=True, text=True)
            if not filename: return
            
            mode = mc.radioButtonGrp(self.mode_radio, q=True, sl=True)
            start_f = mc.intField(self.start_frame_field, q=True, v=True)
            end_f = mc.intField(self.end_frame_field, q=True, v=True)
            
            data_obj = PaieData()
            data_obj.header['type'] = 'pose' if mode == 1 else 'anim'
            data_obj.header['range'] = (start_f, end_f)
            
            total = len(sel)
            # Matikan refresh viewport agar export kilat
            mc.refresh(suspend=True)
            
            try:
                for i, node in enumerate(sel):
                    # Refresh UI hanya setiap 5 objek agar tidak membebani CPU
                    if i % 5 == 0 or i == total - 1:
                        mc.refresh(suspend=False)
                        self.update_status(f"Exporting: {node}...", (float(i)/total)*100)
                        mc.refresh(suspend=True)
                        
                    clean_name = self.get_clean_name(node)
                    data_obj.data[clean_name] = {}
                    
                    attrs = mc.listAttr(node, k=True, w=True) or []
                    for a in attrs:
                        if mode == 1:
                            try: data_obj.data[clean_name][a] = mc.getAttr(f"{node}.{a}")
                            except: pass
                        else:
                            t = mc.keyframe(node, at=a, q=True, tc=True, time=(start_f, end_f))
                            v = mc.keyframe(node, at=a, q=True, vc=True, time=(start_f, end_f))
                            data_obj.data[clean_name][a] = list(zip(t, v)) if t else mc.getAttr(f"{node}.{a}")
            finally:
                mc.refresh(suspend=False)
            
            data_obj.save(os.path.join(self.path, filename + '.paie'))
            self.refresh_list()
            self.update_status("Export Finished!", 100)
            mc.refresh()

    def do_import(self, *args):
        sel_file = mc.textScrollList(self.fileList, q=True, si=True)
        sel_viewport = mc.ls(sl=True)
        if not sel_file or not sel_viewport:
            mc.warning("Pilih file dan kontroler di Viewport!")
            return

        current_time = mc.currentTime(q=True)
        is_bake = mc.radioButtonGrp(self.import_type, q=True, sl=True) == 2
        
        data_obj = PaieData()
        if data_obj.load(os.path.join(self.path, sel_file[0])):
            start_f_orig, end_f_orig = data_obj.header.get('range', (0, 0))
            offset = current_time - start_f_orig
            duration = end_f_orig - start_f_orig
            new_end_f = current_time + duration

            total = len(sel_viewport)
            
            # Membuka Undo Chunk & Suspend Refresh agar proses kalkulasi secepat kilat
            mc.undoInfo(openChunk=True)
            mc.refresh(suspend=True)
            
            try:
                for i, node in enumerate(sel_viewport):
                    if i % 5 == 0 or i == total - 1:
                        mc.refresh(suspend=False)
                        self.update_status(f"Importing... {int((float(i)/total)*100)}%", (float(i)/total)*100)
                        mc.refresh(suspend=True)
                        
                    clean_name = self.get_clean_name(node)
                    if clean_name in data_obj.data:
                        attrs = data_obj.data[clean_name]
                        
                        if data_obj.header['type'] == 'anim':
                            mc.cutKey(node, time=(current_time, new_end_f), clear=True)
                        
                        anim_attrs = []
                        for a, v in attrs.items():
                            try:
                                if isinstance(v, list):
                                    anim_attrs.append(a)
                                    for f_orig, val in v:
                                        mc.setKeyframe(node, at=a, t=f_orig + offset, v=val)
                                else:
                                    mc.setAttr(f"{node}.{a}", v)
                                    mc.setKeyframe(node, at=a, t=current_time)
                            except: pass
                        
                        if is_bake and anim_attrs:
                            mc.bakeResults(node, attribute=anim_attrs, t=(current_time, new_end_f), simulation=False) # Simulation=False mempercepat bake
            finally:
                mc.refresh(suspend=False)
                mc.undoInfo(closeChunk=True)
            
            self.update_status(f"Import Finished at Frame {current_time}!", 100)
            mc.refresh()

PaieGUI()