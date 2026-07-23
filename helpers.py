import json
import subprocess

def load_settings() -> dict:
    global CFG
    with open('config.json', 'r') as f:
        CFG = json.load(f)
    print('Found settings:', CFG)
    return CFG


def run_cmd(*args) -> bytes:
    return subprocess.check_output(args)

def notify(msg: str) -> None:
    print('Notification msg:', msg)
    run_cmd('notify-send', 'PIPEWIRE-STEAM-RECORDING-FIX\n\n' + msg)
