#!/usr/bin/env python3

import time
import string
import random
import json
import numpy as np
import av
import propertybag as pb

from . mc_filter import *

try:
    import sparen
    Log = sparen.log
except Exception as e:
    Log = print


# https://pyav.org/docs/stable/


### Record video from shared buffers
class mcRecord(mcFilter):

    ### Initialize object
    def __init__(self, on_error=None, opts={}):

        super().__init__(on_error=on_error, on_init=self.on_init, on_end=self.on_end,
                         on_video=self.on_video, on_audio=self.on_audio, opts=opts)
        self.avf = pb.Bag()
        self.fname = None


    def __del__(self):
        super().__del__()
        self.close()


    ### Release resources and prepare object for reuse
    def close(self):

        super().close()


    ### Closes any open file
    def closeFile(self):

        # Close any open file
        if self.avf.file:

            # Finalize audio stream
            if self.avf.astream:
                for pkt in self.avf.astream.encode():
                    self.avf.file.mux(pkt)
                del self.avf.astream

            # Finalize video stream
            if self.avf.vstream:
                for pkt in self.avf.vstream.encode():
                    self.avf.file.mux(pkt)
                del self.avf.vstream

            # Close file
            self.avf.file.close()
            del self.avf.file

        self.avf = pb.Bag()


    ''' Creates the shared memory buffer
        @param [in] fname   - File name
        @param [in] opts    - Options
                                video   : The name of the video share
                                audio   : The name of the audio share
                                vtype   : Video encoding, default "libx264"
                                pixfmt  : Pixel format, default "yuv420p"
                                atype   : Audio encoding, default "aac"
                                alayout : Audio layout, defualt [1:'mono', 2:'stereo', ...:'multi']
    '''
    def create(self, fname, opts={}):

        self.close()

        self.fname = fname

        return super().create(opts=opts)


    ### Creates video file
    def createFile(self):

        self.closeFile()

        if not self.fname:
            self.sErr = f"File name not specified"
            self.close()
            return False

        # Attempt to create a video writer
        self.avf.file = av.open(file=self.fname, format=None, mode="w", options={})
        if not self.avf.file:
            self.sErr = f"Failed to create file : {self.fname}"
            self.close()
            return False

        self.avf.vpts = 0
        self.avf.apts = 0

        if self.ashare:

            if not self.ashare.isOpen():
                self.sErr = f"Audio share is not connected : {self.fname}"
                self.close()
                return False

            # Get audio params
            ch = self.ashare.getChannels()
            bps = self.ashare.getBps()
            brate = self.ashare.getBitrate()
            afps = self.ashare.getFps()

            if not self.opts.atype:
                self.opts.atype = 'aac'
            if not self.opts.alayout:
                if 1 == ch:
                    self.opts.alayout = 'mono'
                elif 2 == ch:
                    self.opts.alayout = 'stereo'
                else:
                    self.opts.alayout = 'multi'
            if not self.opts.dtype:
                if 8 == bps:
                    self.opts.dtype = 'int8'
                elif 16 == bps:
                    self.opts.dtype = 'int16'
                else:
                    self.sErr = f"Invalid audio sample type for BPS:{bps}"
                    self.close()
                    return False
            if not self.opts.audbuf:
                if 8 == bps:
                    self.opts.audbuf = 's8'
                elif 16 == bps:
                    self.opts.audbuf = 's16'
                else:
                    self.sErr = f"Invalid audio sample type for BPS:{bps}"
                    self.close()
                    return False

            # Add audio stream
            self.avf.astream = self.avf.file.add_stream(self.opts.atype, rate=brate, layout=self.opts.alayout)
            if not self.avf.astream:
                self.sErr = f"Failed to create audio stream : {self.fname}"
                self.close()
                return False

            self.avf.afps = afps
            self.avf.asr = brate
            self.avf.time_base = "1/" + str(brate)

            # Number of audio samples per interval
            self.avf.isamples = int(brate / afps)

            # Create silence buffer
            # self.avf.silence = np.zeros((ch, self.avf.isamples), dtype=self.opts.dtype)

        if self.vshare:

            if not self.vshare.isOpen():
                self.sErr = f"Video share is not connected : {self.fname}"
                self.close()
                return False

            # Get video parameters
            w = self.vshare.getWidth()
            h = self.vshare.getHeight()
            vfps = self.vshare.getFps()
            brate = int(w * h * 2)

            # Adjust for roi
            if 'roi' in self.opts:
                r = self.opts.roi
                if 0 > r.x or 0 > r.y or w < (r.x+r.w) or h < (r.y+r.h):
                    self.sErr = f"Invalid roi : {r} in {w} x {h}"
                    self.close()
                    return False
                w = r.w - r.x
                h = r.h - r.y

            if 0 >= w or 0 >= h or 0 >= vfps:
                self.sErr = f"Invalid video parameters : {w} x {h} x {vfps}"
                self.close()
                return False

            if not self.opts.vtype:
                self.opts.vtype = "libx264"
            if not self.opts.pixfmt:
                self.opts.pixfmt = "yuv420p"
            if not self.opts.pixtype:
                self.opts.pixbuf = "rgb24"

            # Add video stream libopenh264
            self.avf.vstream = self.avf.file.add_stream(self.opts.vtype, rate=vfps)#, options={'movflags': 'faststart'})
            if not self.avf.vstream:
                self.sErr = f"Failed to create video stream : {self.fname}"
                self.close()
                return False

            self.avf.vstream.pix_fmt = self.opts.pixfmt
            self.avf.vstream.width = w
            self.avf.vstream.height = h
            self.avf.vstream.bit_rate = brate
            self.avf.vstream.bit_rate_tolerance = int(brate)
            self.avf.vstream.time_base = "1/" + str(vfps)
            # self.avf.vstream.thread_type = 'AUTO'

        return True


    ''' Write a video frame to the specified file
        @param [in] arr     - numpy array containing frame to write
    '''
    def writeVideoFrame(self, arr):

        if type(arr) != np.ndarray:
            return False

        if not self.avf or not self.avf.vstream:
            return False

        frame = av.VideoFrame.from_ndarray(arr, format=self.opts.pixbuf)
        frame.pts = self.avf.vpts
        frame.time_base = self.avf.vstream.time_base
        for pkt in self.avf.vstream.encode(frame):
            self.avf.file.mux(pkt)

        self.avf.vpts += 1

        return True


    ''' Write an audio frame to the specified file
        @param [in] arr     - numpy array containing frame to write
    '''
    def writeAudioFrame(self, arr):

        if not self.avf or not self.avf.astream:
            return False

        # Write audio
        aframe = av.AudioFrame.from_ndarray(arr, self.opts.audbuf, layout=self.opts.alayout)
        aframe.pts = self.avf.apts
        aframe.sample_rate = self.avf.asr
        aframe.time_base = self.avf.time_base
        for pkt in self.avf.astream.encode(aframe):
            self.avf.file.mux(pkt)

        self.avf.apts += int(self.avf.asr / self.avf.afps)

        return True

    def on_init(self, ctx):
        self.createFile()

    def on_end(self, ctx):
        self.closeFile()

    def on_video(self, ctx, vfi, vfr):
        self.writeVideoFrame(vfr)

    def on_audio(self, ctx, afi, afr):
        self.writeAudioFrame(afr)
