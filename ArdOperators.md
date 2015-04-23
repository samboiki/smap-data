# Operators #

The query language allows you to optionally filter the time-series data before returning it to the client.  This functionality is somewhere between "alpha" and "beta" right now; it works but isn't finished.  You might have a look at some [slides](http://local.cs.berkeley.edu/wiki2/index.php/File:Local-spring-arql-2012.pptx) which describe at a high level how operators work.

The goal of operators is to allow you to efficiently perform common data cleaning and transformations on your timeseries data before retrieving it; it is not (and will not be) a general-purpose programming language; we believe that more-sophisticated computation is a problem which is already solved elsewhere but ironically, relatively simple operations are hard.

Examples of the types of computation you can perform using operator sequences are resampling/subsampling, timestamp alignment, simple arithmetic operations, and smoothing.

# Processing Overview #

Every operator operates on a set of time-series, and produce new sets of time-series as outputs.  A time series is represented by NxM matrix, where the first column is time stamps and other columns are values corresponding to that timestamp.

Operators can be "piped" together to apply a series of processing steps in order.  The first operator in the pipe receives the data selected by the rest of the query.

# Processing Examples #

The best way to proceed is by example.  You can indicate you wish to use an operator using the **apply** keyword.  Consider this query:

```
query > apply window(mean, field="hour") to data in ("4/20/2012", "4/21/2012") where Metadata/Extra/Type = 'oat'
```

Reading from right to left, this query first "select"s all streams which represent outside air temperature ("oat").  It then specifies that we are interested in one day's worth of data.  Finally, the operator to be applied is `window(mean, field="hour")`.  `window` is an operator which finds non-overlapping time windows in the data, and applies an inner operator to them.  In this case, we first divide the data along the time axis into bins one hour of long, and then apply the `mean` operator to each of these sets of data.  The `window` operator works in parallel on all input time-series, so after processing there are the same number of streams; however they have been resampled so that the time stamps lie on 15-minute boundaries.