import yaml
import json
import openai
import os

# Load API key from env
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise EnvironmentError("Set OPENAI_API_KEY as an environment variable.")

# Load YAML
with open("metadata.yaml", "r") as f:
    data = yaml.safe_load(f)

# Extract global attributes
global_attrs = []
for name, details in data.get("resource_attributes", {}).items():
    if details.get("enabled", False):
        global_attrs.append({
            "name": name,
            "description": details.get("description", ""),
            "type": details.get("type", "")
        })

# Extract attribute definitions
attribute_defs = {}
for name, details in data.get("attributes", {}).items():
    final_name = details.get("name_override", name)
    attribute_defs[name] = {
        "name": final_name,
        "description": details.get("description", ""),
        "type": details.get("type", ""),
        "enum": details.get("enum", None)
    }

# Extract enabled metrics
metrics_output = []
for metric_name, metric_info in data.get("metrics", {}).items():
    if not metric_info.get("enabled", False):
        continue

    attributes = []
    for attr in metric_info.get("attributes", []):
        if attr in attribute_defs:
            attributes.append(attribute_defs[attr])

    # Append global resource attributes to all metrics
    attributes.extend(global_attrs)

    metrics_output.append({
        "name": metric_name,
        "description": metric_info.get("description", ""),
        "unit": metric_info.get("unit", ""),
        "attributes": attributes
    })

# Convert to JSON string
metrics_json_str = json.dumps(metrics_output, indent=2)

# Generic prompt for infra dashboards
prompt = f"""
You are an expert infrastructure dashboard architect.

You are given a list of telemetry metrics exported from a specific infrastructure system (like a server, application, hypervisor, or queue). These metrics have been parsed from a YAML schema and are provided in structured JSON. Each metric includes:
- name
- description
- unit
- a list of attributes (each with name, description, type, and optional enum values)

Your goal is to generate a structured and insightful observability dashboard specification.

You must:
1. Identify viewpoints from the list of metrics. A viewpoint is a logical boundary or resource (e.g., host, instance, node, process, queue, etc.) inferred from metric names or attributes. You may create multiple viewpoints if metrics cover more than one.
2. For each viewpoint:
   - Provide a viewpoint title
   - Write a description that defines what the viewpoint observes (based on metric content only, no external assumptions)

3. Within each viewpoint, define sections. A section groups related metrics under a theme (e.g., CPU usage, memory utilization, disk health, request throughput, message backlog).
   - For each section:
     - Provide a title
     - Provide a description of what the section shows
     - Add one or more charts

4. Each chart must include:
   - title: short and clear chart name
   - description: what this chart visualizes
   - metrics: list of metric names to be used in the chart
   - chart_type: one of [line, bar, gauge, pie, heatmap, stacked_area]
   - filters: list of attributes that can be used to filter, group, or break down the data

Only include metrics that are explicitly marked as enabled.
Use:
- Metric names and descriptions to infer category and viewpoint
- Metric units to guide chart type selection
- Metric attributes for chart-level filters or breakdowns

DO NOT rely on any prior knowledge about the system (e.g., don't assume this is a Kafka or VM system unless the metric names make it obvious).

Here is the JSON list of metrics:
{metrics_json_str}
"""

# Send to OpenAI
response = openai.ChatCompletion.create(
    model="gpt-4-1106-preview",  # or "gpt-4o" if preferred
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.3
)

# Print the dashboard JSON
print(response["choices"][0]["message"]["content"])