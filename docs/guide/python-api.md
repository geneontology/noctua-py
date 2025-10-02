# Python API Guide

## Overview

The `noctua-py` Python API provides a comprehensive interface for manipulating GO-CAM models. This guide covers all major operations with practical examples.

## Client Initialization

### Basic Setup

```python
from noctua import BaristaClient

# Use defaults (dev server with env token)
client = BaristaClient()

# Explicit configuration
client = BaristaClient(
    token="your-token",
    base_url="http://barista-dev.berkeleybop.org",
    namespace="minerva_public_dev"
)
```

## Model Operations

### Creating Models

```python
# Create empty model
response = client.create_model()
model_id = response.model_id

# Create with title
response = client.create_model(title="RAS-RAF-MEK pathway")
```

### Listing Models

```python
# List all models
result = client.list_models()

# Filter models
result = client.list_models(
    limit=20,
    state="development",
    title="kinase",  # Search in title
    contributor="https://orcid.org/0000-0002-6601-2165"
)

# Iterate through results
for model in result["models"]:
    print(f"{model['id']}: {model.get('title')}")
```

### Getting Model Details

```python
response = client.get_model(model_id)

# Access model properties
print(f"Model ID: {response.model_id}")
print(f"State: {response.model_state}")
print(f"Individuals: {len(response.individuals)}")
print(f"Facts: {len(response.facts)}")

# Raw data access
raw_data = response.raw["data"]
```

## Variable Tracking

The client supports automatic variable tracking, allowing you to use simple names instead of complex generated IDs when building models.

### How It Works

When you add individuals to a model, the server generates complex IDs like `gomodel:123/individual-456`. With variable tracking, you can assign simple names and the client will automatically track the mapping:

```python
# Add individuals with variable names
client.add_individual(model_id, "GO:0003924", assign_var="ras")
client.add_individual(model_id, "GO:0004674", assign_var="raf")

# Use variables in subsequent operations
client.add_fact(model_id, "ras", "raf", "RO:0002413")  # No need to track IDs!
```

### Variable vs CURIE Disambiguation

The client automatically distinguishes between:
- **Variables**: Simple names without ':' or '/' (e.g., "ras", "kinase1", "my_protein")
- **CURIEs/IDs**: Contain ':' or '/' (e.g., "GO:0003924", "RO:0002413", "gomodel:123/individual-456")

### Managing Variables

```python
# Check tracked variables for a model
variables = client.get_variables(model_id)
print(variables)  # {'ras': 'gomodel:123/individual-456', ...}

# Get specific variable value
actual_id = client.get_variable(model_id, "ras")

# Manually set a variable (rarely needed)
client.set_variable(model_id, "my_var", "some-individual-id")

# Clear variables for a model
client.clear_variables(model_id)
```

### Disabling Variable Tracking

Variable tracking is enabled by default but can be disabled:

```python
# Disable tracking for performance or specific use cases
client = BaristaClient(track_variables=False)
```

### Complete Example

```python
# Create model and add components with variables
response = client.create_model(title="MAPK Cascade")
model_id = response.model_id

# Add molecular activities with meaningful names
client.add_individual(model_id, "GO:0003924", assign_var="ras")  # GTPase
client.add_individual(model_id, "GO:0004674", assign_var="raf")  # Kinase
client.add_individual(model_id, "GO:0004707", assign_var="mek")  # MAP kinase
client.add_individual(model_id, "GO:0004709", assign_var="erk")  # MAPKKK

# Build pathway using variable names
client.add_fact(model_id, "ras", "raf", "RO:0002413")  # ras activates raf
client.add_fact(model_id, "raf", "mek", "RO:0002413")  # raf activates mek
client.add_fact(model_id, "mek", "erk", "RO:0002413")  # mek activates erk

# Add evidence using variables
client.add_fact_with_evidence(
    model_id,
    "ras",  # Variable name, not complex ID!
    "raf",
    "RO:0002413",
    "ECO:0000314",
    ["PMID:12345678"]
)

# Mix variables with CURIEs
client.add_individual(model_id, "GO:0005737", assign_var="cytoplasm")
client.add_fact(model_id, "ras", "cytoplasm", "BFO:0000066")  # occurs_in
```

## Individual Operations

### Adding Individuals

```python
# Add molecular function
response = client.add_individual(
    model_id,
    "GO:0003924",  # GTPase activity
    assign_var="ras"  # Variable for reference
)

# Get the created individual ID
for ind in response.individuals:
    if any(t.get("id") == "GO:0003924" for t in ind.get("type", [])):
        individual_id = ind["id"]
```

### Removing Individuals

```python
# Remove by ID
response = client.remove_individual(model_id, individual_id)

# Alternative method
response = client.delete_individual(model_id, individual_id)
```

## Fact/Edge Operations

### Adding Facts

```python
# Simple fact
response = client.add_fact(
    model_id,
    subject_id="ras",      # Use variable or actual ID
    object_id="raf",
    predicate_id="RO:0002413"  # directly positively regulates
)

# With evidence
response = client.add_fact_with_evidence(
    model_id,
    subject_id="ras",
    object_id="raf",
    predicate_id="RO:0002413",
    eco_id="ECO:0000314",  # direct assay evidence
    sources=["PMID:12345678", "PMID:87654321"],
    with_from=["UniProtKB:P01112"]
)
```

### Removing Facts

```python
response = client.remove_fact(
    model_id,
    subject_id="ras",
    object_id="raf",
    predicate_id="RO:0002413"
)

# Alternative method
response = client.delete_edge(
    model_id,
    subject_id="ras",
    object_id="raf",
    predicate_id="RO:0002413"
)
```

## Evidence Management

### Adding Evidence to Existing Facts

```python
# Build evidence requests
evidence_requests = client.req_add_evidence_to_fact(
    model_id,
    subject_id="ras",
    object_id="raf",
    predicate_id="RO:0002413",
    eco_id="ECO:0000314",
    sources=["PMID:12345678"],
    with_from=["UniProtKB:P01112", "UniProtKB:P04049"]
)

# Execute batch request
response = client.m3_batch(evidence_requests)
```

## Batch Operations

### Multiple Operations in One Request

```python
# Build multiple requests
requests = []

# Add individuals
requests.append(client.req_add_individual(
    model_id, "GO:0003924", "ras"
))
requests.append(client.req_add_individual(
    model_id, "GO:0004674", "raf"
))

# Add fact
requests.append(client.req_add_fact(
    model_id, "ras", "raf", "RO:0002413"
))

# Execute all at once
response = client.m3_batch(requests)
```

## Model Export

### Native Minerva Format

```python
# Get raw Minerva JSON
response = client.get_model(model_id)
minerva_json = response.raw["data"]

# Save to file
import json
with open("model.json", "w") as f:
    json.dump(minerva_json, f, indent=2)
```

### GO-CAM Structured Format

```python
from gocam.translation.minerva_wrapper import MinervaWrapper

# Convert to GO-CAM
try:
    gocam_model = MinervaWrapper.minerva_object_to_model(minerva_json)

    # Export as JSON
    gocam_json = gocam_model.model_dump_json(indent=2)

    # Export as YAML
    import yaml
    gocam_yaml = yaml.dump(
        gocam_model.model_dump(exclude_none=True),
        default_flow_style=False
    )
except Exception as e:
    print(f"Model may not follow standard GO-CAM structure: {e}")
```

## Model Management

### Clearing Models

```python
# Clear all content (be careful!)
try:
    response = client.clear_model(model_id)
except BaristaError as e:
    print(f"Cannot clear: {e}")
    # Production models are protected

# Force clear (dangerous!)
response = client.clear_model(model_id, force=True)
```

## URL Generation

```python
from noctua import get_noctua_url

# Generate Noctua URL
url = get_noctua_url(model_id, dev=True)
print(f"View in Noctua: {url}")

# With explicit token
url = get_noctua_url(model_id, token="your-token", dev=False)
```

## Error Handling

### Handling API Errors

```python
from noctua import BaristaError

try:
    response = client.create_model()
    if not response.ok:
        print(f"API error: {response.raw}")
except BaristaError as e:
    print(f"Client error: {e}")
```

### Checking Response Status

```python
response = client.add_individual(model_id, "GO:0003924")

if response.ok:
    print("Success!")
    print(f"Signal: {response.signal}")
else:
    print(f"Failed: {response.raw.get('message', 'Unknown error')}")
```

## Advanced Usage

### Custom Request Building

```python
# Build custom request
custom_request = {
    "entity": "individual",
    "operation": "add-annotation",
    "arguments": {
        "individual": "some-id",
        "values": [
            {"key": "comment", "value": "Important note"}
        ],
        "model-id": model_id
    }
}

# Execute
response = client.m3_batch([custom_request])
```

### Resource Cleanup

```python
# Always close client when done
client.close()

# Or use context manager (if implemented)
with BaristaClient() as client:
    response = client.create_model()
    # Client closes automatically
```

## Best Practices

1. **Always check responses**: Verify `response.ok` before proceeding
2. **Use variables**: Assign variables when creating individuals for easy reference
3. **Batch operations**: Combine multiple operations for efficiency
4. **Handle errors gracefully**: Catch BaristaError exceptions
5. **Clean up resources**: Close clients when done

## Complete Example

```python
from noctua import BaristaClient, BaristaError, get_noctua_url

def build_pathway_model():
    """Build a simple signaling pathway model."""

    client = BaristaClient()

    try:
        # Create model
        response = client.create_model(title="RAS-RAF Signaling")
        if not response.ok:
            raise BaristaError(f"Failed to create model: {response.raw}")

        model_id = response.model_id
        print(f"Created model: {model_id}")

        # Add molecular activities
        activities = [
            ("GO:0003924", "ras"),  # GTPase
            ("GO:0004674", "raf"),  # kinase
            ("GO:0004707", "mek")   # MAP kinase
        ]

        for go_id, var in activities:
            response = client.add_individual(model_id, go_id, var)
            if not response.ok:
                print(f"Warning: Failed to add {var}")

        # Add causal chain
        edges = [
            ("ras", "raf"),
            ("raf", "mek")
        ]

        for subject, object in edges:
            response = client.add_fact(
                model_id,
                subject,
                object,
                "RO:0002413"
            )

        # Add evidence
        evidence_reqs = client.req_add_evidence_to_fact(
            model_id,
            "ras", "raf", "RO:0002413",
            "ECO:0000314",
            ["PMID:12345678"]
        )
        client.m3_batch(evidence_reqs)

        # Generate URL
        url = get_noctua_url(model_id, dev=True)
        print(f"View model: {url}")

        return model_id

    except BaristaError as e:
        print(f"Error: {e}")
        return None

    finally:
        client.close()

# Run the example
if __name__ == "__main__":
    model_id = build_pathway_model()
```

## Next Steps

- See [CLI Guide](cli.md) for command-line usage
- Explore [Screenshot Automation](screenshots.md) for visual docs
- Check [Working Examples](../examples/noctua_demo.ipynb) in notebooks