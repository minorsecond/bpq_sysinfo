#!/bin/python
# Get sysinfo and print for BPQ reporting

import os
import time
import platform
import distro
import cpuinfo
import psutil
import uptime

pause_time = 1

cpu_count = os.cpu_count()

if platform.architecture()[0] == "64bit":
    arch = 64
else:
    arch = 32

processor_name = cpuinfo.get_cpu_info()['brand_raw']
os_name = distro.linux_distribution()[0]
os_version = distro.linux_distribution()[1]
cpu_usage = psutil.cpu_percent()
mem_usage = psutil.virtual_memory().percent
total_mem = psutil.virtual_memory().total >> 20
available_mem = psutil.virtual_memory().available >> 20
uptime = uptime.uptime()
swap_usage = psutil.swap_memory().percent
swap_size = psutil.swap_memory().total >> 20
available_swap = psutil.swap_memory().free >> 20


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
    :param kb: integer denoting megabytes.
    :return: integer denoting gigabytes.
    """

    gb = 1.0/1024
    convert_gb = gb * mb
    return round(convert_gb, 2)


print("============================================================================")
print(f"This system has {cpu_count} {arch}-bit {processor_name} cores.")
print(f"The operating system is: {os_name} version {os_version}.")
print("----------------------------------------------------------------------------")
print(f"The current CPU usage is: {cpu_usage}%")
print(f"The current memory usage is: {mem_usage}%")
print(f"The total memory is: {mb_to_gb(total_mem)} GB.")
print(f"The free memory available is: {mb_to_gb(available_mem)} GB.")
print(f"The current swap usage is: {swap_usage}%.")
print(f"The total swap size is: {mb_to_gb(swap_size)} GB.")
print(f"The free swap available is {mb_to_gb(available_swap)} GB.")
print(f"System uptime: {format_time(uptime)}")
print("============================================================================")

start_time = time.time()
while True:
    current_time = time.time()
    elapsed_time = current_time - start_time

    if elapsed_time > pause_time:
        break