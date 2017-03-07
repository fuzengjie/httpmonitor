#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2
# owner:fuzj
# Pw @ 2016-11-21 18:15:40

from base import Base
from alarm import Alarm
import inspect
import datetime
import threading
class Request_total(Base):
    
    def __init__(self,interval,push=False,domain=False):
        super(Request_total,self).__init__()
        self.interval = interval or '1m'
        self.sql = self.buildsql(self.interval)
        self.push = push
        self.monitor = self.getconfig('alarm','request_total')
        self.domain = domain
        self.metric = 'http.request.total'
        self.unit = '%'
        self.lastdata = {}
        self.yesterdaydata = {}
        self.current_data = None
        self.log = self.logger()
        self.alarm = Alarm(self.log)
        self.new_alarm,self.no_recovery_alarm = self.loadfile()
        self.level = 50
    
    def postdata(self,domain,value):
        data = self.formatdata(http_host=domain,metric=self.metric,count=value)
        self.postdatalist.append(data)
        return {domain:value}

    def buildsql(self,interval):
        basic_sql = self.resolve_sql(interval)
        return basic_sql

    def getcurrentdata(self):
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
        self.current_data = monitordata
        #return monitordata
    def getlastdata(self):
        interval = self.resolve_interval(self.interval)
        start_time = (datetime.datetime.utcnow() - datetime.timedelta(seconds=int(interval)*2)).strftime('%Y-%m-%dT%H:%M:%S')
        end_time = (datetime.datetime.utcnow() - datetime.timedelta(seconds=int(interval))).strftime('%Y-%m-%dT%H:%M:%S')
        new_sql = self.resolve_sql(start_time=start_time,end_time=end_time)
        monitordata = self.getmonitordata(new_sql)
        if not monitordata:
            self.log.error(" faild to get last  monitordata from esserver")
            return None
        else:
            try:
                monitordata = monitordata['aggregations']['http_host']['buckets']
                self.log.debug('the yesterdaymonitordata is ok')
            except Exception as e:
                self.log.error("the yesterdaymonitordata is not invaild!!! message:%s" % e)
                return False
        for iterm in monitordata:
            if not self.domain_filter(iterm['key']):
                    self.log.debug('lastdata: %s in exclude list,so ignore' % iterm['key'])
                    continue
            self.lastdata[iterm['key']] = iterm['doc_count']
    def getyesterdaydata(self):
        interval = self.resolve_interval(self.interval)
        lasttime = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        lastsearchIndex = 'heka-nginx-access-' + lasttime.strftime("%Y.%m.%d")
        start_time = (datetime.datetime.utcnow() - datetime.timedelta(seconds=int(interval),days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        end_time = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        new_sql = self.resolve_sql(start_time=start_time,end_time=end_time)
        monitordata = self.getmonitordata(new_sql,lastsearchIndex)
        if not monitordata:
            self.log.error(" faild to get last  monitordata from esserver")
            return None
        else:
            try:
                monitordata = monitordata['aggregations']['http_host']['buckets']
                self.log.debug('the yesterdaymonitordata is ok')
            except Exception as e:
                self.log.error("the yesterdaymonitordata is not invaild!!! message:%s" % e)
                return False
        
        result = {}
        for iterm in monitordata:
            if not self.domain_filter(iterm['key']):
                self.log.debug('yesterdaydata: %s in exclude list,so ignore' % iterm['key'])
                continue
            result[iterm['key']] = iterm['doc_count']
        self.yesterdaydata = result
        self.log.debug('get yesterdaydata  successfull')
        #return result
    def builddata(self):
        result = {}      
        #有上次数据,则开始进行逻辑判断和数据生成
        for iterm in self.current_data:
            if not self.domain_filter(iterm['key']):
                self.log.debug('currentdata:%s in exclude list,so ignore' % iterm['key'])
                continue
            #if not self.base_level_filter(iterm['doc_count']):
            #    self.log.debug('%s request total count %s less then base_level,so ignore' % (iterm['key'],iterm['doc_count']))
            #    continue
            if not iterm['key'] in self.lastdata:
                self.lastdata[iterm['key']] = None
                self.log.debug('the domain %s is not in lastdata,so can not calculate the mom_rate' % iterm['key'])
                continue
            if not iterm['key'] in self.yesterdaydata:
                self.yesterdaydata[iterm['key']] = None
                self.log.debug('the domain %s is not in yesterdaydata,so can not calculate the yoy_rate' % iterm['key'])
            #计算环比
            try:
                if not self.lastdata[iterm['key']]:
                    raise ValueError("domain:%s not find in lastdata" % iterm['key'])
                mom_rate = round((float(iterm['doc_count']) - float(self.lastdata[iterm['key']])) / float(self.lastdata[iterm['key']]) * 100,2)
                self.log.debug('get last mom_rate successfull, domain:%s ,mom_rate:%s' %(iterm['key'],mom_rate))
            except Exception as e:
                mom_rate = None
                self.log.warning('get last mom_rate faild, domain:%s,error message:%s' % (iterm['key'],e))
            finally:
                result[iterm['key']] = {
                    'last':self.lastdata[iterm['key']],
                    'current':iterm['doc_count'],
                    'mom_rate':mom_rate
                }
            #计算同比
            try:
                if not self.yesterdaydata[iterm['key']]:
                    raise ValueError("domain:%s not find in yesterdaydata" % iterm['key'])
                yoy_rate = round((float(iterm['doc_count']) - float(self.yesterdaydata[iterm['key']])) / float(self.yesterdaydata[iterm['key']]) * 100,2)
                self.log.debug('get last yoy_rate successfull, domain:%s ,yoy_rate:%s' %(iterm['key'],yoy_rate))
            except Exception as e:
                yoy_rate = None
                self.log.warning('get last yoy_rate faild, domain:%s,error message:%s' % (iterm['key'],e))
            finally:
                result[iterm['key']].update({
                    'yesterday':self.yesterdaydata[iterm['key']],
                    'yoy_rate':yoy_rate
                    })
            self.postdata(iterm['key'],iterm['doc_count'])
        return result
    def thjudge(self,data):
        alarm_data = {}
        for domain,value in data.items():
            if self.exclude_acl(domain,'request_total_exclude'):
                self.log.warning('%s is in exlude list,so ignore ' %(domain))
                continue
            if not self.only_monitor_filter(domain):
                self.log.debug('%s not in only_monitor_domain ,so ignore' % domain)
                continue
            #baseline = self.getthreshold(domain,'request_total_error_threshold')
            down_threshold = self.getthreshold(domain,'request_total_down_threshold')
            up_threshold = self.getthreshold(domain,'request_total_up_threshold')
            mom_rate = value['mom_rate']
            yoy_rate = value['yoy_rate']
            continue
            if not up_threshold or not down_threshold:
                self.log.error("Error:: domain:%s ,message:not find the request_total_threshold  action from config.ini" % domain)
                continue
            if yoy_rate and mom_rate:           #环比和同比都存在
                if value['current'] < self.level and value['yesterday'] <= self.level and value['last'] <= self.level:
                    continue
                if float(yoy_rate) < 0 and float(mom_rate) < 0:     #流量下降
                    if abs(yoy_rate) > float(down_threshold)  and abs(mom_rate) > float(down_threshold):
                        alarm_data[domain] = value
                    else:
                        base_msg = {'metric':self.metric,'threshold':down_threshold,'unit':self.unit,'interval':self.interval,'value':value['current']}
                        msgnotes = "yesterday:%s(%s%s);last %s:%s(%s%s)" %(value['yesterday'],value['yoy_rate'],self.unit,self.interval,value['last'],value['mom_rate'],self.unit)
                        emailnotes = msgnotes
                        base_msg['msgnotes'] = msgnotes
                        base_msg['emailnotes'] = emailnotes
                        self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)
                elif float(yoy_rate) >= 0 and float(mom_rate) >= 0:   #流量上升
                    if abs(yoy_rate) > float(up_threshold)  and abs(mom_rate) > float(up_threshold):
                        alarm_data[domain] = value
                    else:
                        base_msg = {'metric':self.metric,'threshold':up_threshold,'unit':self.unit,'interval':self.interval,'value':value['current']}
                        msgnotes = "yesterday:%s(%s%s);last %s:%s(%s%s)" %(value['yesterday'],value['yoy_rate'],self.unit,self.interval,value['last'],value['mom_rate'],self.unit)
                        emailnotes = msgnotes
                        base_msg['msgnotes'] = msgnotes
                        base_msg['emailnotes'] = emailnotes
                        self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)


                        #if yoy_rate <=  float(baseline) and  mom_rate <= float(baseline):    #此处用于直接判断流量突降，同比和环比为负数，小于基本线时，直接告警
                        #    base_msg['threshold'] = baseline
                        #    self.no_recovery_alarm.append(domain)
                        #    self.alarm.doalarm(domain,base_msg,self.no_recovery_alarm.count(domain))
                        #    self.log.error('%s:%sis  baseline %s,so straight to alarm ' %(domain,value,baseline))
                        #    continue
                continue
            '''
            elif mom_rate and not yoy_rate:        #只有环比，没有同比
                if abs(mom_rate) < float(threshold):
                    self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)
                    continue
                else:
                    if baseline:
                        if abs(mom_rate) >= float(baseline):
                            base_msg['threshold'] = baseline
                            self.no_recovery_alarm.append(domain)
                            self.alarm.doalarm(domain,base_msg,self.no_recovery_alarm.count(domain))
                            self.log.error('%s:%sis  baseline %s,so straight to alarm ' %(domain,value,baseline))
                continue
            elif yoy_rate and not mom_rate:     #只有同比，没有环比
                if abs(yoy_rate) < float(threshold):
                    self.new_alarm,self.no_recovery_alarm = self.alarm.judg_recovery(domain,base_msg,self.new_alarm,self.no_recovery_alarm)
                    continue
                else:
                    if baseline:
                        if abs(yoy_rate) >= float(baseline):
                            base_msg['threshold'] = baseline
                            self.no_recovery_alarm.append(domain)
                            self.alarm.doalarm(domain,base_msg,self.no_recovery_alarm.count(domain))
                            self.log.error('%s:%sis  baseline %s,so straight to alarm ' %(domain,value,baseline))
                continue
            else:
                self.log.error('the domain[%s]yoy_rate and mom_rate is not exist' %domain)
            '''
        return alarm_data
    def alarmjudge(self,data):
        domain_list = set(self.new_alarm)
        for domain in domain_list:
            max_appear= self.getthreshold(domain,'request_total_max_appear')
            try:
                value = data[domain]
                if value['yoy_rate'] > 0:
                    threshold = self.getthreshold(domain,'request_total_up_threshold')
                else:
                    threshold = self.getthreshold(domain,'request_total_down_threshold')
                if not max_appear:
                    self.log.error("Error:: domain:%s ,message:not find the request_total_max_appear  action from config.ini" % domain)
                    continue
                    base_msg = {'metric':self.metric,'threshold':threshold,'unit':self.unit,'interval':self.interval,'value':value['current']}
                    msgnotes = "yesterday:%s(%s%s);last %s:%s(%s%s)" %(value['yesterday'],value['yoy_rate'],self.unit,self.interval,value['last'],value['mom_rate'],self.unit)
                    emailnotes = msgnotes
                    base_msg['msgnotes'] = msgnotes
                    base_msg['emailnotes'] = emailnotes
                    self.new_alarm,self.no_recovery_alarm = self.alarm.judg_alarm(domain,max_appear,base_msg,self.new_alarm,self.no_recovery_alarm)
            except Exception as e:
                self.log.warning('the domain %s not find in current  monitordata,expect next monitordata' % domain)
                continue
    def run(self):
        t1 = threading.Thread(target=self.getlastdata)
        t2 = threading.Thread(target=self.getyesterdaydata)
        t3 = threading.Thread(target=self.getcurrentdata)
        t1.start()
        t2.start()
        t3.start()
        t1.join()
        t2.join()
        t3.join()
        result = self.builddata()
        source_func = inspect.stack()[1][3]
        if source_func == 'binrouter':
            ret = {}
            if self.domain:
                for i in self.domain:
                    try:
                        ret[i] = result[i]
                    except Exception as e:
                        print e
                        ret[i] = None
            return ret
        if self.push:
            ret,message = self.odinpost(self.postdatalist)
            if ret:
                self.log.info('post data to odin successfull')
            else:
                self.log.info('post data to odin faild,message:%s' %message)
        if self.monitor and result:
            alarm_data = self.thjudge(result)
            self.new_alarm.extend(alarm_data.keys())
            self.alarmjudge(result)

        self.reload_config()
        return result

if __name__ == '__main__':
    import time
    obj = Request_total('2m')
    while True:
        obj.run()
        print obj.new_alarm
        print obj.no_recovery_alarm
        time.sleep(120)

