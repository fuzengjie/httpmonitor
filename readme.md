# httpmonitor 工具

## 功能

* 监控请求时间    request_time
* 监控请求数量		request_total
* 监控服务可用率	request_available
* 监控请求QPS    request_qps

## 脚本结构

```
httpmonitor
├── __init__.py
├── bin
│   ├── __init__.py
│   └── httpmonitor.py  #脚本api
├── conf
│   ├── __init__.py
│   └── config.ini  	#脚本配置文件
├── core
│   ├── __init__.py
│   ├── alarm.py        #报警模块
│   ├── base.py          #基础模块
│   ├── daemonize.py      #后台进程模块
│   ├── index.py          #路由模块
│   ├── request_available.py     #服务可用率模块
│   ├── request_qps.py        #qps模块
│   ├── request_time.py       #请求时间模块
│   └── request_total.py      #请求数模块
├── log
│   ├── __init__.py
│   ├── httpmonitor.log       #log文件
│   └── total_request.log
├── sbin
    ├── __init__.py
    └── httpmonitor.py         #脚本入口文件，后台daemo
```

## 脚本逻辑

https://www.processon.com/view/link/584e5b93e4b0d594ec8f3e38

## 配置文件说明

注意：报警API和数据存储API需要单独提供

```
#es配置
[ElasticSearch]
es_host = 10.20.8.2:9200
es_user = es_admin
es_password = XYWYehkesadmin

#采集配置
[collect]
post_url = http://10.20.7.9:1988/v1/push		#push数据的API
request_time = True  #是否采集，true 表示采集，false 表示不采集
request_time_interval = 1m      #采集频率  单位可以是 秒：s、分：m、小时：h
request_total = True
request_total_interval = 1m
request_available = True
request_available_interval = 1m
request_qps = True
request_qps_interval = 5s

#日志配置
[log]
path = log/httpmonitor.log            #程序log路径，默认是程序的log目录，也可以指定其他，需使用绝对路径
level = warning                       #log级别
#request_total_path = log/total_request.log       #自定义模块的log，配置方法为`模块名_path` 表示路径;模块名_level 表示日志级别，这个优先级大于默认
#request_total_level = debug

#报警配置
[alarm]
ding_url = http://10.20.7.10:1980/ding			#报警API
wchat_url = http://10.20.7.10:1980/sms
email_url = http://10.20.7.10:1980/mail
contact = fuzengjie								#接受报警的联系人，姓名全拼，逗号隔开
alarm_type = wchat,email 					#报警方式  目前支持 微信wchat、钉钉ding、邮件email
max_alarms = 3                         #最大报警次数
request_time = True                    #是否报警，这里的如果设置false，表示只采集，不报警
request_total = True
request_available = True

#阈值配置
[acl]
legal_domain_list = xywy.com,wkimg.com,wksc.com        #合法的一级域名，当多级域名符合这些一级域名的匹配，才会采集和告警
exclude_domain_list = store.xywy.com          #排除域名，在此配置项中的域名会忽略采集和告警
only_monitor_domain_list = page.xywy.com,api.page.xywy.com,ip.display.xywy.com,              #仅仅监控的域名，为空时，表示所有域名都监控，否则只监控指定的域名
request_base_level = 100            #采集的数据个数的最低标准，只有域名的数据的条数超过此值时才会被处理


request_available_threshold = 96			#服务可用率的阈值，单位为百分比%
request_available_exclude = 				#服务可用率监控排除的域名
request_available_max_appear = 3			#阈值最大允许触发的次数

request_total_error_threshold = 80			#请求数波动的严重阈值，超过此阈值，将直接发送告警msg，单位百分比
request_total_threshold = 50				#请求数波动的阈值，单位百分比
request_total_exclude =						#请求数监控排除的域名
request_total_max_appear = 2				#阈值最大允许触发的次数
	
slow_request_level = 3						#慢请求的过滤条件，单位为秒 s
slow_request_threshold = 1					#慢请求的阈值，单位为百分比%
slow_request_exclude = 						#慢请求排除的域名
slow_request_max_appear = 3					#阈值最大允许触发的次数

#自定义域名的阈值,此优先级高于全局配置，但是排除域名的配置会和全局做合并生效
[page.xywy.com]
request_available_threshold = 96			#服务可用率的阈值，单位为百分比%
request_available_exclude = 				#服务可用率监控排除的域名
request_available_max_appear = 3			#阈值最大允许触发的次数

request_total_error_threshold = 80			#请求数波动的严重阈值，超过此阈值，将直接发送告警msg，单位百分比
request_total_threshold = 50				#请求数波动的阈值，单位百分比
request_total_exclude =						#请求数监控排除的域名
request_total_max_appear = 2				#阈值最大允许触发的次数
	
slow_request_level = 3						#慢请求的过滤条件，单位为秒 s
slow_request_threshold = 1					#慢请求的阈值，单位为百分比%
slow_request_exclude = 						#慢请求排除的域名
slow_request_max_appear = 3					#阈值最大允许触发的次数
```


## 使用说明：

### 启动后台damon

```
python sbin/httpmonitor.py -h
usage: httpmonitor.py [-h] (--start | --stop | --restart)

optional arguments:
  -h, --help  show this help message and exit
  --start    启动进程
  --stop	关闭进程
  --restart	重启进程

```

### api使用

```
python bin/httpmonitor.py -t 监控类型 -d 域名 -i 间隔
python bin/httpmonitor.py -h
usage: httpmonitor.py [-h] -t
                      {request_time,request_total,request_available,request_qps}
                      [-i INTERVAL] [-d [DOMAIN [DOMAIN ...]]] [-p]

optional arguments:
  -h, --help            show this help message and exit
  -t , --type {request_time,request_total,request_available,request_qps}
                        choices a monitor type,only must be request_time,reque
                        st_total,request_available,request_qps
  -i INTERVAL, --interval INTERVAL
                        choices monitor interval ,default 1min
  -d [DOMAIN [DOMAIN ...]], --domain [DOMAIN [DOMAIN ...]]
                        choice domain to display
  -p, --push            push data to odin
```

* 例子

```
python bin/httpmonitor.py -t request_qps -d 3g.club.xywy.com -i 5s
{
  "3g.club.xywy.com": {
    "qps": {
      "total": 218,
      "10.20.4.14": 113,
      "10.20.4.15": 105
    },
    "total": 1094,
    "interval": "5s"
  }
}

```

### 报警msg说明

* request_avaliable 报警msg

```
报警msg：

[PROBLEM][http.request.available]
club_detail.xywy.com:95.092%
total:8612;4xx:4.898%;5xx:0.01%
[最多报警3次][当前第1次:2016-12-15 11:10:16]

恢复msg：

[ok][http.request.available]
club_detail.xywy.com:99.131%
total:9309;4xx:0.869%;5xx:0.0%
[最多报警3次][当前第1次:2016-12-15 11:11:19]

说明：
problem／ok  表示状态
http.request.available  采集项
club_detail.xywy.com:95.092%    域名和当前值
total:9309;4xx:0.869%;5xx:0.0% total：本域名本次采集的总条数，4xx：表示 400<= httpcode < 500的占比，5xx 表示 httpcode >= 500的占比

```

* request_time 报警msg

```
报警msg:
[PROBLEM][http.slow.request.count]
zhaopin_club.xywy.com:2.094%
total:191; >3s:4
[最多报警3次][当前第1次:2016-12-14 04:31:45]

恢复msg：
[ok][http.slow.request.count]
zhaopin_club.xywy.com:0.342%
total:292; >3s:1
[最多报警3次][当前第1次:2016-12-14 04:32:46]

说明：
problem／ok  表示状态
http.slow.request.count   采集项
zhaopin_club.xywy.com:0.342%  域名和当前值
total:292; >3s:1     total：本域名本次采集的总条数 >3s:1 大于3s的总条数
```

* request_total 报警msg

```
报警msg：
[PROBLEM][http.request.total]
display.xywy.com
total:34; yoy_rate:-97.56%; mom_rate:-97.59%
[最多报警3次][当前第1次:2016-12-15 05:23:20]

恢复msg：
[ok][http.request.total]
display.xywy.com
total:2065; yoy_rate:8.57%; mom_rate:5973.53%
[最多报警3次][当前第1次:2016-12-15 05:28:22]

说明：
problem／ok  表示状态
http.request.total   采集项
display.xywy.com 域名
total:2065; yoy_rate:8.57%; mom_rate:5973.53%  total：本域名本次采集的数量 ，yoy_rate：同比，mom_rate：环比
```

