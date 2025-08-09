import json
import csv
import os

input_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge-base', 'logistics_datapoints.json')
output_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge-base', 'logistics_datapoints.csv')

with open(input_path, 'r', encoding='utf-8') as f:
    datapoints = json.load(f)

# Collect all possible field names
fieldnames = set()
for dp in datapoints:
    fieldnames.update(dp.keys())
fieldnames = sorted(fieldnames)

with open(output_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for dp in datapoints:
        writer.writerow(dp)

print(f"Successfully converted {len(datapoints)} datapoints to CSV: {output_path}")
