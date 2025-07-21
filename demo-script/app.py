import json
from pprint import pformat
from dotenv import load_dotenv 
from services.signalfx import SignalFxClient
from services.circuit import CircuitClient
from services.metadata import MetadataParser

load_dotenv()

if __name__ == "__main__":
    sf_client = SignalFxClient()
    circuit_client = CircuitClient()
    metadata_parser = MetadataParser()
    
    servicefilename = "apache.yaml"
    token = circuit_client.get_access_token()

    service_metadata = metadata_parser.extract_metrics_with_attributes(
        metadata_parser.read_yaml_file(servicefilename)
    )
    
    perspective_system_prompt = '''
        You are a domain expert in infrastructure observability. Your task is to analyze structured metric metadata and identify logical perspectives from which the service can be monitored. Each perspective corresponds to a unique monitoring view based on how the metrics are organized by attributes or entities.
    '''
    
    perspective_user_prompt = '''
        Analyze the given metric metadata and return a structured observability model with the following:
        
        1.	List of perspectives: A perspective is a logical monitoring dimension or component inferred from the metadata structure. These are typically based on   recurring attributes (e.g., a host identifier, process name, container ID, etc.) that suggest an object-centric view.
        2.	For each perspective:
            - Provide the perspective name (inferred from attributes or metric naming structure).
            - Generate:
                An Instance Dashboard that focuses on a single instance of the object.
                An Aggregate Dashboard that covers all instances under the same perspective.
            - Include:
                A name for each dashboard.
                A description explaining what type of health or KPIs it would cover.
                
        Do not assume the service type or insert example services. Base all logic strictly on the metric metadata.
        
        Format the output in this structure:
        {
            "perspectives": [
                {
                    "name": "<perspective_name>",
                    "dashboards": [
                        {
                            "name": "<instance_dashboard_name>",
                            "type": "instance",
                            "description": "<instance dashboard description>"
                            
                        },
                        {
                            "name": "<aggregate_dashboard_name>",
                            "type": "aggregate",
                            "description": "<aggregate dashboard description>"
                        }
                    ]
                }
            ]
        }
    '''
    
    perspectives = circuit_client.call_circuit(perspective_user_prompt, perspective_system_prompt)
    
    chart_user_prompt = '''
        You are an expert in infrastructure monitoring and observability. Your job is to generate high-quality, structured monitoring content based on user input. Assume no specific service unless explicitly stated. Avoid hallucinating metric names or technical details — use only logical, human-readable metric concepts. All output must strictly follow the JSON structure provided by the user.

        You will be given the name of a dashboard, its type (instance-level or aggregate), its description, and the broader perspective it belongs to. Your job is to return a list of useful charts (KPIs) that help visualize and monitor the described dashboard's goals.

        Always reason through what meaningful metrics and views would help someone operating that dashboard, even in a generic infrastructure context.'''
        
    chart_system_prompt = '''
        Given the following inputs, generate a list of charts in JSON format:
            - perspective_name: "<PERSPECTIVE_NAME>"
            - dashboard_name: "<DASHBOARD_NAME>"
            - dashboard_type: "<instance | aggregate>"
            - description: "<DESCRIPTION_OF_DASHBOARD>"

        Each chart should include:
            - title: short chart name
            - description: what the chart shows and why it's useful
            - metrics: list of metric used
            - chart_type: suitable type of chart (line, bar, column, heatmap, etc.)
            - filters: list of relevant filters (like instance_id, region, environment, etc.)

        Output format:
            {
                "charts": [
                    {
                        "title": "...",
                        "description": "...",
                        "metrics": ["..."],
                        "chart_type": "line",
                        "filters": ["..."]
                    }
                ]
            }
    '''
    
    print(perspectives)
    
    print(json.dumps(service_metadata))