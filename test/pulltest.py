#!/usr/bin/env python3

import os
import time
import asyncio
import memcom

try:
    import sparen
    Log = sparen.log
except:
    Log = print
Fmt = lambda o: json.dumps(o, indent=2)


def on_error(ctx, e):
    Log(ctx.getName(), '---', e)


async def run():

    print(memcom.__info__)

    # Video file name
    if not os.path.isdir('./out'):
        os.mkdir('./out')
    fname = './out/testvid.avi'

    # Clip length in seconds
    # t = 30
    t = 60

    # Time divider
    div = 1
    # div = 4

    #---------------------------------------------------------------
    # Video parameters
    w = 800
    h = 600
    vfps = 15

    Log('Create video share')
    vid = memcom.mcVideo()
    if not vid.create(bufs=2*vfps, width=w, height=h, fps=vfps, cleanup=True):
        raise Exception(vid.getError())

    vsname = vid.getName()
    Log(f'Video share created: {vsname}')


    #---------------------------------------------------------------
    # Audio Parameters
    ch = 2
    bps = 16
    asr = 48000
    afps = 50

    Log('Create audio share')
    aud = memcom.mcAudio()
    if not aud.create(bufs=2*afps, ch=ch, bps=bps, bitrate=asr, fps=afps, cleanup=True):
        raise Exception(aud.getError())

    asname = aud.getName()
    Log(f'Audio share created: {asname}')


    #---------------------------------------------------------------
    # Create initial rectangles

    # Initial rects
    n = 0

    # Target number of rects / adds one each second
    m = 16

    tv = []
    rects = [{'x': 0, 'y': 0, 'w': w, 'h': h}]
    for i in range(0, n-1):
        memcom.addRect(rects)

    ri = 0
    for r in rects:
        ri += 1
        v = memcom.mcTestVid(on_error=on_error,
                             opts={'name': f'Rect{ri}', 'roi':r,
                                   'video':vsname, 'vbias':-0.25, 'vwin':0.25,
                                   'audio':asname, 'abias':-0.25, 'awin':0.25})
        if not v.create():
            raise Exception(v.getError())
        tv.append(v)


    #---------------------------------------------------------------
    # Create file recorder
    Log('Create recorder')
    rec = memcom.mcRecord(on_error=on_error,
                          opts={'name': 'Recorder',
                                'video':vsname, 'vbias':-0.5, 'vwin':0.25,
                                'audio':asname, 'abias':-0.5, 'awin':0.25})
    if not rec.create(fname):
    # if not rec.create(fname, opts={'roi':{'x':int(w/4), 'y':int(h/4), 'w':int(w/2), 'h':int(h/2)}}):
        raise Exception(rec.getError())


    #---------------------------------------------------------------
    # Create frame eraser / clears frames before reuse
    Log('Create Eraser')
    erase = memcom.mcBlank(on_error=on_error,
                           opts={'name': 'Eraser',
                                 'video':vsname, 'vbias':-0.75, 'vwin':0.25,
                                 'audio':asname, 'abias':-0.75, 'awin':0.25})
    if not erase.create():
        raise Exception(rec.getError())


    #---------------------------------------------------------------
    # Create the clock
    Log('Create clock')
    clk = memcom.mcClock(on_error=on_error,
                         opts={'name': 'Clock', 'div':div,
                               'video':vsname, 'vfps':vfps, 'vbias':0, 'vwin':0.25,
                               'audio':asname, 'afps':afps, 'abias':0, 'awin':0.25})
    clk.create()


    #---------------------------------------------------------------
    # Run everything for t * div seconds
    d = 0
    t = t * div
    while 0 < t:
        t -= 1
        d += 1
        if d >= div:
            d = 0
            if len(rects) < m:
                Log('Add rect')
                r = memcom.addRect(rects)
                ri = len(rects) + 1
                v = memcom.mcTestVid(on_error=on_error,
                                     opts={'name': f'Rect{ri}', 'roi':r,
                                           'video':vsname, 'vbias':-0.25, 'vwin':0.25,
                                           'audio':asname, 'abias':-0.25, 'awin':0.25})
                if not v.create():
                    raise Exception(v.getError())
                tv.append(v)
        time.sleep(1)


    # Close everything
    clk.close()
    erase.close()
    rec.close()
    for v in tv:
        v.close()
    vid.close()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        Log(" ~ keyboard ~ ")
    except Exception as e:
        Log(" ~ exception ~ ", e)
    finally:
        Log('\r\n--- Done ---')

