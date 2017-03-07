#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pyversion:python2.7
# owner:fuzj
# Pw @ 2016-11-21 18:15:40

from base import Base
import inspect
class Request_qps(Base):
    
    def __init__(self,interval,push=False,domain=False):
        super(Request_qps,self).__init__()
        self.interval = interval
        self.sql = self.buildsql(self.interval)
        self.push = push
        self.domain = domain
        self.metric = 'http.request.qps'
        self.log = self.logger()
    
    def postdata(self,domain,value):
        for k,v in value.items():
            if k == 'total':
                continue
            data = self.formatdata(http_host=domain,metric=self.metric,count=v,other="server_addr=%s" %k)
            self.postdatalist.append(data)
        return {domain:{'qps':value}}

    def buildsql(self,interval):
        basic_sql = self.resolve_sql(interval)
        custem_sql = {
        "server_addr": {
          "terms": {
            "field": "server_addr",
            "size": 0
          }
        }
      }
        basic_sql['aggs']['http_host']['aggs'] = custem_sql
        return basic_sql
    def getserverqps(self,data):
        unit_time = self.resolve_interval(self.interval)
        result = {}
        total = 0
        for i in data:
            try:
                qps = int(int(i['doc_count']) / int(unit_time))
                total +=qps
            except Exception as e:
                self.debug("get server %s qps faild,error msg:%s " % i['key'],e)
            result[i['key']] = qps
            result['total'] = total
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
                    server_qps = self.getserverqps(iterm['server_addr']['buckets'])

                    result.update(self.postdata(iterm['key'],server_qps))
                    result[iterm['key']].update({'total':iterm['doc_count'],'interval':self.interval})
                continue

            if not self.domain_filter(iterm['key']):
                self.log.debug('%s in exclude list,so ignore' % iterm['key'])
                continue
            if not self.base_level_filter(iterm['doc_count']):
                self.log.debug('%s request qps count %s less then base_level,so ignore' % (iterm['key'],iterm['doc_count']))
                continue
            server_qps = self.getserverqps(iterm['server_addr']['buckets'])
            result.update(self.postdata(iterm['key'],server_qps))
            result[iterm['key']].update({'total':iterm['doc_count'],'interval':self.interval})
        return result
    def run(self):
        self.reload_config()
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
        return result
        
if __name__ == '__main__':
    obj = Request_qps('5s')
    obj.run()
