#!./venv/bin/python

import sys
import time
import os
import glob
import subprocess
import threading

etherserver_path = "snippets/ethernetserver.py"


def run_ether_server(path=etherserver_path):
    """Run the ether server first so that it receives the client's messages."""
    invocation = f"python {os.path.abspath(path)}"
    completed: subprocess.CompletedProcess = subprocess.run(
        ["python", os.path.abspath(path)], stdout=subprocess.PIPE)
    if completed.returncode != 0:
        print(f"Error processing {path}. Output: {completed.stdout}")
    with open(f"{path}.out", "wb") as output_file:
        output_file.write(completed.stdout)


if __name__ == '__main__':

    thread = threading.Thread(target=run_ether_server)
    thread.start()

    time.sleep(2)

    for path in (p for p in glob.glob(os.path.join("snippets", "**", "*.py"), recursive=True)
                 if p != etherserver_path):
        print(f"Running {path}...")
        completed: subprocess.CompletedProcess = subprocess.run(
            ["python", os.path.abspath(path)], stdout=subprocess.PIPE)
        if completed.returncode != 0:
            print(f"Error processing {path}. Output: {completed.stdout}")
        with open(f"{path}.out", "wb") as output_file:
            output_file.write(completed.stdout)
        print(f" done!")

    print("Waiting for etherserver thread...")
    thread.join()
    print(" done!")
