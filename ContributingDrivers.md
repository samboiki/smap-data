# Contributing Drivers #

In order to maintain a decent project organization and separate better-tested code from pre-alpha stuff, we have a two-tier model for code contributions.

Well-tested, core driver modules are located in the `smap.drivers` package.  For drivers which can be implemented in a single module, they should have a short name -- for instance, **example**.  The implementation should be in `smap/drivers/example.py`, and a matching `conf/example.ini` should be present and contain an example configuration file which loads only that driver, using sensible default values.

Newer code which may be less reusable (depends on a specific environment) may be committed to the `smap.contrib` package.  Unlike mainline drivers, contributors should create a new package for each driver.  For instance, for a driver named `contribdriver`, it should be located in `smap/contrib/contribdriver/contribdriver.py`, and include a matching `smap/contrib/contribdriver/contribdriver.ini` file.  This system allows us to include contributed drivers in a release on a case-by-case basis.

Code which is in contrib may be promoted to a mainline driver when it seems generally useful and contains no site-specific code.

## Driver Style Guidelines ##

Both driver modules and packages (in contrib) should be in all lowercase, and the recommended class name for the driver, should be defined as

```
from smap.driver import SmapDriver

class ExampleDriver(SmapDriver): 
    pass
```

Drivers should document the configuration options they accept or require in a pydoc comment on the class.