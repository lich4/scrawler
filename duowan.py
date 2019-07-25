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


threadnum = 16
downpool = threadpool.ThreadPool(threadnum / 2)


def handle_down_file(filepath, imgurl, cururl):
    data = RequestWithDefProxy(imgurl, {
        "User-Agent": "Mozilla/5.0",
        "Referer": cururl
    }, None, 60)
    if data is not None and len(data) > 0:
        print('handle_down_file ' + imgurl)
        try:
            with open(filepath, 'wb') as f:
                f.write(data)
        except:
            pass


def downduowan():
    downdir = './duowan/'
    if not os.path.exists(downdir):
        os.makedirs(downdir)
    offset = 0
    hrefs = list()
    while True:
        url = 'http://tu.duowan.com/tu?offset=%d&order=created&math=0.1' % offset
        response = RequestWithDefProxy(url, dict(), None)
        jhtml = json.loads(response)
        html = etree.HTML(jhtml['html'])
        hrefs += [i for i in html.xpath('//li/a/@href')]
        offset = jhtml['offset']
        if not jhtml['more']:
            break
    hrefs = list(set(hrefs))

    for url in hrefs:
        url = url.replace('gallery', 'scroll')
        try:
            response = RequestWithDefProxy(url, dict(), None)
            html = etree.HTML(response)
        except Exception as e:
            continue
        picboxs = html.xpath('//div[@class="pic-box"]')
        taskarr = list()
        for picbox in picboxs:
            comment = picbox.xpath('p/text()')[0]
            attrib = picbox.xpath('a/span')[0].attrib
            dataimg = attrib['data-img']
            datavideo = attrib['data-video']
            if dataimg.endswith('gif'):
                ext = 'gif'
                suburl = dataimg
            elif datavideo != '':
                 ext = datavideo.split('.')[-1]
                suburl = datavideo
            else:
                ext = dataimg.split('.')[-1]
                suburl = dataimg
            objurl = unifyurl(url, suburl)
            filename = comment + '.' + ext
            filepath = (downdir + filename).replace('?', '')
            if not os.path.exists(filepath):
                taskarr.append(((filepath, objurl, url), None))
        if len(taskarr) > 0:
            poolreqs = threadpool.makeRequests(handle_down_file, taskarr)
            [downpool.putRequest(req) for req in poolreqs]
            print('wait %d tasks' % len(taskarr))
            downpool.wait()


downduowan()