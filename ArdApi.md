# Archiver Daemon #

The archiver daemon is a process which runs continuously somewhere.  Like sMAP sources, it uses twisted for improved concurrency.  The ARD uses a postgres database to manage storage of stream tags, and a readingdb database for the actual time-series data.  It exposes a relatively simple API to clients.

A public copy of the ARD is available through a reverse proxy at http://new.openbms.org/backend

## add and api ##

The two top level resources are **add** and **api**.  If you have an API key, you may post valid objects to the "http://new.openbms.org/backend/add/[key]" location.  These objects should be maps whose keys are resource paths on the sMAP source, and whose values are Timeseries objects following the proper schema.  The archiver daemon will return an HTTP 200 OK code if the data and tags were successfully entered into the databases.

The **api** resource is used to query tags and data.  Several types of query are possible.

### query ###
The query resource is used to discover what tags are present.  Called with no arguments, it returns a list of distinct tags which are known about.  If one of those tag values is appended to the path, it will return a list of distinct tag values.  Any number of tags may be specified in this manor.

The only special tag is the `uuid` tag; it will return the uuid of streams matching the query. Consider:

```
$ curl http://new.openbms.org/backend/api/query
["Description", ..., "Metadata/SourceName", "Path", "Properties/ReadingType", "Properties/Timezone", "Properties/UnitofMeasure"]
```

There are a number of tags which are required, such as the `Properties` ones.  We can now add a restriction on the unit of measure:

```
$ curl http://new.openbms.org/backend/api/query/Properties__UnitofMeasure
["$", "A", "C", "deg", "Hz", "HZ", "kVA", "kVAh", "kVAR", "kVARh", "kVARh-", "kVARh+", "kVAR net", "kW", "kWh", "Lbs", "Lbs/hr", "mm", "m/s", "mVA", "mW", "mWh", "Pa", "pct", "pf", "PF", "rh", "second", "V"]
```

Tag names and values should be properly urlencoded, with slash ('/') characters replaced with ''.

More sophisticated queries can be constructed using the ArdQuery language.

### tags ###

Once a query is constructed you may return the tag set for all matching streams using the tags resource.  To avoid generating a huge result set, it's desirable to check the number of matching streams before trying this one.  Alternatively, you can request the tags for a particular stream by specifying a uuid; that's guaranteed to match only one stream.

```
$ curl http://new.openbms.org/backend/api/tags/uuid/87c395ee-5ee3-5713-8928-c29e32937877 | jprint
[
  {
    "Metadata": {
      "Extra": {
        "DentElement": "elt-B",
        "Driver": "smap.drivers.dent.Dent18",
        "MeterName": "5DPB",
        "Panel": "5DPB",
        "Phase": "ABC",
        "ServiceArea": "BLDG.",
        "ServiceDetail": "East Passenger Elevator",
        "System": "elevator",
        "SystemDetail": "ELEVATOR",
        "SystemType": "Electrical"
      },
      "Instrument": {
        "Manufacturer": "Dent Industries",
        "Model": "PowerScout 18",
        "SamplingPeriod": "20"
      },
      "Location": {
        "Building": "Cory Hall",
        "Campus": "UCB",
        "Floor": "4"
      },
      "SourceName": "Cory Hall Dent Meters"
    },
    "Path": "/5DPB/elt-B/ABC/true_power",
    "Properties": {
      "ReadingType": "double",
      "Timezone": "America/Los_Angeles",
      "UnitofMeasure": "kW"
    },
    "uuid": "87c395ee-5ee3-5713-8928-c29e32937877"
  }
]
```

The result of a list of Timeseries objects with everything but data.

### data, next, prev ###

These are used to retrieve data in the time series.  Like the `tags` resource, it returns a list of partial Timeseries objects, although these contain only `Readings`.  They accept several query params:

| starttime | timestamp of first reading to retrieve (inclusive).  unix milliseconds |
|:----------|:-----------------------------------------------------------------------|
| endtime | timestamp to end the query at (only for data) |
| limit | maximum number of points to retrieve.  "-1" returns the entire result set |
| streamlimit | maximum number of streams to query (default 10) |

**data** returns data within a range.  **prev** and **next** retrieve up to **limit** points behind or head of the start time reference.  These can be used to determine the next point after a known reference time without generating a large result set, or to efficiently locate the latest data.

Again, these have the potential to generate large result sets which are slow to generate so it is recommended that you are careful to test carefully and use limit statements to avoid overwhelming yourself.  By default you can only look up data from 10 streams; you may need to increase streamlimit if you are querying a number of streams in parallel.

For instance, you can use this to find the latest readings from all the ACme meters in room 465 at Berkeley:

```
$ curl 'http://new.openbms.org/backend/api/prev/Metadata__Instrument__Manufacturer/UC%20Berkeley/Metadata__Location__Room/465/Properties__UnitofMeasure/mW?starttime=1315272705000'
[{"uuid": "6fdde16d-d59a-5f38-84ad-6b04b26e0029", "Readings": [[1315272654000, 217.0]]}, {"uuid": "5ff3f108-eb71-531a-872c-e6e4c1aaa31f", "Readings": [[1315272695000, 0.0]]}, {"uuid": "87d1d01c-1358-5af2-b005-036e69c88832", "Readings": [[1315272701000, 3503.0]]}, {"uuid": "d02891b0-6cf0-5d69-a3da-418646c9b779", "Readings": [[1315272701000, 87.0]]}, {"uuid": "5f5ca043-6f34-5bbf-9a6e-6a0eff85f5ad", "Readings": [[1315272699000, 8179.0]]}, {"uuid": "250ba823-0d0c-5b75-906f-ac2f68288352", "Readings": [[1315272700000, 15378.0]]}, {"uuid": "df4c180d-3c78-568f-8ff2-5026c9f42d5d", "Readings": [[1315272692000, 0.0]]}]
```