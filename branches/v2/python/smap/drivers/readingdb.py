
import sys
import logging
import time
import threading
import socket
import json

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import task
# twisted doesn't support ipv6... this patches the reactor to add
# listenUDP6 and listenTCP6 methods.  It's not great, but it's a
# workaround that we can use and is easy to deploy (doesn't involve
# patching the twisted installation directory)
from tx.ipv6.internet import reactor

from smap.driver import SmapDriver

class Driver(SmapDriver, DatagramProtocol):
    fields = ['queries', 'adds', 'failed_adds',
	      'connects', 'disconnects', 'nearest']
    def setup(self, opts):
        self.port = int(opts.get('Port', '4243'))
	for f in self.fields:
            self.add_timeseries('/' + f, 'count')        

    def start(self):
        reactor.listenUDP6(self.port, self)

    def datagramReceived(self, data, addr):
        new = json.loads(data)
        for f in self.fields:
            self._add('/' + f, new[f])
