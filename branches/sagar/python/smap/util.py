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
import time
import re
import uuid
import errno
import cPickle as pickle
import ConfigParser
import traceback as trace

from twisted.internet import task, reactor, threads, defer
from twisted.python.lockfile import FilesystemLock
from twisted.python import log

import core

is_string = lambda x: isinstance(x, str) or isinstance(x, unicode)
is_integer = lambda x: isinstance(x, int) or isinstance(x, long)

def now():
    return int(time.time())

def split_path(path):
    path = re.split('/+', path)
    return filter(lambda x: len(x), path)

def join_path(path):
    return '/' + '/'.join(path)

norm_path = lambda x: join_path(split_path(x))

def str_path(s):
    """Make a string appropriate to be a path compnent"""
    return s.lower().replace(' ', '_').replace('/', '_')

def find(f, lst):
    for o in lst:
        if f(o): return o
    return None

def buildkv(fullname, obj, separator='/'):
    if isinstance(obj, dict):
        rv = []
        for newk, newv in obj.iteritems():
            if len(fullname):
                rv += buildkv(fullname + separator + newk, newv, separator)
            else:
                rv += buildkv(newk, newv, separator)
        return rv
    else:
        return [(fullname, obj)]

# make a nested object from a config file line
def build_recursive(d, suppress=['type', 'key', 'uuid']):
    rv = {}
    for k, v in d.iteritems():
        if k in suppress: continue
        pieces = k.split('/')
        cur = rv
        for cmp in pieces[:-1]:
            if not cur.has_key(cmp):
                cur[cmp] = {}
            cur = cur[cmp]
        cur[pieces[-1]] = v
    return rv

def dict_merge(o1, o2):
    """Recursively merge dict o1 into dict o2.  
    """
    if not isinstance(o1, dict) or not isinstance(o2, dict): 
        return o2
    o2 = dict(o2)
    for k, v in o1.iteritems():
        if k in o2:
            o2[k] = dict_merge(v, o2[k])
        else:
            o2[k] = v
    return o2

def dict_all(dlist):
    keys = set.intersection(*map(lambda x: set(x.iterkeys()), dlist))
    keys = dict(((k, None) for k in keys))
    for t in dlist[1:]:
        for k in keys.keys():
            if t[k] != dlist[0][k]:
                del keys[k]
    return dict(((k, dlist[0][k]) for k in keys.iterkeys()))
    
def flatten(lst):
    rv = []
    for l in lst:
        rv.extend(l)
    return rv

class FixedSizeList(list):
    """
    A class for keeping a circular buffer with a maximum size.
    Used for storing a fixed history of "profile" data.
    """
    def __init__(self, size=None, init=None, sort_profile=False, seqno=0):
        self.size = size
        self.seqno = seqno
        self.sort_profile = sort_profile
        if not init:
            init = []
        list.__init__(self, init)

    def __repr__(self):
        return "FixedSizeList(size=" + str(self.size) + \
            ", seqno=" + str(self.seqno) + ", init=" + \
            list.__repr__(self) + ")"

    def append(self, val):
        if self.sort_profile == True:
            # Find insert point in sorted list
            idx = bisect.bisect_left([r.time for r in self], val.time)
            # Ignore duplicate times
            if idx >= len(self) or self[idx].time != val.time:
                self.insert(idx, val)
            else:
                return False
        else:
            list.append(self, val)
            self.seqno += 1

        if self.size and len(self) > self.size:
            self.pop(0)

        return True

    def extend(self, val):
        list.extend(self, val)
        self.seqno += len(val)
        if self.size and len(self) > self.size:
            self.reverse()
            del self[self.size:]
            self.reverse()

    def truncate(self, seq):
        """Remove first n values from the list"""
        rmpt = seq - (self.seqno - len(self) )
        if rmpt >= 0:
            del self[:rmpt]

    def set_size(self, size):
        if len(self) > size:
            self.__delslice__(0, self.size  - size)
        self.size = size

    def idxtoseq(self, idx):
        return self.seqno - len(self) + idx

def pickle_load(filename):
    """Load an object from a gzipped pickle file while holding a
    filesystem lock
    """
#     lock = FilesystemLock(filename + ".lock")
#     if not lock.lock():
#         raise SmapException("Could not acquire report file lock")

    try:
        fp = open(filename, 'rb')
    except IOError:
#         lock.unlock()
        return None

    try:
        return pickle.load(fp)
    except (IOError, EOFError, pickle.PickleError), e:
        print e
        return None
    finally:
        fp.close()
#         lock.unlock()

def pickle_dump(filename, obj):
    """Pickle an object to a gzipped file while holding a filesystem
    lock.
    """
    if not filename:
        return

    try:
        fp = open(filename + '.tmp', 'wb')
        pickle.dump(obj, fp, protocol=2)
    except (IOError, pickle.PickleError, TypeError), e:
        print "dump failure"
        trace.print_exc()
        return
    finally:
        os.fsync(fp)
        fp.close()

    try:
        # move it atomically if we were able to pickle the object
        os.rename(filename + '.tmp', filename)
    except OSError, e:
        # Windows versions prior to Vista don't support atomic renames
        if e.errno != errno.EEXIST:
            raise
        os.remove(filename)
        os.rename(filename + '.tmp', filename)
    except IOError, e:
        trace.print_exc()
        pass

def periodicCallInThread(fn, *args):
    """Periodically enqueue a task to be run in the ``twisted``
threadpool (not in the main loop).  You'll need to call the
``start(interval)`` method on the return.  Multiple copies may run
concurrently, depending on the thread pool size if you do not finish
fast enough.

:param fn: the function to be called
:param args: arguments to be passed to `fn`
:rtype: the :py:class:`twisted.internet.task.LoopingCall` result
    """
    return task.LoopingCall(lambda: reactor.callInThread(fn, *args))

class PeriodicCaller:
    """The problem with doing a LoopingCall and then deferring to a
    thread is that you might have multiple copies of your function
    running simultaneously.  There are a variety of reasons this might
    be undesirable, so you can use this class instead, which will wait
    for a previous invocation to complete before running the next one.
    """
    def __init__(self, fn, args):
        self.fn, self.args = fn, args

    def _go(self):
        # bad things seem to happen when we throw an exception in the
        # thread pool... let's catch that and just log it
        try:
            self.fn(*self.args)
        except:
            log.err()
        
    def _run(self):
        self.last = time.time()
        d = threads.deferToThread(self._go)
        d.addCallbacks(self._post_run)

    def _post_run(self, result):
        now = time.time()
        sleep_time = self.interval - (now - self.last)
        if sleep_time < 0:
            self._run()
        else:
            reactor.callLater(sleep_time, self._run)

    def start(self, interval, now=True):
        self.interval = interval
        self.last = time.time()
        if now:
            self._run()
        else:
            reactor.callLater(self.interval, self._post_run, None)


def periodicSequentialCall(fn, *args):
    """Periodically run `fn(*args)` in a threadpool.  unlike
:py:func:`~smap.util.periodicCallInThread`, will not run your task
concurrently with itself -- if the last invocation didn't finish in
time for your next execution, it will wait rather than running it in a
different thread.

You also need to call `start(interval)` on the result.
    """
    return PeriodicCaller(fn, args)


def syncMaybeDeferred(fn, *args):
    """Version of maybeDeferred which calls fn(*args) immediately,
    rather than from the event loop as the library version does.
    """
    rv = fn(*args)
    if issubclass(rv.__class__, defer.Deferred):
        return state
    else:
        return defer.succeed(rv)

def import_module(modname):
    """Import a module named by a classic dotted-name"""
    cmps = modname.split('.')
    mod = __import__('.'.join(cmps[:-1]), globals(), locals(), [cmps[-1]]) 
    return getattr(mod, cmps[-1])


if __name__ == '__main__':
    import sys
    log.startLogging(sys.stdout)
    def cb(st):
        print "db running, sleeping", st
        raise Exception('foo')
        time.sleep(st)
    periodicSequentialCall(cb, 3).start(2.5)
    reactor.run()