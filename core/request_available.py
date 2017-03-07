#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python3.5
# owner:fuzj
# Pw @ 2016-11-21 18:15:40

from base import Base
from alarm import Alarm
import inspect


class Request_available(Base):
    
    def __init__(self,interval,push=False,domain=False):
        super(Request_available,self).__init__()
        self.interval = interval
        self.sql = self.buildsql(self.interval)
        self.push = push
        self.monitor = self.getconfig('alarm','request_available')
        self.domain = domain
        self.metric = 'http.request.available'
        self.unit = '%'
        self.log = self.logger()
        self.alarm = Alarm(self.log)
        self.new_alarm,self.no_recovery_alarm = self.loadfile()
    def postdata(self,domain,value):
        for k,v in value.items():
            if k == 'avg':
                continue
            data = self.formatdata(http_host=domain,
                    metric=self.metric,
                    count=v['percent_available'],
                    other="server_addr=%s,action=%s" %(k,'available'))
            self.postdatalist.append(data)
            data = self.formatdata(http_host=domain,
                    metric=self.metric,
                    count=v['percent_4xx'],
                    other="server_addr=%s,action=%s" %(k,'4xx'))
            self.postdatalist.append(data)
            data = self.formatdata(http_host=domain,
                    metric=self.metric,
                    count=v['percent_5xx'],
                    other="server_addr=%s,action=%s" %(k,'5xx'))
            self.postdatalist.append(data)
        return {domain:value}

    def buildsql(self,interval):
        basic_sql = self.resolve_sql(interval)
        custem_sql = {
        "server_addr":{
            "terms":{
                "field": "server_addr",
                "size":0
                },
            "aggs":{
                "http_status": {
                    "terms": {
                        "field": "status",
                        "size": 0
                    }
                }
            }
        }
      }
        basic_sql['aggs']['http_host']['aggs'] = custem_sql
        return basic_sql


    def get_status_percent(self,data):
        result = {}
        avg_available = 0
        avg_4xx = 0
        avg_5xx = 0
        for iterm in data:
            try:
                count_normal = reduce(lambda x,y:x+y,map(lambda x:x['doc_count'],filter(lambda x:x['key'] < 400,iterm['http_status']['buckets'])))
                percent_available = self.get_percent(count_normal,iterm['doc_count'])
                self.log.debug('%s Calculation percent_available  is %s' %(iterm['key'],percent_available))
            except Exception as e:
                percent_available = 0
                self.log.info('%s Calculation percent_available faild,now percent_normal=0,detail message:%s' %(iterm['key'],e))
            try:
                count_4xx = reduce(lambda x,y:x+y,map(lambda x:x['doc_count'],filter(lambda x:x['key'] >= 400 and x['key'] < 500,iterm['http_status']['buckets'])))
                percent_4xx = self.get_percent(count_4xx,iterm['doc_count'])
                self.log.debug('%s Calculation percent_4xx percent is %s' %(iterm['key'],percent_4xx))
            except Exception as e:
                percent_4xx = 0
                self.log.debug('%s Calculation percent_4xx percent percent faild,now percent_4xx=0,detail message:%s' %(iterm['key'],e))

            try:
                count_5xx = reduce(lambda x,y:x+y,map(lambda x:x['doc_count'],filter(lambda x:x['key'] >= 500,iterm['http_status']['buckets'])))
                percent_5xx = self.get_percent(count_5xx,iterm['doc_count'])
                self.log.debug('%s Calculation percent_5xx percent is %s' %(iterm['key'],percent_5xx))
            except Exception as e:
                percent_5xx = 0
                self.log.debug('%s Calculation percent_5xx percent percent faild,now percent_5xx=0,detail message:%s' %(iterm['key'],e))
            avg_available += percent_available
            avg_4xx += percent_4xx
            avg_5xx += percent_5xx
            result[iterm['key']] = {
                'percent_available':percent_available,
                'percent_4xx':percent_4xx,
                'percent_5xx':percent_5xx,
                'total':iterm['doc_count'],
                }
        avg_available  = round(float(avg_available) / len(data),3)
        avg_4xx = round(float(avg_4xx) / len(data),3)
        avg_5xx = round(float(avg_5xx) / len(data),3)
        result['avg'] = {'percent_available':avg_available,'percent_5xx':avg_5xx,'percent_4xx':avg_4xx}
        return result

    def getdata(self):
        '''
        从es中获取原始数据
        '''
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
                    percent = self.get_status_percent(iterm['server_addr']['buckets'])
                    result.update(self.postdata(iterm['key'],percent))
                    result[iterm['key']]['avg']['total'] = iterm['doc_count']
                continue
            if not self.domain_filter(iterm['key']):
                self.log.debug('%s in exclude list,so ignore' % iterm['key'])
                continue
            if not self.base_level_filter(iterm['doc_count']):
                self.log.debug('%s request total count %s less then base_level,so ignore' % (iterm['key'],iterm['doc_count']))
                continue
            percent = self.get_status_percent(iterm['server_addr']['buckets'])
            result.update(self.postdata(iterm['key'],percent))
            result[iterm['key']]['avg']['total'] = iterm['doc_count']
        self.log.debug('success get monitor data')
        return result
    def thjudge(self,data):
        alarm_data = {}
        for domain,value in data.items():
            if not self.only_monitor_filter(domain):
                self.log.debug('%s not in only_monitor_domain ,so ignore' % domain)
                continue
            value = value['avg']
            percent = value['percent_available']
            threshold = self.getthreshold(domain,'request_available_threshold')
            if not threshold:
                self.log.error("Error:: domain:%s ,message:not find the request_available_threshold  action from config.ini" % domain)
                continue
            base_msg = {'metric':self.metric,'threshold':threshold,'unit':self.unit,'interval':self.interval}
            if percent > float(str(threshold)):
                msgnotes = "total:%s;4xx:%s%%;5xx:%s%%" %(value['total'],value['percent_4xx'],value['percent_5xx'])
                emailnotes = "总量:%s;4xx占比:%s%%;5xx占比:%s%%" %(value['total'],value['percent_4xx'],value['percent_5xx'])
                base_msg['msgnotes'] = msgnotes
                base_msg['emailnotes'] = emailnotes
                base_msg['value'] = str(percent) + self.unit
                self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)
                continue
            else:
                if self.exclude_acl(domain,'request_available_exclude'):
                    self.log.warning('%s:%sis outstrip threshold %s,but in exlude list,so ignore ' %(domain,percent,threshold))
                    continue
                alarm_data[domain] = value
        return alarm_data

    def alarmjudge(self,data):
        domain_list = set(self.new_alarm)
        for domain in domain_list:
            max_appear = self.getthreshold(domain,'request_available_max_appear')
            threshold = self.getthreshold(domain,'request_available_threshold')
            if not max_appear:
                self.log.error("Error:: domain:%s ,message:not find the request_available_max_appear  action from config.ini" % domain)
                continue
            try:
                value = data[domain]['avg']
                base_msg = {'metric':self.metric,'threshold':threshold,'unit':self.unit,'interval':self.interval}
                msgnotes = "total:%s;4xx:%s%%;5xx:%s%%" %(value['total'],value['percent_4xx'],value['percent_5xx'])
                emailnotes = "总量:%s;4xx占比:%s%%;5xx占比:%s%%" %(value['total'],value['percent_4xx'],value['percent_5xx'])
                base_msg['msgnotes'] = msgnotes
                base_msg['emailnotes'] = emailnotes
                base_msg['value'] = str(value['percent_available']) + self.unit
                self.new_alarm,self.no_recovery_alarm = self.alarm.judg_alarm(domain,max_appear,base_msg,self.new_alarm,self.no_recovery_alarm)
            except Exception as e:
                self.log.warning('the domain %s not find in current  monitordata,expect next monitordata' % domain)
                continue
    def run(self):
        result = self.getdata()
        source_func = inspect.stack()[1][3]
        if source_func == 'binrouter':
            return result
        if self.push:
            ret,message = self.odinpost(self.postdatalist)
            if ret:
                self.log.info('post data to odin successfull')
            else:
                self.log.info('post data to odin faild,message:%s' %message)
        if self.monitor:
            alarm_data = self.thjudge(result)
            self.new_alarm.extend(alarm_data.keys())
            self.alarmjudge(result)
        self.reload_config()
        return result

if __name__ == '__main__':
    import time
    obj = Request_available('10s')
    while True:
        obj.run()
        print obj.new_alarm
        print obj.no_recovery_alarm
        time.sleep(10)
