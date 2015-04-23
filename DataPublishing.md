# Manual data publication (JSON Edition) #

The sMAP library ordinarily takes care of reliably sending data to the archiver backend; however it's sometimes desirable to add data using some other source.  You can do this using an HTTP `POST` with a properly formatted JSON object in the body.  The sMAP specification contains the necessary details for doing this; here are some simple examples.

A simple example of a valid sMAP object is:
```
{
  "/sensor0" : {
    "Metadata" : {
      "SourceName" : "Test Source",
      "Location" : { "City" : "Berkeley" }
    },
    "Properties": {
      "Timezone": "America/Los_Angeles", 
      "UnitofMeasure": "Watt", 
      "ReadingType": "double"
    },
    "Readings" : [[1351043674000, 0], [1351043675000, 1]],
    "uuid" : "d24325e6-1d7d-11e2-ad69-a7c2fa8dba61"
  }      
}
```

Supposing this was in `data.json`, you could send it to the archiver using `cURL`:
```
$ curl -XPOST -d @data.json -H "Content-Type: application/json" http://localhost:8079/add/<KEY>
```

## Notes ##
  1. `/sensor0` is the resource path of the sensor on the sMAP server.  You can make something sensible up if you're not actually running a web server.
  1. The `Metadata/SourceName` field is needed if you want your time series to show up in the powerdb2 plotter; other than that, all of `Metadata` is optional.
  1. Valid `ReadingTypes` are `double` and `long`; the timezone determines the conversion to be used for display times.
  1. `Readings` can consist of any number of (timestamp, value) arrays.  The timestamps should be UTC milliseconds.  Readings are currently truncated to 1-second resolution.
  1. The `uuid` should be globally unique for each timeseries.  Use an appropriate algorithm to generate them.
  1. In order to add data, only the `uuid` and `Readings` fields are needed; you can only send the metadata fields occasionally (ie, on startup) to reduce the amount of data sent.
  1. Be sure to set the right `Content-Type` if implementing your own sMAP support.

## Examples ##
You can find an example of a valid set of readings here: http://jackalope.cs.berkeley.edu/~stevedh/meter.json

# CSV Edition #
The archiver (as of [r421](https://code.google.com/p/smap-data/source/detail?r=421)) also supports receiving data (but not metadata) using CSV.  This can be a good choice if you have very simple devices.  The CSV format is very simple; an example is here: http://jackalope.cs.berkeley.edu/~stevedh/meter.csv

To add data using this file, you can again use `cURL`:
```
$ curl -XPOST -d @report.csv -H "Content-Type: text/csv" http://localhost:8079/add/<KEY>
```