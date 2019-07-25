#! /usr/bin/env python
# # -*- coding: utf-8 -*-

import datetime
import hashlib
import json
import logging
from lxml import etree
import os
import random
import re
import socket
import ssl
import sys
import threading
import threadpool
import time

defencode = 'utf-8'
ssl._create_default_https_context = ssl._create_unverified_context

if sys.version_info[0] == 2:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    import urllib2 as urllib_
elif sys.version_info[0] == 3:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.request as urllib_


logging.basicConfig(level=logging.INFO, filename='serv.log', filemode='a',
    format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s')


def FLog(msg):
    logging.info(msg)
    print(datetime.datetime.now().strftime('%c') + '\t' + msg)


def RequestWithProxy(url, proxy, headers, postdata, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    try:
        opener = urllib_.build_opener(urllib_.ProxyHandler({
            "http": proxy,
            "https": proxy,
        }))
        content = opener.open(urllib_.Request(url, headers=headers, data=postdata), timeout=timeout).read()
        return content
    except Exception as e:
        print(e)
        return None


def RequestWithDefProxy(url, headers, postdata, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    try:
        opener = urllib_.build_opener()
        content = opener.open(urllib_.Request(url, headers=headers, data=postdata), timeout=timeout).read()
        return content
    except Exception as e:
        print(url, e)
        return None


def md5(s):
    m = hashlib.md5()
    m.update(s.encode("utf-8"))
    return m.hexdigest()


gdict = {
    'todo_url_list': set(list()),
    'all_url_list': set(list()),
}
all_url_list = set(list())
undonejobs = dict()
threadnum = 16
downpool = threadpool.ThreadPool(threadnum / 2)
pagepool = threadpool.ThreadPool(threadnum)
downlock = threading.Lock()
tasknum = 0


def unifyurl(baseurl, href):
    # 检测相对url
    if baseurl is not None:
        baseurl = baseurl.strip() # 去空格
    if href is not None:
        href = href.strip()
    if baseurl is not None:
        if href.startswith('//'):
            href = baseurl.split('//')[0] + href
        elif href.startswith('/'):
            href = baseurl + href
    elif href.startswith('http'):
        href = href
    else:
        print('unifyurl unknown scheme ' + href)
        return None
    if href.find('@') != -1:
        href = href.split('@')[0]
    return href.strip('/')  # 移除末尾的/


def handle_add_xref(url, depth, accept_domain, reject_domain):
    global gdict, all_url_list, todo_url_list, downlock
    if url is None:
        return
    if url.count('/') - 2 > depth:
        return
    indomain = False
    for domain in accept_domain:
        if url.find(domain) != -1:
            indomain = True
            break
    for domain in reject_domain:
        if url.find(domain) != -1:
            indomain = False
            break
    if not indomain:
        return
    todo_url_list = gdict['todo_url_list']
    all_url_list = gdict['all_url_list']
    downlock.acquire()
    if url not in all_url_list:
        print('handle_add_xref ' + url)
        all_url_list.add(url)
        todo_url_list.add(url)
    downlock.release()


def handle_down_file(filepath, url, referer):
    global tasknum, downlock, undonejobs
    downlock.acquire()
    undonejobs[url] = (filepath, url, referer)
    downlock.release()
    data = RequestWithDefProxy(url, {
        "User-Agent": "Mozilla/5.0",
        "Referer": referer
    }, None, 60)
    if data is not None and len(data) > 0:
        downlock.acquire()
        if url in undonejobs:
            undonejobs.pop(url)
        downlock.release()
        if len(data) > 64000:
            print('handle_down_file ' + url)
            with open(filepath, 'wb') as f:
                f.write(data)


def handle_down_page(cururl, config):
    global tasknum, downlock
    depth = config['depth']
    accept_domain = config['accept_domain']
    reject_domain = config['reject_domain']
    accept_ext = config['accept_ext']
    header = config['header']
    downdir = config['downdir']
    tag = config['tag']
    baseurl = '/'.join(cururl.split('/')[:3])
    response = RequestWithDefProxy(cururl, header, None, timeout=60)
    try:
        html = etree.HTML(response)
    except Exception as e:
        return
    for href in html.xpath("//@href"):
        handle_add_xref(unifyurl(baseurl, href), depth, accept_domain, reject_domain)
    taskarr = list()
    for href in html.xpath("//@src"):
        imgurl = unifyurl(baseurl, href)
        indomain = False
        if imgurl is None:
            continue
        for domain in accept_domain:
            if imgurl.find(domain) != -1:
                indomain = True
                break
        for domain in reject_domain:
            if imgurl.find(domain) != -1:
                indomain = False
                break
        filename = os.path.basename(imgurl)
        filepath = downdir + '/' + md5(filename) + '.' + filename.split('.')[-1]
        needdown = False
        for ext in accept_ext:
            if filename.endswith(ext):
                needdown = True
                break
        if indomain and needdown:
            if not os.path.exists(filepath):
                taskarr.append(((filepath, imgurl, cururl), None))
    if len(taskarr) > 0:
        poolreqs = threadpool.makeRequests(handle_down_file, taskarr)
        downlock.acquire()
        tasknum += len(taskarr)
        [downpool.putRequest(req) for req in poolreqs]
        downlock.release()


def config_down_file(config):
    global gdict, downpool, tasknum, undonejobs, downlock
    url = config['url']
    depth = config['depth']
    accept_domain = config['accept_domain']
    reject_domain = config['reject_domain']
    accept_ext = config['accept_ext']
    header = config['header']
    downdir = config['downdir']
    tag = config['tag']
    jobfile = tag + '.job'
    undonefile = tag + '.undone'

    url = unifyurl(baseurl=None, href=url)
    gdict['todo_url_list'].add(url)
    gdict['all_url_list'].add(url)
    if not downdir.endswith('/'):
        downdir += '/'
    if not os.path.exists(downdir):
        os.makedirs(downdir)
    if os.path.exists(undonefile):
        with open(undonefile) as f:
            undonejobs = json.load(f)
            if len(undonejobs) > 0:
                taskarr = [(undonejobs[url], None) for url in undonejobs]
                downlock.acquire()
                tasknum += len(taskarr)
                downlock.release()
                poolreqs = threadpool.makeRequests(handle_down_file, taskarr)
                [downpool.putRequest(req) for req in poolreqs]
                downpool.wait()
                undonejobs.clear()
    while True:
        if os.path.exists(jobfile):
            with open(jobfile) as f:
                fdict = json.load(f)
                gdict['todo_url_list'] = set(fdict['todo_url_list'])
                gdict['all_url_list'] = set(fdict['all_url_list'])
        todo_url_list = gdict['todo_url_list']
        taskarr = list()
        task_c = threadnum
        if len(todo_url_list) == 0:
            break
        while len(todo_url_list) > 0 and task_c > 0:
            cururl = todo_url_list.pop()
            taskarr.append(((cururl, config), None))
            task_c -= 1
        poolreqs = threadpool.makeRequests(handle_down_page, taskarr)
        [pagepool.putRequest(req) for req in poolreqs]
        pagepool.wait()
        if tasknum > threadnum:
            downpool.wait()
            downlock.acquire()
            tasknum = 0
            downlock.release()
        with open(jobfile, 'w') as f:
            fdict = {
                'todo_url_list': list(gdict['todo_url_list']),
                'all_url_list': list(gdict['all_url_list'])
            }
            json.dump(fdict, f)
        with open(undonefile, 'w') as f:
            downlock.acquire()
            json.dump(undonejobs, f)
            downlock.release()
    downpool.wait()


def config_down_content(config):
    pass


if __name__ == '__main__':
    confpath = sys.argv[1]
    with open(confpath) as f:
        config = json.load(f)
    jobtype = config['type']
    if jobtype == 'file':
        config_down_file(config)
    elif jobtype == 'data':
        config_down_content(config)
