"""
GreenRoute Mesh v2 — Test Helpers
Shared formatting, HTTP client, and tracking for all test scripts.
"""

import sys
import requests

# ── ANSI colors ───────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
BG_GREEN  = "\033[42m"
BG_RED    = "\033[41m"
BG_YELLOW = "\033[43m"

LINE_W = 72

# ── Formatting ────────────────────────────────────────────────────────────────

def hr(char="─"):
    print(f"{DIM}{char * LINE_W}{RESET}")

def hr_double():
    print(f"{DIM}{'═' * LINE_W}{RESET}")

def banner(text):
    print()
    hr_double()
    pad = (LINE_W - len(text) - 2) // 2
    print(f"{'═' * pad} {BOLD}{CYAN}{text}{RESET} {'═' * (LINE_W - pad - len(text) - 2)}")
    hr_double()

def section(text):
    print()
    print(f"  {BOLD}{WHITE}▸ {text}{RESET}")
    hr()

def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")

def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")

def info(msg):
    print(f"  {DIM}│{RESET} {msg}")

def kv(key, value, indent=4):
    pad = " " * indent
    print(f"{pad}{DIM}{key:<24}{RESET}{BOLD}{value}{RESET}")

def table_row(cols, widths):
    parts = []
    for col, w in zip(cols, widths):
        parts.append(str(col)[:w].ljust(w))
    print(f"    {DIM}│{RESET} {'  '.join(parts)} {DIM}│{RESET}")

def table_sep(widths):
    total = sum(widths) + 2 * (len(widths) - 1) + 2
    print(f"    {DIM}{'─' * (total + 2)}{RESET}")

def status_badge(passed, total):
    if passed == total:
        return f"{BG_GREEN}{BOLD} PASS {RESET}"
    elif passed == 0:
        return f"{BG_RED}{BOLD} FAIL {RESET}"
    return f"{BG_YELLOW}{BOLD} PARTIAL {RESET}"

def aqi_color(aqi):
    if aqi is None: return DIM
    if aqi <= 50:  return GREEN
    if aqi <= 100: return YELLOW
    if aqi <= 150: return "\033[38;5;208m"
    if aqi <= 200: return RED
    if aqi <= 300: return "\033[95m"
    return "\033[38;5;124m"


# ── Result tracking ──────────────────────────────────────────────────────────

class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def track(self, success):
        if success:
            self.passed += 1
        else:
            self.failed += 1

    def skip(self):
        self.skipped += 1

    @property
    def total(self):
        return self.passed + self.failed + self.skipped

    def summary(self):
        banner("Test Summary")
        print()
        kv("Total checks", self.total)
        kv("Passed", f"{GREEN}{self.passed}{RESET}")
        kv("Failed", f"{RED}{self.failed}{RESET}" if self.failed else "0")
        kv("Skipped", self.skipped)
        print()
        tests_run = self.passed + self.failed
        badge = status_badge(self.passed, tests_run) if tests_run else f"{BG_YELLOW}{BOLD} NONE {RESET}"
        print(f"    {badge}  {self.passed}/{tests_run} checks passed")
        print()
        hr_double()
        print()
        return self.failed == 0


# ── HTTP client ───────────────────────────────────────────────────────────────

class APIClient:
    def __init__(self, base_url="http://localhost:5001"):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path, **kwargs):
        return self.session.get(f"{self.base}{path}", **kwargs)

    def post(self, path, json_data=None, **kwargs):
        return self.session.post(f"{self.base}{path}", json=json_data, **kwargs)

    def put(self, path, json_data=None, **kwargs):
        return self.session.put(f"{self.base}{path}", json=json_data, **kwargs)


def require_server(api):
    """Check server is running. Exit if not."""
    try:
        r = api.get("/api/health")
        if r.status_code == 200:
            return True
    except requests.ConnectionError:
        pass
    fail(f"Cannot connect to {api.base}")
    info("Start the server first:  cd v2 && python app.py")
    sys.exit(1)
