#!/usr/bin/env python3
import yaml
import os

CONFIG_FILE = "export_config.yml"

print(f"Looking for config file: {CONFIG_FILE}")
print(f"File exists: {os.path.exists(CONFIG_FILE)}")

with open(CONFIG_FILE, "r") as f:
    content = f.read()
    print(f"Content: {repr(content)}")
    
config = yaml.safe_load(content)
print(f"Parsed config: {config}")

export_list = config.get("export", [])
print(f"Export list: {export_list}")
print(f"Length of export list: {len(export_list)}")
