# Introduction #

One of the key features of the powerdb2 frontend is the ability to create different tree views of your data based on metadata tags.  This allows you to "slice" your available data streams in different ways; for instance, to expose an instrumentation-centric view which shows which streams are originating from which instrument, or a spatial view, showing which streams come from which room.

The trees can only be as good as your tags; generally you need to tag your streams in a consistent way in order to be able to build useful trees.  All streams have tags for `Path`, `uuid`, and the `Properties/` space which includes units, data type, and time zone.

Trees are created as javascript arrays, where each element in the array specifies what is displayed at each tree level.  You can edit the available trees through the url `/admin/smap/tree` interface; there isn't any error checking so if you specify broken javascript it will break the frontend.

# Simple Tree #

One simple tree installed by default is the **Instrumentation** tree.  It is specified using the definition:
```
[ 
   "Metadata/SourceName",
   "Metadata/Extra/Description"
]
```

This shows how to specify a simple tree.  The first level is specified using a simple tag: `Metadata/SourceName`.  Therefore, the first tree level will show all distinct values for `Metadata/SourceName`, while the second level will show distinct values of `Metadata/Extra/Description`.

To make this concrete, suppose we have a stream with the tags `{"Metadata/SourceName": "Test", "Metadata/Extra/Description" : "Sensor #1"}`.  This would generate the following tree in the interface:

```
- Test
| - Sensor #1
```

# More Complex Tree #

In general, each level in the tree can either be either
  * A bare string, specifying a tag value
  * An js object containing detailed specifications for that tree level
  * An js object containing a `prefixTag` tree.

The object specification may have any of the following keys:
```
{
  tag : "tagname",
  restrict : "ArdQuery where-clause",
  defaultSubStream : "ArdQuery where-clause",
  seriesLabel : ["tag-1", "tag-2", ...],
  sortfn : function (a, b) { return (a < b ? -1 : (a == b ? 0 : 1)); }
}
```

`tag` is required; the rest are all optional.

| Key name | Purpose |
|:---------|:--------|
| `tag` | Specifies what tag value is used to display |
| `restrict` | Additional [where-clause](ArdQuery#Where_Clauses.md) which is added when determining which tags to display at this level |
| `defaultSubStream` | Additional [where-clause](ArdQuery#Where_Clauses.md) which is added to help specify which stream to plot when this level in the tree is plotted; useful to avoid plotting thousands of streams when plotted at a high level. If not present, the tree level will not be plotable. |
| `seriesLabel` | List of tag names used to generate the label in the legend of the plotter. |
| `sortfn` | A javascript sort comparison function used to sort the display order for this level in the tree |

# Prefix Trees #
Alternatively, you can specify a tree using the `prefixTag` directive.  This tells slicr to build a tree by fetching a tag (in this case 'Path'), and building a tree by separating the tag values into path components.  This can be useful if you have a tag containing strings which have some hierarchical component.  This type of tree level must only be placed as the final level of tree definition.

For instance, suppose we have the tree defined by:
```
[
  {  prefixTag : "Path" }
]
```

This will use the "Path" tag to generate a tree.  The component separator is '/', so supposing you had two streams, one with `{"Path" : "/foo/bar"}` and the other `{"Path" : "/foo/baz"}`, the above definition would generate the tree:
```
+ foo
| + bar
| + baz
```

# Examples #

## Raw Instrumentation ##

The default tree in **powerdb2** is the Instrumentation tree; its definition is very simple and relies on only two tags:
  * `Metadata/SourceName`: optional, but recommended for all sMAP sources to identify the source of its data
  * `Path`: required; automatically added to incoming data based on the URL resource hierarchy of the sMAP source.

The tree definition is
```
[
  "Metadata/SourceName",
 {"prefixTag" : "Path"}
]
```

For instance, our example driver, `smap.drivers.example.Driver` driver provides one stream, under the `Path` `/instrument0/sensor0`.  This source is typically tagged with `Metadata/SourceName` = `Example sMAP source`.  This stream would create the following tree according to this slicr definition.

```
- Example sMAP source
| - instrument0
| | - sensor0
```

As you can see, the path has been split up and used to create a replica of the source's resource hierarchy.

## Electrical Instrumentation ##

This definition generates a tree for streams which are provided from Dent electric meters.  Each meter contains six "elements", or three-phase submeters; each of these contains metering data for three electric phases.  A all streams are tagged with some tags either from the metering sMAP driver, or provided during installation.  This tree displays only data originating from Cory Hall due to the top-level "restrict" clause.

  * `Metadata/Extra/MeterName`: the name of the meter
  * `Metadata/Extra/DentElement`: the name of the submeter
  * `Metadata/Extra/Phase`: which of the three electric phases the channel is measuring
  * `Metadata/Location/Building`: which building the meter is installed in

Additionally, some channels are tagged with a `Metadata/Extra/ServiceDetail` tag which we display as part of the caption label.

```
[
  {tag: "Metadata/Extra/MeterName",
   restrict: "Metadata/Location/Building = 'Cory Hall' and has Metadata/Extra/DentElement"},
  {tag: "Metadata/Extra/DentElement",
   defaultSubStream: "Metadata/Extra/Phase = 'ABC' and Properties/UnitofMeasure = 'kW'",
   seriesLabel: ["Metadata/Extra/MeterName",
                 "Metadata/Extra/DentElement",
                 "Metadata/Extra/ServiceDetail"]},
  "Metadata/Extra/Phase",
  "Properties/UnitofMeasure",
]
```

A sample tree generated by this definition would be something like
```
- meter-1
| - elt-A
| | + A
| | + B
| | + C
| | - ABC
| | | kW
| | | kWh
| | | PF
| | | ...
| + elt-B
| ...
```