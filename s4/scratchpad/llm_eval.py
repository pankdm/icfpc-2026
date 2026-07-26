#!/usr/bin/env python3
"""Evaluate LLM controller box for a given port column assignment."""
import sys, os
HERE=os.path.dirname(os.path.abspath(__file__))
S4=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(S4,'tools'))
sys.path.insert(0,os.path.join(S4,'solutions','little-little-man'))
import boustro
import build_banked_dedup as dedup
import build_banked_boustro as bb

_flow=None
def get_flow():
    global _flow
    if _flow is None:
        _flow=bb.alias_empty_gotos(dedup.build_flow())
    return _flow

GLYPH={'ri':'r','sp':'s','rp':'r','sc':'s','rr':'r','sd':'s','sa':'s','ss':'s','cc':'s','cr':'r'}
PORTS=list(GLYPH)

def evaluate(cols, op_slack=0, x0=0, y0=0, max_corr=80, flat_branch=True):
    flow=get_flow()
    bands={}
    bands.update(boustro.voronoi_bands([(n,c) for n,c in cols.items() if GLYPH[n]=='s']))
    bands.update(boustro.voronoi_bands([(n,c) for n,c in cols.items() if GLYPH[n]=='r']))
    opmax=max(cols.values())+op_slack
    labels=list(flow.blocks)
    plans=boustro.branch_plans(flow, GLYPH) if flat_branch else None
    ncorr=6
    for _ in range(60):
        try:
            cursor,entry,edges,intent=boustro._lay_once(flow,labels,cols,GLYPH,bands,x0,y0,ncorr,opmax,(),plans)
        except boustro.Conflict as e:
            return {'error':str(e)}
        assignment,needed=boustro._assign_corridors(edges,entry)
        if needed<=ncorr: break
        ncorr=needed
        if ncorr>max_corr: return {'error':'corridors %d'%ncorr}
    else:
        return {'error':'corridor no converge'}
    max_y=max(y for _,y in cursor.cells)
    height=max_y+1-y0+1
    width=max(opmax,max(cols.values()))+2-x0
    return {'width':width,'height':height,'ncorr':ncorr,'cells':len(cursor.cells)}
