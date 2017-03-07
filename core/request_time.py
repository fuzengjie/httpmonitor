#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2
# owner:fuzj
# Pw @ 2016-11-21 18:15:40

from base import Base
from alarm import Alarm
import inspect

class Request_time(Base):
    
    def __init__(self,interval,push=False,domain=False):
        super(Request_time,self).__init__()
        self.interval = interval
        self.push = push
        self.domain = domain
        self.monitor = self.getconfig('alarm','request_time')
        self.avg_metric = 'http.avg.request.time'
        self.slow_metric = 'http.slow.request.count'
        self.slow_percent_metric = 'http.slow.request.percent'
        self.unit = '%'
        self.slow_request_level = self.getthreshold('acl','slow_request_level') or '3'
        self.log = self.logger()
        self.sql = self.buildsql(self.interval)
        self.alarm = Alarm(self.log)
        self.new_alarm,self.no_recovery_alarm = self.loadfile()
    def buildsql(self,interval):
        basic_sql = self.resolve_sql(interval)
        custem_sql = {
        "slow_request_count": {
          "range": {
            "field": "request_time",
            "ranges": [{"from": float(self.slow_request_level)}]}
            },
        "avg_request_time":{
         "avg": {
            "field": "request_time"}}
        }
        basic_sql['aggs']['http_host']['aggs'] = custem_sql
        return basic_sql





    
    def postdata(self,domain,value,metric):
        data = self.formatdata(http_host=domain,metric=metric,count=value)
        self.postdatalist.append(data)
        return {metric:value}

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
            except Exception as e:
                self.log.error("the monitordata is not invaild!!! message:%s" % e)
                return False
        result = {}
        for iterm in monitordata:
            count = iterm['slow_request_count']['buckets'][0]['doc_count']
            if self.domain:
                if iterm['key'] in self.domain:
                    result[iterm['key']] = {}
                    result[iterm['key']].update(self.postdata(iterm['key'],round(iterm['avg_request_time']['value'],3),self.avg_metric))
                    result[iterm['key']].update(self.postdata(iterm['key'],count,self.slow_metric))
                    result[iterm['key']].update(self.postdata(iterm['key'],self.get_percent(count,iterm['doc_count']),self.slow_percent_metric))
                    result[iterm['key']].update({'total':iterm['doc_count']})
                continue
            if not self.domain_filter(iterm['key']):
                self.log.debug('%s in exclude list,so ignore' % iterm['key'])
                continue
            if not self.base_level_filter(iterm['doc_count']):
                self.log.debug('%s request total count %s less then base_level,so ignore' % (iterm['key'],iterm['doc_count']))
                continue
            result[iterm['key']] = {}
            result[iterm['key']].update(self.postdata(iterm['key'],round(iterm['avg_request_time']['value'],3),self.avg_metric))      # 收集平均请求时间
            result[iterm['key']].update(self.postdata(iterm['key'],count,self.slow_metric))  #收集超过阈值的请求个数
            #result[iterm['key']].update({'percent':self.get_percent(count,iterm['doc_count'])})
            result[iterm['key']].update(self.postdata(iterm['key'],self.get_percent(count,iterm['doc_count']),self.slow_percent_metric))
            result[iterm['key']].update({'total':iterm['doc_count']})

        self.log.debug('success get monitor data')
        return result
    def thjudge(self,data):
        alarm_data = {}
        for domain,value in data.items():
            if not self.only_monitor_filter(domain):
                self.log.debug('%s not in only_monitor_domain ,so ignore' % domain)
                continue
            percent = float(value[self.slow_percent_metric])
            threshold = self.getthreshold(domain,'slow_request_threshold')     #取请求时间的阀值
            if not threshold:
                self.log.error("Error:: domain:%s ,message:not find the slow_request_threshold  action from config.ini" % domain)
                continue
            base_msg = {'metric':self.slow_metric,'threshold':threshold,'unit':self.unit,'interval':self.interval}
            if percent < float(str(threshold)):
                msgnotes = "total:%s; >%ss:%s" %(value['total'],self.slow_request_level,value[self.slow_metric])
                emailnotes = '总计:%s; >%s秒:%s; 平均时间:%s秒' %(
                    value['total'],
                    self.slow_request_level,
                    value[self.slow_metric],
                    value[self.avg_metric])
                base_msg['msgnotes'] = msgnotes
                base_msg['emailnotes'] = emailnotes
                base_msg['value'] = str(percent) + self.unit
                self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)
                continue
            else:
                if self.exclude_acl(domain,'slow_request_exclude'):
                    self.log.warning('%s:%s is outstrip threshold %s,but in exlude list,so ignore ' %(domain,value,threshold))
                    continue
                alarm_data[domain] = value
        return alarm_data
    def alarmjudge(self,data):
        domain_list = set(self.new_alarm)
        for domain in domain_list:
            max_appear= self.getthreshold(domain,'slow_request_max_appear')        #取允许连续出现的次数阈值
            threshold = self.getthreshold(domain,'slow_request_threshold')
            if not max_appear:
                self.log.error("Error:: domain:%s ,message:not find the slow_request_max_appear  action from config.ini" % domain)
                continue
            try:
                base_msg = {'metric':self.slow_metric,'threshold':threshold,'unit':self.unit,'interval':self.interval}
                msgnotes = "total:%s; >%ss:%s" %(data[domain]['total'],self.slow_request_level,data[domain][self.slow_metric])
                emailnotes = '总计:%s; >%s秒:%s; 平均时间:%s秒' %(
                    data[domain]['total'],
                    self.slow_request_level,
                    data[domain][self.slow_metric],
                    data[domain][self.avg_metric])
                base_msg['msgnotes'] = msgnotes
                base_msg['emailnotes'] = emailnotes
                base_msg['value'] = str(float(data[domain][self.slow_percent_metric])) + self.unit
                self.new_alarm,self.no_recovery_alarm = self.alarm.judg_alarm(domain,max_appear,base_msg,self.new_alarm,self.no_recovery_alarm)
            except Exception as e:
                print e
                self.log.warning('the domain %s not find in current  monitordata,expect next monitordata,error messge:%s' %(domain,e))
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
    obj = Request_time('1m')
    while True:
        obj.run()
        print obj.new_alarm
        print obj.no_recovery_alarm
        time.sleep(10)
