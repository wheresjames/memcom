#!/usr/bin/env python3

import time
import string
import random
import json
import math
import numpy as np
import propertybag as pb

from . mc_filter import *
from . mc_shapes import *
from . mc_audio import *

try:
    import sparen
    Log = sparen.log
except Exception as e:
    Log = print


### Creates a test video
class mcTestVid(mcFilter):

    ### Initialize object
    def __init__(self, on_error=None, opts={}):
        super().__init__(on_error=on_error, on_video=self.on_video, on_audio=self.on_audio, opts=opts)
        self.binf = pb.Bag()
        self.vpts = 0
        self.apts = 0

    def __del__(self):
        super().__del__()
        self.close()

    ### Release resources and prepare object for reuse
    def close(self):
        super().close()
        self.binf = pb.Bag()


    #---------------------------------------------------------------
    # VIDEO
    #---------------------------------------------------------------

    ''' Update drawing info
        @param [in] vfi     - Video frame info
        @param [in] vfr     - numpy video buffer
    '''
    def updateFrame(self, vfi, vfr):

        bi = self.binf
        h, w, c = vfr.shape

        def bounce(p, r, s, mn, mx):
            return (0 < s and (p + r + s) >= mx) or (0 > s and mn >= (p - r + s))

        if not bi.ready:
            bi.ready = True
            bi.bounced = False
            bi.xs = 5
            bi.ys = 5
            bi.sz = 30
            bi.x = int(w / 2)
            bi.y = int(h / 2)
            bi.col = [random.randint(100,255), random.randint(100,255), random.randint(100,255)]

        # Update X
        if bounce(bi.x, int(bi.sz/2), bi.xs, 0, w):
            bi.bounced = True
            sp = random.randint(2,10)
            bi.xs = -sp if 0 < bi.xs else sp
        bi.x += bi.xs

        # Update Y
        if bounce(bi.y, int(bi.sz/2), bi.ys, 0, h):
            bi.bounced = True
            sp = random.randint(2,10)
            bi.ys = -sp if 0 < bi.ys else sp
        bi.y += bi.ys


    ''' Draw the frame
        @param [in] vfi     - Video frame info
        @param [in] vfr     - numpy video buffer
    '''
    def drawFrame(self, vfi, vfr):

        bi = self.binf
        h, w, c = vfr.shape

        if (bi.x + int(bi.sz/2)) >= w:
            bi.x = w - bi.sz - 1
        if (bi.y + int(bi.sz/2)) >= h:
            bi.y = h - bi.sz - 1

        mcShapes.drawRect(vfr, 0, 0, w-1, h-1, [255, 255, 255])

        mcShapes.drawLine(vfr, 0, 0, w-1, h-1, [200, 100, 50])
        mcShapes.drawLine(vfr, 0, h-1, w-1, 0, [50, 100, 200])

        # Circles
        # for r in range(10, bi.sz, 10):
        #     mcShapes.drawArc(vfr, bi.x, bi.y, int(r/2), 0, 360, bi.col)

        # Solid ball
        # mcShapes.fillCircle(vfr, bi.x, bi.y, int(bi.sz/2), bi.col, 1, -.5)

        # Shaded ball
        col = bi.col.copy()
        for sh in range(10, -4, -2):
            col = list(map(lambda v : int(float(v)/1.15), col))
            mcShapes.fillCircle(vfr, bi.x, bi.y, int(bi.sz/2), col, sh/10, 1)


    ''' Called when a new video frame buffer is ready/available
        @param [in] ctx     - mcFilter object
        @param [in] afi     - Video frame information
                                pts: Presentation Time Stamp
                                idx: Frame index
        @param [in] afr     - numpy video frame buffer
    '''
    def on_video(self, ctx, vfi, vfr):
        self.updateFrame(vfi, vfr)
        self.drawFrame(vfi, vfr)
        self.vpts += self.vshare.getPtsInc()


    #---------------------------------------------------------------
    # AUDIO
    #---------------------------------------------------------------

    ''' Creates a bounce sound
        @param [in] vol     - Volume
        @param [in] asr     - Audio sampling rate, 48000kHz, etc...
        @param [in] sz      - Buffer size
        @param [in] freq    - Frequency of the tone to generate
        @param [in] off     - Cycle offset for the tone
    '''
    def create_bounce_sound(self, vol, asr, sz, freq, off):

        # Create bounce sound
        bsnd = (vol * np.sin(2 * np.pi * np.arange(off, off + sz) * freq / asr)).astype(np.int16)

        # Apply slope
        att = int(sz / 4)
        for i in range(0, att):
            bsnd[i] = (i/att) * bsnd[i]
            bsnd[sz - i - 1] = (i/att) * bsnd[sz - i - 1]

        return bsnd


    ''' Add sounds to the audio buffer
        @param [in] afi     - Audio frame information
        @param [in] afr     - numpy audio frame buffer
    '''
    def updateAudio(self, afi, afr):

        bi = self.binf
        if not bi.ballsnd:
            bi.freq = random.randint(50,100)
            bi.volume = 5000
            bi.abrate = self.ashare.getBitrate()
            bi.ballsnd = {
                'bouncing': 0,
                'base': bi.freq,
                'freq': bi.freq
            }

        # Bounce sound?
        if bi.bounced:
            bi.bounced = False
            bi.ballsnd.base = bi.freq
            bi.ballsnd.freq = bi.ballsnd.base
            bi.ballsnd.bouncing = 20 # 8

        if 0 < bi.ballsnd.bouncing:

            bi.ballsnd.bouncing -= 1

            bi.ballsnd.freq += bi.ballsnd.base
            freq = bi.ballsnd.freq

            ch, nsamples = afr.shape
            msamples = int(nsamples / ch)

            # For each channel
            snd = np.zeros(shape=afr.shape, dtype=afr.dtype)
            for c in range(0, ch):
                snd[0][c:nsamples:ch] = self.create_bounce_sound(bi.volume, bi.abrate, msamples, freq + (c * bi.ballsnd.base), self.apts)
            mcAudio.mixAudio([afr], {'n':1}, [snd], {'n':1}, {'mix':True})


    ''' Called when a new audio frame buffer is ready/available
        @param [in] ctx     - mcFilter object
        @param [in] afi     - Audio frame information
                                pts: Presentation Time Stamp
                                idx: Frame index
        @param [in] afr     - numpy audio frame buffer
    '''
    def on_audio(self, ctx, afi, afr):
        self.updateAudio(afi, afr)
        self.apts += self.ashare.getPtsInc()

