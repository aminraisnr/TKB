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
# 5) STEP SNAP (snap keyframes ke grid step)
#    - default step=1 (snap ke frame integer)
# =========================================================
def ss():
    if cmds.window('ss',exists=True):
        cmds.deleteUI('ss',window=True)

    def ssfrwrd(*args):
        krg=cmds.timeControl('timeControl1',q=True,rng=True)
        krglen=len(krg)
        krgns=krg.find(':')
        strtkt=krg[1:krgns]
        strtk=int(strtkt)
        endkt=krg[krgns+1:krglen-1]
        endk=int(endkt)
        endk-=1
        sel=cmds.ls(sl=True)
        sel=sel[0]
        if strtk==endk:
            cmds.error('Start and End range is the same')
        else:
            cmds.currentTime(strtk)
            msel = cmds.xform(sel, ws=True, q=True, ro=True)
            locsel = cmds.xform(sel, ws=True, q=True, t=True)
            cmds.setKeyframe(str(sel))
            while strtk<=endk:
                cmds.xform(sel, ws=True, ro=msel)
                cmds.move(locsel[0], locsel[1], locsel[2], sel)
                cmds.setKeyframe(str(sel))
                strtk+=1
                cmds.currentTime(strtk)
        return ssfrwrd

    def ssreverse(*args):
        krg=cmds.timeControl('timeControl1',q=True,rng=True)
        krglen=len(krg)
        krgns=krg.find(':')
        strtkt=krg[1:krgns]
        strtk=int(strtkt)
        endkt=krg[krgns+1:krglen-1]
        endk=int(endkt)
        endk-=1
        sel=cmds.ls(sl=True)
        sel=sel[0]
        if strtk==endk:
            cmds.error('Start and End range is the same')
        else:
            cmds.currentTime(endk)
            msel = cmds.xform(sel, ws=True, q=True, ro=True)
            locsel = cmds.xform(sel, ws=True, q=True, t=True)
            cmds.setKeyframe(str(sel))
            while endk>=strtk:
                cmds.xform(sel, ws=True, ro=msel)
                cmds.move(locsel[0], locsel[1], locsel[2], sel)
                cmds.setKeyframe(str(sel))
                endk-=1
                cmds.currentTime(endk)
        return ssreverse
    cwin=cmds.window('ss',t='SS 4.0',width=200,s=True)
    cmds.columnLayout(adjustableColumn=True )
    cmds.button(l='SS Forward', c=ssfrwrd,w=200)
    cmds.button(l='SS Reverse', c=ssreverse,w=200)
    cmds.showWindow(cwin)
    cmds.window('ss',e=True, width=200, h=50,  s=True)
   