#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2
# owner:fuzj
# Pw @ 2016-11-24 11:25:38
import sys
reload(sys)
sys.setdefaultencoding('utf8')

from base import Base
import urllib
import urllib2
import json
import time


alarm_msg_tpl = """
[%(status)s][%(metric)s]
%(domain)s:%(value)s
%(notes)s
[最多报警%(times)s次][当前第%(current_times)s次:%(date)s]
"""
alarm_email_tpl = """
[%(status)s][%(metric)s]
域名：%(domain)s
阈值：%(threshold)s%(unit)s
当前值：%(value)s
统计周期：%(interval)s
备注：%(notes)s
[最多报警%(times)s次][当前第%(current_times)s次:%(date)s]
"""

class Alarm:
    def __init__(self,logger=None):
        self.base = Base()
        self.alarmconfig = self.base.getconfig('alarm')
        self.alarm_type=self.alarmconfig['alarm_type'].strip().rstrip(',').split(',')
        self.max_alarms = self.alarmconfig['max_alarms'].strip()
        self.contact = self.alarmconfig['contact'].strip().rstrip(',').split(',')
        self.ding_url = self.alarmconfig['ding_url'].strip()
        self.wchat_url = self.alarmconfig['wchat_url'].strip()
        self.email_url = self.alarmconfig['email_url'].strip()
        self.log = logger or self.base.logger()

    def msg(self,*args,**kwargs):
        now = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())
        info = alarm_msg_tpl % {
            'status':kwargs['status'],'metric':kwargs['metric'],
            'domain':kwargs['domain'],'value':kwargs['value'],
            'times':self.max_alarms,'current_times':kwargs['current_times'],
            'date':now,'unit':kwargs['unit'],'notes':kwargs['msgnotes']}
        return info
    def email(self,*args,**kwargs):
        now = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())
        info = alarm_email_tpl % {
            'status':kwargs['status'],'metric':kwargs['metric'],
            'domain':kwargs['domain'],'value':kwargs['value'],
            'threshold':kwargs['threshold'],'interval':kwargs['interval'],
            'times':self.max_alarms,'current_times':kwargs['current_times'],
            'date':now,'unit':kwargs['unit'],'notes':kwargs['emailnotes']}
        subject = "%s::%s %s/%s" %(kwargs['status'],kwargs['domain'],kwargs['metric'],kwargs['value'])
        return subject,info
    def sendmsg(self,data,url,contact,alarm_type):
        for u in contact:
            try:
                data['tos'] = u
                option = urllib.urlencode(data)
                arg = urllib2.Request(url,option)
                result = urllib2.urlopen(arg)
                self.log.info('send %s msg  to %s is success , response is %s' %(alarm_type,u,result.read()))
            except Exception as e:
                print e
                self.log.error('send %s msg  to %s is faild,error message:%s' %(alarm_type,u,e))

    def doalarm(self,domain,base_msg,current_times):
        for i in self.alarm_type:
            if i == 'ding':
                msg = self.msg(status='PROBLEM',domain=domain,current_times=current_times,**base_msg)
                data = {'content':msg}
                url = self.ding_url
                self.sendmsg(data,url,self.contact,i)
                continue
            elif i == 'wchat':
                msg = self.msg(status='PROBLEM',domain=domain,current_times=current_times,**base_msg)
                data = {'content':msg}
                url = self.wchat_url
                self.sendmsg(data,url,self.contact,i)
                continue
            elif i == 'email':
                subject,email_content = self.email(status='PROBLEM',domain=domain,current_times=current_times,**base_msg)
                data = {'content':email_content,'subject':subject}
                url =  self.email_url
                contact = map(lambda x:x+"@xywy.com",self.contact)
                self.sendmsg(data,url,contact,i)
                continue
            else:
                self.log.warning("don`t support this alarm type:%s" %i)

    def recovery_alarm(self,domain,base_msg):
        for i in self.alarm_type:
            if i == 'ding':
                msg = self.msg(status='ok',domain=domain,current_times=1,**base_msg)
                data = {'content':msg}
                url = self.ding_url
                self.sendmsg(data,url,self.contact,i)
                continue
            elif i == 'wchat':
                msg = self.msg(status='ok',domain=domain,current_times=1,**base_msg)
                data = {'content':msg}
                url = self.wchat_url
                self.sendmsg(data,url,self.contact,i)
                continue
            elif i == 'email':
                subject,email_content = self.email(status='ok',domain=domain,current_times=1,**base_msg)
                data = {'content':email_content,'subject':subject}
                url =  self.email_url
                contact = map(lambda x:x+"@xywy.com",self.contact)
                self.sendmsg(data,url,contact,i)
                continue
            else:
                self.log.warning("don`t support this alarm type:%s" %i)


    def judg_recovery(self,domain,base_msg,new_alarm,no_recovery_alarm):
        if domain in new_alarm and not domain in no_recovery_alarm:      #如果在告警列表中，不在未恢复的告警中，说明已有    超出阈值的记录，但是没触发告警,则删除记录，但是不发msg
            new_alarm = filter(lambda x:x!=domain, new_alarm)
            self.log.info('recovery: %s not trigger alarm , has delete from new_alarm list' % domain)
        elif domain in new_alarm and domain in no_recovery_alarm:      #如果在告警列表中同时在告警列表和未恢复的>    告警列表中，说明已触发告警
            no_recovery_alarm = filter(lambda x:x!=domain,no_recovery_alarm)  #从未恢复的告警中删除
            new_alarm = filter(lambda x:x!=domain, new_alarm)     #从告警列表中删除
            self.recovery_alarm(domain,base_msg)           #发送恢复的msg
            self.log.info('recovery: %s has trigger alarm, has delete from no_recovery_alarm and new_alarm list' % domain)
        elif not domain in new_alarm  and domain in no_recovery_alarm:        #如果不在告警列表中，在未恢复的告警    中，说明已经超过告警次数，直接从未恢复的告警中删除，然后发送恢复msg即可
            no_recovery_alarm = filter(lambda x:x!=domain,no_recovery_alarm)  #从未恢复的告警中删除
            self.recovery_alarm(domain,base_msg)           #发送恢复的msg
            self.log.info('recovery: %s has trigger alarm and outstrip max_alarms,has delete from no_recovery_alarm' % domain)
        return new_alarm,no_recovery_alarm
    
    def judg_alarm(self,domain,max_appear,base_msg,new_alarm,no_recovery_alarm):
        if no_recovery_alarm.count(domain) == int(self.max_alarms):  #如果未恢复的告警列表中已经超过最大报警次数，则不在追加，同时将域名从当前的告警列表中删除
            new_alarm = filter(lambda x:x!=domain, new_alarm)
            self.log.error('domain %s outstrip max_alarms,has ignore alarm' %domain)
            return new_alarm,no_recovery_alarm
        if new_alarm.count(domain) <= int(max_appear):       #没触发阈值，忽略
            self.log.warning('domain %s/%s count[%s] is outstrip threshold[%s],but not  outstrip max_appear[%s]' %(domain,base_msg['value'],new_alarm.count(domain),base_msg['threshold'],max_appear))
        
        elif new_alarm.count(domain) >  int(max_appear) and new_alarm.count(domain) <= int(max_appear) + int(self.max_alarms):  #当触发阈值的次数大于允许连续出现的次数，和小于连续出现次数加最大告警次数的时候，进行告警,并且把该域名放到未恢复的告警列表中
            no_recovery_alarm.append(domain)
            self.doalarm(domain=domain,current_times=no_recovery_alarm.count(domain),base_msg=base_msg)
            self.log.warning('domain %s has alarm, now is %s times' %(domain,no_recovery_alarm.count(domain)))
        
        else:       #超出连续出现的次数和最大告警次数之和，将不再告警，放入未恢复的告警列表中
            new_alarm = filter(lambda x:x!=domain, new_alarm)   #将此域名剔除new_alarm列表，并加入未恢复的告警，此时未恢复的告警中的记录个数为告警的次数
            self.log.error('domain %s outstrip max_alarms,has ignore alarm' %domain)
        return new_alarm,no_recovery_alarm


if __name__ == '__main__':
    obj = Alarm()
    data = { 'metric': 'http.request.available', 'interval': '10s', 'value': 0,'msgnotes':'total:17;4xx:100.0%;5xx:0%', 'emailnotes': 'total:17;4xx:100.0%;5xx:0%', 'threshold': '77',  'unit': '%'}
    obj.recovery_alarm('test',data)

