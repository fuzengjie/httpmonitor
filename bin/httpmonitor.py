#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2
# owner:fuzj
# Pw @ 2016-11-22 11:49:13

import sys
import os

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_PATH)
from core.index import binrouter

if __name__ == '__main__':
    binrouter(sys.argv)
