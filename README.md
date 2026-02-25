# NetWatch Utility

A real-time network connectivity monitor with a web dashboard. It tracks ICMP and HTTP targets, logs outages to a local database, and displays detailed WiFi connection information (macOS only).

## Features

- **Real-time Monitoring**: Polling of multiple ICMP and HTTP targets.
- **WiFi Insights**: Displays SSID, Channel (2.4G/5G/6G), Signal Strength, and PHY Mode.
- **Latency Tracking**: Live chart showing average latency over the last 60 seconds.
- **Outage History**: Persistent logging of outages and critical latency events in SQLite.
- **Modern UI**: Clean, dark-mode dashboard built with Tailwind CSS and HTMX.

## Prerequisites

- Python 3.9+
- macOS (for WiFi detail extraction)

## Installation

1. Clone the repository.
2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

To start the monitor and the web server, run:

```bash
uvicorn main:app --reload
```

Once running, access the dashboard at:
[http://127.0.0.1:8000](http://127.0.0.1:8000)

## Configuration

Settings can be adjusted in `config.py` or via environment variables:

- `POLL_INTERVAL`: Frequency of connectivity checks (default: 1.0s).
- `PING_TARGETS`: List of IP addresses or hostnames to ping.
- `HTTP_TARGETS`: List of URLs to check via HTTP HEAD requests.
- `WIFI_POLL_INTERVAL`: Frequency of WiFi detail updates (default: 10.0s).
- `LATENCY_WARNING/CRITICAL`: Thresholds for latency alerts.

## Project Structure

- `main.py`: FastAPI web server and application entry point.
- `monitor.py`: Background connectivity monitoring logic.
- `database.py`: SQLite database initialization and logging.
- `config.py`: Application settings and defaults.
- `templates/`: HTML templates using Jinja2 and HTMX.
- `static/`: Static assets (CSS/JS).
