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
class mcBlank(mcFilter):

    ''' Initialize object
        @param [in] opts    - Options
    '''
    def __init__(self, on_error=None, opts={}):
        super().__init__(on_error=on_error, on_video=self.on_video, on_audio=self.on_audio, opts=opts)


    ### Delete
    def __del__(self):
        super().__del__()
        self.close()


    ### Release resources and prepare object for reuse
    def close(self):
        super().close()


    def on_video(self, ctx, vfi, vfr):
        vfr.fill(0)


    def on_audio(self, ctx, afi, afr):
        afr.fill(0)

