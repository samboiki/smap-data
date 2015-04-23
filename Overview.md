# Introduction #

sMAP, the Simple Measurement and Actuation Profile is a simple specification for accessing data feeds from a variety of instruments using a JSON+HTTP -based protocol.  This google project hosts implementations of sMAP feeds for a variety of data sources using different backends.

Currently in use to expose data from the Cory Hall building monitoring project at UC Berkeley, live public feeds using this protocol are available to researchers.

# Version 2.0 #

We have started work on a detailed specification for version 2 and a python implementation is already available.  Python documentation is available here http://www.eecs.berkeley.edu/~stevedh/smap2/ and the design document is http://www.eecs.berkeley.edu/~stevedh/pubs/v2.pdf.

As of October 2011, we have implemented the key pieces of this specification, including reliable delivery, failover, a tag query engine, and numerous drivers for existing data sources.  Much of the data is available publicly through the http://new.openbms.org plotting interface.  Additionally, it's also possible to directly query the tag set and data using the ArdApi.