#!/usr/bin/env python3
"""Cancel a real pkexec authorization in the disposable acceptance VM.

This agent follows polkit's documented AuthenticationAgent D-Bus protocol. It
never authorizes a request or supplies credentials. Cancellation is delivered
by the real system polkit daemon to the installed, unchanged application.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from gi.repository import Gio, GLib

assert os.getuid() != 0, "authorization cancellation must run as an unprivileged user"
assert Path("/run/lam-disposable-acceptance").is_file(), "disposable VM marker missing"
lam = "/usr/lib/linux-app-manager/lam"
inventory = json.loads(subprocess.check_output([lam, "list", "--all", "--json"]))
fixture = next(app for app in inventory["apps"] if app.get("package_name") == "hello")
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
authority = Gio.DBusProxy.new_sync(
    bus, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.PolicyKit1",
    "/org/freedesktop/PolicyKit1/Authority", "org.freedesktop.PolicyKit1.Authority", None)
interface = Gio.DBusNodeInfo.new_for_xml("""
<node><interface name="org.freedesktop.PolicyKit1.AuthenticationAgent">
<method name="BeginAuthentication">
<arg type="s" direction="in"/><arg type="s" direction="in"/>
<arg type="s" direction="in"/><arg type="a{ss}" direction="in"/>
<arg type="s" direction="in"/><arg type="a(sa{sv})" direction="in"/>
</method><method name="CancelAuthentication"><arg type="s" direction="in"/></method>
</interface></node>""").interfaces[0]
cancelled = []


def handle(_connection, _sender, _path, _interface, method, parameters, invocation):
    if method == "BeginAuthentication":
        action = parameters.unpack()[0]
        assert action == "org.freedesktop.policykit.exec", action
        cancelled.append(action)
        invocation.return_dbus_error("org.freedesktop.PolicyKit1.Error.Cancelled",
                                     "Disposable acceptance test dismissed authentication")
    else:
        invocation.return_value(None)


agent_path = "/io/github/techmigosglobal/AcceptanceCancelAgent"
registration = bus.register_object(agent_path, interface, handle, None, None)
with open("/tmp/lam-polkit-result.txt", "w+") as output:
    # pkexec checks its immediate parent, the CLI process. Register for that
    # exact PID before allowing exec, just as pkttyagent --process PID does.
    child = subprocess.Popen(["bash", "-c", 'kill -STOP $$; exec "$@"', "_",
                              lam, "uninstall", fixture["id"], "--yes"],
                             stdout=output, stderr=subprocess.STDOUT)
    registered = False
    try:
        deadline = time.monotonic() + 10
        while "\nState:\tT" not in Path(f"/proc/{child.pid}/status").read_text():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        # /proc/PID/stat field 22, after the parenthesized command.
        start_time = int(Path(f"/proc/{child.pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
        subject = ("unix-process", {"pid": GLib.Variant("u", child.pid),
                                    "uid": GLib.Variant("i", os.getuid()),
                                    "start-time": GLib.Variant("t", start_time)})
        authority.call_sync("RegisterAuthenticationAgent",
                            GLib.Variant("((sa{sv})ss)", (subject, "C", agent_path)),
                            Gio.DBusCallFlags.NONE, 30000, None)
        registered = True
        child.send_signal(signal.SIGCONT)
        deadline = time.monotonic() + 120
        context = GLib.MainContext.default()
        try:
            while child.poll() is None and time.monotonic() < deadline:
                while context.pending():
                    context.iteration(False)
                time.sleep(0.02)
            assert child.poll() is not None, "authorization cancellation timed out"
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        output.seek(0)
        result = output.read()
        print(result)
        assert cancelled, "the real polkit daemon did not request authentication"
        assert child.returncode != 0, "cancelled authorization unexpectedly succeeded"
        remaining = json.loads(subprocess.check_output([lam, "list", "--all", "--json"]))
        assert any(app["id"] == fixture["id"] for app in remaining["apps"])
        print(json.dumps({"polkit_cancellation": "passed", "requests": len(cancelled),
                          "exit_code": child.returncode, "fixture_preserved": True}))
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        if registered:
            authority.call_sync("UnregisterAuthenticationAgent",
                                GLib.Variant("((sa{sv})s)", (subject, agent_path)),
                                Gio.DBusCallFlags.NONE, 30000, None)
        bus.unregister_object(registration)
