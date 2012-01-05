
import traceback
import time
import json
import operator
import urllib
import csv

from twisted.internet import threads, defer
from twisted.web import resource, server
from twisted.web.resource import NoResource
import pgdb as sql

import smap.util as util
import data
import queryparse as qp
import settings

def makeErrback(request_):
    request = request_
    def errBack(outp):
        try:
            request.setResponseCode(500)
            request.finish()
        except:
            traceback.print_exc()

def build_authcheck(request):
    """Build an SQL WHERE clause which enforces access restrictions.
    Will pull any credentials out of the request object passed in.
    """
    if not 'private' in request.args:
        query = "(sub.public "
    else:
        query = "(false "
    if 'key' in request.args:
        query += 'OR ' + ' OR '.join(["sub.key = '%s'" % sql.escape_string(x) 
                                      for x in request.args['key']])
    query += ")"
    return query

class ApiResource(resource.Resource):
    def __init__(self, db):
        self.db = db
        resource.Resource.__init__(self)

class DataRequester:
    """Manage loading data from a single stream from a readingdb
    backend.  Will chain deferred together to return a partial
    timeseries which contains just the uuid and the requested data.
    """
    def __init__(self, uid):
        self.uid = uid

    def _load_data(self, qfunc):
        """Run in thread pool - connect and execute query func
        """
        try:
            conn = data.rdb_pool.get()
            rv = qfunc(conn)
            return rv
        except:
            return None
        finally:
            data.rdb_pool.put(conn)

    def _munge_data(self, (request, data)):
        """Tweak the resulting object to be a Timeseries
        """
        if data != None:
            return request, {
                'uuid': self.uid,
                'Readings' : map(lambda x: (x[0] * 1000, x[2]), data)
                }
        return request, None

    def load_data(self, request, method, streamid):
        """Called to kick off a load -- returns a deferred which will
        yield a (request, Timeseries) tuple when it finishes.        
        """
        # if these raise an exception we'll cancel all the loads
        now = int(time.time()) * 1000
        start = int(request.args.get('starttime', [now - 3600 * 24 * 1000])[0])
        end = int(request.args.get('endtime', [now])[0])
        limit = int(request.args.get('limit', [-1])[0])
        # print now, start, end, method, streamid

        def mkQueryFunc():
            request_, method_, start_, end_, limit_, streamid_ =  \
                request, method, start, end, limit, streamid
            def queryFunc(db):
                qstart = start_
                qlimit = limit_
                if method_ == 'data':
                    try:
                        rv = []
                        # no limit if zero
                        if qlimit == -1:
                            qlimit = 1000000

                        while True:
                            data = settings.rdb.db_query(db, streamid_, qstart / 1000, end_ / 1000)
                            rv += data[:min(len(data), qlimit)]
                            qlimit -= min(len(data), qlimit)
                            if len(data) < 10000 or \
                               qlimit <= 0: break
                            qstart = (rv[-1][0] + 1) * 1000
                        return request, rv
                    except:
                        traceback.print_exc()
                elif method == 'next':
                    if qlimit == -1: qlimit = 1
                    return request, settings.rdb.db_next(db, streamid_, start_ / 1000, n = qlimit)
                elif method == 'prev':
                    if qlimit == -1: qlimit = 1
                    return request, settings.rdb.db_prev(db, streamid_, start_ / 1000, n = qlimit)
                return request, []
            return queryFunc

        d = threads.deferToThread(self._load_data, mkQueryFunc())
        d.addCallback(self._munge_data)
        d.addErrback(makeErrback(request))
        return d


class SubscriptionResource(ApiResource):
    """Show the client a list of sMAP sources, or a small description
    of the streams associated with one subscription.
    """
    def getChild(self, name, resource):
        return self

    def _done_subs(self, request, result):
        try:
            result = [{'id' : x[0],
                       'SmapUrl' : x[1],
                       'ReportResource' : x[2]} for x in result]
            d = util.AsyncJSON(result).startProducing(request)
            d.addBoth(lambda _: request.finish())
        except:
            traceback.print_exc()

    def _done_streams(self, request, result):
        result = [{'Path' : x[0],
                   'uuid' : x[1]} for x in result]
        result.sort(key=operator.itemgetter('Path'))
        d = util.AsyncJSON(result).startProducing(request)
        d.addBoth(lambda _: request.finish())

    def render_GET(self, request):
        if len(request.prepath) == 2 or \
                (len(request.prepath) == 3 and request.prepath[-1] == ''):
            d = self.db.runQuery("""
SELECT id, url, resource
FROM subscription sub WHERE """ + build_authcheck(request))
            d.addCallback(lambda x: self._done_subs(request, x))
            d.addErrback(makeErrback(request))
        else:
            when = int(time.time()) * 1000
            
            d = self.db.runQuery("""
SELECT m.tagval, s.uuid
FROM subscription sub, stream s, metadata2 m
WHERE """ + build_authcheck(request) + """ AND 
    tagname = 'Path' AND
    m.stream_id = s.id AND
    s.subscription_id = sub.id AND
    sub.id = %s 
""", (int(request.prepath[-1]), ))
            d.addCallback(lambda x: self._done_streams(request, x))
            d.addErrback(makeErrback(request))
        return server.NOT_DONE_YET

def build_inner_query(request, tags):
    """Build an "inner query" -- a query which yields a list of stream
    ids (indexes in the stream table).  These match the identifiers
    used in the reading db, or can be used as part of a join.  The
    query performs auth checks and will check for the tags specified.
    """
    clauses = []
    uuid_clause = "true"
    for (k, v) in tags:
        if k == 'uuid': 
            if v != None:
                uuid_clause = "s.uuid = '%s'" % sql.escape_string(v)
            continue
        if v != None:
            clauses.append("(tagname = '%s' AND tagval = '%s')" % (sql.escape_string(k),
                                                                   sql.escape_string(v)))
        else: break

    # the inner query builds a list of streams matching all the
    # clauses which we can then select from

    # perform the auth check in the inner query to give us the
    # most selectivity and avoid returning rows which the user
    # can't access.
    if len(clauses) == 0:
        inner_query = """
(SELECT s.id FROM stream s, subscription sub
 WHERE s.subscription_id = sub.id AND %s AND %s)""" % (
            build_authcheck(request), uuid_clause)
    else:
        inner_query = ("""
(SELECT oq.stream_id FROM
(SELECT stream_id, count(stream_id) AS cnt
FROM metadata2 mi, subscription sub, stream si
WHERE (%s) AND """ + build_authcheck(request) + """ AND
   mi.stream_id = si.id AND si.subscription_id = sub.id
GROUP BY stream_id) AS oq
WHERE oq.cnt = %i) AND %s""") % (' OR '.join(clauses), len(clauses), uuid_clause)
    return inner_query, clauses

def build_query(db, request, tags):
    """Will wrap a query which an appropriate selector to yield
    distinct tagnames, tagvals, or uuids depending on what is needed.
    """
    inner_query, clauses = build_inner_query(request, tags)

    if len(clauses) == 0 and len(tags) == 0:
        query = """
SELECT DISTINCT tagname
FROM metadata2 m, subscription sub, stream s
WHERE """ + build_authcheck(request) + """ AND
m.stream_id = s.id AND s.subscription_id = sub.id
ORDER BY tagname ASC"""
    elif tags[-1][0] == 'uuid':
        query = """
SELECT DISTINCT s.uuid 
FROM metadata2 AS m, stream AS s
WHERE m.stream_id IN """ + inner_query + """ AND
m.stream_id = s.id"""

    elif len(clauses) == 0:
        query = ("""
SELECT DISTINCT m.tagval FROM metadata2 m, stream s, subscription sub
WHERE m.tagname = '%s' AND """ + build_authcheck(request) + """ AND
m.stream_id = s.id AND s.subscription_id = sub.id
ORDER BY m.tagval ASC
""") % (tags[-1][0])
    elif tags[-1][1] == None or tags[-1][1] == '':
        query = ("""
SELECT DISTINCT m.tagval 
FROM metadata2 AS m
WHERE m.stream_id IN """ + inner_query + """ AND
m.tagname = '%s'
ORDER BY m.tagval ASC""") % (tags[-1][0])
    else:
        query = """
SELECT DISTINCT tagname
FROM metadata2 AS m
WHERE m.stream_id IN """ + inner_query + """
ORDER BY tagname ASC"""

    print query
    d = db.runQuery(query)
    return d

def build_tag_query(db, request, tags):
    """Wraps an inner query to select all tags for streams which match
    the tags query.
    """
    inner_query, clauses = build_inner_query(request, tags)
    query = """
SELECT s.uuid, m.tagname, m.tagval
FROM metadata2 m, stream s
WHERE m.stream_id IN """ + inner_query + """ AND
  m.stream_id = s.id
ORDER BY m.stream_id ASC"""
    print query
    return db.runQuery(query)


class Api(resource.Resource):
    """Provide api calls against the databases for data and tag lookups.
    """
    def __init__(self, db):
        self.db = db
        resource.Resource.__init__(self)

    def generic_extract_result(self, request, result):
        """Extract postgres results which are just wrapped with an extra
        list"""
        return request, map(operator.itemgetter(0), result)

    def tag_extract_result(self, request, result):
        """For a tag query, we want to return a nested dict so we pipe the
        result through this filter instead.
        """
        rv = {}
        for uid, tn, tv in result:
            if not uid in rv: rv[uid] = {}
            rv[uid][tn] = tv
            rv[uid]['uuid'] = uid
        return request, map(lambda x: util.build_recursive(x, suppress=[]), rv.values())

    def data_load_extract(self, result):
        return result[0][1][0], map(lambda x: x[1][1], result)
    
    def data_load_result(self, request, method, result):
        count = int(request.args.get('streamlimit', ['10'])[0])
        if count == 0:
            count = len(result)

        if len(result) > 0:
            callbacks = []
            for uid, stream_id in result[:count]:
                loader = DataRequester(uid)
                callbacks.append(loader.load_data(request, method, stream_id))
            d = defer.DeferredList(callbacks)
            d.addCallback(self.data_load_extract)
            return d
        else:
            return defer.succeed((request, []))

    def write_one_stream(self, request, stream, stags, mime_header=False):
        """For a CSV downlod, add some hweaders and write the data to the stream
        """
        writer = csv.writer(request)
        if 'tags' in request.args and not 'none' in request.args['tags']:
            request.write("# uuid: %s\n" % stream['uuid'])
            request.write("# DownloadTime: " + time.ctime() + "\n")
            request.write("# ")
            request.write('\n# '.join((': '.join(x) for x in stags)))
            request.write('\n')
        map(writer.writerow, stream['Readings'])

    def send_csv_reply(self, request, result, tags):
        """CSV replies are easy"""
        request.setHeader('Content-disposition', 'attachment; filename=%s.csv' % result[0]['uuid'])
        self.write_one_stream(request, 
                              result[0], 
                              sorted(map(operator.itemgetter(1,2), tags[0][1])))
        
        request.finish()

    def send_data_reply(self, (request, result)):
        """After reading back some data, format it and send it to the client
        """
        if not 'format' in request.args or 'json' in  request.args['format']:
            request.setHeader('Content-type', 'application/json')
            request.write(util.json_encode(result))
            request.finish()
        elif 'format' in request.args and 'csv' in request.args['format']:
            if len(result) > 1:
                request.setResponseCode(400)
                request.write("CSV only supported for one data stream")
                request.finish()
                return
            # return cvs
            request.setHeader('Content-type', 'text/csv')
            if 'tags' in request.args:
                dl = []
                for str in result:
                    dl.append(build_tag_query(self.db, request, [('uuid', str['uuid'])]))
                d = defer.DeferredList(dl)
                d.addCallback(lambda x: self.send_csv_reply(request, result, x))
                return d
            else:
                return self.send_csv_reply(request, result, [(False, [])] * len(result))
        else:
            request.setResponseCode(400)
            request.finish()

    def send_reply(self, (request, result)):
        """Send a generic json reply.
        """
        request.setHeader('Content-type', 'application/json')
        request.write(util.json_encode(result))
        request.finish()

    def getChild(self, name, request):
        # except for streams, all api resources specify a set of
        # streams using a query path.  therefore they all operate on
        # sets of streams.
        if name == 'streams':
            return SubscriptionResource(self.db)
        else:
            return self

    def render_POST(self, request):
        """The POST method is only used for sql-like queries.

        The logic for parsing the query, building the true SQL
        statement, and parsing out the results are in the queryparse
        and querygen modules.
        """
        # make a parser and parse the request
        parser = qp.QueryParser(request)
        query = request.content.read()
        ext, query, datagetter = parser.parse(query)

        # pipe the results through whatever filter is necessary
        if not ext and not datagetter:
            d = self.db.runOperation(query)
        else:
            d = self.db.runQuery(query)
        if ext:
            d.addCallback(lambda x: (request, ext(x)))
        else:
            d.addCallback(lambda x: (request, []))

        d.addCallback(self.send_reply)
        return server.NOT_DONE_YET

    def render_GET(self, request):
        """The GET method exposes a RESTful API to ARD functions.

        This lets clients look at tags and get data.
        """
        if len(request.prepath) == 1:
            return json.dumps({'Contents': ['streams', 'query', 'data', 
                                            'next', 'prev', 'tags']})
        # start by looking up the set of streams we are going to operate on
        path = map(lambda x: x.replace('__', '/'), request.prepath[2:])
        path = map(urllib.unquote, path)
        method = request.prepath[1]

        # dispatch based on the method name
        if method != 'query':
            if len(path) % 2 != 0:
                request.setResponseCode(400)
                request.finish()
                return server.NOT_DONE_YET
            path.append('uuid')            
        if method == 'query':
            # this allows a user to enumerate tags
            d = build_query(self.db,
                            request,
                            zip(path[::2], 
                                path[1::2] + [None]))
            d.addCallback(lambda r: self.generic_extract_result(request, r))
            d.addCallback(self.send_reply)
        elif method == 'tags':
            # retrieve tags
            d = build_tag_query(self.db,
                                request, 
                                zip(path[::2], 
                                    path[1::2] + [None]))
            d.addCallback(lambda r: self.tag_extract_result(request, r))
            d.addCallback(self.send_reply)
        elif method in ['data', 'next', 'prev']:
            # retrieve data
            d = self.db.runQuery("""SELECT uuid, id FROM stream WHERE
id IN """ + build_inner_query(request,
                              zip(path[::2], 
                                  path[1::2] + [None]))[0])
            d.addCallback(lambda r: self.data_load_result(request, method, r))
            d.addCallback(self.send_data_reply)
        else:
            request.setResponseCode(404)
            request.finish()
            return server.NOT_DONE_YET

        return server.NOT_DONE_YET

