# Quick Start

This guide will get you creating GO-CAM models in under 5 minutes.

## Setup Environment

First, set up your environment with a Barista token:

```bash
# Set your Barista token (required)
export BARISTA_TOKEN=your-token-here

# For development: Contact the GO team for a dev token
# For production: Get token from Noctua login
```

## Create Your First Model

### Using Python

```python
from noctua import BaristaClient

# Initialize client
client = BaristaClient()

# Create a new model
response = client.create_model(title="My First GO-CAM Model")
model_id = response.model_id
print(f"Created model: {model_id}")

# Add molecular activities with variable names for easy reference
response = client.add_individual(
    model_id,
    "GO:0003924",  # GTPase activity
    assign_var="gtpase"  # Variable name instead of tracking complex ID
)

response = client.add_individual(
    model_id,
    "GO:0004674",  # protein kinase activity
    assign_var="kinase"  # Another simple variable
)

# Connect them using variable names - no need to track IDs!
response = client.add_fact(
    model_id,
    subject_id="gtpase",  # Use the variable name
    object_id="kinase",   # Use the variable name
    predicate_id="RO:0002413"  # directly positively regulates
)

# View the model in Noctua
from noctua import get_noctua_url
url = get_noctua_url(model_id, dev=True)
print(f"View in Noctua: {url}")
```

### Using the CLI

```bash
# Create a model
noctua barista create-model --title "My First Model"

# Add individuals
noctua barista add-individual \
    --model 6796b94c00003233 \
    --class GO:0003924

# Add facts/edges
noctua barista add-fact \
    --model 6796b94c00003233 \
    --subject id1 \
    --object id2 \
    --predicate RO:0002413

# Export the model
noctua barista export-model \
    --model 6796b94c00003233 \
    --format minerva-json \
    --output my-model.json
```

## Working with Existing Models

### List Available Models

```python
# List all development models
result = client.list_models(state="development", limit=10)

for model in result["models"]:
    print(f"{model['id']}: {model.get('title', 'Untitled')}")
```

### Modify an Existing Model

```python
# Get an existing model
model_id = "gomodel:6796b94c00003233"
response = client.get_model(model_id)

# Check current state
print(f"Individuals: {len(response.individuals)}")
print(f"Facts: {len(response.facts)}")

# Add evidence to a fact
evidence_requests = client.req_add_evidence_to_fact(
    model_id,
    subject_id="subject-id",
    object_id="object-id",
    predicate_id="RO:0002413",
    eco_id="ECO:0000314",  # direct assay evidence
    sources=["PMID:12345678"]
)
response = client.m3_batch(evidence_requests)
```

## Export Models

### Export Formats

```python
# Native Minerva JSON
response = client.get_model(model_id)
minerva_json = response.raw["data"]

# GO-CAM structured JSON
from gocam.translation.minerva_wrapper import MinervaWrapper
gocam_model = MinervaWrapper.minerva_object_to_model(minerva_json)
gocam_json = gocam_model.model_dump_json(indent=2)

# YAML format
import yaml
gocam_yaml = yaml.dump(gocam_model.model_dump(), default_flow_style=False)
```

## Visual Documentation

Capture screenshots as you build models:

```python
from noctua import NoctuaScreenshotCapture

# Initialize screenshot capture
with NoctuaScreenshotCapture(headless=False) as capture:
    # Open model in browser
    capture.open_model(model_id)

    # Take screenshot
    capture.capture(filename="model_state.png")

    # Make changes via API
    client.add_individual(model_id, "GO:0003924")

    # Refresh and capture again
    capture.refresh_model()
    capture.capture(filename="after_changes.png")
```

## Next Steps

- Explore the [Python API Guide](../guide/python-api.md) for detailed usage
- See [Complete Examples](../examples/noctua_demo.ipynb) in Jupyter notebooks
- Learn about [Screenshot Automation](../guide/screenshots.md) for visual documentation
- Check the [CLI Reference](../guide/cli.md) for all command options