#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2.7
# owner:fuzj
# Pw @ 2016-11-21 18:24:25

import os
import sys
import ConfigParser
import json
import datetime
import time
import urllib
import urllib2
import re
import logging
from collections import Iterable
from elasticsearch import Elasticsearch
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

es_sql = {
  "size": 0,
  "timeout": 30,
  "query": {
    "bool": {
      "must": {
        "range": {
          "@timestamp": {
            "gte": "%s",
            "lte": "%s"
          }
        }
      }
    }
  },
  "aggs": {
    "http_host": {
      "terms": {
        "field": "http_host",
        "size": 0
      }
    }
  }
}

class Base(object):
    def __init__(self):
        self.configration = self.parserconfig()
        self.es = self.esserver()
        self.new_alarm = []
        self.no_recovery_alarm = []
        self.postdatalist = []
        self.timestamp = int(time.time())
    def esserver(self):
        try:
            es_host = self.getconfig('ElasticSearch')['es_host']
            es_url = 'http://' + es_host
            es = Elasticsearch([es_url],timeout=10)
            return es
        except Exception as e:
            exit('Error: connect esserver faild!!! message:%s' %(e))
    def getconfig(self,option,subitem=None):
        if self.configration:          
            if option in self.configration:     #判断是获取的action 是否在配置中
                if not subitem:             #判断是否需要获取action下的子项目值
                    result = self.configration[option]
                    return result
                else:
                    if subitem in self.configration[option]:
                        return self.configration[option][subitem]
                    else:
                        return None
            else:
                return None
        else:
            return None

    def parserconfig(self):
        config_path = os.path.join(BASE_DIR,'conf/config.ini')
        if os.path.exists(config_path):
            if os.path.isfile(config_path):
                configration = {}
                config = ConfigParser.ConfigParser()
                config.read(config_path)
                sections = config.sections()
                for i in sections:
                    options = config.items(i)
                    configration[i] = dict(options)
                for i in configration:
                    for k,v in configration[i].items():
                        if v == 'True':
                            configration[i][k] = True
                        elif v == 'False':
                            configration[i][k] = False
                        elif v == 'None' or v == '':
                            configration[i][k] = None
                        elif k.endswith('exclude'):
                            if v.strip():
                                configration[i][k] = v.strip().rstrip(',').split(',')
                            else:
                                configration[i][k] = []
                return configration
            else:
                exit('%s is a directory, that must be file' % config_path)
        else:
            exit('%s is not exists' % config_path)
    def reload_config(self):
        self.sql = self.buildsql(self.interval)
        self.configration = self.parserconfig()
        self.timestamp = int(time.time())
        self.postdatalist = []
        history_alarm = {'no_recovery_alarm':self.no_recovery_alarm,'new_alarm':self.new_alarm}
        self.dumpfile(history_alarm)

    def getmonitordata(self,sql,searchIndex=None):
        '''
        从es中获取指定时间间隔的数据
        '''
        if not searchIndex:
            searchIndex = 'heka-nginx-access-' + time.strftime("%Y.%m.%d",time.gmtime())
        try:
            result = self.es.search(index=searchIndex,body=sql)
            return result
        except Exception as e:
            print e
            return None

    def formatdata(self,http_host, metric, count,other=None):
	'''
	格式化向odin push的数据
	'''
	if other:
	    notes = "," + other 
	else:
	    notes = ''
	myData = {
	      "timestamp": self.timestamp,
	      "metric": metric,
	      "value": count,
	      "tags": "domain=" + http_host + notes + ",host=puppet.node.kddi.op.xywy.com,ip=10.20.7.9"
	      }
	return myData
    def odinpost(self,data):
        try:
            url = self.getconfig('collect')['post_url']
            arg = urllib2.Request(url,json.dumps(data))
            result = urllib2.urlopen(arg)
            return True,result
        except Exception as e:
            return False,e
    def resolve_sql(self,interval=None,start_time=None,end_time=None):
        if interval and start_time and end_time:
            exit('resolve_sql faild,the interval is not upports both  with start_time[end_time]')
        elif interval:
            unit = interval[-1]
            interval = self.resolve_interval(interval)
            #start_time = 'now-' + interval + "/" + unit
            #end_time = 'now/' + unit
            start_time = (datetime.datetime.utcnow() - datetime.timedelta(seconds=int(interval))).strftime('%Y-%m-%dT%H:%M:%S')
            end_time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            result = json.dumps(es_sql) % (start_time,end_time)
        elif start_time and end_time:
            #start_time = 'now-' + start_time 
            #end_time = 'now-' + end_time
            result = json.dumps(es_sql) % (start_time,end_time)
        else:
            exit('resolve_sql faild,you must choice interval or start_time[end_time]')
        return json.loads(result)
    
    def domain_filter(self,domain):
        legal_domain = self.getconfig('acl')['legal_domain_list'].strip().rstrip(',').split(',')
        exclude_domain = self.getconfig('acl')['exclude_domain_list'].strip().rstrip(',').split(',')
        match_domain = None
        for i in legal_domain:
            if re.search(i,domain):
                for e in exclude_domain:
                    if not re.search(e,domain):
                        match_domain = domain
                        break
        return match_domain
    def base_level_filter(self,value):
        request_base_level = self.getthreshold('acl','request_base_level').strip()
        if int(request_base_level) > int(value):
            return False
        else:
            return True

    def getthreshold(self,section,action):
        try:
            threshold = self.getconfig(section,action)
            if not threshold:
                threshold = self.getconfig('acl',action)
            else:
                if action.endswith('exclude'):
                    global_acl = self.getconfig('acl',action)
                    threshold.extend(global_acl)
                    threshold = list(set(threshold))
            return threshold
        except Exception as e:
            print e
            return None
    def getlogconf(self,action):
        try:
            logconf = self.getconfig('log',action.lower())
            if not logconf:
                logconf = self.getconfig('log',action.lower().split('_')[-1])
            return logconf
        except Exception as e:
            print e
            return None
                
    def exclude_acl(self,domain,action):
        flag = False
        rule = self.getthreshold(domain,action)
        if not rule:
            return flag
        for i in rule:
            if re.search(i,domain):
                flag =True
                break
            else:
                continue
        return flag
    def logger(self,logact=None):
        logact = logact or self.__class__.__name__
        logpath = self.getlogconf(logact + "_path")
        try:
            if logpath.startswith('/'):
                if not os.path.exists(os.path.dirname(logpath)) or not os.path.isdir(os.path.dirname(logpath)):
                    print 'log file path is must be exists and directory'
            else:
                logpath = os.path.join(BASE_DIR,logpath)
        except Exception as e:
            print e
            logpath = os.path.join(BASE_DIR,'log/httpmonitor.log')

        loglevel = self.getlogconf(logact+ "_level")
        logger = logging.getLogger(logact)
        try:
            loglevel = getattr(logging,loglevel.upper())
            logger.setLevel(loglevel)
        except Exception as e:
            print e
            logger.setLevel(logging.INFO)
        logfile = logging.FileHandler(logpath)
        term = logging.StreamHandler()
        formatter1 = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        formatter2 = logging.Formatter('%(name)s-%(levelname)s-%(message)s')
        logfile.setFormatter(formatter1)
        term.setFormatter(formatter2)
        logger.addHandler(logfile)
        logger.addHandler(term)

        return logger
    def get_percent(self,value,total):
        result = round((float(value) / float(total) * 100 ),3)
        return result
    def resolve_interval(self,interval):
	if interval.lower()[-1] == 'm':
            result = int(interval[:-1]) * 60
        elif interval.lower()[-1] == 's':
            result = int(interval[:-1])
        elif interval.lower()[-1] == 'h':
            result = int(interval[:-1]) * 3600
        else:
            exit('config is invaild, neer :%s' % interval)
        return result
    def only_monitor_filter(self,domain):
        domain_list = self.getconfig('acl','only_monitor_domain_list')
        if not domain_list: 
            return True
        if domain in domain_list:
            return True
        else:
            return False

    def dumpfile(self,data):
        try:
            filename = '.' + self.__class__.__name__
            logfile = os.path.join(BASE_DIR,'log',filename)           #以当前调用的class名为log名字
            if not os.path.exists(logfile):
                os.mknod(logfile)
            with open(logfile,'w') as history_alarm:
                json.dump(data,history_alarm)
                return True
        except Exception as e:
            return False
    def loadfile(self):
        try:
            filename = '.' + self.__class__.__name__
            logfile = os.path.join(BASE_DIR,'log',filename)           #以当前调用的class名为log名字
            if not os.path.exists(logfile):
                return list(),list()
            with open(logfile,'r') as history_alarm:
                result = json.load(history_alarm)
                return result['new_alarm'],result['no_recovery_alarm']
        except Exception as e:
            return False,False
    def historyalarm(self):
        try:
            new_alarm,no_recovery_alarm = self.loadfile()
            history_alarm = {'new_alarm':new_alarm,'no_recovery_alarm':no_recovery_alarm}
        except Exception:
            history_alarm = None
        return history_alarm
