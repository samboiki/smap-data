# Introduction #
It is desirable to use SSL to secure sMAP in several places; for authenticating clients when using actuation; or for providing privacy when reporting data over a public connection.

# Creating a PKI #
A pre-requisite for using SSL is to configure a public-key infrastructure (PKI).  The details of how to use this are beyond the scope of this tutorial, but typically involves using [openssl](http://www.openssl.org/) to create a set of certificates and keys which are then used by sMAP servers and clients to secure communication and authenticate users.

For the purposes of this example, we'll assume you've created a sample PKI as shown below.  Note that this isn't really what you want in production unless you only have a small number of mutually-trusting users.  I generated these using [xca](http://sourceforge.net/projects/xca/), a gui on top of `openssl`.

```
- sMAP Root Signing Key and Certificate (root.pem, root.crt)
| - sMAP Server 1 key (server1.pem) and cert (server1.crt)
| - sMAP Client 1 key (client1.pem) and cert (client1.crt)
```

# Securing a sMAP Daemon #

sMAP daemons support running over HTTP, HTTPS, or both.  You can enable SSL by including three additional configuration options in the `[server]` section of the daemon config file.  For instance:

```
[server]
# port = 8082
sslport = 8000
cert = server1.crt
key = server1.pem
ca = root.crt
# verify = true
```

In this example, the server will run an HTTPS server on port 8000.  Since `verify` is commented-out, it will not verify any client certificates, so any HTTPS client will be allowed.  In this case, the server provides data privacy but not authentication.

If client verification is enabled, you'll need to supply a client certificate when connecting.  This depends on your client, but using curl is done with a:

```
curl --cert client1.crt  --key client1.pem https://localhost:8000 
```