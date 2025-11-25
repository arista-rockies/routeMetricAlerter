#!/usr/bin/python3
# https://github.com/aristanetworks/EosSdk/blob/master/examples/IntfIpAddrMergeExample.py
#### http://aristanetworks.github.io/EosSdk/docs/2.19.0/ref/
##  updates

import eossdk, yaml, json, sys, pyeapi, uuid, io, urllib.request, subprocess
import os

class MonitoredPrefix():
    def __init__(self, prefix=None, nextHops=None, metric=None, tracer=None):
        self.prefix = eossdk.IpPrefix(prefix)
        self.metric = metric
        self.nextHops = set()
        self.tracer = tracer

        if isinstance(nextHops, str):
            nextHops = list([nextHops])
        elif nextHops == None:
            nextHops = list()

        for nextHop in nextHops:
            self.tracer.trace9(f"---------adding {nextHop}")
            self.addNH(nextHop)

    def addNH(self, nextHop):
        self.nextHops.add(eossdk.IpAddr(nextHop))

    def __eq__(self, other):
        # equality should include metric if we have one, along with nexthops
        if self.prefix != other.prefix:
            self.tracer.trace9("prefix not equal")
            return False

        if self.nextHops != other.nextHops:
            self.tracer.trace9("nexthops not equal")
            return False

        if (self.metric and other.metric):
            if self.metric != other.metric:
                self.tracer.trace9("metric not equal")
                return False

        self.tracer.trace9(f"we are equal! {self}:{other}")
        return True

    def __lt__(self, other):
        return self.prefix.__lt__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.prefix.__hash__()

"""
class MonitoredPrefixes(dict):
    def __init__(self):
        super().__init__()

    def update(self, prefix, nextHop, metric):
        if p := self.get(prefix, None):
            # it's already here.  we need to potentially update and alert
            if p ==
            if (p.nextHop == nextHop
                and p.metric ==
"""

class BGPMonitor(eossdk.AgentHandler, eossdk.BgpPathHandler, eossdk.BgpPeerHandler, eossdk.FibHandler):
    def __init__(self, sdk):
        self.sdk = sdk
        self.agentMgr = sdk.get_agent_mgr()
        self.bgpPathMgr = sdk.get_bgp_path_mgr()
        self.bgpMgr = sdk.get_bgp_mgr()
        self.fibMgr = sdk.get_fib_mgr(eossdk.MODE_TYPE_READ_NOTIFYING)
        self.primaryNextHop = None
        self.alertMethods = set()
        self.supportedAlertMethods = set(['syslog', 'snmp'])
        self.snmpCommand = None
        self.monitoredPrefixes = set()
        self.prefixes = None

        eossdk.AgentHandler.__init__(self, self.agentMgr)
        eossdk.BgpPeerHandler.__init__(self, self.bgpMgr)
        eossdk.BgpPathHandler.__init__(self, self.bgpPathMgr)
        eossdk.FibHandler.__init__(self, self.fibMgr)

        self.tracer = eossdk.Tracer("routeMetricAlerter")
        self.tracer.trace9(f"startup")

    def on_initialized(self):
        for optionName in ['config']:
            optionValue = self.agentMgr.agent_option(optionName)
            if optionName == 'config' and not optionValue:
                optionValue = """
{
    "commands": [
        "logger {}",
        "snmptrap -v2c -c trapcommunity 192.168.1.245 1.3.6.1.4.1.30065.3.25.0 0 s \\"HelloJeff\\""
    ],
    "cli_commands": [],
    "prefixes": [
        {"prefix": "0.0.0.0/0","metric": 40,"next_hops": ["10.36.128.14"],"next_hop_interfaces": [""]},
        {"prefix": "1.1.1.0/24","metric": 0,"next_hops": ["192.168.1.1"],"next_hop_interfaces": [""]}
    ]
}"""

            if optionValue:
                self.on_agent_option(optionName, optionValue)

        if False:
            self.watch_all_peers(True)
            self.watch_all_paths(True)
            self.watch_ipv4_unicast_paths(True)

        self.tracer.trace9("initialized")

    def on_agent_option(self, optionName, optionValue):
        optionName = optionName.lower()
        if optionName == 'config':
            try:
                self.tracer.trace0(f"attempting to load {optionValue}")
                c = json.loads(optionValue)
            except Exception as e:
                self.tracer.trace0(f"error in loading the config {e}")
                return

            self.prefixes = {}
            for prefix in c["prefixes"]:
                self.tracer.trace9(f"adding prefix: {prefix}")
                self.prefixes[eossdk.IpPrefix(prefix["prefix"])] = MonitoredPrefix(prefix=prefix["prefix"], nextHops=prefix.get("next_hops", None), metric=prefix.get("metric", None), tracer=self.tracer)

            self.tracer.trace9(f"{self.prefixes}")

    def _doAlert(self, prefix, isDown=True):
        self.tracer.trace0(f" alerting for prefix: {prefix}, isDown: {isDown}")
        os.system(f'logger "this is the log message"')

    def on_route_del(self, routeKey):
        self.tracer.trace9("on_route_del")
        s = f"del: {routeKey.to_string()}"
        if monitoredPrefix := self.prefixes.get(routeKey.prefix(), None):
            # we have the prefix, let's alert on it. and move on
            self._doAlert(monitoredPrefix, isDown=True)
            return

    def on_route_set(self, fibRoute):
        self.tracer.trace9("on_route_set")
        if monitoredPrefix := self.prefixes.get(fibRoute.route_key().prefix(), None):
            self.tracer.trace9(f" - we found prefix: {fibRoute.route_key().prefix().to_string()}")
            # this is in our monitored prefix list, we need to check it
            # to compare we need a new internal object.  let's make a temporary one:
            nextHops = []
            fec = self.fibMgr.fib_fec(eossdk.FibFecKey(fibRoute.fec_id()))
            for via in fec.via():
                self.tracer.trace9(f" --- {via.hop().to_string()}")
                nextHops.append(via.hop().to_string())

            updatedPrefix = MonitoredPrefix(prefix=fibRoute.route_key().prefix().to_string(), nextHops=nextHops, metric=None, tracer=self.tracer)
            self.tracer.trace9("checking equal")
            if updatedPrefix != monitoredPrefix:
                self._doAlert(updatedPrefix, True)
            else:
                self._doAlert(updatedPrefix, False)

if __name__ == "__main__":
    sdk = eossdk.Sdk()
    _ = BGPMonitor(sdk)
    sdk.main_loop(sys.argv)


