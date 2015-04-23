An enormous amount of _physical information_; that is, information from and about the world is available today as the cost of communication and instrumentation has fallen.  However, making use of that information is still challenging.  The information is frequently siloed into proprietary systems, available only in batch, fragmentary, and disorganized.  The **sMAP** project aims to change this by making available and usable:

  * a specification for transmitting physical data and describing its contents,
  * a large set of free and open drivers with communicating with devices using native protocols and transforming it to the sMAP profile, and
  * tools for building, organizing, and querying large repositories of physical data.

The pieces of the sMAP system are designed to separate concerns and allow users to, for instance, run their own web frontend while using hosted infrastructure for storing the actual data and metadata.
![http://smap-data.googlecode.com/svn/wiki/img/highlevel.png](http://smap-data.googlecode.com/svn/wiki/img/highlevel.png)

The core object in sMAP is the Timeseries, a single progression of (time, value) tuples.  Each Timeseries in sMAP is identified by a UUID, and can be tagged with metadata; all grouping of time series occurs using these tags.  These objects are exchanged between all components in this ecosystem.

# Instrument Drivers #
The first, essential piece of sMAP is a library for writing drivers.  These drivers connect to existing instrumentation and provide tools for exposing the data over http/sMAP.  The library and protocol are designed to support various common scenarios:

  * Intermittent connectivity: provide local buffering
  * Local metadata: apply tags at the source
  * Bulk loading and real-time: support both bulk-loads from existing databases and real-time data from streaming or polling sources in the same framework.
  * Actuation (using SSL)

![http://smap-data.googlecode.com/svn/wiki/img/smap.png](http://smap-data.googlecode.com/svn/wiki/img/smap.png)

Information about available drivers is in DriverIndex, and a tutorial on using the sMAP library is available in [pydoc](http://www.eecs.berkeley.edu/~stevedh/smap2/).

# Repository #
The repository gives drivers a place for instruments to send their data.  It supports

  * Efficient storage and retrieval of time-series data
  * Maintenance of metadata using structured key-value pairs
  * Metadata querying using the ArdQuery language

# Front-end #
Most systems provide some amount of dashboarding and plotting.  Out of the box, the **powerdb** project provides plotting and organization of time-series data, built on top of the ArdApi.  Due to the decoupled nature of the design, this front-end can be run by anyone.  The application is designed to give users a large amount of flexibility to organize, display and plot streams using ArdQuery to generate tree views of their streams using the SlicrApi.

You can see a running instance [here](http://new.openbms.org) with lots of real data!

# Getting Started #

To install the whole system, including drivers, repository, and front-end, follow the instructions in ArchiverInstallation.  This should just take a few minutes on a modern Ubuntu system!

You can also take a look at the DriverIndex to see if there is already a data source available for your system.

# More Information #

This project is supported through the [LoCal](http://local.cs.berkeley.edu) project at UC Berkeley.  See also our [Resources](Resources.md) page for more information about sMAP itself.

# Mailing List #

You can subscribe to **smap-users**, a list for questions and announcements at https://lists.eecs.berkeley.edu/sympa/info/smap-users

# Support #

sMAP receives support from the NSF under grants [CPS-0932209 (LoCal)](http://www.nsf.gov/awardsearch/showAward.do?AwardNumber=0932209), [CPS-0931843 (ActionWebs)](http://www.nsf.gov/awardsearch/showAward.do?AwardNumber=0931843), and [CPS-1239552 (SDB)](http://www.nsf.gov/awardsearch/showAward?AWD_ID=1239552).  In addition, we are the recipient of a [Energy and Climate Research Innovation Seed Fund](http://vcresearch.berkeley.edu/energy/innovation-seed-fund) grant.