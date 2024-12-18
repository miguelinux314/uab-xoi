#!/usr/bin/python

import os
import glob
import subprocess

if __name__ == '__main__':
    for path in glob.glob(os.path.join("snippets", "**", "*.py"), recursive=True):
        print(f"Processing {path}...", end="")
        
        completed: subprocess.CompletedProcess = subprocess.run(["python", os.path.abspath(path)],
                                                                stdout=subprocess.PIPE)
        if completed.returncode != 0:
            raise ValueError(f"Error processing {path}. Output: {completed.stdout}") 
        with open(f"{path}.out", "wb") as output_file:
            output_file.write(completed.stdout)

        print(f" done!")
        
            