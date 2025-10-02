# BaristaClient API Reference

## Class: BaristaClient

Main client for interacting with the Barista/Minerva API.

### Constructor

```python
BaristaClient(
    token: Optional[str] = None,
    base_url: str = DEFAULT_BARISTA_BASE,
    namespace: str = DEFAULT_NAMESPACE,
    provided_by: str = DEFAULT_PROVIDED_BY,
    timeout: float = 30.0,
    track_variables: bool = True
)
```

**Parameters:**
- `token`: Barista API token (reads from BARISTA_TOKEN env if not provided)
- `base_url`: Base URL for Barista server
- `namespace`: Minerva namespace
- `provided_by`: Provider URL
- `timeout`: HTTP request timeout in seconds
- `track_variables`: Enable automatic variable tracking for model building

## Model Methods

### create_model

```python
create_model(title: Optional[str] = None) -> BaristaResponse
```

Create a new empty GO-CAM model.

### get_model

```python
get_model(model_id: str) -> BaristaResponse
```

Retrieve complete model details.

### list_models

```python
list_models(
    limit: Optional[int] = None,
    offset: int = 0,
    title: Optional[str] = None,
    state: Optional[str] = None,
    contributor: Optional[str] = None,
    group: Optional[str] = None
) -> Dict[str, Any]
```

List models with optional filtering.

### clear_model

```python
clear_model(model_id: str, force: bool = False) -> BaristaResponse
```

Clear all nodes and edges from a model.

### export_model

```python
export_model(model_id: str, format: str = "owl") -> BaristaResponse
```

Export a model in the specified format.

**Parameters:**
- `model_id`: The model to export
- `format`: Export format (default: "owl")
  - `owl` - OWL RDF/XML format
  - `ttl` - Turtle format
  - `json-ld` - JSON-LD format
  - `gaf` - GAF format
  - `markdown` - Human-readable markdown format

**Note:** The markdown format provides a human-friendly representation of the model, showing:
- Model metadata (title, state, comments)
- Activities and entities with their annotations
- Relationships grouped by type
- Evidence for relationships

**Example:**
```python
# Export as markdown
resp = client.export_model("gomodel:123", format="markdown")
markdown_content = resp.raw.get("data", "")
print(markdown_content)
```

## Individual Methods

### add_individual

```python
add_individual(
    model_id: str,
    class_curie: str,
    assign_var: str = "x1",
    enable_undo: bool = False
) -> BaristaResponse
```

Add an individual of a specified class to the model.

**Parameters:**
- `model_id`: Target model ID
- `class_curie`: Class CURIE to instantiate (e.g., "GO:0003924")
- `assign_var`: Variable name for tracking (if enabled)
- `enable_undo`: Enable undo capability on the response

**Returns:** BaristaResponse with optional undo support

### add_individual_validated

```python
add_individual_validated(
    model_id: str,
    class_curie: str,
    expected_type: Optional[Dict[str, str]] = None,
    assign_var: str = "x1"
) -> BaristaResponse
```

Add an individual with automatic validation and rollback on failure.

**Parameters:**
- `expected_type`: Dict with 'id' and/or 'label' to validate

### remove_individual / delete_individual

```python
remove_individual(
    model_id: str,
    individual_id: str,
    enable_undo: bool = False
) -> BaristaResponse
```

Remove an individual from the model. Variables are automatically resolved to IDs.

### update_individual_annotation

```python
update_individual_annotation(
    model_id: str,
    individual_id: str,
    key: str,
    value: str,
    old_value: Optional[str] = None,
    validation: Optional[Dict[str, str]] = None
) -> BaristaResponse
```

Update an annotation on an individual with optional validation.

**Parameters:**
- `key`: Annotation key (e.g., 'rdfs:label', 'enabled_by')
- `value`: New value for the annotation
- `old_value`: Current value for replacement (optional)
- `validation`: Optional validation dict to verify the individual

### remove_individual_annotation

```python
remove_individual_annotation(
    model_id: str,
    individual_id: str,
    key: str,
    value: str,
    validation: Optional[Dict[str, str]] = None
) -> BaristaResponse
```

Remove a specific annotation from an individual.

## Fact/Edge Methods

### add_fact

```python
add_fact(
    model_id: str,
    subject_id: str,
    object_id: str,
    predicate_id: str,
    enable_undo: bool = False
) -> BaristaResponse
```

Add a fact (edge) between two individuals.

**Parameters:**
- `subject_id`: Subject individual (variable, CURIE, or ID)
- `object_id`: Object individual (variable, CURIE, or ID)
- `predicate_id`: Predicate/relation (e.g., "RO:0002413")
- `enable_undo`: Enable undo capability

### add_fact_with_evidence

```python
add_fact_with_evidence(
    model_id: str,
    subject_id: str,
    object_id: str,
    predicate_id: str,
    eco_id: str,
    sources: List[str],
    with_from: Optional[List[str]] = None,
    enable_undo: bool = False
) -> BaristaResponse
```

Add a fact with evidence annotations.

### remove_fact / delete_edge

```python
remove_fact(
    model_id: str,
    subject_id: str,
    object_id: str,
    predicate_id: str,
    enable_undo: bool = False
) -> BaristaResponse
```

Remove a fact/edge from the model.

## Model Annotation Methods

### update_model_metadata

```python
update_model_metadata(
    model_id: str,
    title: Optional[str] = None,
    state: Optional[str] = None,
    comment: Optional[str] = None,
    replace: bool = False
) -> BaristaResponse
```

Update model-level metadata (title, state, comments).

### add_model_annotation

```python
add_model_annotation(
    model_id: str,
    key: str,
    value: str
) -> BaristaResponse
```

Add a single annotation to the model.

### remove_model_annotation

```python
remove_model_annotation(
    model_id: str,
    key: str,
    value: str
) -> BaristaResponse
```

Remove a specific annotation from the model.

## Variable Tracking Methods

### set_variable

```python
set_variable(model_id: str, var_name: str, actual_id: str) -> None
```

Manually set a variable mapping.

### get_variable

```python
get_variable(model_id: str, var_name: str) -> Optional[str]
```

Get the actual ID for a variable name.

### get_variables

```python
get_variables(model_id: str) -> Dict[str, str]
```

Get all variable mappings for a model.

### clear_variables

```python
clear_variables(model_id: Optional[str] = None) -> None
```

Clear variable mappings for a model or all models.

## Validation Methods

### execute_with_validation

```python
execute_with_validation(
    requests: List[Dict[str, Any]],
    expected_individuals: Optional[List[Dict[str, str]]] = None,
    expected_facts: Optional[List[Dict[str, str]]] = None,
    privileged: bool = True
) -> BaristaResponse
```

Execute requests with automatic validation and rollback on failure.

**Parameters:**
- `requests`: List of request dictionaries to execute
- `expected_individuals`: Expected individual types after execution
- `expected_facts`: Expected facts (future feature)
- `privileged`: Use privileged endpoint

**Returns:** BaristaResponse with `_validation_failed` flag if rolled back

## Low-Level Methods

### m3_batch

```python
m3_batch(
    requests: List[Dict[str, Any]],
    privileged: bool = True,
    enable_undo: bool = False
) -> BaristaResponse
```

Execute a batch of requests against the Minerva API.

### Request Builders

Static methods for building request dictionaries:

- `req_add_individual(model_id, class_id, assign_var)`
- `req_remove_individual(model_id, individual_id)`
- `req_add_fact(model_id, subject_id, object_id, predicate_id)`
- `req_remove_fact(model_id, subject_id, object_id, predicate_id)`
- `req_add_evidence_to_fact(...)`
- `req_update_model_annotation(model_id, key, value, old_value)`
- `req_remove_model_annotation(model_id, key, value)`
- `req_update_individual_annotation(model_id, individual_id, key, value, old_value)`
- `req_remove_individual_annotation(model_id, individual_id, key, value)`
- `req_create_model(title)`
- `req_get_model(model_id)`
- `req_export_model(model_id, format)`

## Response Class: BaristaResponse

### Properties

#### ⚠️ CRITICAL: Success Checking Properties

| Property | What it checks | When to use |
|----------|---------------|-------------|
| `ok` | ONLY the API call | ⚠️ DO NOT use for validated operations |
| `succeeded` | API call + validation | ✅ ALWAYS use for validated operations |
| `validation_passed` | Just validation | Rarely needed |

```python
# ⚠️ WRONG - will execute even if validation failed!
response = client.add_individual_validated(...)
if response.ok:  # WRONG!
    print(response.individual_id)  # May crash - individual was rolled back!

# ✅ CORRECT - checks both API and validation
response = client.add_individual_validated(...)
if response.succeeded:  # CORRECT!
    print(response.individual_id)  # Safe - validation passed
```

#### Model Data Properties
- `model_id`: The model ID from the response
- `individuals`: List of individuals in the model
- `facts`: List of facts/edges in the model
- `model_state`: Model state (e.g., 'production', 'development')
- `raw`: Raw response dictionary from the API

#### Error and Validation Properties
- `error`: Universal error message for any failure (API or validation) ✨ **NEW**
- `validation_failed`: `True` if validation failed and changes were rolled back
- `validation_reason`: Explanation of why validation failed

> **See Also:** [Validation & Rollback API Reference](validation-rollback.md) for comprehensive documentation

### Methods

#### can_undo

```python
can_undo() -> bool
```

Check if this response supports undo operations.

#### undo

```python
undo() -> BaristaResponse
```

Undo the operations that created this response.

**Raises:** BaristaError if undo is not possible

#### validate_individuals

```python
validate_individuals(expected: List[Dict[str, str]]) -> bool
```

Validate that individuals in the response match expected types.

#### validate_and_rollback

```python
validate_and_rollback(
    expected: List[Dict[str, str]],
    validation_type: str = "individuals"
) -> BaristaResponse
```

Validate the response and automatically rollback if validation fails.

## Examples

### Building a Model with Variables

```python
client = BaristaClient()

# Create model
response = client.create_model(title="My Pathway")
model_id = response.model_id

# Add individuals with variables
client.add_individual(model_id, "GO:0003924", assign_var="ras")
client.add_individual(model_id, "GO:0004674", assign_var="raf")

# Use variables in facts
client.add_fact(model_id, "ras", "raf", "RO:0002413")
```

### Operations with Undo

```python
# Add with undo support
response = client.add_individual(model_id, "GO:0003924", enable_undo=True)

# Check and undo if needed
if some_condition:
    undo_response = response.undo()
```

### Validation with Auto-Rollback

```python
# Add individual with validation
response = client.add_individual_validated(
    model_id,
    "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)

if response._validation_failed:
    print(f"Rolled back: {response._validation_reason}")
```

### Updating Individual Annotations

```python
# Update annotation with validation
response = client.update_individual_annotation(
    model_id,
    individual_id,
    "enabled_by",
    "UniProtKB:P12345",
    validation={"id": individual_id, "label": "kinase activity"}
)
```

## Evidence Finding Methods

These methods integrate with the Amigo/GOlr interface to find GO annotation evidence that supports GO-CAM model edges.

### find_evidence_for_edge

```python
find_evidence_for_edge(
    model_id: str,
    subject_id: str,
    object_id: str,
    predicate: str,
    amigo_base_url: Optional[str] = None,
    evidence_types: Optional[List[str]] = None,
    limit: int = 50
) -> Dict[str, Any]
```

Find GO annotation evidence that could support a specific edge in a GO-CAM model.

**Parameters:**
- `model_id`: The model ID
- `subject_id`: Subject individual ID (can be variable name)
- `object_id`: Object individual ID (can be variable name)
- `predicate`: The predicate/relation (e.g., "RO:0002333" for enabled_by)
- `amigo_base_url`: Optional custom GOlr endpoint
- `evidence_types`: Optional list of evidence codes to filter (e.g., ["IDA", "IPI"])
- `limit`: Maximum number of annotations to return

**Returns:** Dictionary with:
- `edge`: Edge information with subject, object, predicate
- `mapping_type`: Type of mapping ("enabled_by", "activity_to_process", "activity_to_location", "unknown")
- `annotations`: List of matching GO annotations
- `summary`: Human-readable summary

**GO-CAM to GAF Mapping Logic:**
- **enabled_by edges**: Searches for MF annotations on the bioentity
- **activity→process edges**: Searches for BP annotations on the activity's enabled_by bioentity
- **activity→location edges**: Searches for CC annotations on the activity's enabled_by bioentity

**Example:**
```python
# Find evidence for an enabled_by edge
evidence = client.find_evidence_for_edge(
    model_id="gomodel:123",
    subject_id="ind1",  # Molecular function
    object_id="ind2",    # Bioentity
    predicate="RO:0002333",  # enabled_by
    evidence_types=["IDA", "IPI", "IMP"]
)

print(f"Found {len(evidence['annotations'])} supporting annotations")
for ann in evidence['annotations']:
    print(f"  {ann['annotation_class_label']} - {ann['evidence_type']} - {ann['reference']}")
```

### find_evidence_for_model

```python
find_evidence_for_model(
    model_id: str,
    amigo_base_url: Optional[str] = None,
    evidence_types: Optional[List[str]] = None,
    limit_per_edge: int = 10
) -> Dict[str, Any]
```

Find GO annotation evidence for all edges in a GO-CAM model.

**Parameters:**
- `model_id`: The model ID
- `amigo_base_url`: Optional custom GOlr endpoint
- `evidence_types`: Optional list of evidence codes to filter
- `limit_per_edge`: Maximum annotations per edge

**Returns:** Dictionary with:
- `model_id`: The model ID
- `model_title`: The model title
- `edges_with_evidence`: List of edge evidence dictionaries
- `total_annotations`: Total count of annotations found
- `summary`: Human-readable summary

**Example:**
```python
# Find evidence for all edges in a model
model_evidence = client.find_evidence_for_model(
    model_id="gomodel:123",
    evidence_types=["IDA", "IPI", "IMP", "IGI"],
    limit_per_edge=5
)

print(f"Total annotations found: {model_evidence['total_annotations']}")
print(f"Summary: {model_evidence['summary']}")

for edge_ev in model_evidence['edges_with_evidence']:
    if edge_ev['annotations']:
        print(f"\nEdge type: {edge_ev['mapping_type']}")
        print(f"  Annotations: {len(edge_ev['annotations'])}")
```

## Error Handling

All methods may raise `BaristaError` for API failures or invalid operations.

```python
from noctua import BaristaError

try:
    response = client.add_individual(model_id, "GO:0003924")
except BaristaError as e:
    print(f"Operation failed: {e}")
```