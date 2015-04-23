# Query Language #

To express more complicated queries, you can use a simple query language.  The exact syntax is still in flux but the parts documented here should remain fairly constant.  The core problem this language solves is that if we had a relational model for the set of tags, we could just query it using SQL where the tag names are columns, and tag values are rows.  Since we don't know all the column names ahead of time (you can tag your data with whatever you'd like), it's tedious to construct queries on tags.  This query language rewrites queries into SQL; this lets you pretend tag names are columns.

The language supports **select**, **delete**, and **set** operations; there is no need to refer to particular table since there is only one flat datastore.  The **select** operation may be performed by anyone, and by default queries all public streams; the mutation operations **delete** and **set** will only operate on streams where the request includes an API key.

## Using the query language ##
You can execute queries by putting them in the body of a POST request to `http://new.openbms.org/backend/api/query`.  If you have sMAP installed, there is an interactive tool, **smap-query** which you can use to do this.

If you have received an API key, you may include it in your request using the "key" query param; multiple keys may be specified by repeating the param.  For instance, the query string `?key=[key]&key=[k2]` will pass along those two keys.  This will (a) allow you to query those streams, if they are marked as private, and (b) allow you to mutate them using the **set** and **delete** operators.

## **select** ##

_syntax_: **select** _selector_ **where** _where-clause_

| selector type | possible values |
|:--------------|:----------------|
| tag names | `*` or comma-separated list |
| **distinct** query | tag name or **tags** literal |
| _data selector_ | data specification |

The result of a **distinct** query is a JSON list of all matching strings, while the result of a tag name query is a list of sMAP Timeseries objects populated only with the requested fields.

### data selector ###

You can access stored data from multiple streams by specifying a data specification:

**select data in** (_start reference_, _end reference_) _limit_ **where** _where-clause_

**select data before** _reference_ _limit_ **where** _where-clause_

**select data after** _reference_ _limit_ **where** _where-clause_

A limit is optional, and can have the form **limit** _number_, **streamlimit** _number_, or **limit** _number_ **streamlimit** _number_.  Limit controls the number of points returned per stream, and streamlimit controls the number of streams returned.

The time references (_start time_, _end time_) are inclusive, exclusive, while (**before**, **after**) select data starting at the first point with timestamp (less than, greater than) the reference time stamp.

_reference_ must either be an timestamp in units of UNIX milliseconds, the string literal **now**, or a quoted time string.  Valid time strings are "%m/%d/%Y", "%m/%d/%Y %M:%H", and "%Y-%m-%dT%H:%M:%S".  For instance "10/16/1985" and "2/29/2012 20:00" are valid.  They will be interpreted relative to the timezone of the server.

The reference may be modified by appending a relative time string, using unix "at"-style specifications.  You can for instance say `now + 1hour` or `now -1h -5m` for the last 1:05.  Available relative time quantities are days, hours, minutes, and seconds.

### Examples ###

Get all tags in the system
```
query> select distinct tags
```

Get entire tag database
```
query> select *
```

Get all buildings in use
```
query> select distinct Metadata/Location/Building
```

Get  all buildings and cities
```
query> select Metadata/Location/Building, Metadata/Location/City
```

Get the latest readings from two streams:
```
select data before now limit 1 where uuid = 'd26f4650-329a-5e14-8e5a-73e820dff9f0' or uuid = '87c395ee-5ee3-5713-8928-c29e32937877'
```

Retrieve a week's worth of data for matching streams:
```
select data in ("1/1/2012", "1/7/2012") streamlimit 50 where Metadata/SourceName ~ "^410"
```

Retrieve the last five minutes of outside air data:
```
select data in (now -5minutes, now) where Metadata/Extra/Type = 'oat'
```

## Where Clauses ##
You can filter your result set using several operators.

| operator | description |
|:---------|:------------|
| **=** | compare tag values; _tagname_ **=** "_tagval_" |
| **like** | string matching with SQL LIKE; _tagname_ **like** "_pattern_" |
| **~** | postgres regular expression matching; _tagname_   **~** "_pattern_" |
| **has** | assert the stream has a tag; **has** _tagname_ |
| **and** | logical and of two queries |
| **or** | logical or of two queries |
| **not** | invert a match|

These statements can be grouped with parenthesis.  Tag values should be specified as quoted strings, while tag names should not be quoted.

See the [postgres manual](http://www.postgresql.org/docs/8.3/static/functions-matching.html) for more information on regular expression syntax.

### Examples ###

Find all the sources using Dent meters
```
query> select distinct Metadata/SourceName where Metadata/Instrument/Manufacturer like 'Dent%'
```

Find all paths taged as refrigerators, in units of milliwatts
```
query> select distinct Path where Metadata/Extra/ProductType = 'Refrigerator' and Properties/UnitofMeasure = 'mW'
```

## **delete** ##

_Form 1_: **delete** **where** _where-clause_

_Form 2_: **delete** _tag-list_ **where** _where-clause_

Form 1 deletes a stream, including all tags and data from the repository; it cannot be recovered.  It returns a list of deleted UUIDs.

Form 2 deletes a list of tag names; data and other tag names are unchanged.

The where-clause has the same syntax as for **select** statements; the tag-list is a comma-separated list of (unquoted) tag names.

### Examples ###
Delete a stream, where we know its identifier.
```
query> delete where uuid = '39ba89fe-29f9-5f61-82b6-f5c8a6d5d923'
[
  "39ba89fe-29f9-5f61-82b6-f5c8a6d5d923"
]
```

Remove a single tag from a stream.
```
query> delete Metadata/Instrument/Model where uuid = 'a8bec5d1-dced-5a05-a938-41f618a92ac0'
```

## **set** ##

_syntax_: **set** _set-list_ **where** _where-clause_

The set command applies tags to a list of streams.  The set-list is a comma separated list of new tag names and values.  The where-clause has the same syntax as previously discussed.  This command is limited to operating on streams owned by the API keys passed with the request.

### Examples ###

Change a timezone by UUID:
```
query> set Properties/Timezone = 'America/Los_Angeles' where uuid = '3f4d3767-74df-5882-9fcc-4ab530f0f1af'
```

Mark two feeds as full-building feeds:
```
query> set Metadata/Extra/ServiceRegion = 'building' where uuid = '960075e9-fb89-5527-9044-cd4239513478' or uuid = '814ed855-0174-5ca9-8f01-53c244d8996f'
```