# -*- coding: UTF-8 -*-
import os
import json
import logging
import time
import copy
import math
import re
from decimal import Decimal

import tornado
from sqlalchemy.orm import query,aliased
from sqlalchemy import and_,or_,desc,asc
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

import async
import static_config
import rrd
import database
import config
from rrd import RrdWrapper
import util
import callback_lib
import mm
from controller import BaseHandler
from controller import shell_lib
from model.instance import Instance
from model.host_group_var import Host,Group,GroupHost,HostVar,GroupVar
from model.task import Task
from model.services import Service
from model.callback import CallBack

app_log = logging.getLogger("tornado.application")
        
class MonitorBackHandler(BaseHandler):

    def __init__(self, application, request, **kwargs):
        super(MonitorBackHandler, self).__init__(application, request, **kwargs)

    @tornado.web.authenticated
    def get(self , path):
        user = self.get_current_user();
        if user['type'] != 0 :
            self.ret("error","this user is not monitor")
            return
        if hasattr(self, path) :
            fun = getattr(self, path);
            if callable(fun):
                apply(fun)
        else:
            self.ret("error","unsupport action")
            
    @tornado.web.authenticated
    def post(self , path):
        self.get(path)
        
    def user(self):
        user = self.get_current_user();
        ret = {"user":user,"menus":static_config.monitormenus}
        self.ret("ok", "", ret);
    
    # unuse 
    def submenu(self):
        ret = {"submenu":static_config.monitormenus}
        self.ret("ok", "", ret);
   
    def _query_var(self, group, name):
        session = database.getSession()
        try:
            groupVars = session.query(GroupVar).filter(and_( GroupVar.name == name , GroupVar.group == group ) )
            for groupVar in groupVars:
                if groupVar.type == 0:
                    return groupVar.value
                return groupVar.value.split(',')
        finally:
            session.close()

    def _checkout_groups_metrics(self, group_names):
        all_metric_groups = static_config.monitor_show_info['metrics']

        # 指定组的指标
        # { name:,metrics:{} }
        groups_metrics = {} 
        for group_name in group_names:
            group_name = self._sure_str(group_name)
            if group_name in all_metric_groups:
                group_metrics = all_metric_groups[group_name]
                group_metrics_map = dict([(m['name'],m) for m in group_metrics])
                groups_metrics.update(group_metrics_map)
        return groups_metrics

    def show_info(self):
        group_names = self.get_arguments("groups")
    
        cluster_name = self._query_var('all', 'cluster_name')
        cluster_name = self._sure_str(cluster_name)
        rrd_wrapper  = RrdWrapper(config.ganglia_rrd_dir , config.rrd_image_dir)

        show_info = {}
        rras = self._query_var('all', 'gmetad_rras')
        precisions = rrd.parse_precision(rras)

        show_info['precisions']=[]
        for sec in precisions:
            if sec < 86400:
                h = int(math.ceil(sec/3600))
                precision='%d小时' % h
            else:
                d = int(math.ceil(sec/86400))
                if d == 7:
                    precision='1周'
                elif d >=28 and d <=31:
                    precision='1月'
                elif d > 360 and d <= 366:
                    precision='1年'
                else: 
                    precision='%d天' % d
            show_info['precisions'].append({'name':'p%d'%sec, 'display':precision})
        show_info['precision'] = show_info['precisions'][0]['name'] # default
        

        # 指定组的指标
        # { name:,metrics:{} }
        groups_metrics = self._checkout_groups_metrics(group_names)
    
        all_rrd_metrics = rrd_wrapper.get_all_rrd_names(clusterName=cluster_name)

        show_info['metrics'] = [] 
        #metric_name_map = dict([ (m['name'], m['display']) for m in static_config.monitor_show_info['metrics'] ])
        for metric in all_rrd_metrics:
            if metric not in groups_metrics: 
                app_log.debug("metric %s not in groups_metrics" % metric)
                continue
            app_log.debug("metric %s ok" % metric)
            m = groups_metrics[metric] 
            show_info['metrics'].append(m)
        
        if show_info['metrics']:
            show_info['metric'] = show_info['metrics'][0]['name']
        show_info['hosts'] = self._host_list()
        show_info['host'] = show_info['hosts'][0]

        ret = {"data":show_info}
        self.ret("ok", "", ret);
  
    # [{name:, roles:{role:[instance]}}]
    def _query_active_services(self):
        session = database.getSession()
        try:
            active = []
            for service in session.query(Service):
                if service.status != Service.STATUS_ACTIVE : continue
                instances = session.query(Instance).filter(Instance.service == service.service)
                service = {'name':service.service, 'roles':{}}
                for ins in instances:
                    if ins.role not in service['roles']:
                        service['roles'][ins.role] = []
                    service['roles'][ins.role].append(ins.host)
                    
                active.append(service)
            return active
        finally:
            session.close()

    # services overview
    def services_metrics(self):
        # [{name:, roles:{role:[instance]}}]
        services         = self._query_active_services()
        services_metrics = copy.deepcopy(static_config.services_metrics)
        cluster_name     = self._query_var('all', 'cluster_name')
        cluster_name     = self._sure_str(cluster_name)
    
        rrd_wrapper     = RrdWrapper(config.ganglia_rrd_dir , config.rrd_image_dir)

        for service in services:
            service_shows = None
            for item in services_metrics:
                if item['name'] == service['name']:
                    service_shows = item['show']
            if  service_shows is None: continue

            for show in service_shows:
                hosts = service['roles'][show['role']]
                if show['type'] == 'instance-status':
                    instance_status =  []
                    #找到实体
                    metric = show['metric']
                    metric = self._sure_str(metric)
                    for host in hosts:
                        host = self._sure_str(host)
                        (ts, value) = (None, None)
                        try:
                            (ts, value) = rrd_wrapper.query_last(metric, hostname=host, clusterName=cluster_name)
                            if value is None: continue
                            instance_status.append([host,value])
                        except Exception, e:
                            pass
                    if instance_status:
                        show['instance-status'] = instance_status
                    else:
                        show.clear()
                    continue

                if show['type'] == 'list':
                    show['list'] =  []
                    metrics = []
                    if 'metric-groups' in show:
                        for group in show['metric-groups']:
                            metrics.extend(static_config.monitor_show_info['metrics'][group])
                    for metric in metrics:
                        metric_name = self._sure_str(metric['name'])
                        for host in hosts: 
                            host = self._sure_str(host)
                            (ts, value) = (None, None)
                            try:
                                (ts, value) = rrd_wrapper.query_last(metric_name, hostname=host, clusterName=cluster_name)
                                if value is None: continue
                                show['list'].append([metric, value])
                            except Exception, e:
                                pass
                            break
                    if not show['list']:
                        show.clear()
                    continue
            
            # 清理空值
            for i in range(len(service_shows) - 1, -1, -1):
                if not service_shows[i]:
                    service_shows.pop(i)

        # 清理空值
        for i in range(len(services_metrics) - 1, -1, -1):
            if not services_metrics[i]['show']:
                services_metrics.pop(i)
        
        ret = {"data":services_metrics}
        self.ret("ok", "", ret);

    # 获取所有的机器
    def _host_list(self):
        session = database.getSession()
        hosts = session.query(Host)
        temp = [host.hostname for host in hosts]
        session.close()
        return temp

    def _sure_str(self, str):
        if isinstance(str, unicode): 
            str = str.encode('ascii', 'ignore')
        return str

    def show_hosts_metric(self):
        precision = self.get_argument("precision")
        precision = self._sure_str(precision)
        metric = self.get_argument("metric")
        metric = self._sure_str(metric)
        hosts = self.get_arguments("hosts")
        
        rrd_wrapper     = RrdWrapper(config.ganglia_rrd_dir , config.rrd_image_dir)

        sec = int(precision[1:])
        start = "-%ds" % sec
        end = "now" 

        data = []
        
        for host in hosts:
            host = self._sure_str(host)
            try:
                rrd_metric = rrd_wrapper.query(metric, start, end, hostname=host, clusterName=cluster_name)
            except Exception, e:
                if 'RRD File not exists' in str(e): continue
                raise e
            xy = rrd.convert_to_xy(rrd_metric)
            data.append({'host':host, 'x':xy[0], 'y':xy[1]})
        ret = {"data":data}
        self.ret("ok", "", ret);

    # 显示单机的全部指标
    def show_host_metrics(self):
        group_names  = self.get_arguments("groups")
        precision    = self.get_argument("precision")
        host         = self.get_argument("host")
        precision    = self._sure_str(precision)
        host         = self._sure_str(host)
        
        cluster_name = self._query_var('all', 'cluster_name')
        cluster_name = self._sure_str(cluster_name)
        rrd_wrapper     = RrdWrapper(config.ganglia_rrd_dir , config.rrd_image_dir)

        sec = int(precision[1:])
        start = "-%ds" % sec
        end = "now" 

        data = []
        
        metrics = rrd_wrapper.get_all_rrd_names(clusterName=cluster_name)
        
        groups_metrics = self._checkout_groups_metrics(group_names)

        for metric in metrics:
            if metric not in groups_metrics: continue
            metric = self._sure_str(metric)
            try:
                rrd_metric = rrd_wrapper.query(metric, start, end, hostname=host, clusterName=cluster_name)
            except Exception, e:
                if 'RRD File not exists' in str(e): continue
                raise e
            xy = rrd.convert_to_xy(rrd_metric)
            data.append({'metric':metric, 'x':xy[0], 'y':xy[1]})
        ret = {"data":data}
        self.ret("ok", "", ret);

    def _fetch_host_last_metric(self, rrd_wrapper, cluster_name, host, metric):
        host   = self._sure_str(host)
        metric = self._sure_str(metric)
        (ts, value) = rrd_wrapper.query_last(metric, hostname=host, clusterName=cluster_name)
        return value

    
    # 计算表达式
    # -1: 未获取
    def _eval_rrd_expression(self, rrd_wrapper, cluster_name, host, expression):
        # total - free = use
        # use - buffer - cached
        # expression = "(mem_total - mem_free - mem_cached - mem_buffers)*100/mem_total" 
        p = re.compile(r'[a-zA-Z_][\w\.]*')
        expr_vars = p.findall(expression)
        # metrics = ['mem_total','mem_free','mem_cached','mem_buffers']
        i = 0;
        for metric in expr_vars:
            value = self._fetch_host_last_metric(rrd_wrapper,cluster_name, host, metric)
            if value is None: return -1
            # 为了变量安全，进行替换
            new_var = 'loc_pvar_%d' % i
            expression = re.sub(r'\b%s\b'%metric.replace('.',r'\.'), new_var, expression)
            locals()[new_var] = value
            i += 1
        value = eval(expression)
        return value
    
    # 指定机器的当前健康度
    def _host_current_health(self, rrd_wrapper, cluster_name, host):
        host_load_percent = self._eval_rrd_expression(rrd_wrapper, cluster_name, host, static_config.host_load_percent_expression)
        if host_load_percent < 0: return -1
        host_mem_percent = self._eval_rrd_expression(rrd_wrapper, cluster_name, host, static_config.host_mem_percent_expression)
        if host_mem_percent < 0: return -1
        host_net_percent = self._eval_rrd_expression(rrd_wrapper, cluster_name, host, static_config.host_net_percent_expression)
        if host_net_percent < 0: return -1
        host_disk_percent = self._eval_rrd_expression(rrd_wrapper, cluster_name, host, static_config.host_disk_percent_expression)
        if host_disk_percent < 0: return -1

        health = 100
        if host_disk_percent > 80:
            health -= 20 
        if host_net_percent > 80:
            health -= 20 
        if host_mem_percent > 80:
            health -= 20 
        if host_load_percent > 80:
            health -= 20

        if health < 0: health = 0
        return health
   
    # 服务单实例的健康度
    # 服务健康度：进程，端口，响应，性能
    def _service_instance_current_health(self, rrd_wrapper, cluster_name, service, role, host):
        session = database.getSession()
        for instance in session.query(Instance).filter(and_(Instance.service==service, Instance.role==role,
            Instance.host==host)):
            if instance.health == Instance.HEALTH_HEALTHY:
                return 100
            if instance.health == Instance.HEALTH_UNKNOW:
                return -1
        return 0

    # 当前的监控指标
    # healths:[{type:,name:,display:,value:,
    #   x:[],y:[],
    #   group:[{name:,display:,value:,x:[],y:[]}]}]
    def fetch_current_healths(self):
        data = []
        
        cluster_name = self._query_var('all', 'cluster_name')
        cluster_name = self._sure_str(cluster_name)
        rrd_wrapper  = RrdWrapper(config.ganglia_rrd_dir , config.rrd_image_dir)

        # host
        host_healths = {'type':'single','name':'host','display':'机器健康度'}
        hosts = self._host_list()
        y = []
        for host in hosts:
            y.append(self._host_current_health(rrd_wrapper, cluster_name, host))
        health = int(reduce(lambda x,y:x+y,y,0)/len(y))
        host_healths['value'] = health
        host_healths['x']     = hosts
        host_healths['y']     = y
       
        data.append(host_healths)

        # Service
        # [{name:, roles:{role:[instance]}}]
        services         = self._query_active_services()
        services_healths =  {'type':'multi', 'name':'service','display':'服务健康度', 'group':[]}
        for service in services:
            # group
            service_health = {'name':service['name'], 'display':service['name'],'roles':[]}
            service_health_value = 100 # 各个角色的乘积
            for role, hosts in service['roles'].items():
                role_health = {'name':role, 'display':role}
                y = []
                for host in hosts:
                    ins_health = self._service_instance_current_health(rrd_wrapper, cluster_name, service['name'], role, host) 
                    y.append(ins_health)
                role_health['x'] = hosts
                role_health['y'] = y
                role_health_value = int(reduce(lambda x,y:x+y,y,0)/len(y)) # 平均值
                service_health_value *= role_health_value/100.0
                service_health['roles'].append(role_health)
            service_health['value'] = int(service_health_value)
            services_healths['group'].append(service_health)
       
        data.append(services_healths)
       
        # Job : 最近失败比率
        jobs_healths =  {'type':'multi', 'name':'job','display':'作业健康度', 'group':[]}
        jobs_healths['group'].append({'name':'','display':'作业健康度',"value":"90"})
        jobs_healths['group'].append({'name':'','display':'作业运行数',"value":"30"})
        jobs_healths['group'].append({'name':'','display':'作业失败数',"value":"3"})
        jobs_healths['group'].append({'name':'','display':'资源使用数',"value":"40/40G"})
        
        data.append(jobs_healths)

        ret = {"data":data}
        self.ret("ok", "", ret);

    def _get_rmhost(self):
        return "hadoop2"

    def _get_rmport(self):
        return "50088"
    #for running job

    def app_running_state(self):
        url = "http://%s:%s/ws/v1/cluster/metrics" %( self._get_rmhost(),self._get_rmport() )
        metrics = util.get_http_json(url)
        self.ret("ok","",metrics)

    def app_running(self):
        url = "http://%s:%s/ws/v1/cluster/apps?state=RUNNING" %(self._get_rmhost(),self._get_rmport())
        runningApp = util.get_http_json(url)
        queues = {}
        if runningApp != None and runningApp.has_key("apps") and runningApp["apps"]!=None and  runningApp["apps"].has_key("app"):
            for app in runningApp["apps"]["app"]:
                queue = app["queue"]
                appid = app['id']
                if not queues.has_key(queue):
                    queues[queue] = {}
                queues[queue][appid]=app
        result={"queues":queues,"rmhost":self._get_rmhost(),"rmport":self._get_rmport()}
        self.ret("ok","",result)

    def app_waitting(self):
        url = "http://%s:%s/ws/v1/cluster/apps?state=ACCEPTED" %(self._get_rmhost(),self._get_rmport() )
        waittingApp = util.get_http_json(url)
        if waittingApp.has_key("apps") :
            apps = waittingApp["apps"]
        else:
            apps = []
        result={"waitting":apps,"rmhost":self._get_rmhost(),"rmport":self._get_rmport()}
        self.ret("ok","",result) 

    def app_proxy(self):
        appid = self.get_argument("appid") 
        url = ("http://%s:%s/proxy/%s/ws/v1/mapreduce/jobs/" %(self._get_rmhost(),self._get_rmport(),appid))
        jobInfo = util.get_http_json(url)
        keyList = ["mapsTotal","mapsPending","mapsRunning","failedMapAttempts","killedMapAttempts","successfulMapAttempts",
                   "reducesTotal","reducesPending","reducesRunning","failedReduceAttempts","killedReduceAttempts","successfulReduceAttempts"]
        if jobInfo:
            result = {}
            temp = jobInfo["jobs"]["job"][0]
            result["amTime"] = temp["elapsedTime"]
            for key in keyList:
                result[key] = temp[key]
            self.ret("ok","",result)
        else:
            result = {}
            result["amTime"] ="x"
            for key in keyList:
                result[key] = "x"
            self.ret("ok","",result)

    #for rm query
    def rm_query(self):
        fields = self.get_argument("fields",""); 
        fields = fields.split(",")
        happenTimeMax = self.get_argument("happenTimeMax",0);
        happenTimeMin = self.get_argument("happenTimeMin",0);
        happenTimeSplit = self.get_argument("happenTimeSplit",600);
        if len(fields)!=0 :
            where = "1" 
            if happenTimeMax != 0:
                where = where + " and happenTime < "+str(happenTimeMax)
            if happenTimeMin != 0:
                where = where + " and happenTime > "+str(happenTimeMin)
        
            sqlFields=""
            for field in fields:
                sqlFields = sqlFields+" , sum("+field+") as " + field
        
            sql = ("select (happenTime/%s)*%s as printTime  %s from rm where %s group by printTime" % (happenTimeSplit,happenTimeSplit,sqlFields,where) )
            session = database.getSession()
            cursor = session.execute(sql)
            queryResult = []
            for record in cursor:
                temp = []
                for value in record:
                    app_log.info(type(value))
                    if isinstance(value,Decimal):
                        app_log.info("into deci")
                        temp.append(float(value))    
                    else:
                        temp.append(value)
                queryResult.append(temp)
            app_log.info(queryResult)
        
            #特殊处理mapTime和reduceTime
            #由于前面有一个printTime的查询，所以偏移一位
            fieldOffset = 1 
            if "mapTime" in fields and "mapNum"  in fields :
                timeIndex = fields.index("mapTime") + fieldOffset
                numIndex = fields.index("mapNum") + fieldOffset
                for record in queryResult:
                    if record[numIndex] != None and record[numIndex] != 0:
                        record[timeIndex] = record[timeIndex] / record[numIndex] 
        
            if "reduceTime" in fields and "reduceNum"  in fields :
                timeIndex = fields.index("reduceTime") + fieldOffset
                numIndex = fields.index("reduceNum") + fieldOffset
                for record in queryResult:
                    if record[numIndex] != None and record[numIndex] != 0:
                        record[timeIndex] = record[timeIndex] / record[numIndex]
        else:
            sql = ""
            queryResult = []

        result= {"result":queryResult,"sql":sql}
        self.ret("ok","",result)               
                    
    #for nm query

    
    #for app query
    def app_sum(self):
        where = self.get_argument("where","1").replace("o|o","%")
        session = database.getSession()
        sumKey=["mapsTotal","mapsCompleted","successfulMapAttempts","killedMapAttempts","failedMapAttempts",
                "localMap","rackMap",
                "reducesTotal","reducesCompleted","successfulReduceAttempts","killedReduceAttempts",
                "failedReduceAttempts",
                "fileRead","fileWrite","hdfsRead","hdfsWrite"]
        select = "count(appid) as appidCount"
        for key in sumKey:
            select = select +" , sum("+key+") as "+key+"Sum "
        sql = (("select "+select+" from app where %s ") % (where))
        app_log.info(sql)
        cursor = session.execute(sql)
        resultRecord = {}
        temp = []
        for record in cursor:
            app_log.info(record)
            for value in record:
                temp.append(value)
                app_log.info(value)
        for (key,value) in zip(cursor.keys(),temp):
            if value != None:
                resultRecord[key]=int(value)
            else:
                resultRecord[key]=0
        session.close()
        result={"resultRecord":resultRecord}
        
        self.ret("ok","",result)

    def app_list(self):
        where = self.get_argument("where","1").replace("o|o","%")
        offset = self.get_argument("offset",0)
        limit = self.get_argument("limit",50)
        orderField = self.get_argument("orderField","appid")
        orderDirection = self.get_argument("orderDirection","desc")
        session = database.getSession()
        selectKeyArray=["appid","user","name","queue","startedTime","finishedTime","state","finalStatus",
                   "attemptNumber","mapsTotal","mapsCompleted","localMap","reducesTotal","reducesCompleted",
                   "fileRead","fileWrite","hdfsRead","hdfsWrite"]
        if orderField=="appid" :
            selectKeyArray.append("CAST(SUBSTR(appid,27 ) AS SIGNED) as appnum")
            orderby = "appnum "+orderDirection
        else:
            orderby = orderField+" "+orderDirection 
        selectKey = ",".join(selectKeyArray)
        sql = ("select "+selectKey+" from app where %s order by %s LIMIT %s OFFSET %s " % (where,orderby,limit,offset))
        cursor = session.execute(sql)
        queryResult = []
        for record in cursor:
            temp = []
            for v in record:
                temp.append(v)
            queryResult.append(temp)
        #queryResult = cursor.fetchall()
        session.close()
        result={"applist":queryResult,"rmhost":self._get_rmhost(),"rmport":self._get_rmport()}
        self.ret("ok","",result)

