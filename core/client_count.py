#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python3.5
# owner:fuzj
# Pw @ 2016-12-27 15:09:34

from base import Base
import inspect

class Client_count(Base):
    def __init__(self,interval,push=False,domain=False):
        super(Client_count,self).__init__()
        self.interval = interval
        self.sql = self.buildsql(interval)
        self.push = push
        self.domain = domain
        self.metric = 'http.request.client.count'
        self.log = self.logger()
        self.unit = ''
        self.new_alarm = {}
        self.no_recovery_alarm = {}

    def buildsql(self,interval):
        base_sql = self.resolve_sql(interval)
        custem_sql = {
            "remote_addr": {
              "terms": {
                "field": "remote_addr",
                "size": 20
              }
            }
        }
        base_sql['aggs']['http_host']['aggs'] = custem_sql
        return base_sql
    def builddomaindata(self,data):
        result = {}
        for i in data:
            result[i['key']] = i['doc_count']
        return result
    def getdata(self):
        monitordata = self.getmonitordata(self.sql)
        if not monitordata:
            self.log.error(" faild to get monitordata from esserver")
            return None
        else:
            try:
                monitordata = monitordata['aggregations']['http_host']['buckets']
                self.log.debug('the monitordata is ok')
            except Exception as e:
                self.log.error("the monitordata is not invaild!!! message:%s" % e)
                return False
        result = {}
        for iterm in monitordata:
            if self.domain:
                if iterm['key'] in self.domain:
                   result[iterm['key']] = self.builddomaindata(iterm['remote_addr']['buckets'])
                continue
            if not self.domain_filter(iterm['key']):
                self.log.debug('%s in exclude list,so ignore' % iterm['key'])
                continue
            if not self.base_level_filter(iterm['doc_count']):
                self.log.debug('%s request total count %s less then base_level,so ignore' % (iterm['key'],iterm['doc_count']))
                continue
            result[iterm['key']] = self.builddomaindata(iterm['remote_addr']['buckets'])
        return result
    def thjudge(self,data):
        alarm_data = {}
        for domain,value in data.items():
            temp = {}
            if not self.only_monitor_filter(domain):
                self.log.debug('%s not in only_monitor_domain ,so ignore' % domain)
                continue
            threshold = self.getthreshold(domain,'client_request_count_threshold')
            if not threshold:
                self.log.error("Error:: domain:%s ,message:not find the client_request_count_threshold  action from config.ini" % domain)
                continue
            base_msg = {'metric':self.metric,'threshold':threshold,'unit':self.unit,'interval':self.interval}
            for k,v in value.items():
                if float(v) < float(str(threshold)):
                    if domain in self.new_alarm.keys():
                        if k in self.new_alarm[domain].keys():
                            pass

                        
                    msgnotes = ""
                    emailnotes = ""
                    base_msg['msgnotes'] = msgnotes
                    base_msg['emailnotes'] = emailnotes
                    base_msg['value'] = str(k) + '/' + str(v) + self.unit
                    self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)
                    continue
                else:
                    if self.exclude_acl(domain,'client_request_count_exclude'):
                        self.log.warning('%s:%sis outstrip threshold %s,but in exlude list,so ignore ' %(domain,percent,threshold))
                        continue
                    temp[k] = v
            if temp:
                alarm_data[domain] = temp
        return alarm_data
               
    def alarmjudge(self,data):
        domain_list = set(self.new_alarm)
        for domain in domain_list:
            max_appear = self.getthreshold(domain,'client_request_count_max_appear')
            threshold = self.getthreshold(domain,'client_request_count_threshold')
            if not max_appear:
                self.log.error("Error:: domain:%s ,message:not find the ient_request_count_max_appear action from config.ini" % domain)
                continue
            try:
                
    def run(self):
        result = self.getdata()
        return result
