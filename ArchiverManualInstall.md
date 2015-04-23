# Manual Install #

Installing the archiver has a few steps, which aren't very well automated at the moment.  They are

  1. Install **readingdb**, the time-series database.,
  1. Install and set up postgres, and populate it with the necessary tables.
  1. Install the python dependancies for the archiver.

This assumes you're running debian or maybe ubuntu.  For other distributions, the dependancies will be the same, but how you install them is probably different.


The repository homepage can be found here: https://launchpad.net/~stevedh/+archive/smap

## Install **readingdb** ##

The easiest way to install readingdb on ubuntu is using the package repository.  Just do a
```
$ apt-get install readingdb readingdb-python monit
```

Monit is a service manager which can keep a lot of our services running.  Once you've done this, do a `monit reload`, and you should see **readingdb** started before long.

Alternatively, you can build and install readingdb from source using the instructions at https://github.com/stevedh/readingdb

## Get the sMAP Archiver Source ##

At the moment, you should start from svn by following the checkout instructions.  You will want to check out both the sMAP distribution and the powerdb projects:

```
$ svn checkout http://smap-data.googlecode.com/svn/trunk/ smap-data-read-only
$ svn checkout http://smap-data.googlecode.com/svn/branches/powerdb2/ powerdb2
$ cd smap-data-read-only/python
$ sudo python setup.py install
```

## Setup postgres ##

Follow the instructions for your operating system to install postgres.  You may have to change `listen_addresses`, and may wish to adjust `shared_buffers` to increase the size of the buffer pool.  You probably also want to turn `autovacuum` on to avoid badness.

Once you've done this, create an account and database for the archiver.  Let's say (logged in as root),

```
CREATE USER archiver WITH PASSWORD 'password';
CREATE DATABASE archiver WITH owner = archiver;
```

## Install Python Dependencies ##

You'll need python dependencies for both the archiver and the powerdb project:

  * twisted
  * zope.interface
  * avro
  * ply
  * psycopg2
  * python-dateutil
  * ordereddict
  * django 1.4
  * numpy
  * scipy

I recommend installing all of these except for numpy and scipy using  `easy_install`, from pypi.  The versions from pypi are managed by the individual teams and are usually more up-to-date.

### Notes ###
  1. The avro packages are a bit messed up due to dependencies on snappy.  I recommend installing it without dependencies using `easy_install -N avro`.

## Setup **powerdb2** and the database ##

PowerDB provides the web frontend for viewing your data.  Although you can use smap drivers and the archiver without it, it provides a convenient interface for managing api keys and looking at data.

In `powerdb2/`, edit `settings.py` to point to your databases.  For instance:

```
DATABASE_ENGINE = 'postgresql_psycopg2' 
DATABASE_NAME = 'archiver'                                                        
DATABASE_USER = 'archiver'                                    
DATABASE_PASSWORD = 'password'                                                            
DATABASE_HOST = 'localhost' 
```

Once you've done this, you should go ahead and create the django admin tables.  This creates all the tables needed by the archiver, so even if you're not planning on using **powerdb2**, you should still do this; alternatively the raw sql is located in `smap-data/python/smap/archiver/sql`.
```
$ python manage.py syncdb
```
Make sure you create a superuser account when prompted; if you're not prompted, run `python manage.py createsuperuser`.

## Setup and run archiver ##

Edit the `python/conf/archiver.ini` file to have the correct postgres and readingdb databases.  If everything is running on the same machine, you shouldn't need to change much.

Now, you should be able to run the archiver using twistd (remove the "-n" to daemonize).

```
$ twistd -n smap-archiver -c python/conf/archiver.ini
2012-01-04 22:37:43-0800 [-] Log opened.
2012-01-04 22:37:43-0800 [-] twistd 11.1.0 (/usr/bin/python 2.6.6) starting up.
2012-01-04 22:37:43-0800 [-] Site starting on 8079
2012-01-04 22:37:43-0800 [-] Starting factory <twisted.web.server.Site instance at 0x2aacdd0>
```

## Start **powerdb2** ##

You should now edit `powerdb2/settings.py` so that the `ARD_URL` points to your copy of the archiver.  Once this is done, start the development server:

```
$ cd powerdb2
$ python manage.py runserver 0.0.0.0:8000
```


## Running **powerdb2** in Apache ##

It's not recommended to use the django server for production use.  Apache works well and is easy to configure.  To install your project in apache, you just need to do a few things.  These steps are for an apache install where this is the only site; if you have other sites you may need to alter these steps.

  1. Install the apache wsgi module: `$ apt-get install libapache2-mod-wsgi libapache2-mod-python`
  1. Enable the apache modules: `$ a2enmod proxy_http wsgi python`
  1. Disable the default site: `$ a2dissite default`
  1. Collect static files: in the powerdb/ directory, do `$ python manage.py collectstatic`
  1. Edit `/etc/apache2/mods-enabled/proxy.conf` and enable reverse proxying; you you can just comment out the line starting with `ProxyRequests` and the whole `<Proxy>` section.
  1. Create an apache2 site.  Here is my `/etc/apache2/sites-available/001-powerdb2` file; you'll need to edit the absolute paths to point at your copy of powerdb2.
```
 <VirtualHost *:80>
        # statically serve media files
        Alias "/media" "/mnt/md0/django/smap2/powerdb2/static/"

        # reverse proxy the backend through a failover pool
        ProxyPass "/backend" http://locahost:8079

        # serve the django project using WSGI
        WSGIScriptAlias / /mnt/md0/django/smap2/powerdb2/django.wsgi
        
        # make sure to enable gzip responses
        SetOutputFilter DEFLATE
        SetEnvIfNoCase Request_URI \
        \.(?:gif|jpe?g|png)$ no-gzip dont-vary
        # Make sure proxies don't deliver the wrong content
</VirtualHost>
```
  1. Finally, enable the site: `a2ensite powerdb2` and restart apache: `/etc/init.d/apache2 reload`.