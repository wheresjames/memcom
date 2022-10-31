#!/usr/bin/env python3

import time
import string
import random
import json
import time
import numpy as np
import propertybag as pb
import threadmsg as tm

from . mc_video import *
from . mc_audio import *

try:
    import sparen
    Log = sparen.log
except Exception as e:
    Log = print


''' Audio / Video filter

    This class attaches to a in memory video and/or audio share,
    creates a worker thread, and provides the following callbacks.

    # Called on initialization of the callback thread
    def on_init(ctx)
        @param [in] ctx - Pointer to the mcFilter object

    # Called when the thread is idle.  Return a time in seconds to delay the next call.
    def on_idle(ctx)
        @param [in] ctx - Pointer to the mcFilter object

    # Called before the thread shuts down
    def on_end(ctx)
        @param [in] ctx - Pointer to the mcFilter object

    # Called when an error is detected
    def on_error(ctx)
        @param [in] ctx - Pointer to the mcFilter object
        @param [in] e   - Description of error or Exception object

    # Called when a new video frame is available / ready
    def on_video(ctx, vfi, vfr)
        @param [in] ctx     - Pointer to the mcFilter object
        @param [in] vfi     - Video frame information
                                buf - Buffer Frame index
                                pts - Presentation Time Stamp
                                idx - Frame index
                                clk - Clock value
                                rds - Number of reads
                                wts - Number of writes
        @param [in/out] vfr - Video frame numpy array

    # Called when a new audio frame is available / ready
    def on_audio(ctx, afi, afr)
        @param [in] ctx     - Pointer to the mcFilter object
        @param [in] afi     - Audio frame information
                                buf - Buffer Frame index
                                pts - Presentation Time Stamp
                                idx - Frame index
                                clk - Clock value
                                rds - Number of reads
                                wts - Number of writes
        @param [in/out] afr - Audio frame numpy array
'''
class mcFilter(tm.ThreadMsg):

    ''' Initialize object
        @param [in] on_init     - Called when the filter starts running
        @param [in] on_idle     - Called every loop
        @param [in] on_end      - Called when the filter stops
        @param [in] on_error    - Called when the errors are detected
        @param [in] on_video    - Called when a new video frame is available
        @param [in] on_audio    - Called when a new audio frame is available
        @param [in] opts        - Options
                                    verbose : Print log information
                                    video   : The name of the video share
                                    audio   : The name of the audio share
                                    thread  : True if internal thread should run
                                              If False, you must call run() yourself
                                    vbias   : Video buffer offset bias (0-1)
                                    vwin    : Video buffer window size (0-1)
                                    abias   : Audio buffer offset bias (0-1)
                                    awin    : Audio window buffer size (0-1)
    '''
    def __init__(self, on_init=None, on_idle=None, on_end=None, on_error=None,
                       on_video=None, on_audio=None, opts={}, thread=True, start=False):

        super().__init__(self.msgThread, start=False)

        self.sErr = ""
        self.iopts = opts
        self.opts = pb.Bag(opts)
        self.delay = 0

        self.on_init_callback = on_init if callable(on_init) else None
        self.on_idle_callback = on_idle if callable(on_idle) else None
        self.on_end_callback = on_end if callable(on_end) else None
        self.on_error_callback = on_error if callable(on_error) else None

        # Options
        self.verbose = self.opts.get('verbose', False)

        # Video
        self.on_video_callback = on_video if callable(on_video) else None
        self.video = None
        self.vshare = None
        self.vptr = 0
        self.vbias = self.opts.get('vbias', 0)
        self.vwin = self.opts.get('vwin', 0.25)

        # Audio
        self.on_audio_callback = on_audio if callable(on_audio) else None
        self.audio = None
        self.ashare = None
        self.aptr = 0
        self.abias = self.opts.get('abias', 0)
        self.awin = self.opts.get('awin', 0.25)

        if start:
            self.create()


    ### Destructor
    def __del__(self):
        super().__del__()
        self.close()


    ### Returns the last error string
    def getError(self):
        return self.sErr

    ### Returns the name of the filter if set
    def getName(self):
        return self.opts.get('name', '')

    ### Return video share object
    def getVideoShare():
        return self.vshare

    ### Return current video frame index
    def getVideoPtr():
        return self.vptr

    ### Return video buffer offset bias
    def getVideoBias():
        return self.vbias

    ### Return audio share object
    def getAudioShare():
        return self.ashare

    ### Return current audio frame index
    def getAudioPtr():
        return self.aptr

    ### Return audio buffer offset bias
    def getAudioBias():
        return self.abias

    ### Release resources and prepare object for reuse
    def close(self):

        self.join(True)

        if self.vshare:
            self.vshare.close()
            self.vshare = None

        if self.ashare:
            self.ashare.close()
            self.ashare = None

        self.opts = pb.Bag(self.iopts)
        self.vptr = 0
        self.aptr = 0
        self.video = None
        self.audio = None


    ''' Creates the shared memory buffer
        @param [in] on_init     - Called when the filter starts running
        @param [in] on_idle     - Called every loop
        @param [in] on_end      - Called when the filter stops
        @param [in] on_error    - Called when the errors are detected
        @param [in] on_video    - Called when a new video frame is available
        @param [in] on_audio    - Called when a new audio frame is available
        @param [in] opts        - Options
                                    video   : The name of the video share
                                    audio   : The name of the audio share
                                    thread  : True if internal thread should run
                                              If False, you must call run() yourself
                                    vbias   : Video buffer offset bias
                                    vwin    : Video buffer window size (0-1)
                                    abias   : Audio buffer offset bias
                                    awin    : Audio buffer window size (0-1)
    '''
    def create(self, on_init=None, on_idle=None, on_end=None, on_error=None, on_video=None, on_audio=None, opts={}):

        self.sErr = ""
        self.close()
        self.opts.merge(opts)

        # Options
        self.verbose = self.opts.get('verbose', False)

        # Video
        self.vbias = self.opts.get('vbias', 0)
        self.vwin = self.opts.get('vwin', 0.25)
        self.video = self.opts.get("video", self.video)

        self.abias = self.opts.get('abias', 0)
        self.awin = self.opts.get('awin', 0.25)
        self.audio = self.opts.get("audio", self.audio)

        if on_init and callable(on_init):
            self.on_init_callback = on_init
        if on_idle and callable(on_idle):
            self.on_idle_callback = on_idle
        if on_end and callable(on_end):
            self.on_end_callback = on_end
        if on_error and callable(on_error):
            self.on_error_callback = on_error
        if on_video and callable(on_video):
            self.on_video_callback = on_video
        if on_audio and callable(on_audio):
            self.on_audio_callback = on_audio

        if not self.video and not self.audio:
            self.sErr = "No audio or video share"
            self.close()
            return False

        fps = 1

        if self.video:
            self.vshare = mcVideo()
            if not self.vshare.create(name=self.video, mode='existing'):
                self.sErr = "Failed to open video share"
                self.close()
                return False

            self.vbufs = self.vshare.getBuffers()
            self.vfps = self.vshare.getFps()
            self.vbiasf = int(self.vbias * self.vbufs)
            self.vwinf = int(self.vwin * self.vbufs)
            self.vptr = self.vshare.calcIdx(self.vbiasf)
            self.vidx = -1
            fps = self.vfps

        if self.audio:
            self.ashare = mcAudio()
            if not self.ashare.create(name=self.audio, mode='existing'):
                self.sErr = "Failed to open audio share"
                self.close()
                return False

            self.abufs = self.ashare.getBuffers()
            self.afps = self.ashare.getFps()
            self.abiasf = int(self.abias * self.abufs)
            self.awinf = int(self.awin * self.abufs)
            self.aptr = self.ashare.calcIdx(self.abiasf)
            self.aidx = -1
            if fps < self.afps:
                fps = self.afps

        if not self.opts.name:
            self.opts.name = f'Filter_{time.time()}'

        self.delay = 1 / fps / 2
        if self.thread and self.delay:
            super().start()

        return True


    ### Called to run the filter
    def runLoop(self):

        # While we processed a buffer
        process = True
        while process:
            process = False

            # If video
            if self.vshare and self.vshare.isOpen():

                vid = self.vshare

                # Get current frame
                b = vid.getBuffers()

                # Get current buffer offset
                i = vid.calcIdx(self.vbiasf)

                # Calculate drift
                d = vid.calcDrift(i, self.vptr)

                # Make sure we're still in the window
                if -self.vwinf >= d:
                    if self.on_error_callback:
                        self.on_error_callback(self, f'VOWIN : {-self.vwinf} > {d}')
                    self.vptr = (self.vptr + 1) % b

                # If there is a frame to process
                elif 0 > d:

                    process = True
                    vfr = vid.getBuf(self.vptr)
                    vfi = vid.getFrameInfo(self.vptr)
                    self.vptr = (self.vptr + 1) % b

                    # Ensure valid frame (this can happen normally sometimes)
                    if not vfi or 'idx' not in vfi:
                        pass

                    # Check for overrun
                    elif vfi['idx'] <= self.vidx:
                        if self.on_error_callback:
                            self.on_error_callback(self, f'Video overrun at {vfi["clk"]}:{i}, - {vfi["idx"]} <= {self.vidx}')

                    # Good to go!
                    else:
                        self.vidx = vfi['idx']
                        if 'roi' in self.opts:
                            r = self.opts.roi
                            vfr = vfr[r.y:r.y+r.h, r.x:r.x+r.w]
                        try:
                            if self.on_video_callback:
                                self.on_video_callback(self, vfi, vfr)
                        except Exception as e:
                            if self.on_error_callback:
                                self.on_error_callback(self, e)


            # If Audio
            if self.ashare and self.ashare.isOpen():

                aud = self.ashare

                # Get current frame
                b = aud.getBuffers()

                # Get current buffer offset
                i = aud.calcIdx(self.abiasf)

                # Calculate drift
                d = aud.calcDrift(i, self.aptr)

                # Ensure we're still in the window
                if -self.awinf >= d:
                    if self.on_error_callback:
                        self.on_error_callback(self, f'AOWIN : {-self.awinf} > {d}')
                    self.aptr = (self.aptr + 1) % b

                # If there is a frame to process
                elif 0 > d:

                    process = True
                    afr = aud.getBuf(self.aptr)
                    afi = aud.getFrameInfo(self.aptr)
                    self.aptr = (self.aptr + 1) % b

                    # Ensure valid frame (this can happen normally sometimes)
                    if not afi or 'idx' not in afi:
                        pass

                    # Check for overrun
                    elif afi['idx'] <= self.aidx:
                        if self.on_error_callback:
                            self.on_error_callback(self, f'Audio overrun at {afi["clk"]}:{i}, - {afi["idx"]} <= {self.aidx}')

                    # Good to go!
                    else:
                        self.aidx = afi['idx']
                        try:
                            if self.on_audio_callback:
                                self.on_audio_callback(self, afi, afr)
                        except Exception as e:
                            if self.on_error_callback:
                                self.on_error_callback(self, e)


    @staticmethod
    async def msgThread(self):

        delay = self.delay

        # Init
        if not self.loops:
            if self.on_init_callback:
                try:
                    self.on_init_callback(self)
                except Exception as e:
                    if self.on_error_callback:
                        self.on_error_callback(self, e)

        # Run
        if self.on_video_callback or self.on_audio_callback:
            self.runLoop()

        # Idle
        if self.on_idle_callback:
            try:
                delay = self.on_idle_callback(self)
            except Exception as e:
                if self.on_error_callback:
                    self.on_error_callback(self, e)

        # Cleanup
        if not self.run:
            if self.on_end_callback:
                try:
                    self.on_end_callback(self)
                except Exception as e:
                    if self.on_error_callback:
                        self.on_error_callback(self, e)
            return

        return delay

