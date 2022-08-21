#!/usr/bin/python3
import os
import sys
from typing import List, Union
import psutil
import subprocess
import time
import jinja2
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import socket

from utils import render_template, send_email

to_addr = "admin@company.com"
from_addr = "monit@company.com"
basedir = "/etc/monit/scripts/"


class HumanBytes:
    METRIC_LABELS: List[str] = ["B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    BINARY_LABELS: List[str] = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    PRECISION_OFFSETS: List[float] = [0.5, 0.05, 0.005, 0.0005]  # PREDEFINED FOR SPEED.
    PRECISION_FORMATS: List[str] = ["{}{:.0f} {}", "{}{:.1f} {}", "{}{:.2f} {}", "{}{:.3f} {}"]  # PREDEFINED FOR SPEED.

    @staticmethod
    def format(num: Union[int, float], metric: bool = False, precision: int = 1) -> str:
        """
        Human-readable formatting of bytes, using binary (powers of 1024)
        or metric (powers of 1000) representation.
        """

        assert isinstance(num, (int, float)), "num must be an int or float"
        assert isinstance(metric, bool), "metric must be a bool"
        assert isinstance(precision, int) and precision >= 0 and precision <= 3, "precision must be an int (range 0-3)"

        unit_labels = HumanBytes.METRIC_LABELS if metric else HumanBytes.BINARY_LABELS
        last_label = unit_labels[-1]
        unit_step = 1000 if metric else 1024
        unit_step_thresh = unit_step - HumanBytes.PRECISION_OFFSETS[precision]

        is_negative = num < 0
        if is_negative:  # Faster than ternary assignment or always running abs().
            num = abs(num)

        for unit in unit_labels:
            if num < unit_step_thresh:
                # VERY IMPORTANT:
                # Only accepts the CURRENT unit if we're BELOW the threshold where
                # float rounding behavior would place us into the NEXT unit: F.ex.
                # when rounding a float to 1 decimal, any number ">= 1023.95" will
                # be rounded to "1024.0". Obviously we don't want ugly output such
                # as "1024.0 KiB", since the proper term for that is "1.0 MiB".
                break
            if unit != last_label:
                # We only shrink the number if we HAVEN'T reached the last unit.
                # NOTE: These looped divisions accumulate floating point rounding
                # errors, but each new division pushes the rounding errors further
                # and further down in the decimals, so it doesn't matter at all.
                num /= unit_step

        return HumanBytes.PRECISION_FORMATS[precision].format("-" if is_negative else "", num, unit)


def filter_non_printable(str):
    ret = ""
    for c in str:
        if ord(c) > 31 or ord(c) == 9:
            ret += c
        else:
            ret += " "
    return ret


def memory():
    """
    Get list of running process sorted by Memory Usage
    """
    ret = {}
    ret["procs"] = []
    ret["mem_total"] = HumanBytes.format(psutil.virtual_memory().total)
    ret["mem_avail"] = HumanBytes.format(psutil.virtual_memory().available)
    ret["mem_used"] = HumanBytes.format(psutil.virtual_memory().used)
    ret["mem_free"] = HumanBytes.format(psutil.virtual_memory().free)
    ret["swap_free"] = HumanBytes.format(psutil.swap_memory().free)
    ret["swap_total"] = HumanBytes.format(psutil.swap_memory().total)
    ret["swap_pct"] = psutil.swap_memory().percent

    for proc in psutil.process_iter():
        try:
            pinfo = {}
            pinfo["pid"] = proc.as_dict(attrs=["pid"])["pid"]
            pinfo["cmd"] = proc.as_dict(attrs=["name"])["name"]
            pinfo["user"] = proc.as_dict(attrs=["username"])["username"]
            pinfo["mem"] = proc.memory_info().vms >> 20
            process = psutil.Process(pinfo["pid"])
            pinfo["mem_pct"] = round(process.memory_percent(), 2)

            with open(os.path.join("/proc/", str(pinfo["pid"]), "cmdline"), "r") as pidfile:
                pinfo["args"] = filter_non_printable(pidfile.readline())
            ret["procs"].append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    ret["procs"] = sorted(ret["procs"], key=lambda procObj: procObj["mem_pct"], reverse=True)[:5]

    html = render_template(
        basedir + "/jinja/top.j2",
        result=ret,
        hostname=os.uname()[1],
        title="mem",
        date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    )
    return html


def cpu():
    """returns CPU usage per process"""
    ret = {}
    cmd = "ps -efl --sort=-pcpu | head -n 6"
    state_code = {
        "S": "Sleep",
        "D": "I/O wait",
        "I": "Idle",
        "R": "Running",
        "T": "Stopped",
        "t": "Stopped by debugger",
        "W": "Paging",
        "X": "Dead",
        "Z": "Zombie",
    }

    try:
        result = subprocess.check_output(cmd, shell=True).decode("utf-8").split("\n")
    except subprocess.CalledProcessError as e:
        print(e.output)

    time.sleep(2)  # wait for snapshot to be generated
    result.pop(0)  # remove header row
    result = [x for x in result if x]
    procs = {}
    for row in result:
        pr = row.split()
        pid = pr[3]
        procs[pid] = {}
        procs[pid]["user"] = pr[2]
        procs[pid]["cpu_pct"] = pr[5]
        procs[pid]["cmd"] = " ".join(pr[14:])
        procs[pid]["state"] = state_code[pr[1]]
        procs[pid]["time"] = pr[13]
    ret["procs"] = procs
    ret["num_cpus"] = psutil.cpu_count()
    ret["iowait"] = psutil.cpu_times_percent(interval=2, percpu=False).iowait
    ret["irq"] = psutil.cpu_times_percent(interval=2, percpu=False).irq
    ret["load_avg"] = psutil.getloadavg()
    ret["cpu"] = psutil.cpu_percent()

    html = render_template(
        basedir + "/jinja/top.j2",
        result=ret,
        hostname=os.uname()[1],
        title="cpu",
        date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    )
    return html


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("provide mem or cpu")
        sys.exit(0)

    if sys.argv[1] == "mem":
        send_email(to_addr, from_addr, cc=None, bcc=None, subject=f"MEM Snapshot {os.uname()[1]}", body=memory())
    else:
        send_email(to_addr, from_addr, cc=None, bcc=None, subject=f"CPU Snapshot {os.uname()[1]}", body=cpu())
