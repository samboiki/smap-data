# Introduction #

The recommended way to install the entire backend is using Debian packages.  The process has been tested on Ubuntu 11.10 and 12.04, although it will probably work on other similar distributions.  It contains stable version of the sMAP system.  If an Ubuntu machine is not available, or you wish to install the system manually, please read ArchiverManualInstall.

## Resources ##
  1. You can see a screencast of this process [here](http://windows.lbl.gov/smap/video/smap_installation.mov), contributed by Christian Kohler.
  1. Another installation option is an experimental [vm image](http://jackalope.cs.berkeley.edu/~stevedh/Ubuntu-11.10-smap-444.ova) [1.6G].  It has Ubuntu 11.10 installed; the username/password is ubuntu/reverse, and the login for the sMAP admin page is root/reverse.

# Automated Install #

If you are on Ubuntu oneiric (11.10) or precise (12.04), you can add our package repository using
```
$ sudo add-apt-repository ppa:stevedh/smap
$ sudo apt-get update
```

The archive is here (https://launchpad.net/~stevedh/+archive/smap).

You can then install the entire system using apt:

```
$ sudo apt-get install readingdb readingdb-python python-smap powerdb2 monit
```

You will be prompted to create a django admin account during this installation.

After installation completes, you should tweak `monit`'s configuration: open `/etc/monit/monitrc`, and ensure the following three lines are uncommented:
```
set httpd port 2812 and
    use address localhost
    allow localhost 
```
After doing this, restart monit: `sudo /etc/init.d/monit restart`.

The Debian packages will automatically setup and start all required services, with the exception of the web frontend.  They install an apache site called `powerdb2`; if you are not running anything else on your server you can enable it by doing the following; if you have multiple sites you may want to edit the site to add a `ServerName` or `ServerAlias`.

```
$ sudo a2dissite default
$ sudo a2ensite powerdb2
$ sudo service apache2 reload
```

Following this step, you should be able to visit "http://localhost" in your browser and see the front end.  You will also have access to "http://localhost/admin", through which you can manage API keys and the trees visible in the plotting front-end.

## Sending data ##

Once everything is running, you'll want to create a feed and send it to your installation.  Go to `http://localhost/admin`, and log in with the superuser account you've created.  You can then add a new subscription, which will generate an API key; it will be visible as a random 36-character string.

Then create a configuration file called `conf.ini` with the following contents; replace the `<MY NEW KEY>` with the value you generated on the web page.
```
[report 0]
ReportDeliveryLocation = http://localhost:8079/add/<MY NEW KEY>

[/]
Metadata/SourceName = Example sMAP Source
uuid = 4a1ed488-a458-11e1-91af-00508dca5a06

[/example]
type = smap.drivers.example.Driver
```

You'll then be able to start the source with a
```
$ twistd -n smap conf.ini
```

After a few moments, you should see some data being sent to your local server, and then be able to find it on the plotting web page.

# Next Steps #

If you've gotten this far, you have the entire backend running.  You'll want to explore and extend this in a couple of different ways.  For instance, you could

  * Explore making [ArdQuery](http://code.google.com/p/smap-data/wiki/ArdQuery) queries against your backend.  Just fire up `smap-query -u http://localhost:8079/api/query` on your machine.
  * Check out how to write your own sMAP source in the [tutorial](http://www.eecs.berkeley.edu/~stevedh/smap2/tutorial.html)
  * Create some new slices on your data in the frontend using SlicrApi
  * Build your own dashboard or other frontend using **powerdb2** as a template