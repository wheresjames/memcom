#!/usr/bin/env python3

# https://bugs.python.org/issue38119

import time
import string
import random
import json
import numpy as np
from multiprocessing import shared_memory

try:
    import sparen
    Log = sparen.log
except:
    Log = print

class mcMessage:

    ### Initialize object
    def __init__(self):

        # Packet overhead
        self.nOv = 8
        self.nOvInts = int(self.nOv/4)

        # Header ID
        self.nId = 0x148219F8

        self.cShm = None
        self.sErr = ""
        self.close()

    def __del__(self):
        self.close()

    ### Returns the last error string
    def getError(self):
        return self.sErr

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
        self.cb = {}

    ### Return the header
    def getHeader(self, off):
        return np.ndarray(shape=(self.nOvInts,), dtype=np.int32, buffer=self.cShm.buf[off:off+self.nOv])

    ### Sets header info
    def setHeader(self, off, h1):
        hdr = self.getHeader(off)
        hdr[1] = h1
        hdr[0] = self.nId


    ### Creates the shared memory buffer
    #   @param [in] mode    - How to create the share
    #                           always      = [default] Attach to existing share if it exists, otherwise create
    #                           existing    = Open only if it already exists
    #                           new         = Always create a new share, existing share will be unlinked
    #   @param [in] name    - Name for memory buffer, if not provided a random name will be generated.
    #   @param [in] size    - Desired total size of the memory buffer
    #   @param [in] cleanup - Non-zero if the shared memory should be unlinked on close
    #
    #   @returns True if success
    def create(self, name = "", mode = "always", size = 64 * 1024, cleanup = False):

        self.sErr = ""
        self.close()

        if 0 >= size:
            self.sErr = "Invalid size"
            return False

        self.sMode = mode
        self.sName = name if name else ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(32))
        self.nSize = size
        self.bCleanup = cleanup

        try:

            # Attempt to open existing share
            try:
                self.cShm = shared_memory.SharedMemory(name=self.sName, create=False, size=self.nSize)
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

                # Create new share
                self.cShm = shared_memory.SharedMemory(name=self.sName, create=True, size=self.nSize)

        except Exception as e:
            Log(e)
            self.sErr = str(e)
            self.close()
            return False

        # Initialize header if new
        if not self.bExisting:
            self.setHeader(0, 0)

        return True

    ### Write a message into the shared queue
    # @param [in] msg   - Message to write
    def send(self, msg):

        self.sErr = ""

        if not self.cShm:
            self.sErr = "No shared memory object"
            return False

        pkt = msg.encode("utf8")

        if len(pkt) <= 0:
            self.sErr = "Message length is too short"
            return False

        ov = self.nOv + len(pkt)
        if int(self.nSize / 2) <= ov + self.nOv:
            self.sErr = "Message length is too long"
            return False

        # Time to wrap?
        if self.nSize <= self.nWrite + ov + self.nOv:
            self.setHeader(0, 0)
            self.setHeader(self.nWrite, -1)
            self.nWrite = 0

        # Add packet data
        off = self.nWrite + self.nOv
        self.cShm.buf[off:off+len(pkt)] = pkt

        # Update next header
        self.setHeader(self.nWrite + ov, 0)

        # Update this header
        self.setHeader(self.nWrite, ov)

        # Update write pointer
        self.nWrite += ov

        return True

    ### Read one message from the shared queue
    def read(self):

        self.sErr = ""

        if not self.cShm:
            self.sErr = "No shared memory object"
            return None

        # Time to wrap read pointer?
        if ((self.nRead+self.nOv) >= self.nSize):
            self.nRead = 0

        # Try to read a packet
        while True:

            # header
            hdr = self.getHeader(self.nRead)

            # Verify id
            if hdr[0] != self.nId:
                self.sErr = "Invalid memory block header: %s" % hex(hdr[0])
                self.nRead = 0
                return None

            # Read block size
            h1 = hdr[1]

            # Check for empty buffer
            if not h1:
                return None

            # Check for wrapper marker
            if -1 == h1:
                self.nRead = 0
                continue

            # Make sure block size makes sense
            if self.nOv >= h1:
                self.sErr = "Invalid block size: %s" %h1
                self.nRead = 0
                return None

            break

        # Read the message from the buffer
        off = self.nRead + self.nOv
        msg = bytes(self.cShm.buf[off:off+h1-self.nOv])

        # Skip to next block
        self.nRead += h1

        try:
            return msg.decode()
        except Exception as e:
            Log(e)
            Log(msg)
            return None

