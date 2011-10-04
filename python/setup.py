
from distutils.core import setup, Extension

# build modbus extension module
modbus_module = Extension('smap.iface.modbus._TCPModbusClient',
                          sources=map(lambda f: "smap/iface/modbus/" + f,
                                      ["TCPModbusClient_wrap.c", "TCPModbusClient.c",
                                       "utility.c", "crc16.c", "DieWithError.c",
                                       "HandleModbusTCPClient.c"]))

setup(name="Smap",
      version="2.0.79",
      description="sMAP standard library and drivers",
      author="Stephen Dawson-Haggerty",
      author_email="stevedh@eecs.berkeley.edu",
      url="http://cs.berkeley.edu/~stevedh/smap2/",
      packages=[
        # core sMAP libs and drivers
        "smap", 
        "smap.drivers", 
        "smap.contrib",

        # smap archiver components
        "smap.archiver",

        "twisted", "twisted.plugins",

        # interfaces for talking to different backends
        "smap.iface", "smap.iface.http", "smap.iface.modbus",

        # hack to support ipv6 sockets -- needed for acme, at least
        "tx", "tx.ipv6", "tx.ipv6.application", "tx.ipv6.internet",

        # various extra divers and dependencies -- might want to leave this out on mainline
        "smap.drivers.obvius",
        # packages for the acme driver -- don't install this in trunk/
        "smap.drivers.acmex2", "tinyos", "tinyos.message",
        ],
      requires=["avro", "twisted", "ordereddict", "ply"],
      package_dir={"smap" : "smap"},
      package_data={"smap" : ['schema/*.av']},
      ext_modules=[modbus_module],
      scripts=['bin/jprint', 'bin/uuid', 'bin/smap-query'])
