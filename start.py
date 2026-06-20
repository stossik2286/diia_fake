import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

server = subprocess.Popen([sys.executable, str(BASE / "server.py")])
bot = subprocess.Popen([sys.executable, str(BASE / "bot.py")])

try:
    server.wait()
except KeyboardInterrupt:
    server.terminate()
    bot.terminate()
