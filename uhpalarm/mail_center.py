#!/usr/bin/env python
# coding=utf-8

import os
import sys
import time
import thread
import threading

import config
import mail
import database
from jinja2 import Environment, FileSystemLoader
from lib.logger import log
from model.alarm import AlarmAssist

mutex = threading.Lock()
alarm_list = []
max_length = 100
last_send = -1
env = Environment(loader = FileSystemLoader("%s/uhpalarm/templates" % config.uhphome))

def add_alarm_info(content):
    '''
    推送一个报警内容
    内容一定是dict
    '''
    re = True
    mutex.acquire()
    global alarm_list
    global max_length
    if len(alarm_list) > max_length:
        re = False
    else:
        alarm_list.append(content)
    mutex.release()
    return re

def get_alarm_info():
    '''
    获取报警内容的队列
    '''
    re = []
    mutex.acquire()
    global alarm_list
    re = alarm_list
    alarm_list = []
    mutex.release()
    return re

def start_mail_center():
    thread.start_new_thread(mail_center,())

def mail_center():
    while True:
        try:
            _need_send_period_mail()
            _need_send_alarm_mail()
            time.sleep(config.mail_interval)
        except:
            log.exception("mail center loop die")

def _need_send_period_mail():
    pass

def _need_send_alarm_mail():
    now = int(time.time())
    global last_send
    if last_send == -1 or now - last_send > config.mail_send_interval:
        al = get_alarm_info()
        if len(al) > 0 :
            _send_alarm_mail(al)
            last_send = now

def _get_mail_to():
    session = database.getSession()
    mail_list = session.query(AlarmAssist).filter(AlarmAssist.name=="mail_to").first()
    log.info("to mail %s" % mail_list.value)
    return mail_list.value.split(",")
    #return ['qiujw@ucweb.com']

def _send_alarm_mail(a_list):
    _send_mail("alarm_mail",{"alarm_list":a_list})

def _send_mail(template_name,dict):
    template = env.get_template("%s.html" % template_name)
    html = template.render(**dict)
    to_list = _get_mail_to()
    log.info("send mail to"+str(to_list))
    mail.send_mail(to_list, "UHP alarm mail", html, "html")

if __name__ == "__main__" :
    print "x"
    add_alarm_info({"a":"b","c":"d"})
    _need_send_alarm_mail()

