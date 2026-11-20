import asyncio
import time
import httpx
import re
from datetime import datetime
from collections import deque
from config import settings
from database import log_outage

class ConnectivityMonitor:
    def __init__(self):
        self.history = deque(maxlen=settings.MAX_BUFFER_SIZE)
        self.is_running = False
        self.consecutive_failures = {}  # target -> count
        self.wifi_info = {}
        self.last_wifi_check = 0
        self.public_ip = "Fetching..."
        self.last_ip_check = 0

    async def ping(self, host):
        """Perform a single ICMP ping."""
        try:
            # -c 1: one packet, -W: timeout in ms on macOS/Linux
            # Note: macOS ping timeout is -t but -W is common on many systems. 
            # Using a simple subprocess for robustness.
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-t", str(int(settings.TIMEOUT * 1000)), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            start = time.time()
            stdout, stderr = await proc.communicate()
            latency = (time.time() - start) * 1000
            
            return {
                "target": host,
                "success": proc.returncode == 0,
                "latency": latency if proc.returncode == 0 else None,
                "type": "ICMP"
            }
        except Exception as e:
            return {"target": host, "success": False, "error": str(e), "type": "ICMP"}

    async def http_check(self, url):
        """Perform an HTTP HEAD request."""
        async with httpx.AsyncClient(timeout=settings.TIMEOUT) as client:
            try:
                start = time.time()
                response = await client.head(url, follow_redirects=True)
                latency = (time.time() - start) * 1000
                return {
                    "target": url,
                    "success": response.status_code < 400,
                    "latency": latency,
                    "type": "HTTP"
                }
            except Exception as e:
                return {"target": url, "success": False, "error": str(e), "type": "HTTP"}

    async def get_wifi_info(self):
        """Fetch WiFi details on macOS."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "system_profiler", "SPAirPortDataType",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode()
            
            info = {
                "ssid": "Unknown",
                "phy_mode": "Unknown",
                "channel": "Unknown",
                "signal": "Unknown",
                "type": "Unknown"
            }
            
            if "Current Network Information:" in output:
                section = output.split("Current Network Information:")[1].split("Other Local Wi-Fi Networks:")[0]
                lines = section.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if line and not any(x in line for x in ["PHY Mode", "Channel", "Signal", "Country", "Network Type", "Security", "Transmit", "MCS"]) and line.endswith(":"):
                        info["ssid"] = line[:-1]
                        break
                
                phy_match = re.search(r"PHY Mode: (.*)", section)
                if phy_match:
                    info["phy_mode"] = phy_match.group(1).strip()
                
                channel_match = re.search(r"Channel: (.*)", section)
                if channel_match:
                    channel_val = channel_match.group(1).strip()
                    info["channel"] = channel_val
                    if "5GHz" in channel_val:
                        info["type"] = "5G"
                    elif "2.4GHz" in channel_val:
                        info["type"] = "2.4G"
                    elif "6GHz" in channel_val:
                        info["type"] = "6G"
                
                signal_match = re.search(r"Signal / Noise: (.*) /", section)
                if signal_match:
                    info["signal"] = signal_match.group(1).strip()
            
            self.wifi_info = info
            self.last_wifi_check = time.time()
            return info
        except Exception as e:
            self.wifi_info = {"error": str(e)}
            return self.wifi_info

    async def get_public_ip(self):
        """Fetch public IP address."""
        print(f"Fetching public IP from {settings.IP_CHECK_URL}...")
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(settings.IP_CHECK_URL)
                if response.status_code == 200:
                    self.public_ip = response.text.strip()
                    print(f"Fetched public IP: {self.public_ip}")
                else:
                    self.public_ip = f"Error: {response.status_code}"
                    print(f"Error fetching public IP: {response.status_code}")
            except Exception as e:
                self.public_ip = "Offline"
                print(f"Exception fetching public IP: {e}")
        self.last_ip_check = time.time()

    async def run_checks(self):
        # Update WiFi info periodically
        if time.time() - self.last_wifi_check > settings.WIFI_POLL_INTERVAL:
            asyncio.create_task(self.get_wifi_info())

        # Update Public IP periodically
        if time.time() - self.last_ip_check > settings.IP_POLL_INTERVAL:
            asyncio.create_task(self.get_public_ip())

        tasks = []
        for target in settings.PING_TARGETS:
            tasks.append(self.ping(target))
        for target in settings.HTTP_TARGETS:
            tasks.append(self.http_check(target))
        
        results = await asyncio.gather(*tasks)
        
        # Log failures and critical latency to DB after 3 consecutive occurrences
        for res in results:
            target = res["target"]
            if target not in self.consecutive_failures:
                self.consecutive_failures[target] = 0

            thresholds = settings.CUSTOM_THRESHOLDS.get(target, {
                "critical": settings.LATENCY_CRITICAL,
                "warning": settings.LATENCY_WARNING
            })
            
            is_critical_latency = (
                res["success"] and
                res.get("latency") is not None and
                res["latency"] > thresholds["critical"]
            )

            is_bad = not res["success"] or is_critical_latency

            if is_bad:
                self.consecutive_failures[target] += 1
            else:
                self.consecutive_failures[target] = 0

            if self.consecutive_failures[target] == 3:
                error_msg = res.get("error")
                if is_critical_latency:
                    error_msg = f"Critical latency (3x): {res['latency']:.1f}ms (threshold: {thresholds['critical']}ms)"
                elif not res["success"] and not error_msg:
                    error_msg = "Target offline (3x)"
                
                await log_outage(
                    target,
                    res["type"],
                    error_msg,
                    res.get("latency")
                )

        entry = {
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "overall_success": any(r["success"] for r in results)
        }
        self.history.append(entry)
        return entry

    async def start_polling(self):
        self.is_running = True
        while self.is_running:
            await self.run_checks()
            await asyncio.sleep(settings.POLL_INTERVAL)

    def stop_polling(self):
        self.is_running = False

monitor = ConnectivityMonitor()
