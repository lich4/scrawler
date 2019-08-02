#! /usr/bin/env python
# # -*- coding: utf-8 -*-

import datetime
import gzip
import hashlib
import json
import logging
from lxml import etree
import os
import random
import re
import socket
import ssl
import StringIO
import sys
import threading
import threadpool
import time
import jieba

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


class NoRedirection(urllib_.HTTPRedirectHandler):
    def http_error_301(req, fp, code, msg, hdrs, newurl):
        return code

    def http_error_302(req, fp, code, msg, hdrs, newurl):
        return code

    def http_error_303(req, fp, code, msg, hdrs, newurl):
        return code


def httpRequest(url, headers=None, postdata=None, proxy=None):
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
    try:
        if proxy is None:
            opener = urllib_.build_opener(NoRedirection)
        else:
            opener = urllib_.build_opener(NoRedirection, urllib_.ProxyHandler({
                "http": proxy,
                "https": proxy,
            }))
        resp = opener.open(urllib_.Request(
            url, headers=headers, data=postdata))
        data = resp.read()
        if 'content-encoding' in resp.headers and resp.headers['content-encoding'] == 'gzip':
            gz = gzip.GzipFile(fileobj=StringIO.StringIO(data))
            data = gz.read()
            gz.close()
        return resp.code, data
    except Exception as e:
        return 600, None


def downFile(url, path, headers=None, postdata=None, proxy=None):
    code, data = httpRequest(url=url, headers=headers,
                             postdata=postdata, proxy=proxy)
    if code == 200 and data is not None:
        with open(path, 'wb') as f:
            f.write(data)


g_categories = [
    {"id": "local", "name": u"本地新闻"},
    {"id": "1639", "name": u"时尚"},
    {"id": "233244711", "name": u"收藏"},
    {"id": "1640", "name": u"文化"},
    {"id": "video", "name": u"视频"},
    {"id": "1655", "name": u"历史"},
    {"id": "1631", "name": u"教育"},
    {"id": "1668", "name": u"动漫"},
    {"id": "1644", "name": u"育儿"},
    {"id": "46073964", "name": u"宠物"},
    {"id": "1654", "name": u"家居"},
    {"id": "1641", "name": u"时政"},
    {"id": "8841383", "name": u"科学"},
    {"id": "1658", "name": u"旅游"},
    {"id": "1653", "name": u"游戏"},
    {"id": "1661", "name": u"数码"},
    {"id": "1649", "name": u"科技"},
    {"id": "1629", "name": u"娱乐"},
    {"id": "1656", "name": u"美食"},
    {"id": "1637", "name": u"社会"},
    {"id": "1635", "name": u"体育"},
    {"id": "1630", "name": u"健康"},
    {"id": "1651", "name": u"汽车"},
    {"id": "1645", "name": u"国际"},
    {"id": "1648", "name": u"军事"},
    {"id": "168744590", "name": u"三农"},
    {"id": "1632", "name": u"财经"},
    {"id": "31135316", "name": u"技术"},
    {"id": "31135318", "name": u"移民"},
    {"id": "1638", "name": u"房产"},
    {"id": "235782276", "name": u"摄影"},
    {"id": "141902056", "name": u"传媒"},
    {"id": "438266921", "name": u"心理"}
]

headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cookie': 'mlab-session=MTU2NDUzNDIyNXxEdi1CQkFFQ180SUFBUkFCRUFBQUpmLUNBQUVHYzNSeWFXNW5EQWtBQjNWelpYSmZhV1FGYVc1ME5qUUVCd0Q3TTVrV2k1ST18sjYqcxiJ5mtNEURIYP7DZ7qK4oIIN0jJCN9DmK-UTbo=',
}


def gethotissues():
    endtime = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    starttime = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3600 * 24 * 3))
    urlhot = 'https://mlab.toutiao.com/api/issues/hot?start=%s&end=%s&rid=0&cid=%s&filter_official_media=0'
    urlrise = 'https://mlab.toutiao.com/api/issues/rise?start=%s&end=%s&rid=0&cid=%s&filter_official_media=0'
    for item in g_categories:
        try:
            code, data = httpRequest(urlhot % (starttime, endtime, item['id']), headers=headers)
            issue = json.loads(data)['hot_issues'][0]
            if issue['score']/10000 > 1:
                print(item['name'] + u"热门事件(%dW):" % (issue['score']/10000) + u' '.join(issue['keywords']))
            code, data = httpRequest(urlrise % (starttime, endtime, item['id']), headers=headers)
            issue = json.loads(data)['issues_rise'][0]
            if issue['score']/10000 > 1:
                print(item['name'] + u"上升事件(%dW):" % (issue['score']/10000) + u' '.join(issue['keywords']))
        except Exception as e:
            pass


'''
unicode -> utf8    unicode_str.encode('utf8')
utf8 -> unicode    unicode(utf8_str, 'utf8')
'''
def gethotkeyword(s):
    endtime = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    starttime = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3600 * 24 * 3))
    totaltrends = 0
    for ss in set(jieba.lcut(s)):
        if len(ss) < 2 or ss.isalnum():
            continue
        if type(u'宝直接') == unicode:
            ss = ss.encode('utf8')
        uss = unicode(ss, "utf8")
        url = 'https://mlab.toutiao.com/api/keyword/detail_hot_index?rid=0&cid=0&keyword=%s&start=%s&end=%s'
        try:
            code, data = httpRequest(url % (urllib_.quote(ss), starttime, endtime), headers=headers)
            trends = json.loads(data)['trends'][uss]
            if trends[0]/10000 > 1:
                print(uss + "=%dW" % (trends[0]/10000))
                totaltrends += int(trends[0]/10000)
        except Exception as e:
            pass
    print('total trends=%dW' % totaltrends)


if __name__ == '__main__':
    if sys.argv[1] == '--gethotissues':
        gethotissues()
    elif sys.argv[1] == '--gethotkeyword':
        s = sys.argv[2]
        gethotkeyword(s)


# gethotkeyword('保时捷女车主掌掴男子 网传女车主是派出所长妻子')
