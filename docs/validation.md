# Validation and Hallucination Prevention

## Overview

The noctua library includes robust validation features designed to prevent common errors when working with GO-CAM models through APIs and CLIs. A key innovation is the use of **label-based checksums** to prevent ID hallucination and ensure operations target the correct entities.

> **Note:** For comprehensive API documentation on validation and rollback behavior, including `BaristaResponse` properties and error handling, see [Validation & Rollback API Reference](api/validation-rollback.md).

## The Problem: ID Hallucination and Misidentification

When working with biological ontologies and models programmatically, several issues can arise:

1. **Wrong ID Entry**: Accidentally typing the wrong CURIE (e.g., `GO:0003924` instead of `GO:0003925`)
2. **ID Hallucination**: AI systems or scripts generating plausible but non-existent IDs
3. **Mismatched Operations**: Applying changes to the wrong individual in a model
4. **Silent Failures**: Operations succeeding but on wrong entities, leading to corrupt models

These errors are particularly dangerous because:
- IDs like `GO:0003924` are not human-readable
- Operations may succeed even with wrong IDs
- Errors may go unnoticed until much later
- Fixing corrupted models is time-consuming

## The Solution: Label-Based Validation

noctua implements a validation system that uses human-readable labels as checksums to verify operations target the correct entities. This approach is inspired by [making IDs hallucination-resistant](https://ai4curation.github.io/aidocs/how-tos/make-ids-hallucination-resistant/).

### How It Works

1. **Specify Expected Types**: When creating or modifying entities, specify both the ID and expected label
2. **Automatic Verification**: The system checks that created entities match expectations
3. **Automatic Rollback**: If validation fails, all changes are automatically rolled back
4. **Clear Error Messages**: Failed validations provide clear explanations of mismatches

## Using Validation in Python

### Basic Individual Creation with Validation

```python
from noctua import BaristaClient

client = BaristaClient()

# Create an individual with validation
response = client.add_individual_validated(
    model_id="gomodel:12345",
    class_curie="GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)

if response.ok:
    print("✓ Individual created and validated")
else:
    print(f"✗ Creation failed: {response.raw}")
```

### Batch Operations with Validation

```python
# Build multiple requests
requests = [
    client.req_add_individual(model_id, "GO:0003924"),
    client.req_add_fact(model_id, "ind1", "ind2", "RO:0002413")
]

# Execute with validation
response = client.execute_with_validation(
    requests,
    expected_individuals=[
        {"id": "GO:0003924", "label": "GTPase activity"},
        {"id": "GO:0016301", "label": "kinase activity"}
    ]
)

if response.validation_failed:
    print(f"✗ Validation failed: {response.validation_reason}")
    # Changes have been automatically rolled back
```

### Updating Individual Annotations with Validation

```python
# Update an annotation with validation to ensure correct individual
response = client.update_individual_annotation(
    model_id="gomodel:12345",
    individual_id="gomodel:12345/ind123",
    key="contributor",
    value="https://orcid.org/0000-0002-6601-2165",
    validation={
        "id": "gomodel:12345/ind123",
        "label": "GTPase activity"  # Verify this is the right individual
    }
)

if response.validation_failed:
    print("Wrong individual! Expected 'GTPase activity'")
    # The annotation was NOT added due to validation failure
```

## Using Validation in CLI

### Individual Creation with Validation

```bash
# Add individual with ID-only validation
noctua barista add-individual \
  --model gomodel:12345 \
  --class GO:0003924 \
  --validate GO:0003924

# Add with label validation (recommended)
noctua barista add-individual \
  --model gomodel:12345 \
  --class GO:0003924 \
  --validate "GO:0003924=GTPase activity"
```

### Fact Creation with Validation

```bash
# Add fact with validation of all individuals
noctua barista add-fact \
  --model gomodel:12345 \
  --subject ind1 --object ind2 \
  --predicate RO:0002413 \
  --validate "GO:0003924=GTPase activity" \
  --validate "GO:0016301=kinase activity"
```

### Annotation Updates with Validation

```bash
# Update annotation with individual verification
noctua barista update-individual-annotation \
  --model gomodel:12345 \
  --individual gomodel:12345/ind123 \
  --key contributor \
  --value https://orcid.org/0000-0002-6601-2165 \
  --validate "gomodel:12345/ind123=GTPase activity"
```

## Validation Specification Format

The validation system accepts several formats:

### ID Only
```
GO:0003924
```
Validates that an entity with this exact ID exists.

### ID with Label
```
GO:0003924=GTPase activity
```
Validates both the ID and that its label matches.

### Label Only
```
GTPase activity
```
Validates that an entity with this label exists (less common).

## Automatic Rollback

When validation fails, the system automatically:

1. **Detects the mismatch** - Compares actual vs expected
2. **Generates reverse operations** - Creates undo operations for each change
3. **Applies rollback** - Executes the undo operations
4. **Returns failure status** - Indicates validation failed with reason

Example rollback scenario:

```python
# This operation will fail validation and rollback
response = client.add_individual_validated(
    model_id="gomodel:12345",
    class_curie="GO:0003925",  # Wrong ID!
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)

# response.validation_failed = True
# response.validation_reason = "Expected GO:0003924 but got GO:0003925"
# The individual was created but then immediately deleted
```

## Best Practices

### 1. Always Use Labels for Critical Operations

```python
# Good - includes label for verification
response = client.add_individual_validated(
    model_id, "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)

# Less safe - no label verification
response = client.add_individual(model_id, "GO:0003924")
```

### 2. Validate Before Bulk Operations

When performing multiple operations, validate critical entities first:

```python
# Validate the model exists and has expected state
model_resp = client.get_model(model_id)
if model_resp.model_state == "production":
    raise ValueError("Cannot modify production model")

# Now proceed with changes
# ...
```

### 3. Use Validation for Individual Updates

When updating annotations on individuals, always validate you're updating the right one:

```python
# Ensure we're updating the correct individual
response = client.update_individual_annotation(
    model_id, individual_id,
    key="enabled_by",
    value="UniProtKB:P12345",
    validation={"id": individual_id, "label": expected_label}
)
```

### 4. Handle Validation Failures Gracefully

```python
response = client.execute_with_validation(requests, expected_individuals)

if response.validation_failed:
    # Log the failure
    logger.error(f"Validation failed: {response.validation_reason}")

    # Notify user
    print("The operation was rolled back due to validation failure")

    # Don't proceed with dependent operations
    return
```

## How Rollback Works

The rollback system generates inverse operations for each change:

| Original Operation | Rollback Operation |
|-------------------|-------------------|
| Add individual | Remove individual |
| Add fact | Remove fact |
| Add annotation | Remove annotation |
| Remove annotation | Add annotation back |
| Remove individual | Re-add with same type |
| Remove fact | Re-add fact |

Example rollback sequence:

```python
# Original operations:
# 1. Add individual (GO:0003924)
# 2. Add fact (ind1 -> ind2)
# 3. Add annotation (contributor)

# Validation fails, rollback executes:
# 1. Remove annotation (contributor)
# 2. Remove fact (ind1 -> ind2)
# 3. Remove individual (GO:0003924)
# Operations are reversed in opposite order
```

## Advanced Validation Scenarios

### Multi-Step Operations with Checkpoints

```python
def create_complex_model(client, model_id):
    # Step 1: Create activity with validation
    activity_resp = client.add_individual_validated(
        model_id, "GO:0003924",
        expected_type={"id": "GO:0003924", "label": "GTPase activity"}
    )
    if activity_resp.validation_failed:
        return None

    activity_id = activity_resp.individuals[0]["id"]

    # Step 2: Create protein with validation
    protein_resp = client.add_individual_validated(
        model_id, "UniProtKB:P12345",
        expected_type={"id": "UniProtKB:P12345", "label": "RAS protein"}
    )
    if protein_resp.validation_failed:
        # Clean up activity since protein failed
        client.delete_individual(model_id, activity_id)
        return None

    # Step 3: Connect with validation
    # ... continue with validated operations
```

### Conditional Validation

```python
def update_if_correct_type(client, model_id, individual_id, expected_label):
    # Only update if individual has expected type
    response = client.update_individual_annotation(
        model_id, individual_id,
        key="reviewed",
        value="true",
        validation={"id": individual_id, "label": expected_label}
    )

    if response.validation_failed:
        print(f"Skipping {individual_id} - not a {expected_label}")
        return False

    return True
```

## Validation in Production

For production systems, consider:

1. **Always validate in production** - Never skip validation for production models
2. **Log validation failures** - Track patterns of errors
3. **Use strict mode** - Fail fast on any validation error
4. **Test validation** - Include validation tests in your test suite

Example production configuration:

```python
class ProductionClient(BaristaClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.strict_validation = True

    def add_individual(self, model_id, class_curie, **kwargs):
        # Always use validated version in production
        if not kwargs.get('expected_type'):
            raise ValueError("Production requires validation")
        return self.add_individual_validated(model_id, class_curie, **kwargs)
```

## Troubleshooting Validation Issues

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Validation always fails | Label mismatch | Check exact label in ontology |
| Rollback fails | Missing undo info | Ensure `enable_undo=True` |
| Wrong individual updated | No validation used | Add validation parameter |
| Silent corruption | Validation skipped | Always use validated methods |

### Debugging Validation

```python
# Enable verbose validation logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check what was validated
response = client.execute_with_validation(requests, expected_individuals)
print(f"Validation checked: {expected_individuals}")
print(f"Validation result: {response.validation_failed}")
print(f"Validation reason: {response.validation_reason}")

# Inspect actual vs expected
if response.validation_failed:
    print("Expected individuals:", expected_individuals)
    print("Actual individuals:", response.individuals)
```

## See Also

- [Making IDs Hallucination-Resistant](https://ai4curation.github.io/aidocs/how-tos/make-ids-hallucination-resistant/)
- [GO-CAM Documentation](http://geneontology.org/docs/gocam-overview/)
- [Noctua User Guide](http://wiki.geneontology.org/index.php/Noctua)