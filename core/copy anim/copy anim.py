# ==========================
# GLOBAL IMPORTS (WAJIB)
# ==========================
import os
import sys
import pickle
import maya.cmds as cmds
import maya.mel as mel

# =========================================================
# PAIE SYSTEM (Animation & Pose Manager)
# =========================================================

class PaieData(object):
    def __init__(self):
        self.header = {}
        self.data = {}

    def save(self, path):
        try:
            with open(path, "wb") as f:
                pickle.dump(self.header, f)
                pickle.dump(self.data, f)
        except Exception:
            pass

    def load(self, path):
        try:
            with open(path, "rb") as f:
                self.header = pickle.load(f)
                self.data = pickle.load(f)
        except Exception:
            pass


class PaieGUI(object):
    def __init__(self):
        self.name = "paieGUI_v3_FinalFix"
        self.title = "TKB Copy Manager v3.1 (Optimized)"
        self.paie_data = os.path.join(cmds.internalVar(userTmpDir=True), "paie_data").replace("\\", "/")
        if not os.path.exists(self.paie_data):
            os.makedirs(self.paie_data)
        self.createUI()

    def createUI(self):
        if cmds.window(self.name, exists=True):
            cmds.deleteUI(self.name)

        self.window = cmds.window(self.name, title=self.title, widthHeight=(300, 520))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        
        cmds.text(label="ANIMATION & POSE MANAGER", bgc=(0.2, 0.2, 0.2), height=25, font="boldLabelFont")
        cmds.text(label="REFRESH LIST", align="left")
        
        cmds.button(label="REFRESH LIST", command=lambda x: self.refresh_list(), height=25)
        
        self.fileList = cmds.textScrollList(height=120, allowMultiSelection=False, selectCommand=self.on_file_selected)
        
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(145, 145), adjustableColumn=2)
        cmds.button(label="DELETE FILE", bgc=(0.6, 0.2, 0.2), command=self.do_delete_file)
        cmds.button(label="SELECT CONTROLS FROM FILE", bgc=(0.2, 0.4, 0.6), command=self.do_select_from_file)
        cmds.setParent("..")

        cmds.separator(height=10, style="doubleDash")
        cmds.text(label="EXPORT SECTION", align="left", font="boldLabelFont")
        
        self.mode_radio = cmds.radioButtonGrp(labelArray2=["Pose Only", "Animation"], numberOfRadioButtons=2, select=1)
        
        cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 60, 70, 60))
        cmds.text(label="Frame Range:")
        start_min = cmds.playbackOptions(q=True, minTime=True)
        end_max = cmds.playbackOptions(q=True, maxTime=True)
        self.start_frame_field = cmds.intField(value=int(start_min))
        self.end_frame_field = cmds.intField(value=int(end_max))
        cmds.setParent("..")

        cmds.button(label="EXPORT SELECTED", bgc=(0.2, 0.5, 0.3), height=30, command=self.do_export)

        cmds.separator(height=10, style="doubleDash")
        cmds.text(label="IMPORT METHOD (To Selection Only)", align="left", font="boldLabelFont")
        
        self.import_type = cmds.radioButtonGrp(labelArray2=["Smart", "Bake"], numberOfRadioButtons=2, select=1)
        cmds.button(label="IMPORT TO SELECTED", bgc=(0.2, 0.4, 0.5), height=35, command=self.do_import)

        self.status_text = cmds.text(label="Ready", align="center", font="smallObliqueLabelFont")
        self.progress_bar = cmds.progressBar(maxValue=100, width=280)
        
        self.refresh_list()
        cmds.showWindow(self.window)

    def on_file_selected(self):
        self.update_status("File selected. Ready to import.", 0)

    def refresh_list(self):
        cmds.textScrollList(self.fileList, edit=True, removeAll=True)
        if os.path.exists(self.paie_data):
            files = [f for f in os.listdir(self.paie_data) if f.endswith(".paie")]
            files = sorted(files)
            for f in files:
                cmds.textScrollList(self.fileList, edit=True, append=f)

    def do_delete_file(self, *args):
        sel_file = cmds.textScrollList(self.fileList, query=True, selectItem=True)
        if not sel_file:
            return
        res = cmds.confirmDialog(title="Delete", message=f"Hapus {sel_file[0]}?", button=["Yes", "No"], defaultButton="No")
        if res == "Yes":
            file_path = os.path.join(self.paie_data, sel_file[0])
            if os.path.exists(file_path):
                os.remove(file_path)
            self.refresh_list()

    def get_clean_name(self, node):
        return node.split(":")[-1]

    def update_status(self, message, progress=0):
        cmds.text(self.status_text, edit=True, label=message)
        cmds.progressBar(self.progress_bar, edit=True, progress=progress)

    def do_select_from_file(self, *args):
        sel_file = cmds.textScrollList(self.fileList, query=True, selectItem=True)
        if not sel_file:
            return
            
        curr_sel = cmds.ls(selection=True)
        ns = ""
        if curr_sel and ":" in curr_sel[0]:
            ns = curr_sel[0].rsplit(":", 1)[0] + ":"

        data_obj = PaieData()
        file_path = os.path.join(self.paie_data, sel_file[0])
        if os.path.exists(file_path):
            data_obj.load(file_path)
            to_select = [ns + k for k in data_obj.data.keys() if cmds.objExists(ns + k)]
            if to_select:
                cmds.select(to_select, replace=True)
                self.update_status(f"Selected {len(to_select)} objects.", 100)
                cmds.refresh()
            else:
                cmds.warning("Tidak ditemukan objek yang cocok dengan namespace saat ini.")

    def do_export(self, *args):
        sel = cmds.ls(selection=True)
        if not sel:
            cmds.warning("Pilih setidaknya satu kontroler/objek di viewport!")
            return

        res = cmds.promptDialog(title="Export", message="Filename:", button=["OK", "Cancel"], defaultButton="OK")
        if res != "OK":
            return
            
        filename = cmds.promptDialog(query=True, text=True)
        if not filename:
            return

        mode = cmds.radioButtonGrp(self.mode_radio, query=True, select=True)
        start_f = cmds.intField(self.start_frame_field, query=True, value=True)
        end_f = cmds.intField(self.end_frame_field, query=True, value=True)

        data_obj = PaieData()
        data_obj.header["type"] = "pose" if mode == 1 else "anim"
        data_obj.header["range"] = (start_f, end_f)

        total = len(sel)
        cmds.refresh(suspend=True)

        try:
            for i, obj in enumerate(sel):
                if total > 0:
                    progress = int((float(i) / total) * 100)
                    self.update_status(f"Exporting: {obj}...", progress)

                clean_name = self.get_clean_name(obj)
                attrs = cmds.listAttr(obj, keyable=True, unlocked=True) or []
                
                data_obj.data[clean_name] = {}

                for a in attrs:
                    if mode == 1:
                        try:
                            val = cmds.getAttr(f"{obj}.{a}")
                            data_obj.data[clean_name][a] = val
                        except Exception:
                            pass
                    else:
                        keys = cmds.keyframe(obj, attribute=a, query=True, timeChange=True, valueChange=True)
                        if keys:
                            times = keys[0::2]
                            vals = keys[1::2]
                            data_obj.data[clean_name][a] = list(zip(times, vals))
                        else:
                            try:
                                val = cmds.getAttr(f"{obj}.{a}")
                                data_obj.data[clean_name][a] = val
                            except Exception:
                                pass
        finally:
            cmds.refresh(suspend=False)

        file_path = os.path.join(self.paie_data, filename + ".paie")
        data_obj.save(file_path)
        self.refresh_list()
        self.update_status("Export Finished!", 100)
        cmds.refresh()

    def do_import(self, *args):
        sel_file = cmds.textScrollList(self.fileList, query=True, selectItem=True)
        sel_viewport = cmds.ls(selection=True)

        if not sel_file or not sel_viewport:
            cmds.warning("Pilih file dan kontroler di Viewport!")
            return

        is_bake = cmds.radioButtonGrp(self.import_type, query=True, select=True) == 2
        
        data_obj = PaieData()
        file_path = os.path.join(self.paie_data, sel_file[0])
        
        if os.path.exists(file_path):
            data_obj.load(file_path)

            current_time = cmds.currentTime(query=True)
            start_f_orig, end_f_orig = data_obj.header.get("range", (current_time, current_time))
            
            offset = current_time - start_f_orig
            duration = end_f_orig - start_f_orig
            new_end_f = current_time + duration

            total = len(sel_viewport)
            cmds.undoInfo(openChunk=True)
            cmds.refresh(suspend=True)

            try:
                for i, obj in enumerate(sel_viewport):
                    if total > 0:
                        progress = int((float(i) / total) * 100)
                        self.update_status(f"Importing... {progress}%", progress)

                    clean_name = self.get_clean_name(obj)
                    if clean_name in data_obj.data:
                        anim_attrs = data_obj.data[clean_name]
                        
                        if data_obj.header.get("type") == "pose":
                            for a, val in anim_attrs.items():
                                try:
                                    cmds.setAttr(f"{obj}.{a}", val)
                                except Exception:
                                    pass
                        else:
                            for a, val in anim_attrs.items():
                                try:
                                    if isinstance(val, list):
                                        cmds.cutKey(obj, attribute=a)
                                        for f_orig, v_orig in val:
                                            cmds.setKeyframe(obj, attribute=a, time=f_orig + offset, value=v_orig)
                                    else:
                                        cmds.setAttr(f"{obj}.{a}", val)
                                except Exception:
                                    pass

                            if is_bake:
                                cmds.bakeResults(obj, time=(current_time, new_end_f), simulation=True)
            finally:
                cmds.refresh(suspend=False)
                cmds.undoInfo(closeChunk=True)

            self.update_status(f"Import Finished at Frame {int(current_time)}!", 100)
            cmds.refresh()


def run_paie_original():
    PaieGUI()

def run():
    run_paie_original()