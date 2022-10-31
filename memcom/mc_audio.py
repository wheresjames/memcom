#!/usr/bin/env python3

import time
import string
import random
import json
import numpy as np

from multiprocessing import shared_memory

try:
    import sparen
    Log = sparen.log
except Exception as e:
    Log = print


### Share audio buffers between processes
class mcAudio:

    ### Initialize object
    def __init__(self):

        # Buffer overhead
        # [0] = Id
        # [1] = Buffers
        # [2] = IDX
        # [3] = Channels
        # [4] = Bps
        # [5] = Bitrate
        # [6] = FPS
        self.nOvInts = 8 # Use an even number for byte alignment
        self.nOvBytes = self.nOvInts * 8

        # Packet overhead
        # [0] = Id
        # [1] = PTS
        # [2] = IDX
        # [3] = CLK
        # [4] = WTS
        # [5] = RDS
        self.nPktOvInts = 6 # Use an even number
        self.nPktOvBytes = self.nPktOvInts * 8

        # ID
        self.nBufferId = 0x1D13E088FF530CBB
        self.nPacketId = 0x16881400350AF97E

        self.cShm = None
        self.sErr = ""
        self.close()

        self.nBufs = []


    ### Delete
    def __del__(self):
        self.close()


    ### Returns the last error string
    def getError(self):
        return self.sErr


    ### Returns True if share is open
    def isOpen(self):
        return True if self.cShm else False


    ### Return the share name of the buffer
    def getName(self):
        return self.sName


    ### Return the size of the buffer in bytes
    def getSize(self):
        return self.nSize


    ### Return the create flag
    def getMode(self):
        return self.sMode


    ### Returns the number of buffers
    def getBuffers(self):
        return self.nBuffers


    ### Returns the number of channels
    def getChannels(self):
        return self.nCh


    ### Returns the bps (bits per sample)
    def getBps(self):
        return self.nBps


    ### Returns the bitrate (bits per second)
    def getBitrate(self):
        return self.nBitrate


    ### Returns the video frame rate
    def getFps(self):
        return self.nFps


    ### How much to increment pts each frame
    def getPtsInc(self):
        if not self.nFps:
            return 0
        n = int(self.nBitrate / self.nFps)
        return n
        # return int(self.nBitrate / self.nFps)

    ### Release shared memory and prepare object for reuse
    def close(self):

        if self.cShm:
            self.cShm.close()
            if self.bCleanup:
                self.cShm.unlink()

        self.cShm = None
        self.sMode = ""
        self.bCleanup = False
        self.sName = ""
        self.nSize = 0
        self.nWrite = 0
        self.nRead = 0
        self.bExisting = False

        self.nBufs = []
        self.nBuffers = 0
        self.nCh = 0
        self.nBps = 0
        self.nBitrate = 0
        self.nFps = 0
        self.nPacketSize = 0
        self.nFrameSize = 0
        self.nChSize = 0


    ### Return the main header
    def getHeader(self):
        return np.ndarray(shape=(self.nOvInts,), dtype=np.int64, buffer=self.cShm.buf[0:self.nOvBytes])


    ### Get the current index
    def getIdx(self):
        hdr = self.getHeader()
        return hdr[2] % self.nBuffers


    ### Set the current index
    def setIdx(self, idx):
        hdr = self.getHeader()
        hdr[2] = idx % self.nBuffers
        return hdr[2]


    ''' Calculates the index based on the specified offset
        @param [in] off - Offset from the index
    '''
    def calcIdx(self, off):
        hdr = self.getHeader()
        idx = (hdr[2] + off) % self.nBuffers
        return idx


    # ''' Calculates the index based drift on the specified offset
    #     @param [in] off - Offset from the index
    # '''
    # def calcDrift(self, off):
    #     hdr = self.getHeader()
    #     # return int(hdr[2] - off) % int(self.nBuffers / 2)
    #     return -(int(off - hdr[2]) % int(self.nBuffers))

    ''' Calculates the index based drift on the specified offset
        @param [in] off - Offset from the index
        @param [in] ref - Reference frame, None for current frame
    '''
    def calcDrift(self, off, ref=None):
        hdr = self.getHeader()
        # return -(int(off - hdr[2]) % int(self.nBuffers / 2))
        return -(int(off - (hdr[2] if (None == ref) else ref)) % int(self.nBuffers))



    ### Add to the current index
    #   @param [in] add - Value to add to index
    def addIdx(self, add):
        hdr = self.getHeader()
        hdr[2] = (hdr[2] + add) % self.nBuffers
        return hdr[2]


    ### Get header for the specified frame
    def getFrameHeader(self, n):
        off = self.nOvBytes + (n * self.nPacketSize)
        return np.ndarray(shape=(self.nPktOvInts,), dtype=np.int64, buffer=self.cShm.buf[off:off+self.nPktOvBytes])


    ''' Set frame info
        @param [in] n   - Frame index
        @param [in] pts - PTS - Presentation Time Stamp
        @param [in] idx - IDX - Frame index
        @param [in] clk - CLK - Clock value
        @param [in] rds - RDS - Number of reads
        @param [in] wts - WTS - Number of writes
    '''
    def setFrameInfo(self, n, pts, idx, clk, rds, wts):
        fh = self.getFrameHeader(n)
        fh[1] = pts
        fh[2] = idx
        fh[3] = clk
        fh[4] = rds
        fh[5] = wts
        fh[0] = self.nPacketId


    ''' Get frame info
        @returns Object containing the following
                    {
                        pts: Presentation Time Stamp
                        idx: Frame index
                    }
    '''
    def getFrameInfo(self, n):
        fh = self.getFrameHeader(n)
        if fh[0] != self.nPacketId:
            return {}
        return {'buf': n, 'pts': fh[1], 'idx': fh[2], 'clk': fh[3], 'rds': fh[4], 'wts': fh[5]}


    ''' Creates the shared memory buffer
        @param [in] mode    - How to create the share
                                always      = [default] Attach to existing share if it exists, otherwise create
                                existing    = Open only if it already exists
                                new         = Always create a new share, existing share will be unlinked
        @param [in] name    - Name for memory buffer, if not provided a random name will be generated.
        @param [in] size    - Desired total size of the memory buffer
        @param [in] cleanup - Non-zero if the shared memory should be unlinked on close

        @returns True if success
    '''
    def create(self, name = None, bufs = 0, ch = 0, bps = 0, bitrate = 0, fps = 0, mode = "always", cleanup = False):

        self.sErr = ""
        self.close()

        self.sMode = mode
        self.sName = name if name else ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(32))
        self.bCleanup = cleanup

        try:

            # Attempt to open existing share
            try:
                self.cShm = shared_memory.SharedMemory(name=self.sName, create=False) #, size=self.nSize)
                if self.cShm:
                    self.bExisting = True
            except Exception as e:
                self.cShm = None

            # Kill existing share if caller wants a new one
            if self.cShm and "new" == mode:
                self.cShm.close()
                self.cShm.unlink()
                self.bExisting = False

            if not self.cShm:
                if "existing" == mode:
                    self.sErr = "Share does not exist: %s" % name
                    self.close()
                    return False

                # Calculate buffer size
                if 0 >= bufs or 0 >= ch or 0 >= bps or 0 >= bitrate or 0 >= fps:
                    self.sErr = f"Invalid parameters: bufs: {bufs}, channels: {ch}, bps: {bps}, bitrate: {bitrate}, fps: {fps}"

                self.nChSize = int(bps / 8) * int(bitrate / fps)
                self.nFrameSize = ch * self.nChSize
                if 0 >= self.nFrameSize:
                    self.sErr = f"Invalid audio parameters: channels: {ch}, bps: {bps}, bitrate: {bitrate}, fps: {fps}"
                    return False

                self.nPacketSize = self.nPktOvBytes + self.nFrameSize
                self.nSize = self.nOvBytes + (bufs * self.nPacketSize)
                if 0 >= self.nSize:
                    self.sErr = "Invalid buffer size: %s" % nSize
                    return False

                # Create new share
                self.cShm = shared_memory.SharedMemory(name=self.sName, create=True, size=self.nSize)

        except Exception as e:
            Log(e)
            self.sErr = str(e)
            self.close()
            return False

        # Initialize header if new
        hdr = self.getHeader()
        if not self.bExisting:
            hdr[1] = bufs
            hdr[2] = 0
            hdr[3] = ch
            hdr[4] = bps
            hdr[5] = bitrate
            hdr[6] = fps
            hdr[0] = self.nBufferId

        # Validate header id
        if hdr[0] != self.nBufferId:
            self.sErr = "Invalid header id %s != %s : Existing: %s" % (hdr[0], self.nBufferId, self.bExisting)
            self.close()
            return False

        # Read buffer header info
        self.nBuffers = hdr[1]
        self.nCh = hdr[3]
        self.nBps = hdr[4]
        self.nBitrate = hdr[5]
        self.nFps = hdr[6]
        self.nChSize = int(self.nBps / 8) * int(self.nBitrate / self.nFps)
        self.nFrameSize = self.nCh * self.nChSize
        self.nPacketSize = self.nPktOvBytes + self.nFrameSize
        self.nSize = self.nOvBytes + (self.nBuffers * self.nPacketSize)

        self.nBufs = []
        for i in range(0, self.nBuffers):
            self.nBufs.append(self.getBuf(i))

        return True


    ### Returns an array of all buffers
    def getBufs(self):
        return self.nBufs


    ''' Returns the specified buffer as a numpy array
        @param [in] n   - Buffer index to return
    '''
    def getBuf(self, n):

        if 0 > n or n >= self.nBuffers:
            self.sErr = "Invalid buffer index: %s" % n
            return None

        # Calculate buffer offset
        off = self.nOvBytes + (n * self.nPacketSize) + self.nPktOvBytes
        # return np.ndarray(shape=(self.nCh, self.nChSize), dtype=np.uint8, buffer=self.cShm.buf[off:off+self.nFrameSize])
        return np.ndarray(shape=(1, int(2 * self.nBitrate / self.nFps)), dtype=np.int16, buffer=self.cShm.buf[off:off+self.nFrameSize])
        # self.arr = numpy.zeros((1, self.nsamples), dtype='int16')


    ''' Correct audio drift
        @param [in] pa - First pointer
        @param [in] pb - Second pointer
        @param [in] sz - Ring buffer size
        @param [in] r  - [min, max, bias]
    '''
    def mixPtr(pa, pb, sz, r):

        # drift = (pa - pb) % (sz / 2)

        drift = pa - pb
        hsz = int(sz / 2)

        # Correct ring buffer offset
        if -hsz > drift:
            drift = drift + sz
        elif hsz < drift:
            drift = drift - sz

        # Correct if drift is too far out
        if r[0] > drift or r[1] < drift:
            # pa = (pb + r[2]) % sz
            pa = pb + r[2]
            if pa > sz:
                pa -= sz
            elif pa < 0:
                pa += sz

        # return pa, (drift - r[2]), drift
        return pa, (drift - r[2])


    ''' Mix audio buffers
        @param [out]    dst  - Output buffer array
        @param [in/out] dctx - Output context
        @param [in]     src  - Input buffer array
        @param [in/out] sctx - Input context
        @param [in]     opts - Options
                                [mix]
                                    True  = Mix audio into current buffer
                                    False = Overwrite current buffer

        Input / Output contexts
            i - array index
            n - number of buffers to copy
            o - current buffer offset
            r - Resample
    '''
    def mixAudio(dst, dctx, src, sctx, opts={}):

        # Initialize mixing context
        def initCtx(d, s):
            for k in s:
                if k not in d:
                    d[k] = s[k]

        # Mixing?
        mix = False
        if 'mix' in opts:
            mix = opts['mix']

        # Init context objects
        initCtx(dctx, {'i':0, 'n':0, 'o':0})
        initCtx(sctx, {'i':0, 'n':0, 'o':0})

        # How big is the destination ring buffer?
        dl = len(dst)
        if dctx['n'] > dl:
            dctx['n'] = dl

        # How big is the source ring buffer?
        sl = len(src)
        if sctx['n'] > sl:
            sctx['n'] = sl

        # Resample
        r = 0
        if 'r' in dctx:
            r = float(dctx['r'])
        elif 'r' in sctx:
            r = float(sctx['r'])

        # Range limit r
        if -1.0 > r:
            r = -1.0
        elif 1.0 < r:
            r = 1.0

        # While we have stuff to copy
        while 0 < dctx['n'] or 0 < sctx['n']:

            # Destination buffer
            if dctx['i'] >= dl:
                dctx['i'] = 0
            d = dst[dctx['i']]
            if 'ndarray' != type(d).__name__:
                Log("Invalid destination object")
                return

            # Source buffer
            if sctx['i'] >= sl:
                sctx['i'] = 0
            s = src[sctx['i']]
            if 'ndarray' != type(s).__name__:
                Log("Invalid source object")
                return

            # Buffer size
            dch, dsz = d.shape
            sch, ssz = s.shape

            # Next source buffer?
            if sctx['o'] >= ssz:
                sctx['o'] = 0
                sctx['n'] -= 1
                sctx['i'] += 1

            # Next destination buffer?
            elif dctx['o'] >= dsz:
                dctx['o'] = 0
                dctx['n'] -= 1
                dctx['i'] += 1

            else:

                # Dividers
                sdv = 1 if (sch >= dch) else dch
                ddv = 1 if (dch >= sch) else sch

                # How much to copy
                scp = int((ssz - sctx['o']) / sdv)
                dcp = int((dsz - dctx['o']) / ddv)

                # Scaling?
                rcp = scp
                if 0 != r:
                    rcp = int(rcp + (r * rcp * 2))

                cp = rcp
                if cp > dcp:
                    cp = dcp
                    if rcp != scp:
                        tmp = scp
                        scp = int(cp * scp / rcp)
                    else:
                        scp = cp

                # We could get zero after scaling
                if 0 < cp and 0 < scp:

                    # Same channel layout
                    if dch == sch:
                        for i in range(dch):

                            sb = s[i][sctx['o']:sctx['o']+scp]

                            if cp != scp:
                                sb = scipy.signal.resample(sb, cp)

                            if mix:
                                sa = d[i][dctx['o']:dctx['o']+cp]
                                d[i][dctx['o']:dctx['o']+cp] = sa / 2 + sb / 2
                            else:
                                d[i][dctx['o']:dctx['o']+cp] = sb

                    # Interleaved destination
                    elif 1 == dch and 1 < sch:
                        for i in range(sch):

                            sb = s[i][sctx['o']:sctx['o']+scp]
                            if cp != scp:
                                sb = scipy.signal.resample(sb, cp)

                            if mix:
                                sa = d[0][dctx['o']+i:dctx['o']+(cp*sch)+i:sch]
                                d[0][dctx['o']+i:dctx['o']+(cp*sch)+i:sch] = sa / 2 + sb / 2
                            else:
                                d[0][dctx['o']+i:dctx['o']+(cp*sch)+i:sch] = sb

                    # Interleaved source
                    elif 1 < dch and 1 == sch:
                        for i in range(dch):

                            sb = s[0][sctx['o']+i:sctx['o']+(scp*dch)+i:dch]
                            if cp != scp:
                                sb = scipy.signal.resample(sb, cp)

                            if mix:
                                sa = d[i][dctx['o']:dctx['o']+cp]
                                d[i][dctx['o']:dctx['o']+cp] = sa / 2 + sb / 2
                            else:
                                d[i][dctx['o']:dctx['o']+cp] = sb

                    else:
                        Log("UNHANDLED CHANNEL LAYOUT : " + str(sch) + " --> " + str(dch))
                        return

                dctx['o'] += cp * ddv
                sctx['o'] += scp * sdv

