import logging
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

# Log messages
YAML_FILE_NOT_FOUND = "❌ YAML file not found: %s"
YAML_PARSE_FAILED = "❌ Failed to parse YAML file: %s"
PROMPT_FILE_NOT_FOUND = "❌ Prompt file not found: %s"
PROMPT_FILE_ERROR = "❌ Error reading prompt file: %s"

class MetadataParser:
    """
    A utility class for reading and parsing YAML files to extract metric metadata
    and render prompt templates with optional context.
    """

    def __init__(self, base_path: str = "./metadata"):
        """
        Initialize the parser with a base directory for YAML files.

        Args:
            base_path (str): Directory path where YAML files are located.
        """
        self.base_path = Path(base_path)

    def read_yaml_file(self, filename: str) -> dict:
        """
        Reads a YAML file and returns its contents as a dictionary.

        Args:
            filename (str): Name of the YAML file (relative to base_path).

        Returns:
            dict: Parsed YAML content.

        Raises:
            FileNotFoundError: If the file does not exist.
            Exception: If the YAML is invalid.
        """
        file_path = self.base_path / filename
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
            return data
        except FileNotFoundError:
            logger.error(YAML_FILE_NOT_FOUND, filename)
            raise
        except yaml.YAMLError as e:
            logger.error(YAML_PARSE_FAILED, str(e))
            raise

    def extract_metrics_with_attributes(self, data: dict) -> list:
        """
        Extracts metrics and their associated attributes from a given YAML structure.

        Args:
            data (dict): Parsed YAML dictionary.

        Returns:
            list: List of metrics with their descriptions and attributes.
        """        
        resource_level_attributes = []
        for name, details in data.get("resource_attributes", {}).items():
            if details.get("enabled", False):
                resource_level_attributes.append({
                    "name": name,
                    "description": details.get("description", ""),
                    "type": details.get("type", ""),
                    "enum": details.get("enum", None)
                })

        metric_level_attributes = {}     
        for name, details in data.get("attributes", {}).items():
            final_name = details.get("name_override", name)
            metric_level_attributes[name] = {
                "name": final_name,
                "description": details.get("description", ""),
                "type": details.get("type", ""),
                "enum": details.get("enum", None)
            }

        metrics_output = []
        for metric_name, metric_info in data.get("metrics", {}).items():
            if not metric_info.get("enabled", False):
                continue
            
            attributes = []
            attributes.extend(resource_level_attributes)
            for attr in metric_info.get("attributes", []):
                if attr in metric_level_attributes:
                    attributes.append(metric_level_attributes[attr])

            metrics_output.append({
                "name": metric_name,
                "description": metric_info.get("description", ""),
                "unit": metric_info.get("unit", ""),
                "attributes": attributes
            })

        return metrics_output