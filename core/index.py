#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2
# owner:fuzj
# Pw @ 2016-11-22 10:43:22

import argparse
import json
import os
import time
import importlib
from multiprocessing import Process
from core import daemonize
from core import base

baseobj = base.Base()
log = baseobj.logger('index')
monitor_type = ['request_time','request_total','request_available','request_qps','client_count']
def getbinargs(arg):
    parser = argparse.ArgumentParser()
    parser.add_argument('-t','--type',required=True,choices=monitor_type,help="choices a monitor type,only must be %s" % ','.join(monitor_type))
    parser.add_argument('-i','--interval',default='1m',help="choices monitor interval ,default 1min")
    parser.add_argument('-d','--domain',nargs='*',help='choice domain to display')
    parser.add_argument('-p','--push',action='store_true',help='push data to odin')
    args = parser.parse_args()
    return vars(args)

def binrouter(arg):
    if len(arg) < 3:
        options = getbinargs(arg[1:])
    else:
        arg = getbinargs(arg)
        handle = arg['type']
        model = importlib.import_module('core.' + handle)
        model_class = getattr(model,handle.capitalize())
        obj = model_class(arg['interval'],arg['push'],arg['domain'])
        func = getattr(obj,'run')
        result = func()
        print json.dumps(result,indent=2)

def getsbinargs(arg):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--start',action='store_true')
    group.add_argument('--stop',action='store_true')
    group.add_argument('--restart',action='store_true')
    args = parser.parse_args()
    return vars(args)

def loop_run(interval,handle):
    try:
        model = importlib.import_module('core.' + handle)
    except Exception as e:
        log.error(e)
    if hasattr(model,handle.capitalize()):
        model_class = getattr(model,handle.capitalize())
    else:
        log.error('module %s is not have class %s' %(model,handle.capitalize()))
        exit()
    obj = model_class(interval=interval,push=True)
    func = getattr(obj,'run')
    sleep_time = baseobj.resolve_interval(interval)
    while True:
        try:
            result = func()
            print json.dumps(result,indent=2)
        except Exception as e:
            print e
            log.error(e)
        finally:
            time.sleep(sleep_time)
def start_process(collectconf):
    monitor_list = filter(lambda x:collectconf[x] == True,collectconf)
    for i in monitor_list:
        try:
            interval = collectconf[i + '_interval']
        except Exception:
            interval = '1m'
        p = Process(target=loop_run,args=(interval,i))
        p.start()


def sbinrouter(arg):
    if len(arg) < 2:
        options = getsbinargs(arg[0:])
    else:
        arg = getsbinargs(arg)
        action = filter(lambda x:arg[x],arg)[0]
        collectconf = baseobj.getconfig('collect')
        try:
            pidfile = collectconf['pidfile']
            if pidfile.startswith('/'):
                if not os.path.exists(os.path.dirname(pidfile)) or not os.path.isdir(os.path.dirname(pidfile)):
                    print 'pidfile path is must be exists and directory'
            else:
                pidfile = os.path.join(base.BASE_DIR,pidfile)
                
        except Exception as e:
            print e
            pidfile = os.path.join(base.BASE_DIR,'log/httpmonitor.pid')
        daemon = daemonize.Daemonize(app='httpmonitor',pid=pidfile,action=start_process,args=(collectconf,),logger=log,foreground=False)
        func = getattr(daemon,action)
        func()
