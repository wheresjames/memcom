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


### Share video buffers between processes
class mcVideo:

    ### Initialize object
    def __init__(self):

        # Buffer overhead
        # [0] = ID
        # [1] = Buffers
        # [2] = IDX
        # [3] = Width
        # [4] = Height
        # [5] = FPS
        self.nOvInts = 6 # Use an even number for byte alignment
        self.nOvBytes = self.nOvInts * 8

        # Packet overhead
        # [0] = ID
        # [1] = PTS
        # [2] = IDX
        # [3] = CLK
        # [4] = WTS
        # [5] = RDS
        self.nPktOvInts = 6 # Use an even number
        self.nPktOvBytes = self.nPktOvInts * 8

        # ID
        self.nBufferId = 0x1DDA5A7A2C4C8918
        self.nPacketId = 0x1E6BA49114CE2619

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


    ### Returns the width of a single frame
    def getWidth(self):
        return self.nWidth


    ### Returns the height of a single frame
    def getHeight(self):
        return self.nHeight


    ### Returns the video frame rate
    def getFps(self):
        return self.nFps


    ### How much to increment pts each frame
    def getPtsInc(self):
        return 1


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
        self.nWidth = 0
        self.nHeight = 0
        self.nFps = 0
        self.nPacketSize = 0
        self.nFrameSize = 0


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


    ''' Calculates the index based drift on the specified offset
        @param [in] off - Offset from the index
        @param [in] ref - Reference frame, None for current frame
    '''
    def calcDrift(self, off, ref=None):
        hdr = self.getHeader()
        # return -(int(off - hdr[2]) % int(self.nBuffers / 2))
        return -(int(off - (hdr[2] if (None == ref) else ref)) % int(self.nBuffers))


    ''' Add to the current index
        @param [in] add - Value to add to index
        https://pypi.org/project/atomics/
    '''
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
    def create(self, name = None, bufs = 0, width = 0, height = 0, fps = 0, mode = "always", cleanup = False):

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
                if 0 >= bufs or 0 >= width or 0 >= height:
                    self.sErr = "Invalid parameters: bufs: %s, width: %s, height %s" % (bufs, width, height)
                self.nFrameSize = width * height * 3
                if 0 >= self.nFrameSize:
                    self.sErr = "Invalid video size: %sx%s" % (width, height)
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
            hdr[3] = width
            hdr[4] = height
            hdr[5] = fps
            hdr[0] = self.nBufferId

        # Validate header id
        if hdr[0] != self.nBufferId:
            self.sErr = "Invalid header id %s != %s" % (hdr[0], self.nBufferId)
            self.close()
            return False

        # Read buffer header info
        self.nBuffers = hdr[1]
        self.nWidth = hdr[3]
        self.nHeight = hdr[4]
        self.nFps = hdr[5]
        self.nFrameSize = self.nWidth * self.nHeight * 3
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
        return np.ndarray(shape=(self.nHeight, self.nWidth, 3), dtype=np.uint8, buffer=self.cShm.buf[off:off+self.nFrameSize])


    ''' Return the buffer or region of interest
        @param [in] fname   - File name
        @param [in] n       - Buffer index to save, -1 for current frame
        @param [in] roi     - Optional ROI (Region Of Interest)
                                {x:?, y:?, w:?, h:?}
    '''
    def getRoi(self, n=-1, roi=None):

        if not self.isOpen():
            return None

        if 0 > n:
            n = self.getIdx()
        arr = self.getBuf(n)

        if type(arr) != np.ndarray:
            self.sErr = "Not of type numpy.ndarray"
            return None

        h, w, c = arr.shape
        if roi:
            arr = varr[roi['y']:roi['y']+roi['h'], roi['x']:roi['x']+roi['w']]
            h, w, c = arr.shape

        if 3 != c:
            self.sErr = f'Invalid video format {w} x {h} x {c}'
            return None

        return arr


    ''' Save a buffer to the disk as an image
        @param [in] fname   - File name
        @param [in] n       - Buffer index to save, -1 for current frame
        @param [in] roi     - Optional ROI (Region Of Interest)
                                {x:?, y:?, w:?, h:?}
    '''
    def saveImage(self, fname, n=-1, roi=None):

        buf = self.getRoi(n, roi)
        if type(buf) != np.ndarray:
            return None

        from PIL import Image
        img = Image.fromarray(buf)
        if img:
            img.save(fname)

        return img
