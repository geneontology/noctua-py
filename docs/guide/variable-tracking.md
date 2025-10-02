# Variable Tracking Guide

## Overview

Variable tracking is a powerful feature in `noctua-py` that simplifies working with GO-CAM models by allowing you to use meaningful names instead of complex server-generated IDs.

## The Problem It Solves

When you create individuals in a GO-CAM model, the server generates complex IDs like:
- `gomodel:6796b94c00003233/individual-1234567890`
- `gomodel:6796b94c00003233/individual-9876543210`

Without variable tracking, you would need to:
1. Parse response data to find the created ID
2. Store it in a variable for later use
3. Manage these mappings manually throughout your code

Variable tracking automates this entire process.

## How Variable Tracking Works

### Automatic ID Discovery

When you add an individual with a variable name, the client:

1. **Takes a snapshot** of the model's current state
2. **Adds the individual** via the API
3. **Compares the new state** to find the newly created individual
4. **Maps your variable name** to the discovered ID

```python
# Before the add_individual call
# Model has individuals: [ind-123, ind-456]

client.add_individual(model_id, "GO:0003924", assign_var="ras")

# After the call
# Model has individuals: [ind-123, ind-456, ind-789]
# Client detects ind-789 is new and maps: "ras" -> "ind-789"
```

### Automatic Resolution

Once mapped, variables are automatically resolved in all operations:

```python
# You write this:
client.add_fact(model_id, "ras", "raf", "RO:0002413")

# Client executes this:
client.add_fact(model_id, "ind-789", "ind-456", "RO:0002413")
```

## Variable Naming Rules

### Valid Variable Names

Variables are simple identifiers without special characters:
- ✅ `ras`, `raf`, `mek`, `erk`
- ✅ `kinase1`, `kinase2`, `phosphatase`
- ✅ `my_protein`, `upstream_regulator`
- ✅ `p53`, `mapk`, `nfkb`

### Not Variables (Automatically Recognized as IDs/CURIEs)

Anything containing `:` or `/` is treated as an ID or CURIE:
- `GO:0003924` - Gene Ontology term
- `RO:0002413` - Relation Ontology term
- `gomodel:123/individual-456` - Server-generated ID
- `ECO:0000314` - Evidence ontology term

## Complete Workflow Example

### Building a Signaling Cascade

```python
from noctua import BaristaClient

client = BaristaClient()

# Create a new model
response = client.create_model(title="RAS-RAF-MEK-ERK Cascade")
model_id = response.model_id

# Step 1: Add molecular functions with meaningful names
print("Adding molecular functions...")
client.add_individual(model_id, "GO:0003924", assign_var="ras")  # GTPase
client.add_individual(model_id, "GO:0004674", assign_var="raf")  # Ser/Thr kinase
client.add_individual(model_id, "GO:0004707", assign_var="mek")  # MAP kinase
client.add_individual(model_id, "GO:0004709", assign_var="erk")  # MAPKKK

# Step 2: Add cellular locations
print("Adding cellular components...")
client.add_individual(model_id, "GO:0005886", assign_var="membrane")  # plasma membrane
client.add_individual(model_id, "GO:0005737", assign_var="cytoplasm")

# Step 3: Build the cascade using variable names
print("Building cascade relationships...")
client.add_fact(model_id, "ras", "raf", "RO:0002413")  # ras activates raf
client.add_fact(model_id, "raf", "mek", "RO:0002413")  # raf activates mek
client.add_fact(model_id, "mek", "erk", "RO:0002413")  # mek activates erk

# Step 4: Add location information
print("Adding location information...")
client.add_fact(model_id, "ras", "membrane", "BFO:0000066")   # occurs_in
client.add_fact(model_id, "raf", "cytoplasm", "BFO:0000066")
client.add_fact(model_id, "mek", "cytoplasm", "BFO:0000066")
client.add_fact(model_id, "erk", "cytoplasm", "BFO:0000066")

# Step 5: Add evidence to key relationships
print("Adding evidence...")
client.add_fact_with_evidence(
    model_id,
    "ras",  # Just use the variable!
    "raf",
    "RO:0002413",
    "ECO:0000314",  # direct assay evidence
    sources=["PMID:12345678", "PMID:87654321"],
    with_from=["UniProtKB:P01112"]  # HRAS
)

# Check what variables are tracked
variables = client.get_variables(model_id)
print("\nTracked variables:")
for var_name, actual_id in variables.items():
    print(f"  {var_name:10} -> {actual_id}")
```

## Managing Variables

### Inspecting Variables

```python
# Get all variables for a model
variables = client.get_variables(model_id)
print(variables)
# {'ras': 'gomodel:123/ind-1', 'raf': 'gomodel:123/ind-2', ...}

# Get a specific variable's ID
ras_id = client.get_variable(model_id, "ras")
print(f"The actual ID for 'ras' is: {ras_id}")
```

### Manual Variable Management

While rarely needed, you can manually manage variables:

```python
# Manually set a variable (useful for existing individuals)
client.set_variable(model_id, "my_kinase", "existing-individual-id")

# Clear variables for a specific model
client.clear_variables(model_id)

# Clear all variables across all models
client.clear_variables()
```

### Variable Scope

Variables are scoped to models, preventing naming conflicts:

```python
# Model 1
client.add_individual(model1_id, "GO:0003924", assign_var="ras")

# Model 2 - same variable name, different ID
client.add_individual(model2_id, "GO:0003924", assign_var="ras")

# Each model maintains its own mapping
print(client.get_variable(model1_id, "ras"))  # gomodel:123/ind-1
print(client.get_variable(model2_id, "ras"))  # gomodel:456/ind-1
```

## Working with Existing Models

When working with existing models, you can assign variables to existing individuals:

```python
# Get an existing model
response = client.get_model(model_id)

# Find an individual and assign a variable
for ind in response.individuals:
    types = ind.get("type", [])
    if any(t.get("id") == "GO:0003924" for t in types):
        # Found the GTPase activity
        client.set_variable(model_id, "existing_ras", ind["id"])
        break

# Now you can use the variable
client.add_fact(model_id, "existing_ras", "some_other_id", "RO:0002413")
```

## Performance Considerations

### When to Disable Tracking

Variable tracking adds a small overhead (one extra API call per `add_individual`). You might disable it when:

```python
# Disable for bulk operations where you don't need variables
client = BaristaClient(track_variables=False)

# Bulk add without tracking
for go_term in large_list_of_terms:
    client.add_individual(model_id, go_term)  # No variable assignment
```

### Re-enabling Tracking

```python
# Create separate clients for different use cases
tracking_client = BaristaClient(track_variables=True)   # Default
bulk_client = BaristaClient(track_variables=False)      # For bulk ops

# Or toggle tracking on existing client
client.track_variables = False  # Disable
# ... bulk operations ...
client.track_variables = True   # Re-enable
```

## Best Practices

### 1. Use Descriptive Variable Names

```python
# Good - descriptive and meaningful
client.add_individual(model_id, "GO:0003924", assign_var="hras_gtpase")
client.add_individual(model_id, "GO:0004674", assign_var="braf_kinase")

# Avoid - too generic
client.add_individual(model_id, "GO:0003924", assign_var="x1")
client.add_individual(model_id, "GO:0004674", assign_var="x2")
```

### 2. Document Your Variables

```python
# Document the mapping for complex models
VARIABLES = {
    "ras": "HRAS GTPase activity",
    "raf": "BRAF kinase activity",
    "mek": "MAP2K1 kinase activity",
    "erk": "MAPK1 kinase activity"
}

for var_name, description in VARIABLES.items():
    print(f"Creating {description} as '{var_name}'")
    # ... add_individual calls ...
```

### 3. Use Variables Consistently

Once you start using variables in a model, use them consistently:

```python
# Consistent - all using variables
client.add_fact(model_id, "ras", "raf", "RO:0002413")
client.add_fact(model_id, "raf", "mek", "RO:0002413")

# Avoid mixing (though it works)
client.add_fact(model_id, "ras", actual_raf_id, "RO:0002413")  # Mixed
```

## Troubleshooting

### Variable Not Found

If a variable isn't resolving:

```python
# Check if the variable is tracked
variables = client.get_variables(model_id)
if "my_var" not in variables:
    print("Variable 'my_var' not tracked. Was it assigned?")
```

### Tracking Not Working

If tracking seems to fail:

```python
# Verify tracking is enabled
print(f"Tracking enabled: {client.track_variables}")

# Check the response for errors
response = client.add_individual(model_id, "GO:0003924", assign_var="test")
if not response.ok:
    print(f"Add failed: {response.raw}")
```

## Summary

Variable tracking makes GO-CAM model creation more intuitive by:

- **Eliminating ID management** - No need to parse responses and track IDs
- **Improving code readability** - Use meaningful names like "ras" instead of "gomodel:123/ind-456"
- **Reducing errors** - No risk of using wrong IDs or typos in long ID strings
- **Enabling cleaner scripts** - Focus on biology, not bookkeeping

The feature is enabled by default and works transparently with all model operations, making it the recommended way to build GO-CAM models programmatically.