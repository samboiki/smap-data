"""
Copyright (c) 2011, 2012, Regents of the University of California
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions 
are met:

 - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 - Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL 
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES 
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, 
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
OF THE POSSIBILITY OF SUCH DAMAGE.
"""
"""
@author Stephen Dawson-Haggerty <stevedh@eecs.berkeley.edu>
"""

import os
import operator
import time
import inspect
import logging
import collections

from twisted.internet import defer

from smap import operators
from smap.util import build_recursive, is_string
from smap import sjson as json
from smap.contrib import dtutil

import querygen as qg
from data import escape_string
from querydata import extract_data
import data
import stream
import help

import ply
import ply.lex as lex
import ply.yacc as yacc
import copy

tokens = (
    'HAS', 'AND', 'OR', 'NOT', 'LIKE', 'DISTINCT', 'STAR',
    'LPAREN', 'RPAREN', 'COMMA', 'TAGS', 'SELECT', 'WHERE',
    'QSTRING', 'EQ', 'NUMBER', 'LVALUE', 'IN', 'DATA', 'DELETE',
    'SET', 'TILDE', 'BEFORE', 'AFTER', 'NOW', 'LIMIT', 'STREAMLIMIT',
    'APPLY', 'TO', 'AS', 'GROUP', 'BY', 'HELP', 'OPSEP',
    )

precedence = (
    ('left', 'LIKE', 'TILDE', 'IN'),
    ('left', 'AND'),
    ('left', 'OR'),
    ('right', 'EQ'),
    ('right', 'NOT'),
    ('left', 'COMMA')
    )

reserved = {
    'where' : 'WHERE',
    'distinct' : 'DISTINCT',
    'select' : 'SELECT',
    'delete' : 'DELETE',
    'set' : 'SET',
    'tags' : 'TAGS',
    'has' : 'HAS',
    'and' : 'AND',
    'or' : 'OR',
    'not' : 'NOT',
    'like' : 'LIKE',
    'data': 'DATA',
    'in' : 'IN',
    'before' : 'BEFORE',
    'after' : 'AFTER',
    'now' : 'NOW',
    'limit' : 'LIMIT',
    'streamlimit' : 'STREAMLIMIT',
    '~' : 'TILDE',
    'apply' : 'APPLY',
    'to' : 'TO',
    'as' : 'AS',
    'group' : 'GROUP',
    'by' : 'BY',
    'help' : 'HELP',
    }

t_LPAREN = r'\('
t_RPAREN = r'\)'
t_STAR = r'\*'
t_COMMA = r','
t_OPSEP = r'<'

def t_QSTRING(t):
    r'("[^"\\]*?(\\.[^"\\]*?)*?")|(\'[^\'\\]*?(\\.[^\'\\]*?)*?\')'    
    if t.value[0] == '"':
        t.value = t.value[1:-1].replace('\\"', '"')
    elif t.value[0] == "'":
        t.value = t.value[1:-1].replace("\\'", "'")
    return t

t_EQ = r'='

def t_LVALUE(t):
    r'[a-zA-Z\~\$\_][a-zA-Z0-9\/\%_\-]*'
    t.type = reserved.get(t.value, 'LVALUE')
    return t


def t_NUMBER(t):
    r'([+-]?([0-9]*\.)?[0-9]+)'
    if '.' in t.value:
        try:
            t.value = float(t.value)
        except ValueError:
            print "Invalid floating point number", t.value
            t.value = 0
    else:
        try:
            t.value = int(t.value)
        except ValueError:
            print "Integer value too large %d", t.value
            t.value = 0
        
    return t

t_ignore = " \t"
def t_newline(t):
    r'[\n\r]+'
    t.lexer.lineno += t.value.count("\n")

def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)

smapql_lex = lex.lex()

# precedence = ('and')
names = {}

def ext_default(x):
    return map(operator.itemgetter(0), x)

def ext_deletor(x):
    data.del_streams(map(operator.itemgetter(0), x))
    return map(operator.itemgetter(1), x)

def ext_plural(tags, vals):
    return [build_recursive(dict(zip(tags, v)), suppress=[]) for v in vals]

def ext_recursive(vals):
    return [build_recursive(x[0], suppress=[]) for x in vals]

TIMEZONE_PATTERNS = [
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    ]
def parse_time(ts):
    for pat in TIMEZONE_PATTERNS:
        try:
            dt = dtutil.strptime_tz(ts, pat, tzstr='America/Los_Angeles')
            return dtutil.dt2ts(dt) * 1000
        except ValueError:
            continue
    raise ValueError("Invalid time string:" + ts)

def make_select_rv(t, sel, wherestmt='true'):
    return sel.extract, ("""SELECT %s FROM stream s, subscription sub
              WHERE (%s) AND (%s) AND
              sub.id = s.subscription_id""" % (sel.select, 
                                               wherestmt,
                                               qg.build_authcheck(t.parser.request)))

# top-level statement dispatching
def p_query(t):
    '''query : SELECT selector WHERE statement
             | SELECT selector
             | SELECT data_clause WHERE statement
             | DELETE tag_list WHERE statement
             | DELETE WHERE statement
             | SET set_list WHERE statement
             | APPLY apply_statement
             | HELP
             | HELP LVALUE
             '''
    if t[1] == 'select': 
        if len(t) == 5:
            t[0] = make_select_rv(t, t[2], t[4])
        elif len(t) == 3:
            t[0] = make_select_rv(t, t[2])
        
    elif t[1] == 'delete':
        # a new delete inner statement enforces that we only delete
        # things which we have the key for.
        if t[2] == 'where':
            # delete the whole stream, gone.  this also deletes the
            # data in the backend readingdb.
            return
            t[0] = ext_deletor, \
                """DELETE FROM stream s WHERE id IN %s
                   RETURNING s.id, s.uuid
                """ % delete_inner
        else:
            # this alters the tags but doesn't touch the data
            del_tags = ', '.join(map(escape_string, t[2]))
            q = "UPDATE stream SET metadata = metadata - ARRAY[" + del_tags + \
                "] WHERE id IN " + \
                "(SELECT s.id FROM stream s, subscription sub " + \
                "WHERE (" + t[4] + ") AND s.subscription_id = sub.id AND " + \
                qg.build_authcheck(t.parser.request, forceprivate=True)  + ")"
            t[0] = None, q

    elif t[1] == 'set':
        #  set tags 
        new_tags = ' || '.join(map(lambda (t,v): "hstore(%s, %s)" % 
                                   (escape_string(t), escape_string(v)),
                               t[2]))
        q = "UPDATE stream SET metadata = metadata || " + new_tags + \
            " WHERE id IN "  + \
            "(SELECT s.id FROM stream s, subscription sub " + \
            "WHERE (" + t[4] + ") AND s.subscription_id = sub.id AND " + \
            qg.build_authcheck(t.parser.request, forceprivate=True)  + ")"
        t[0] = None, q

    elif t[1] == 'apply':
        t[0] = t[2]
    elif t[1] == 'help':
        if len(t) == 2:
            t[0] = help.help(), None
        else:
            t[0] = help.help(t[2]), None

# apply a sequence of operators to data
def p_apply_statement(t):
    """apply_statement  : operator_list TO data_clause WHERE statement_as_list
                        | operator_list TO data_clause WHERE statement_as_list GROUP BY tag_list
    """
    tag_extractor, tag_query = make_select_rv(t, make_tag_select('*'), t[5][0][1])
    _, data_query = make_select_rv(t, t[3], t[5][0][1])

    # this does not make me feel good.
    
    data_extractor = lambda x: x
    if len(t) > 7: group = t[8]
    else: group = None
    app = stream.OperatorApplicator(t[1], t[3].dparams,
                                    t.parser.request, group=group)
    print tag_query
    t[0] = [app.start_processing, tag_extractor, data_extractor], [None, tag_query, data_query]


selector = collections.namedtuple('selector', 'select extract')
def make_tag_select(tagset):
    if '*' in tagset:
        return selector("s.metadata || hstore('uuid', s.uuid)", ext_recursive)
    else:
        if 'uuid' in tagset:
            tagset.add('Path')
        def make_clause(x):
            if x == 'uuid':
                return "(s.uuid)"
            else:
                return "(s.metadata -> %s)" % escape_string(x)
    tags = list(tagset)
    select = ', '.join(map(make_clause, tags))
    return selector(select, lambda vals: ext_plural(tags, vals))

# make a tag selector: the things to select.  this is how you specify
# what tags you want back.
def p_selector(t):
    '''selector : tag_list
                | STAR
                | DISTINCT LVALUE
                | DISTINCT TAGS'''
    if t[1] == 'distinct':
        if t[2] == 'uuid':
            t[0] = selector("DISTINCT s.uuid", ext_default)
        else:
            t[0] = selector("DISTINCT (s.metadata -> %s)" % escape_string(t[2]),
                            ext_default)
    else:
        t[0] = make_tag_select(t[1])

data_selector = collections.namedtuple("data_selector", "select extract dparams")
# make a data selector: what data to load.
def p_data_clause(t):
    '''data_clause : DATA IN LPAREN timeref COMMA timeref RPAREN limit
                   | DATA BEFORE timeref limit
                   | DATA AFTER timeref limit'''
    if t[2] == 'in':
        method = 'data'
        start, end = t[4], t[6]
        limit = t[8]
        if limit[0] == None: limit[0] = 10000
    elif t[2] == 'before':
        method = 'prev'
        start, end = t[3], 0
        limit = t[4]
        if limit[0] == None: limit[0] = 1
    elif t[2] == 'after':
        method = 'next'
        start, end = t[3], 0
        limit = t[4]
        if limit[0] == None: limit[0] = 1

    t.parser.request.args.update({
        'starttime' : [start],
        'endtime' : [end],
        'limit' : [limit[0]],
        'streamlimit' : [limit[1]],
        })

    t[0] = data_selector("distinct(s.uuid), s.id",
                         lambda streams: data.data_load_result(t.parser.request,
                                                               method,
                                                               streams,
                                                               ndarray=False,
                                                               as_smapobj=True,
                                                               send=True), {
            'start' : start,
            'end' : end,
            'method' : method,
            'chunk': None,
            'limit' : limit })

# a time reference point.  can be a unix timestamp, a date string, or
# "now"
def p_timeref(t):
    '''timeref : NUMBER 
               | QSTRING
               | NOW'''
    if t[1] == 'now':
        t[0] = int(time.time()) * 1000
    elif type(t[1]) == type(''):
        t[0] = parse_time(t[1])
    else:
        t[0] = t[1]

# limit the amount of data returned by number of streams and number of
# points
def p_limit(t):
    '''limit : 
             | LIMIT NUMBER
             | STREAMLIMIT NUMBER
             | LIMIT NUMBER STREAMLIMIT NUMBER'''
    limit, slimit = [None, 10]
    if len(t) == 1:
        pass
    elif t[1] == 'limit':
        limit = t[2]
        if len(t) == 5:
            slimit = t[4]
    elif t[1] == 'streamlimit':
        slimit = t[2]
    t[0] = [limit, slimit]

def p_operator_list(t):
    """operator_list   : priv_operator_list"""
    if len(t[1]) > 1:
        t[0] = operators.make_composition_operator(t[1])
    else:
        t[0] = t[1][0]


def p_priv_operator_list(t):
    '''priv_operator_list   : apply_operator
                            | apply_operator OPSEP priv_operator_list'''
    if len(t) == 2:
        t[0] = [t[1]]
    else:
        t[3].append(t[1])
        t[0] = t[3]

# apply operators
def p_apply_operator(t):
    '''apply_operator   : LVALUE LPAREN arg_list RPAREN
                        | LPAREN apply_operator RPAREN
                        | LVALUE
    '''
    if len(t) == 2:
        t[0] = stream.get_operator(t[1], empty_arg_list())
    elif len(t) == 5:
        t[0] = stream.get_operator(t[1], t[3])
    else:
        t[0] = t[2]

def empty_arg_list():
    return (list(), dict())

def p_arg_list(t):
    '''arg_list     : 
                    | call_argument
                    | call_argument COMMA arg_list
                     '''
    if len(t) == 1:
        t[0] = empty_arg_list()
        return
    if len(t) == 2:
        alist = empty_arg_list()
    else:
        alist = t[3]

    if t[1][0] == 'arg':
        alist[0].reverse()
        alist[0].append(t[1][1])
        alist[0].reverse()
    elif t[1][0] == 'kwarg':
        alist[1].update(t[1][1])
    t[0] = alist
        
def p_call_argument(t):
    '''call_argument   : QSTRING
                       | NUMBER
                       | LVALUE EQ NUMBER
                       | LVALUE EQ QSTRING
                       | operator_list '''
    if len(t) == 4:
        t[0] = ('kwarg', {
            t[1] : t[3]
            })
    else:
        t[0] = ('arg', t[1])

def p_tag_list(t):
    '''tag_list : LVALUE
                | LVALUE COMMA tag_list'''
                
    if len(t) == 2:
        t[0] = set([t[1]])
    else:
        t[3].add(t[1])
        t[0] = t[3]

def p_set_list(t):
    '''set_list : LVALUE EQ QSTRING
                | LVALUE EQ QSTRING COMMA set_list'''
    if len(t) == 4:
        t[0] = [(t[1], t[3])]
    else:
        t[0] = [(t[1], t[3])] + t[5]

def p_statement_as_list(t):
    """statement_as_list   : statement
                           | statement AS LVALUE
                           | statement_as_list COMMA statement
                           | statement_as_list COMMA statement AS LVALUE 
                           """
    if len(t) == 2:
        t[0] = [('$1', t[1])]
    elif len(t) == 4 and t[2] == 'as':
        t[0] = [(t[3], t[1])]
    elif len(t) == 4 and t[2] == ',':
        t[0] = t[1] + [("$%i" % (len(t[1]) + 1), t[3])]
    else:
        t[0] = t[1] + [(t[5], t[3])]

def p_statement(t):
    '''statement : statement_unary
                 | statement_binary
                 | LPAREN statement RPAREN
                 | statement AND statement
                 | statement OR statement
                 | NOT statement
                '''
    if len(t) == 2:
        t[0] = t[1]
    elif t[2] == 'and':
        t[0] = '(%s) AND (%s)' % (t[1], t[3])
    elif t[2] == 'or':
        t[0] = '(%s) OR (%s)' % (t[1], t[3])
    elif t[1] == 'not':
        t[0] = 'NOT (%s)' % t[2]
    else:
        t[0] = t[2]

def p_statement_unary(t):
    '''statement_unary : HAS LVALUE'''
    if t[1] == 'has':
        t[0] = 's.metadata ? %s' % escape_string(t[2])

def p_statement_binary(t):
    '''statement_binary : LVALUE EQ QSTRING
                        | LVALUE LIKE QSTRING
                        | LVALUE TILDE QSTRING
    '''
    if t[1] == 'uuid':
        t[0] = 's.uuid %s %s' % (t[2], escape_string(t[3]))
    else:
        if t[2] == '=':
            t[0] = "s.metadata @> hstore(%s, %s)" % (escape_string(t[1]), escape_string(t[3]))
        elif t[2] == 'like':
            t[0] = "(s.metadata -> %s) LIKE %s" % (escape_string(t[1]), escape_string(t[3]))
        elif t[2] == '~':
            t[0] = "(s.metadata -> %s) ~ %s" % (escape_string(t[1]), escape_string(t[3]))


def p_error(t):
    raise qg.QueryException("Syntax error at '%s'" % t.value, 400)

smapql_parser = yacc.yacc(tabmodule='arq_tab',
                          outputdir=os.path.dirname(__file__),
                          debugfile='/dev/null',
                          debuglog=logging.getLogger('ply-debug'),
                          errorlog=logging.getLogger('ply-errors'))

def parse_opex(exp):
    global opex_parser
    try:
        opex_parser
    except NameError:
        opex_parser = yacc.yacc(start="operator_list", 
                                tabmodule='opex_tab.py',
                                debugfile='/dev/null',
                                debuglog=logging.getLogger('ply-debug'),
                                errorlog=logging.getLogger('ply-errors'))
    return opex_parser.parse(exp)

class QueryParser:
    """Class to manage parsing and extracting results from the
    database and readingdb"""
    def __init__(self, request): 
        self.parser = copy.copy(smapql_parser)
        self.parser.request = request

    def parse(self, s):
        return self.parser.parse(s, lexer=smapql_lex)

    def runquery(self, db, s, run=True, verbose=False):
        ext, q = self.parse(s)
        if is_string(ext):
            return defer.succeed(ext)
        elif not isinstance(q, list):
            q = [None, q]
            ext = [None, ext]

        if verbose: print q
        if not run: return defer.succeed([])
        
        def eb(error):
            print error
        deferreds = []

        for ext_, q_ in zip(ext[1:], q[1:]):
            if not ext_:
                d = db.runOperation(q_)
                d.addCallback(lambda _: [])
            else:
                d = db.runQuery(q_)
                d.addCallback(ext_)

            d.addErrback(eb)
            deferreds.append(d)

        if len(deferreds) > 1:
            d = defer.DeferredList(deferreds)
            if ext[0]:
                d.addCallback(ext[0])
        else:
            d = deferreds[0]

        return d


if __name__ == '__main__':
    import os
    import readline
    import traceback
    import sys
    import pprint
    import settings as s
    import data
    import atexit
    from twisted.internet import reactor
    from twisted.enterprise import adbapi
    from optparse import OptionParser

    logging.basicConfig()

    # pull out options
    usage = "usage: %prog [options] archiver-config.ini"
    parser = OptionParser(usage=usage)
    parser.add_option("-n", "--no-action", dest="run", 
                      action="store_false", default=True,
                      help="don't perform queries")
    parser.add_option("-v", "--verbose", dest="verbose", 
                      action="store_true", default=False,
                      help="print generated SQL")
    parser.add_option("-k", "--keys", dest="keys",
                      default="",
                      help="comma-separated list of keys to use in query")
    parser.add_option("-p", "--private", dest="private",
                      default=False, action="store_true",
                      help="request only private results")
    opts, args = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)

    s.load(args[0])
    s.import_rdb()

    # set up readline
    HISTFILE = os.path.expanduser('~/.smap-query-history')
    readline.parse_and_bind('tab: complete')
    readline.parse_and_bind('set editing-mode emacs')
    if hasattr(readline, "read_history_file"):
        try:
            readline.read_history_file(HISTFILE)
        except IOError:
            pass
    atexit.register(readline.write_history_file, HISTFILE)

    cp = adbapi.ConnectionPool(s.DB_MOD,
                               host=s.DB_HOST,
                               database=s.DB_DB,
                               user=s.DB_USER,
                               password=s.DB_PASS,
                               port=int(s.DB_PORT),
                               cp_min=5, cp_max=15)

    # make a fake request to give the parser with whatever
    # command-line options we need.
    class Request(object):
        def write(self, data):
            print "got data", data

        def finish(self):
            print "data done"

        def registerProducer(self, a1, a2):
            pass

        def unregisterProducer(self):
            pass

    request = Request()
    args = {}
    if opts.keys: args['key'] = opts.keys.split(',')
    if opts.private: args['private'] = []
    setattr(request, 'args', args)

    # make a parser and start reading from the console
    qp = QueryParser(request)

    def readquery():
        try:
            s = raw_input('query > ')   # Use raw_input on Python 2
            if s == '': 
                return readquery()
        except EOFError:
            return reactor.callFromThread(reactor.stop)
        except:
            traceback.print_exc()
            return readquery()
            
        # print  parse_opex(s)
        d = qp.runquery(cp, s, verbose=opts.verbose, run=opts.run)
        d.addCallback(lambda v: pprint.pprint(v))
        d.addCallback(lambda x: readquery())
        return d

    d = readquery()
    reactor.run()

    cp.close()
