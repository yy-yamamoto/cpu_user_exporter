# CPU User Exporter

The **CPU User Exporter** is a Python-based tool that collects and exports CPU and memory usage metrics for users on a Linux system. It integrates with Prometheus for monitoring and visualization.

---

## Features

- Collects per-user CPU and memory usage metrics.
- Exposes metrics via an HTTP endpoint for Prometheus.
- Supports configurable:
  - Metric scrape interval.
  - Grace period for metric cleanup.
  - CPU usage threshold for filtering users.
  - HTTP port for exposing metrics.
  - (Optional) Exclude system users (UID < 1000).

---

## Installation

Follow the steps below to install the CPU User Exporter.

### Prerequisites

- Python 3.12 or later
- Prometheus and Grafana for monitoring and visualization

---

### Steps

1. Clone this repository to your system:

```bash
git clone https://github.com/yy-yamamoto/cpu_user_exporter
cd cpu-user-exporter
```

2. Install the exporter using the provided Makefile:

```bash
sudo make install
```

3. Enable and start the service:

```bash
sudo make enable
```

The exporter will now be running and exposing metrics on the default port `8010`.

---

## Configuration

You can configure the exporter **dynamically** by passing arguments to the `make install` command:

- **Metric scrape interval**: `INTERVAL` (default: `15` seconds).
- **Grace period**: `GRACE_PERIOD` (default: `60` seconds).
- **CPU usage threshold**: `CPU_THRESHOLD` (default: `10.0`%).
- **HTTP port**: `PORT` (default: `8010`).
- **Exclude system users**: `EXCLUDE_SYSTEM_USERS` (default: `true`).

For example:

```bash
sudo make install INTERVAL=20 GRACE_PERIOD=120 CPU_THRESHOLD=5.0 PORT=9000 EXCLUDE_SYSTEM_USERS=true
```

This will install the exporter with:
- A metric scrape interval of 20 seconds
- A grace period of 120 seconds
- A CPU usage threshold of 5.0%
- Listening on port 9000
- System users (UID < 1000) are excluded

If you need to make further changes, you can also edit the `Makefile` directly.

After making changes, reinstall the exporter:

```bash
sudo make install
```

---

## Usage

Once installed, the exporter will automatically start as a systemd service.

### Viewing Metrics

Metrics are exposed at:

```text
http://<your-server-ip>:<port>
```

Example (default port 8010):

```text
http://localhost:8010
```

You can integrate this endpoint into Prometheus for monitoring.

### Managing the Service

- **Enable and Start:**

```bash
sudo make enable
```

- **Disable and Stop:**

```bash
sudo make disable
```

- **Uninstall:**

```bash
sudo make uninstall
```

---

## Example Metrics

Here are some example metrics exported by the tool:

```text
# HELP cpu_total_usage Total CPU Usage (%)
# TYPE cpu_total_usage gauge
cpu_total_usage 10.5

# HELP cpu_user_usage User CPU Usage (%)
# TYPE cpu_user_usage gauge
cpu_user_usage{user="john"} 1.5

# HELP memory_total_usage Total Memory Usage (Bytes)
# TYPE memory_total_usage gauge
memory_total_usage 5.192065024e+09

# HELP memory_user_usage User Memory Usage (Bytes)
# TYPE memory_user_usage gauge
memory_user_usage{user="john"} 102400
```

---

## Logs and Debugging

To view logs for the exporter service:

```bash
sudo journalctl -u cpu_user_exporter.service -f
```

---

## Customization

If you need to change additional settings, such as the service configuration, you can modify the `cpu_user_exporter.service` file.

After changes, reload and restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart cpu_user_exporter.service
```

---

## Uninstallation

To completely remove the exporter:

```bash
sudo make uninstall
```

This will:

- Stop and disable the service.
- Remove the installation directory `/opt/cpu_user_exporter`.
- Remove the systemd service file.

---

## License

This project is licensed under the MIT License.
