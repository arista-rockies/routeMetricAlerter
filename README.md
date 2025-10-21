# routeMetricAlerter
EOSSDK agent to alert on change to the fib for a specified subset of routes

## installation
Copy the script to /mnt/flash and set it executable.  Long term this will be completed by the extension subsystem, however no extension is currently provided

## configuration
The agent can be configured in EOS using the following config stanza as an example:
```
daemon routeMetricAlerter
   exec /mnt/flash/routeMetricAlerter.py
   option config value <PASTE_HERE_THE_SINGLE_LINE_JSON_CONFIGURATION>
```

## debugging
A default test configuration is embedded in the code. Run the following from a root prompt on switch:
```
TRACE=routeMetricAlerter/0-9 /mnt/flash/routeMetricAlerter.py
```
