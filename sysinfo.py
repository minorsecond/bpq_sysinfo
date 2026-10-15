#!/bin/python3
# Get sysinfo and print for BPQ reporting.
# Output is kept short because users may be reading it over 1200 baud.

import json
import os
import platform
import subprocess
import sys
import time
import urllib.request

import distro
import psutil
#import speedtest

pause_time = 1

# limonitor's JSON status page for the LiFePO4 battery. Leave empty to skip.
battery_url = "http://127.0.0.1:8081/api/status"

cpu_count = os.cpu_count()

if platform.architecture()[0] == "64bit":
    arch = 64
else:
    arch = 32


def get_processor_name():
    # The Pi kernel puts the board name under "Model"; x86 uses "model name".
    fields = {}
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                key, _, value = line.partition(":")
                fields.setdefault(key.strip(), value.strip())
    except OSError:
        pass
    return fields.get("Model") or fields.get("model name") or platform.machine()


def get_cpu_temp():
    """
    Read the SoC temperature.
    :return: float of degrees C, or None if there is no sensor.
    """

    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000
    except (OSError, ValueError):
        return None


def get_power_status():
    """
    Decode vcgencmd get_throttled on a Pi.
    :return: string like "OK" or "undervoltage now", or None if not a Pi.
    """

    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=3).stdout
        flags = int(out.strip().split("=")[1], 16)
    except (OSError, IndexError, ValueError, subprocess.SubprocessError):
        return None

    # Bits 0-3 are happening now, bits 16-19 are the same events since boot.
    names = ("undervoltage", "freq capped", "throttled", "temp limit")
    now = [n for i, n in enumerate(names) if flags & (1 << i)]
    past = [n for i, n in enumerate(names)
            if flags & (1 << (i + 16)) and n not in now]
    parts = []
    if now:
        parts.append(", ".join(now) + " now")
    if past:
        parts.append(", ".join(past) + " since boot")
    return "; ".join(parts) or "OK"


def get_bpq_uptime():
    """
    Find how long LinBPQ has been running.
    :return: int of seconds, or None if it is not running.
    """

    for proc in psutil.process_iter(["name", "create_time"]):
        if proc.info["name"] in ("pilinbpq", "linbpq"):
            return int(time.time() - proc.info["create_time"])
    return None


def get_battery():
    """
    Ask limonitor for the battery state.
    :return: string for the battery line, or None if it can't be read.
    """

    if not battery_url:
        return None
    try:
        with urllib.request.urlopen(battery_url, timeout=2) as resp:
            b = json.load(resp)
    except (OSError, ValueError):
        return None
    if not b.get("valid"):
        return None

    # limonitor reports discharge as positive current and charge as negative.
    amps = b.get("current_a", 0)
    if amps > 0.05:
        flow = f"discharging {amps:.1f}A"
    elif amps < -0.05:
        flow = f"charging {-amps:.1f}A"
    else:
        flow = "idle"
    line = f"{b['soc_pct']:.0f}%, {b['voltage_v']:.2f}V, {flow}"

    temps = [t["temp_c"] for t in b.get("temperatures", [])]
    if temps:
        line += f", {max(temps):.0f}C"
    tripped = [k.replace("_", " ") for k, v in b.get("protection", {}).items() if v]
    if tripped:
        line += ", ALARM: " + ", ".join(tripped)
    return line


def get_44net():
    """
    Find an interface holding an AMPRNet (44.x) address.
    :return: string with the interface, address and traffic, or None.
    """

    stats = psutil.net_if_stats()
    counters = psutil.net_io_counters(pernic=True)
    for nic, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == "AF_INET" and addr.address.startswith("44."):
                state = "up" if stats.get(nic) and stats[nic].isup else "down"
                line = f"{addr.address} on {nic} {state}"
                if nic in counters:
                    c = counters[nic]
                    line += (f", rx {human_bytes(c.bytes_recv)}"
                             f" tx {human_bytes(c.bytes_sent)}")
                return line
    return None


def human_bytes(n):
    """
    Format a byte count with a short unit.
    :param n: int of bytes.
    :return: string like "1.2 GB".
    """

    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


processor_name = get_processor_name()
os_name = distro.name()
os_version = distro.version()
cpu_usage = psutil.cpu_percent(interval=0.5)
load_1, load_5, load_15 = os.getloadavg()
cpu_temp = get_cpu_temp()
power_status = get_power_status()
mem_usage = psutil.virtual_memory().percent
total_mem = psutil.virtual_memory().total >> 20
available_mem = psutil.virtual_memory().available >> 20
uptime = int(time.time() - psutil.boot_time())
bpq_uptime = get_bpq_uptime()
swap_usage = psutil.swap_memory().percent
swap_size = psutil.swap_memory().total >> 20
available_swap = psutil.swap_memory().free >> 20
disk = psutil.disk_usage('/')
disk_size = round(disk.total / (1024 ** 3), 1)
disk_free = round(disk.free / (1024 ** 3), 1)
disk_percent = disk.percent
battery = get_battery()
amprnet = get_44net()
eth = psutil.net_io_counters(pernic=True).get("eth0")

#print("Calculating internet speeds & latency...")
#st = speedtest.Speedtest()
#dl_speed = round(st.download() * 0.000001, 2)
#ul_speed = round(st.upload() * 0.000001, 2)
#server_names = []
#st.get_servers(server_names)
#ping = st.results.ping


def format_time(time):
    """
    Format seconds into weeks, days, hours, minutes, seconds.
    :param time: int of seconds.
    :return: string denoting time.
    """

    result = []

    intervals = (
        ('weeks', 604800),  # 60 * 60 * 24 * 7
        ('days', 86400),  # 60 * 60 * 24
        ('hours', 3600),  # 60 * 60
        ('minutes', 60),
        ('seconds', 1),
    )

    for name, count in intervals:
        value = time // count
        if value:
            time -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append(f"{value} {name}")
    return ', '.join(result[:2])


def mb_to_gb(mb):
    """
    Convert megabytes to gigabytes.
    :param mb: integer denoting megabytes.
    :return: integer denoting gigabytes.
    """

    gb = 1.0/1024
    convert_gb = gb * mb
    return round(convert_gb, 2)


print("-" * 40)
print(f"Board: {processor_name}, {cpu_count} cores, {arch}-bit")
print(f"OS: {os_name} {os_version}")
uptime_line = f"Up: {format_time(uptime)}"
if bpq_uptime is not None:
    uptime_line += f" (node {format_time(bpq_uptime)})"
print(uptime_line)
cpu_line = f"CPU: {cpu_usage}%, load {load_1:.2f} {load_5:.2f} {load_15:.2f}"
if cpu_temp is not None:
    cpu_line += f", {cpu_temp:.0f}C"
print(cpu_line)
if power_status is not None:
    print(f"Power: {power_status}")
if battery is not None:
    print(f"Battery: {battery}")
print(f"Mem: {mem_usage}% used, {mb_to_gb(available_mem)} of "
      f"{mb_to_gb(total_mem)} GB free")
print(f"Swap: {swap_usage}% used, {mb_to_gb(available_swap)} of "
      f"{mb_to_gb(swap_size)} GB free")
print(f"Disk: {disk_percent}% used, {disk_free} of {disk_size} GiB free")
if eth is not None:
    print(f"eth0: rx {human_bytes(eth.bytes_recv)} tx {human_bytes(eth.bytes_sent)}")
if amprnet is not None:
    print(f"44Net: {amprnet}")
#print(f"The current download speed is {dl_speed} Mb/s.")
#print(f"The current upload speed is {ul_speed} Mb/s.")
#print(f"Latency: {ping} ms.")
print("Script: github.com/minorsecond/bpq_sysinfo")
print("-" * 40)

# Give BPQ a moment to pass the output along before the socket closes.
sys.stdout.flush()
time.sleep(pause_time)
