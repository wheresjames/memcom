#!/usr/bin/env python3

import sys
import time
import json
import asyncio
import inspect
import memcom
import numpy as np

# https://code.activestate.com/recipes/519626-simple-file-based-mutex-for-very-basic-ipc/

try:
    import sparen
    Log = sparen.log
except:
    Log = print
Fmt = lambda o: json.dumps(o, indent=2)


#------------------------------------------------------------------------------
def test_1():

    msg = memcom.mcMessage()

    if not msg.create(cleanup=True):
        Log(msg.getError())
        exit(-1)

    Log("Created shared memory buffer: %s" % msg.getName())

    writes = 10000
    start = time.time()
    for i in range(0, writes):

        snd = 'This is a message'

        if not msg.send(snd):
            Log(msg.getError())
            exit(-1)

        r = msg.read()
        if not r:
            Log(msg.getError())
            exit(-1)

        if r != snd:
            Log("%s != %s" % (r, snd))
            exit(-1)

    end = time.time() - start
    Log("%s messages sent and read in %s seconds : %s messages/second" % (writes, '{0:.6f}'.format(end), '{0:.3f}'.format(writes / end)))


#------------------------------------------------------------------------------
def test_2():

    msg = memcom.mcMessage()

    if not msg.create(cleanup=True):
        Log(msg.getError())
        exit(-1)

    Log("Created shared memory buffer: %s" % msg.getName())

    writes = 10000
    start = time.time()
    for i in range(0, writes):

        snd = "Message %s" % str(i).rjust(i%200, '-')

        if not msg.send(snd):
            Log(msg.getError())
            exit(-1)

        r = msg.read()
        if not r:
            Log(msg.getError())
            exit(-1)

        if r != snd:
            Log("%s != %s" % (r, snd))
            exit(-1)

    end = time.time() - start
    Log("%s messages sent and read in %s seconds : %s messages/second" % (writes, '{0:.6f}'.format(end), '{0:.3f}'.format(writes / end)))


#------------------------------------------------------------------------------
def test_3():

    msg = memcom.mcMessage()

    if not msg.create(cleanup=True, size=2 * 1024):
        Log(msg.getError())
        exit(-1)

    Log("Created shared memory buffer: %s" % msg.getName())

    loops = 100
    writes = 1000
    start = time.time()
    for sz in range(0, loops):

        for i in range(0, writes):

            snd = '-'.rjust(sz, '-')

            if not msg.send(snd):
                Log(sz, i, len(snd), snd)
                Log("Tx failed: ", msg.getError())
                exit(-1)

            r = msg.read()
            if not r:
                Log(sz, i, r, len(snd), snd)
                Log("Rx failed: ", msg.getError())
                exit(-1)

            if r != snd:
                Log("%s != %s" % (r, snd))
                exit(-1)

    tot = loops * writes
    end = time.time() - start
    Log("%s messages sent and read in %s seconds : %s messages/second" % (tot, '{0:.6f}'.format(end), '{0:.3f}'.format(tot / end)))


#------------------------------------------------------------------------------
def test_4():

    b = 16
    w = 320
    h = 240
    fps = 15
    name = 'testAvShare'

    Log('Create video share')
    vb1 = memcom.mcVideo()
    if not vb1.create(name=name, bufs=b, width=w, height=h, fps=fps, cleanup=True):
        raise Exception(vb1.getError())

    Log('Open video share')
    vb2 = memcom.mcVideo()
    if not vb2.create(name=name, mode='existing'):
        raise Exception(name + " : " + vb2.getError())

    if b != vb2.getBuffers():
        raise Exception(f'Invalid buffer size {b} / {vb2.getBuffers()}')

    if w != vb2.getWidth():
        raise Exception(f'Invalid width {w} / {vb2.getWidth()}')

    if h != vb2.getHeight():
        raise Exception(f'Invalid height {h} / {vb2.getHeight()}')

    if fps != vb2.getFps():
        raise Exception(f'Invalid FPS {fps} / {vb2.getFps()}')

    # Write to each frame and verify
    for i in range(0, b):

        # Iterate forward
        assert vb1.getIdx() == i
        assert vb2.getIdx() == i
        assert vb1.calcIdx(1) == (i+1)%b
        assert vb2.calcIdx(1) == (i+1)%b
        assert vb1.addIdx(1) == (i+1)%b
        assert vb2.getIdx() == (i+1)%b

        vb1.setFrameInfo(i, i * 1000, i, i+1, i+2, i+3)
        fi = vb2.getFrameInfo(i)
        if fi['pts'] != i * 1000:
            raise Exception(f'PTS does not match {fi["pts"]} !≃ {i * 1000}')
        if fi['idx'] != i:
            raise Exception(f'IDX does not match {fi["idx"]} !≃ {i}')
        if fi['clk'] != i+1:
            raise Exception(f'CLK does not match {fi["clk"]} !≃ {i+1}')
        if fi['rds'] != i+2:
            raise Exception(f'RDS does not match {fi["rds"]} !≃ {i+2}')
        if fi['wts'] != i+3:
            raise Exception(f'WTS does not match {fi["wts"]} !≃ {i+3}')

        buf1 = vb1.getBuf(i)
        if not isinstance(buf1, np.ndarray):
            raise Exception(f'Failed to get shared buffer pointer vb1 {name}')

        b1h, b1w, b1c = buf1.shape

        buf2 = vb2.getBuf(i)
        if not isinstance(buf2, np.ndarray):
            raise Exception(f'Failed to get shared buffer pointer vb2 {name}')

        b2h, b2w, b2c = buf2.shape

        if b1h != b2h or b1w != b2w or b1c != b2c:
            raise Exception(f'Buffers sizes do not match {(b1h, b1w, b1c)} !≃ {(b2h, b2w, b2c)}')

        # Pixel write test
        buf1[0][0][0] = 123
        if 123 != buf2[0][0][0] or buf2[0][0][0] != 123:
            raise Exception(f'Buffer write failed {123}, {buf1[0][0][0]}, {buf2[0][0][0]}')

        vb1.getBufs()[i][0][0][0] = 111
        if 111 != buf1[0][0][0] or buf1[0][0][0] != buf2[0][0][0]:
            raise Exception(f'Buffer write failed {111}, {buf1[0][0][0]}, {buf2[0][0][0]}')


    vb2.close()
    vb1.close()

    if vb2.create(name=name, mode='existing'):
        raise Exception(f'Buffer still exists {name}!')

#------------------------------------------------------------------------------
def test_5():

    b = 3 * 50
    ch = 2
    bps = 16
    bitrate = 48000
    fps = 50
    name = 'testAvShare'

    Log('Create audio share')
    ab1 = memcom.mcAudio()
    if not ab1.create(name=name, bufs=b, ch=ch, bps=bps, bitrate=bitrate, fps=fps, cleanup=True):
        raise Exception(ab1.getError())

    Log('Open audio share')
    ab2 = memcom.mcAudio()
    if not ab2.create(name=name, mode='existing'):
        raise Exception(name + " : " + ab2.getError())

    if b != ab2.getBuffers():
        raise Exception(f'Invalid buffer size {b} / {ab2.getBuffers()}')

    if ch != ab2.getChannels():
        raise Exception(f'Invalid channels {ch} / {ab2.getChannels()}')

    if bps != ab2.getBps():
        raise Exception(f'Invalid bps {bps} / {ab2.getBps()}')

    if bitrate != ab2.getBitrate():
        raise Exception(f'Invalid bitrate {bitrate} / {ab2.getBitrate()}')

    if fps != ab2.getFps():
        raise Exception(f'Invalid FPS {fps} / {ab2.getFps()}')

    # Write to each frame and verify
    for i in range(0, b):

        # Iterate backward
        assert ab1.getIdx() == (b-i)%b
        assert ab2.getIdx() == (b-i)%b
        assert ab1.addIdx(-1) == (b-i-1)%b
        assert ab2.getIdx() == (b-i-1)%b

        ab1.setFrameInfo(i, i * 1000, i, i+1, i+2, i+3)
        fi = ab2.getFrameInfo(i)
        if fi['pts'] != i * 1000:
            raise Exception(f'PTS does not match {fi["pts"]} !≃ {i * 1000}')
        if fi['idx'] != i:
            raise Exception(f'IDX does not match {fi["idx"]} !≃ {i}')
        if fi['clk'] != i+1:
            raise Exception(f'CLK does not match {fi["clk"]} !≃ {i+1}')
        if fi['rds'] != i+2:
            raise Exception(f'RDS does not match {fi["rds"]} !≃ {i+2}')
        if fi['wts'] != i+3:
            raise Exception(f'WTS does not match {fi["wts"]} !≃ {i+3}')

        buf1 = ab1.getBuf(i)
        if not isinstance(buf1, np.ndarray):
            raise Exception(f'Failed to get shared buffer pointer ab1 {name}')

        b1ch, b1sz = buf1.shape

        buf2 = ab2.getBuf(i)
        if not isinstance(buf2, np.ndarray):
            raise Exception(f'Failed to get shared buffer pointer ab2 {name}')

        b2ch, b2sz = buf2.shape

        if b1ch != b2ch or b1sz != b2sz:
            raise Exception(f'Buffers sizes do not match {(b1ch, b1sz)} !≃ {(b2ch, b2sz)}')

        buf1[0][0] = 123
        if 123 != buf1[0][0] or buf1[0][0] != buf2[0][0]:
            raise Exception(f'Buffer write failed {123}, {buf1[0][0]}, {buf2[0][0]}')

        ab1.getBufs()[i][0][0] = 111
        if 111 != buf1[0][0] or buf1[0][0] != buf2[0][0]:
            raise Exception(f'Buffer write failed {111}, {buf1[0][0]}, {buf2[0][0]}')

    ab2.close()
    ab1.close()

    if ab2.create(name=name, mode='existing'):
        raise Exception(f'Buffer still exists {name}!')


#------------------------------------------------------------------------------

async def run():

    Log(Fmt(memcom.__info__))

    # https://bugs.python.org/issue38119
    # Remove shared memory from resource tracker
    memcom.remove_shm_from_resource_tracker()

    # Run specific tests
    if 1 < len(sys.argv):
        Log(f'\r\nRunning tests {sys.argv[1]}')

        tests = sys.argv[1].split(',')
        for v in tests:
            fn = f'test_{v}'
            if fn in globals() and callable(globals()[fn]):
                Log(f'\r\n-----------------------------------\r\nRunning test {v}\r\n-----------------------------------')
                r = globals()[fn]()
                if inspect.isawaitable(r):
                    await r

    # Run all tests
    else:
        Log('Running all tests...')
        i = 1
        while True:
            fn = f'test_{i}'
            if fn not in globals() or not callable(globals()[fn]):
                break
            Log(f'\r\n-----------------------------------\r\nRunning test {i}\r\n-----------------------------------')
            r = globals()[fn]()
            if inspect.isawaitable(r):
                await r
            i += 1


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

