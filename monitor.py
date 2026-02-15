import asyncio
import time
import httpx
from datetime import datetime
from collections import deque
from config import settings
from database import log_outage

class ConnectivityMonitor:
    def __init__(self):
        self.history = deque(maxlen=settings.MAX_BUFFER_SIZE)
        self.is_running = False

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

    async def run_checks(self):
        tasks = []
        for target in settings.PING_TARGETS:
            tasks.append(self.ping(target))
        for target in settings.HTTP_TARGETS:
            tasks.append(self.http_check(target))
        
        results = await asyncio.gather(*tasks)
        
        # Log failures and critical latency to DB
        for res in results:
            thresholds = settings.CUSTOM_THRESHOLDS.get(res["target"], {
                "critical": settings.LATENCY_CRITICAL,
                "warning": settings.LATENCY_WARNING
            })
            
            is_critical_latency = (
                res["success"] and
                res.get("latency") is not None and
                res["latency"] > thresholds["critical"]
            )

            if not res["success"] or is_critical_latency:
                error_msg = res.get("error")
                if is_critical_latency:
                    error_msg = f"Critical latency: {res['latency']:.1f}ms (threshold: {thresholds['critical']}ms)"
                
                await log_outage(
                    res["target"],
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
