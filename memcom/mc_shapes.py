#!/usr/bin/env python3

import math
import numpy as np


### Creates a test video
class mcShapes:

    ''' Draws a line into a numpy array
        @param [in] arr     - The numpy array to draw into
        @param [in] x1      - The x coord of the line start
        @param [in] y1      - The y coord of the line start
        @param [in] x2      - The x coord of the line end
        @param [in] y2      - The y coord of the line end
        @param [in] col     - Color as array.  Example: [red, green, blue]
    '''
    @staticmethod
    def drawLine(arr, x1, y1, x2, y2, col):

        h, w, c = arr.shape

        # Horizontal line?
        if y1 == y2:
            if x1 > x2:
                x1, x2 = x2, x1
            arr[y1][x1:x2] = col

        # Veritical line?
        elif x1 == x2:
            if y1 > y2:
                y1, y2 = y2, y1
            for y in range(y1, y2):
                arr[y][x1] = col
                arr[y][x1] = col

        # Arbitrary line
        else:
            mx = 0
            sx = abs(x2 - x1)
            dx = 1 if x1 < x2 else -1
            x = x1
            my = 0
            sy = abs(y2 - y1)
            dy = 1 if y1 < y2 else -1
            y = y1
            arr[y][x] = col
            mxl = sx + sy
            while 0 < mxl:
                mxl -= 1
                mx += sx
                if mx >= sy:
                    x += dx
                    if (0 < dx and (x < x1 or x > x2)) or (0 > dx and (x < x2 or x > x1)):
                        break
                    mx -= sy
                    arr[y][x] = col
                my += sy
                if my >= sx:
                    y += dy
                    if (0 < dy and (y < y1 or y > y2)) or (0 > dy and (y < y2 or y > y1)):
                        break
                    my -= sx
                    arr[y][x] = col


    ''' Draws a rectangle into a numpy array
        @param [in] arr     - The numpy array to draw into
        @param [in] x1      - The x coord of the top left corner
        @param [in] y1      - The y coord of the top left corner
        @param [in] x2      - The x coord of the bottom right corner
        @param [in] y2      - The y coord of the bottom right corner
        @param [in] col     - Color as array.  Example: [red, green, blue]
    '''
    @staticmethod
    def drawRect(arr, x1, y1, x2, y2, col):
        mcShapes.drawLine(arr, x1, y1, x2, y1, col)
        mcShapes.drawLine(arr, x1, y2, x2, y2, col)
        mcShapes.drawLine(arr, x1, y1, x1, y2, col)
        mcShapes.drawLine(arr, x2, y1, x2, y2, col)


    ''' Fills a rectangle into a numpy array
        @param [in] arr     - The numpy array to draw into
        @param [in] x1      - The x coord of the top left corner
        @param [in] y1      - The y coord of the top left corner
        @param [in] x2      - The x coord of the bottom right corner
        @param [in] y2      - The y coord of the bottom right corner
        @param [in] col     - Color as array.  Example: [red, green, blue]
    '''
    @staticmethod
    def fillRect(arr, x1, y1, x2, y2, col):
        for y in range(y1, y2, 1 if y1 < y2 else -1):
            arr[y][x1:x2] = col


    ''' Draw an arc into a numpy buffer
        @param [in] arr     - The numpy buffer to draw into
        @param [in] x       - The horizontal offset to the center of the circle
        @param [in] y       - The vertical offset to the center of the circle
        @param [in] r       - The circle radius
        @param [in] start   - Starting angle in degrees
        @param [in] end     - Ending angle in degrees
        @param [in] col     - Color as array.  Example: [red, green, blue]
    '''
    @staticmethod
    def drawArc(arr, x, y, r, start, end, col):
        h, w, c = arr.shape
        pi2 = math.pi * 2
        arc = end - start
        pts = int((r * math.pi) * arc / 360) * 2
        for i in range(0, pts):
            px = x + int(r * math.cos(start + i * pi2 / pts))
            py = y + int(r * math.sin(start + i * pi2 / pts))
            arr[py][px] = col


    ''' Fills a circle into a numpy buffer
        @param [in] arr     - The numpy buffer to draw into
        @param [in] x       - The horizontal offset to the center of the circle
        @param [in] y       - The vertical offset to the center of the circle
        @param [in] r       - The circle radius
        @param [in] col     - Color as array.  Example: [red, green, blue]
        @param [in] ls      - Left side scalar
        @param [in] rs      - Right side scalar
    '''
    @staticmethod
    def fillCircle(arr, x, y, r, col, ls=1, rs=1):
        h, w, c = arr.shape
        pih = math.pi / 2
        pi2 = math.pi * 2
        pts = int(r * math.pi)
        pts2 = pts * 2
        ly = None
        for i in range(0, pts):
            px = x + int(r * math.cos(pih + i * pi2 / pts2))
            py = y + int(r * math.sin(pih + i * pi2 / pts2))
            if ly == None or ly != py:
                ly = py
                # arr[py][int(px*ls):int(x+(rs*(x - px)))] = col
                arr[py][int(px-((ls-1)*(x - px))):int(x+(rs*(x - px)))] = col


