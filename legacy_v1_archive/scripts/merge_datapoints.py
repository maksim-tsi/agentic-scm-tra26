import json
import os

# List of your source files and their corresponding 'port_area' value
files_to_merge = {
    "Antwerp_Datapoints.json": "Antwerp",
    "IMO_Datapoints.json": "International - IMO",
    "INCOTERMS_Datapoints.json": "Guidelines - INCOTERMS",
    "Hamburg_Datapoints.json": "Hamburg",
    "Riga_Datapoints.json": "Riga",
    "Rotterdam_Datapoints.json": "Rotterdam",
    "Yangshan_Datapoints.json": "Shanghai",
    "Singapore_Datapoints.json": "Singapore"
}

all_datapoints = []

raw_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'datapoints-raw')
output_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge-base', 'logistics_datapoints.json')

for filename, port_area in files_to_merge.items():
    file_path = os.path.join(raw_dir, filename)
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for datapoint in data:
            # Ensure the port_area is set correctly
            datapoint['port_area'] = port_area
            all_datapoints.append(datapoint)

# Save the unified dataset to a new file
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_datapoints, f, indent=4)

print(f"Successfully merged {len(all_datapoints)} datapoints into '{output_path}'")
