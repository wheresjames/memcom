#!/usr/bin/env python3

import time
import string
import random
import json
import math
import numpy as np
import propertybag as pb

from . mc_filter import *

try:
    import sparen
    Log = sparen.log
except Exception as e:
    Log = print


### Creates a test video
class mcClock(mcFilter):

    ''' Initialize object
        @param [in] opts    - Options
                                video   : The name of the video share
                                audio   : The name of the audio share
                                vfps    : Video frame rate
                                afps    : Audio frame rate
    '''
    def __init__(self, on_error=None, opts={}):
        super().__init__(on_error=on_error, on_init=self.on_init, on_idle=self.on_idle, opts=opts)
        self.vfps = None
        self.afps = None
        self.div = None
        self.clk = 0


    ### Delete
    def __del__(self):
        super().__del__()
        self.close()


    ### Release resources and prepare object for reuse
    def close(self):
        super().close()


    ''' Creates the shared memory buffer
        @param [in] opts    - Options
                                video   : The name of the video share
                                audio   : The name of the audio share
                                vfps    : Video frame rate
                                afps    : Audio frame rate
                                div     : Time divider
    '''
    def create(self, opts={}):

        self.close()

        self.vfps = None
        self.afps = None
        self.div = None
        self.clk = 0

        r = super().create(opts=opts)
        if not r:
            return False

        if self.opts.div:
            self.div = self.opts.div

        if self.opts.vfps:
            self.vfps = self.opts.vfps
        if self.opts.afps:
            self.afps = self.opts.afps

        return r


    def on_init(self, ctx):
        self.start_time = time.time()
        self.vpts = 0
        self.vind = 0
        self.apts = 0
        self.aind = 0

    def on_idle(self, ctx):

        t = time.time()
        dly = 0
        if not self.div:
            self.div = 1

        self.clk = (t - self.start_time) / self.div

        if self.vshare and self.vfps:
            vdly = self.start_time + (self.vind / (self.vfps / self.div)) - t
            if -1 > vdly:
                Log("Video lagging : %s" % vdly)
                # self.start_time = t - (self.vind / self.vfps)

            if 0 >= vdly:
                n = self.vshare.getIdx()
                # Log(f'CLKSRC: {int(self.clk * 1000)}:{n}:{self.vind}')
                self.vshare.setFrameInfo(n, 0, self.vind, int(self.clk*1000), 0, 0)
                self.vshare.setIdx(n+1)
                self.vind += 1
                dly = 0
            else:
                dly = vdly

        if self.ashare and self.afps:
            adly = self.start_time + (self.aind / (self.afps / self.div)) - t
            if -1 > adly:
                Log("Audio lagging : %s" % adly)
                # self.start_time = t - (self.aind / self.afps)

            if 0 >= adly:
                n = self.ashare.calcIdx(1)
                self.ashare.setFrameInfo(n, 0, self.aind, int(self.clk*1000), 0, 0)
                self.ashare.setIdx(n)
                self.aind += 1
                dly = 0
            elif dly > adly:
                dly = adly

        return dly


