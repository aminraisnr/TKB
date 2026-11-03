# ==========================
# GLOBAL IMPORTS (WAJIB)
# ==========================
import os
import re
import sys
import maya.cmds as cmds  # <--- Ganti 'mc' menjadi 'cmds'
import maya.cmds as mc    # (opsional) simpan ini jika ada fungsi yang pakai mc
import maya.mel as mel
import traceback

# =========================================================
# 4) NULL (buat empty di posisi selection)
#    - kalau seleksi banyak: buat null per object
# =========================================================
def create_null(*args):
    obj=[str(o) for o in cmds.ls( sl=True,tr=True)]
    for i in obj:
        name=str(i)+"Locator"
        objctrl= cmds.curve(n=name,d=1,p=[(-1,1,1),(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1),(-1,-1,1),(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1),(1,-1,1),(1,1,1),(1,1,-1),(1,-1,-1),(1,-1,1),(1,-1,-1),(-1,-1,-1),],k=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16])
        pos = cmds.xform(str(i), q=True, ws=True, m=True)
        sca = cmds.xform(str(i), q=True, ws=True, s=True)
        #pos = cmds.xform(str(i), q=True, ws=True, translation=True)
        #cmds.move(pos[0], pos[1], pos[2], objctrl)
        cmds.xform(objctrl, ws=True, m=pos)
        cmds.xform(objctrl, ws=True, s=sca)
        cmds.setAttr (objctrl+".overrideEnabled", 1)
        cmds.setAttr(objctrl+".overrideColor", 30)
        cmds.select(objctrl)