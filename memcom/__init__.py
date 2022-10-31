
import os
from . mc_message import *
from . mc_video import *
from . mc_audio import *
from . mc_filter import *
from . mc_clock import *
from . mc_shapes import *
from . mc_blank import *
from . mc_record import *
from . mc_testvid import *

def loadConfig(fname):
    globals()["__info__"] = {}
    with open(fname) as f:
        lines = f.readlines()
        for line in lines:
            parts = line.strip().replace("\t", " ").split(" ")
            k = parts.pop(0).strip()
            if '#' != k[0]:
                globals()["__%s__"%k] = " ".join(parts).strip()
                globals()["__info__"][k] = " ".join(parts).strip()

loadConfig(os.path.join(os.path.dirname(__file__), 'PROJECT.txt'))


""" Monkey-patch multiprocessing.resource_tracker so SharedMemory won't be tracked
    More details at: https://bugs.python.org/issue38119
"""
def remove_shm_from_resource_tracker():

    from multiprocessing import resource_tracker

    def fix_register(name, rtype):
        if rtype == "shared_memory":
            return
        return resource_tracker._resource_tracker.register(self, name, rtype)
    resource_tracker.register = fix_register

    def fix_unregister(name, rtype):
        if rtype == "shared_memory":
            return
        return resource_tracker._resource_tracker.unregister(self, name, rtype)
    resource_tracker.unregister = fix_unregister

    if "shared_memory" in resource_tracker._CLEANUP_FUNCS:
        del resource_tracker._CLEANUP_FUNCS["shared_memory"]


def addRect(rects):

    i = -1
    area = -1

    # Find the largest rectangle
    for k in range(0, len(rects)):
        v = rects[k]
        if area < v['w'] * v['h']:
            area = v['w'] * v['h']
            i = k

    # Did we find a slot
    if 0 > i:
        return False

    r = rects[i]
    if r['w'] >= r['h']:
        w = r['w']
        w1 = int(w / 2)
        w2 = w - w1
        r['w'] = w1
        n = {'x': r['x'] + w1, 'y': r['y'], 'w': w2, 'h': r['h']}

    else:
        h = r['h']
        h1 = int(h / 2)
        h2 = h - h1
        r['h'] = h1
        n = {'x': r['x'], 'y': r['y'] + h1, 'w': r['w'], 'h': h2}

    rects.append(n)

    return n

