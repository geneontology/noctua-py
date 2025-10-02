# Advanced Features Examples

This guide demonstrates the advanced features of noctua including variable tracking, undo operations, validation, and individual annotations.

## Variable Tracking

Variable tracking allows you to use simple names instead of complex IDs:

```python
from noctua.barista import BaristaClient

client = BaristaClient()

# Create model
resp = client.create_model("Signal Transduction Pathway")
model_id = resp.model_id

# Add individuals with variable names
client.add_individual(model_id, "GO:0004888", assign_var="receptor")  # receptor activity
client.add_individual(model_id, "GO:0003924", assign_var="ras")       # GTPase activity
client.add_individual(model_id, "GO:0004674", assign_var="raf")       # kinase activity
client.add_individual(model_id, "GO:0004707", assign_var="mapk")      # MAP kinase activity

# Build pathway using variable names
client.add_fact(model_id, "receptor", "ras", "RO:0002413")  # directly positively regulates
client.add_fact(model_id, "ras", "raf", "RO:0002413")
client.add_fact(model_id, "raf", "mapk", "RO:0002413")

# Variables work with annotations too
client.update_individual_annotation(model_id, "ras", "enabled_by", "UniProtKB:P01112")
client.update_individual_annotation(model_id, "raf", "enabled_by", "UniProtKB:P04049")
```

## Undo Operations

Operations can be undone if something goes wrong:

```python
# Add operation with undo capability
resp = client.add_individual(model_id, "GO:0003924", enable_undo=True)

# Check if we can undo
if resp.can_undo():
    print("Operation can be undone")

# Perform undo if needed
if some_error_condition:
    undo_resp = resp.undo()
    print("Operation undone successfully")

# Works with facts too
fact_resp = client.add_fact(
    model_id,
    "ras",
    "wrong_target",
    "RO:0002413",
    enable_undo=True
)

# Undo the incorrect fact
if fact_resp.can_undo():
    fact_resp.undo()
```

## Validation with Auto-Rollback

Ensure operations succeed with expected results or automatically rollback:

```python
# Add individual with validation
resp = client.add_individual_validated(
    model_id,
    "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)

if resp.validation_failed:
    print(f"Operation rolled back: {resp.validation_reason}")
else:
    print("Individual added successfully with correct type")

# Batch operations with validation
requests = [
    client.req_add_individual(model_id, "GO:0003924"),
    client.req_add_individual(model_id, "GO:0004674")
]

resp = client.execute_with_validation(
    requests,
    expected_individuals=[
        {"id": "GO:0003924", "label": "GTPase activity"},
        {"id": "GO:0004674", "label": "protein serine/threonine kinase activity"}
    ]
)

if resp.validation_failed:
    print("Batch rolled back due to validation failure")
```

## Individual Annotations

Manage annotations on individual model elements:

```python
# Update annotations
client.update_individual_annotation(
    model_id,
    individual_id="ras",  # Can use variable
    key="enabled_by",
    value="UniProtKB:P01112"
)

# Update with validation
client.update_individual_annotation(
    model_id,
    individual_id="raf",
    key="rdfs:label",
    value="RAF kinase activity",
    validation={"id": "raf", "label": "protein serine/threonine kinase activity"}
)

# Remove annotations
client.remove_individual_annotation(
    model_id,
    individual_id="ras",
    key="rdfs:label",
    value="old label"
)
```

## Complex Workflow Example

Here's a complete example combining all features:

```python
from noctua.barista import BaristaClient

def build_mapk_cascade():
    client = BaristaClient()

    # Create model
    resp = client.create_model("MAPK Cascade Model")
    model_id = resp.model_id
    print(f"Created model: {model_id}")

    # Add components with validation
    components = [
        ("receptor", "GO:0004888", "G protein-coupled receptor activity"),
        ("gprotein", "GO:0003925", "G protein activity"),
        ("ras", "GO:0003924", "GTPase activity"),
        ("raf", "GO:0004674", "protein serine/threonine kinase activity"),
        ("mek", "GO:0004708", "MAP kinase kinase activity"),
        ("erk", "GO:0004707", "MAP kinase activity")
    ]

    for var_name, go_id, expected_label in components:
        resp = client.add_individual_validated(
            model_id,
            go_id,
            expected_type={"id": go_id, "label": expected_label},
            assign_var=var_name
        )

        if resp.validation_failed:
            print(f"Failed to add {var_name}: {resp.validation_reason}")
            return None

        print(f"Added {var_name} ({go_id})")

    # Build cascade with undo capability
    connections = [
        ("receptor", "gprotein"),
        ("gprotein", "ras"),
        ("ras", "raf"),
        ("raf", "mek"),
        ("mek", "erk")
    ]

    added_facts = []
    for source, target in connections:
        resp = client.add_fact(
            model_id,
            source,
            target,
            "RO:0002413",  # directly positively regulates
            enable_undo=True
        )
        added_facts.append(resp)
        print(f"Connected {source} -> {target}")

    # Add protein annotations
    proteins = {
        "ras": "UniProtKB:P01112",  # HRAS
        "raf": "UniProtKB:P04049",  # RAF1
        "mek": "UniProtKB:Q02750",  # MEK1
        "erk": "UniProtKB:P27361"   # ERK2
    }

    for var_name, uniprot_id in proteins.items():
        client.update_individual_annotation(
            model_id,
            var_name,
            "enabled_by",
            uniprot_id
        )
        print(f"Added protein annotation: {var_name} enabled by {uniprot_id}")

    # Add evidence to key connections
    client.add_fact_with_evidence(
        model_id,
        "ras",
        "raf",
        "RO:0002413",
        eco_id="ECO:0000314",  # direct assay evidence
        sources=["PMID:8626452", "PMID:7961731"],
        with_from=["UniProtKB:P01112", "UniProtKB:P04049"]
    )

    return model_id, added_facts

# Run the workflow
model_id, facts = build_mapk_cascade()

# If something went wrong, we can undo the facts
if need_to_rollback:
    for fact in reversed(facts):  # Undo in reverse order
        if fact.can_undo():
            fact.undo()
    print("Rolled back all facts")
```

## CLI Examples with Validation

The CLI also supports validation:

```bash
# Add individual with validation
noctua barista add-individual \
    --model 6796b94c00003233 \
    --class GO:0003924 \
    --validate "GO:0003924=GTPase activity"

# Add fact with multiple validations
noctua barista add-fact \
    --model 6796b94c00003233 \
    --subject ind-123 \
    --object ind-456 \
    --predicate RO:0002413 \
    --validate "GO:0003924" \
    --validate "GO:0004674=protein kinase activity"

# Update individual annotation
noctua barista update-individual-annotation \
    --model 6796b94c00003233 \
    --individual ind-123 \
    --key "enabled_by" \
    --value "UniProtKB:P12345"

# Remove individual annotation
noctua barista remove-individual-annotation \
    --model 6796b94c00003233 \
    --individual ind-456 \
    --key "rdfs:label" \
    --value "old label"
```

## Best Practices

1. **Use variables for readability**: Assign meaningful variable names when adding individuals
2. **Enable undo for critical operations**: Use `enable_undo=True` for operations you might need to reverse
3. **Validate important additions**: Use validation to ensure model consistency
4. **Track your variables**: Use `client.get_variables(model_id)` to see current mappings
5. **Clear variables when done**: Use `client.clear_variables(model_id)` to clean up

## Error Recovery Pattern

```python
def safe_model_operation(client, model_id):
    """Pattern for safe operations with rollback."""

    # Store operations for potential rollback
    operations = []

    try:
        # Operation 1: Add with undo
        resp1 = client.add_individual(
            model_id,
            "GO:0003924",
            enable_undo=True
        )
        operations.append(resp1)

        # Operation 2: Add with validation
        resp2 = client.add_individual_validated(
            model_id,
            "GO:0004674",
            expected_type={"id": "GO:0004674"}
        )

        if resp2.validation_failed:
            raise Exception(f"Validation failed: {resp2.validation_reason}")

        operations.append(resp2)

        # Operation 3: Add fact
        resp3 = client.add_fact(
            model_id,
            resp1.individuals[0]["id"],
            resp2.individuals[0]["id"],
            "RO:0002413",
            enable_undo=True
        )
        operations.append(resp3)

        return operations

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Rolling back operations...")

        # Rollback in reverse order
        for op in reversed(operations):
            if op.can_undo():
                op.undo()
                print(f"Rolled back operation")

        raise
```

## Markdown Export

Export models in a human-readable markdown format:

```python
from noctua.barista import BaristaClient

client = BaristaClient()

# Export model as markdown
resp = client.export_model("gomodel:6796b94c00003233", format="markdown")

if resp.ok:
    markdown_content = resp.raw.get("data", "")

    # Save to file
    with open("model.md", "w") as f:
        f.write(markdown_content)

    print("Model exported as markdown")
```

### Example Markdown Output

```markdown
# Signal Transduction Pathway

## Model Information

- **Model ID**: `gomodel:6796b94c00003233`
- **State**: development
- **Comments**: Example pathway model

## Activities and Entities

### GTPase activity
- **ID**: `ind-123`
- **Type**: [GTPase activity](GO:0003924)
- **Enabled by**: UniProtKB:P12345
- **Label**: RAS protein

### protein serine/threonine kinase activity
- **ID**: `ind-456`
- **Type**: [protein serine/threonine kinase activity](GO:0004674)
- **Enabled by**: UniProtKB:P67890

## Relationships

### directly positively regulates

- **GTPase activity** → **protein serine/threonine kinase activity**
  - Evidence: ECO:0000314
```

### CLI Usage

```bash
# Export model as markdown
noctua barista export-model \
    --model 6796b94c00003233 \
    --format markdown \
    --output pathway.md

# View markdown in terminal
noctua barista export-model \
    --model 6796b94c00003233 \
    --format markdown
```

## Next Steps

- See [API Reference](../api/barista.md) for complete method documentation
- Review [Python API Guide](../guide/python-api.md) for basic usage
- Check [Variable Tracking Guide](../guide/variable-tracking.md) for detailed variable usage