#!/usr/bin/python3

import argparse
import os
import subprocess
import time
from collections import defaultdict

from prometheus_client import Gauge, start_http_server

# Prometheus metrics
cpu_total_usage_gauge = Gauge("cpu_total_usage", "Total CPU Usage (%)")
cpu_user_usage_gauge = Gauge("cpu_user_usage", "User CPU Usage (%)", ["user"])
memory_total_usage_gauge = Gauge("memory_total_usage", "Total Memory Usage (Bytes)")
memory_user_usage_gauge = Gauge(
    "memory_user_usage", "User Memory Usage (Bytes)", ["user"]
)


def getent_password():
    """Fetch system user information via getent."""
    passwd = subprocess.Popen(("getent", "passwd"), stdout=subprocess.PIPE)
    users = dict()
    for line in passwd.stdout:
        line = line.strip().split(b":")
        users[int(line[2])] = line[0].decode()
    return users


def is_system_user(uid):
    """
    Determine if the user is considered a system user.
    Here, we assume that uid < 1000 is a system user.
    Adjust logic if needed.
    """
    return uid < 1000


def get_total_cpu_times():
    """Get total CPU times from /proc/stat."""
    with open("/proc/stat", "r") as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith("cpu "):
            fields = line.strip().split()
            total_cpu_time = sum(map(int, fields[1:]))
            idle_time = int(fields[4])  # idle is the 5th field
            return total_cpu_time, idle_time
    return 0, 0


def get_total_memory():
    """Get total memory from /proc/meminfo."""
    with open("/proc/meminfo", "r") as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith("MemTotal:"):
            total_memory_kb = int(line.split()[1])
            return total_memory_kb * 1024  # Convert to bytes
    return 0


def collect_cpu_memory_data(exclude_system_users=False, excluded_usernames=None):
    """
    Collect CPU and memory usage data.
      - exclude_system_users=True の場合、UID < 1000 を除外
      - excluded_usernames=set(...) の場合、該当ユーザ名を除外
    """
    if excluded_usernames is None:
        excluded_usernames = set()

    users = getent_password()
    user_cpu_times = defaultdict(int)  # {user: total_cpu_time}
    user_memory_usage = defaultdict(int)  # {user: total_memory_usage}

    total_cpu_time, idle_time = get_total_cpu_times()
    total_memory = get_total_memory()
    total_memory_used = 0

    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                # Get process CPU times
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat = f.read().split()
                utime = int(stat[13])
                stime = int(stat[14])
                total_time = utime + stime

                # Get process memory usage
                with open(f"/proc/{pid}/statm", "r") as f:
                    statm = f.read().split()
                rss_pages = int(statm[1])  # Resident Set Size in pages
                page_size = os.sysconf("SC_PAGE_SIZE")  # Bytes
                memory_usage = rss_pages * page_size  # Bytes

                # Get process UID
                with open(f"/proc/{pid}/status", "r") as f:
                    lines = f.readlines()
                uid_line = next(
                    (line for line in lines if line.startswith("Uid:")), None
                )
                if uid_line:
                    uid = int(uid_line.split()[1])
                    if exclude_system_users and is_system_user(uid):
                        # システムユーザを除外
                        continue
                    user = users.get(uid, "[Unknown]")
                else:
                    user = "[Unknown]"

                # ユーザ名が除外リストに含まれている場合はスキップ
                if user in excluded_usernames:
                    continue

                user_cpu_times[user] += total_time
                user_memory_usage[user] += memory_usage
                total_memory_used += memory_usage

            except (FileNotFoundError, IndexError, ValueError):
                continue

    return (
        total_cpu_time,
        idle_time,
        user_cpu_times,
        total_memory,
        total_memory_used,
        user_memory_usage,
    )


def update_metrics(
    previous_stats,
    grace_period,
    cpu_usage_threshold,
    exclude_system_users=False,
    excluded_usernames=None,
):
    """Update Prometheus metrics."""
    current_time = time.time()

    (
        total_cpu_time,
        idle_time,
        user_cpu_times,
        total_memory,
        total_memory_used,
        user_memory_usage,
    ) = collect_cpu_memory_data(
        exclude_system_users=exclude_system_users,
        excluded_usernames=excluded_usernames,
    )

    if "previous_total_cpu_time" not in previous_stats:
        # First run, store current values and initialize
        previous_stats["previous_total_cpu_time"] = total_cpu_time
        previous_stats["previous_idle_time"] = idle_time
        previous_stats["previous_user_cpu_times"] = user_cpu_times
        previous_stats["last_update_time"] = current_time
        previous_stats["all_users"] = set(user_cpu_times.keys())
        previous_stats["users_above_threshold"] = set()
        previous_stats["last_seen"] = {}
        return

    delta_total_cpu_time = total_cpu_time - previous_stats["previous_total_cpu_time"]
    delta_idle_time = idle_time - previous_stats["previous_idle_time"]
    total_used_cpu_time = delta_total_cpu_time - delta_idle_time

    # Calculate total CPU usage percentage
    if delta_total_cpu_time > 0:
        cpu_usage_percent = (total_used_cpu_time / delta_total_cpu_time) * 100.0
    else:
        cpu_usage_percent = 0.0
    cpu_total_usage_gauge.set(cpu_usage_percent)

    # Set total memory usage
    memory_total_usage_gauge.set(total_memory_used)

    # Get all users (previous and current)
    all_users = previous_stats.get("all_users", set()).union(user_cpu_times.keys())
    previous_stats["all_users"] = all_users

    for user in all_users:
        prev_cpu_time = previous_stats["previous_user_cpu_times"].get(user, 0)
        current_cpu_time = user_cpu_times.get(user, 0)
        delta_user_cpu_time = current_cpu_time - prev_cpu_time

        if delta_total_cpu_time > 0:
            usage_percent = (delta_user_cpu_time / delta_total_cpu_time) * 100.0
        else:
            usage_percent = 0.0

        memory_usage = user_memory_usage.get(user, 0)

        if usage_percent >= cpu_usage_threshold:
            # User is above the threshold
            cpu_user_usage_gauge.labels(user=user).set(usage_percent)
            memory_user_usage_gauge.labels(user=user).set(memory_usage)

            # Update last seen time
            previous_stats["last_seen"][user] = current_time
            # Add to users_above_threshold
            previous_stats["users_above_threshold"].add(user)
        elif user in previous_stats["users_above_threshold"]:
            # User was previously above threshold but now is below
            # Set metrics to zero
            cpu_user_usage_gauge.labels(user=user).set(0.0)
            memory_user_usage_gauge.labels(user=user).set(0)
            # Do not update last_seen
        else:
            # User has never been above threshold; ignore
            continue

    # Handle users for removal after grace period
    for user in list(previous_stats["users_above_threshold"]):
        elapsed_time = current_time - previous_stats["last_seen"].get(user, 0)
        if elapsed_time >= grace_period:
            # Remove metrics
            cpu_user_usage_gauge.remove(user)
            memory_user_usage_gauge.remove(user)
            previous_stats["users_above_threshold"].remove(user)
            previous_stats["last_seen"].pop(user, None)
            previous_stats["all_users"].discard(user)

    # Update previous stats
    previous_stats["previous_total_cpu_time"] = total_cpu_time
    previous_stats["previous_idle_time"] = idle_time
    previous_stats["previous_user_cpu_times"] = user_cpu_times
    previous_stats["last_update_time"] = current_time


if __name__ == "__main__":
    # Parse arguments and environment variables
    parser = argparse.ArgumentParser(
        description="CPU and Memory Exporter for Prometheus"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("METRIC_SCRAPE_INTERVAL", 10)),
        help="Metric scrape interval in seconds (default: 10 seconds)",
    )
    parser.add_argument(
        "--grace-period",
        type=int,
        default=60,
        help="Time (in seconds) to keep metrics after a user falls below the threshold (default: 60 seconds)",
    )
    parser.add_argument(
        "--cpu-threshold",
        type=float,
        default=5.0,
        help="Minimum CPU usage percentage to consider a user active (default: 5.0%)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8010,
        help="Port number to run the exporter on (default: 8010)",
    )
    parser.add_argument(
        "--exclude-system-users",
        action="store_true",
        help="Exclude system users (UID < 1000) from metrics collection (default: False).",
    )
    parser.add_argument(
        "--exclude-users",
        nargs="*",
        default=[],
        help="List of usernames to exclude from metrics collection (space-separated).",
    )

    args = parser.parse_args()

    scrape_interval = args.interval
    grace_period = args.grace_period
    cpu_usage_threshold = args.cpu_threshold
    port = args.port
    exclude_system_users = args.exclude_system_users

    # デフォルト除外ユーザ（root, vmladmin）に、ユーザが指定した --exclude-users をマージする
    default_excluded = {
        "root",
    }
    excluded_usernames = default_excluded.union(args.exclude_users)

    # Start Prometheus HTTP server
    start_http_server(port)
    print(
        f"Exporter is running on port {port} with a scrape interval of {scrape_interval} seconds, "
        f"grace period of {grace_period} seconds, CPU usage threshold of {cpu_usage_threshold}%, "
        f"exclude_system_users={exclude_system_users}, excluded_usernames={excluded_usernames}."
    )

    # Track previous CPU times and user stats
    previous_stats = {
        "last_seen": {},
        "all_users": set(),
        "users_above_threshold": set(),
    }

    while True:
        update_metrics(
            previous_stats,
            grace_period,
            cpu_usage_threshold,
            exclude_system_users=exclude_system_users,
            excluded_usernames=excluded_usernames,
        )
        time.sleep(scrape_interval)
