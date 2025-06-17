from pathlib import Path
import requests
import yaml

def read_yaml_file(filename: str) -> dict:
    """
    Reads a YAML file and returns its contents as a dictionary.
    
    Args:
        path (str): Path to the YAML file.
    
    Returns:
        dict: Parsed YAML data.
    """
    try:
        with open(f"./services/{filename}", "r") as f:
            data = yaml.safe_load(f)
        return data
    except FileNotFoundError:
        raise FileNotFoundError(f"YAML file not found filename: {filename}")
    except yaml.YAMLError as e:
        raise Exception(f"Failed to parse YAML file: {e}")

def extract_metrics_with_attributes(data):
    attributes = data.get("attributes", {})
    resource_attrs = data.get("resource_attributes", {})
    metrics = data.get("metrics", {})

    # Parse resource attributes (available for all metrics)
    resource_attr_details = []
    for key, info in resource_attrs.items():
        name = info.get("name_override", key)
        desc = info.get("description", "")
        resource_attr_details.append({
            "name": name,
            "description": desc
        })

    result = []

    for metric_name, metric_info in metrics.items():
        metric_desc = metric_info.get("description", "")
        attr_keys = metric_info.get("attributes", [])
        attr_details = []

        for attr_key in attr_keys:
            if attr_key in attributes:
                attr_info = attributes[attr_key]
                name = attr_info.get("name_override", attr_key)
                desc = attr_info.get("description", "")
                attr_details.append({
                    "name": name,
                    "description": desc
                })

        # Combine resource attributes + specific attributes
        combined_attributes = resource_attr_details + attr_details

        result.append({
            "metric": metric_name,
            "description": metric_desc,
            "attributes": combined_attributes
        })

    return result

def get_yaml_dump(yaml_data_dict) -> str:
    return yaml.dump(yaml_data_dict, default_flow_style=False)

def load_prompt(file_path, context_vars=None):
    try:
        prompt_template = Path(file_path).read_text()
        if context_vars:
            for key, value in context_vars.items():
                prompt_template = prompt_template.replace(f"{{{{{key}}}}}", value)
        return prompt_template
    except FileNotFoundError:
        print(f"❌ Prompt file not found: {file_path}")
        return None
    except Exception as e:
        print(f"❌ Error reading prompt file: {e}")
        return None