# Validation and Rollback API Reference

## Overview

The noctua library provides automatic validation and rollback capabilities to ensure data integrity when making changes to GO-CAM models. This feature allows you to specify expected outcomes and automatically revert changes if those expectations aren't met.

## How It Works

1. **Execute with Undo Enabled**: Operations are performed with undo capability enabled
2. **Validate Results**: After execution, the results are checked against expected conditions
3. **Automatic Rollback**: If validation fails, changes are automatically reverted
4. **Response Flags**: The response includes special flags indicating validation status

## BaristaResponse Validation Properties

### ⚠️ CRITICAL DISTINCTION: `ok` vs `succeeded`

When validation is used, `BaristaResponse` has THREE different success indicators:

```python
class BaristaResponse:
    # Properties
    ok: bool                      # ⚠️ ONLY checks if API call worked (ignores validation!)
    succeeded: bool               # ✅ Checks BOTH API success AND validation pass
    validation_passed: bool       # Only checks validation status

    # Error information (all public!)
    error: str                    # ✅ Universal error message (API or validation)
    validation_failed: bool       # True if validation failed and rollback occurred
    validation_reason: str        # Reason for validation failure
```

### The Confusion Problem

**DO NOT USE `ok` for validated operations!** Here's why:

```python
# WRONG - This will execute even if validation failed!
response = client.add_individual_validated(model_id, "GO:wrong", expected_type={"label": "kinase"})
if response.ok:  # ⚠️ WRONG! ok=True even though validation failed!
    print(f"Individual created: {response.individual_id}")  # ERROR: individual was rolled back!

# CORRECT - Use succeeded for validated operations
response = client.add_individual_validated(model_id, "GO:wrong", expected_type={"label": "kinase"})
if response.succeeded:  # ✅ CORRECT! This checks both API and validation
    print(f"Individual created: {response.individual_id}")
else:
    if response.validation_failed:
        print(f"Validation failed: {response.validation_reason}")
    else:
        print(f"API call failed: {response.raw}")
```

### Quick Reference Table

| Property | What it checks | When to use |
|----------|---------------|-------------|
| `ok` | API call succeeded | Non-validated operations only |
| `succeeded` | API call + validation both passed | **Always use for validated operations** |
| `validation_passed` | Validation passed (or wasn't used) | Checking validation specifically |
| `validation_failed` | Validation was used and failed | Getting validation status |
| `error` | Universal error message | **Getting error details for any failure** |
| `validation_reason` | Specific validation failure reason | Getting validation error details |

## Understanding Validation Results

### Successful Validation

When validation passes:
- `response.ok` returns `True` (API succeeded)
- `response.succeeded` returns `True` (API + validation both passed) ✅
- `response.validation_failed` is `False`
- The changes remain in the model
- No rollback occurs

### Failed Validation

When validation fails:
- `response.ok` returns `True` (⚠️ API succeeded, but this doesn't mean success!)
- `response.succeeded` returns `False` (validation failed) ✅
- `response.validation_failed` is `True`
- `response.validation_reason` contains explanation
- Changes have been rolled back automatically
- The response contains the result of the undo operation

## Methods

### execute_with_validation

The primary method for operations with automatic validation:

```python
execute_with_validation(
    requests: List[Dict[str, Any]],
    expected_individuals: Optional[List[Dict[str, str]]] = None,
    expected_facts: Optional[List[Dict[str, str]]] = None,
    privileged: bool = True
) -> BaristaResponse
```

**Parameters:**
- `requests`: List of operations to execute
- `expected_individuals`: List of expected individual types after execution
- `expected_facts`: List of expected relationships (not yet implemented)
- `privileged`: Whether to use privileged endpoint

**Returns:**
- `BaristaResponse` with validation flags set

### add_individual_validated

Convenience method for adding an individual with validation:

```python
add_individual_validated(
    model_id: str,
    class_id: str,
    expected_type: Optional[Dict[str, str]] = None
) -> BaristaResponse
```

**Example:**
```python
response = client.add_individual_validated(
    model_id,
    "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)

if not response.succeeded:  # Use succeeded, not ok!
    print(f"Failed: {response.validation_reason}")
    # The individual was added but then removed because validation failed
```

## Validation Format

### Expected Individuals Format

The `expected_individuals` parameter is a list of dictionaries, where each dictionary can contain:
- `id`: The expected GO/RO term ID
- `label`: The expected term label
- Both `id` and `label` for strict validation

```python
# Check only ID
expected = [{"id": "GO:0003924"}]

# Check only label
expected = [{"label": "GTPase activity"}]

# Check both ID and label must match
expected = [{"id": "GO:0003924", "label": "GTPase activity"}]

# Check multiple individuals
expected = [
    {"id": "GO:0003924", "label": "GTPase activity"},
    {"id": "UniProtKB:P12345"}
]
```

## Complete Examples

### Example 1: Add Individual with Validation

```python
from noctua.barista import BaristaClient

client = BaristaClient()

# Add a kinase activity with validation
response = client.add_individual_validated(
    model_id="gomodel:123",
    class_id="GO:0004672",
    expected_type={
        "id": "GO:0004672",
        "label": "protein kinase activity"
    }
)

# Check the result - USE succeeded, NOT ok!
if response.succeeded:
    print("Successfully added protein kinase activity")
    print(f"Individual ID: {response.individual_id}")
else:
    if response.validation_failed:
        print(f"Validation failed: {response.validation_reason}")
        print("The individual was added but then automatically removed")
        print("Reason: The GO term ID doesn't match its expected label")
    else:
        print("API call itself failed")
```

### Example 2: Batch Operations with Validation

```python
# Create multiple requests
requests = [
    client.req_add_individual(model_id, "GO:0003924"),
    client.req_add_individual(model_id, "GO:0005525"),
]

# Execute with validation
response = client.execute_with_validation(
    requests,
    expected_individuals=[
        {"id": "GO:0003924", "label": "GTPase activity"},
        {"id": "GO:0005525", "label": "GTP binding"}
    ]
)

if response.succeeded:
    print("Both individuals added successfully")
else:
    print("Batch operation rolled back!")
    print(f"Reason: {response.validation_reason}")
    # Both individuals were added then removed
```

### Example 3: Update with Validation

```python
# Update an annotation with validation
response = client.update_individual_annotation(
    model_id,
    individual_id,
    "enabled_by",
    "UniProtKB:P12345",
    validation={
        "id": individual_id,
        "label": "protein kinase activity"
    }
)

if not response.succeeded:
    print("Update rolled back - individual doesn't have expected type")
    print(f"Expected: protein kinase activity")
    print(f"Reason: {response.validation_reason}")
```

## Common Validation Scenarios

### Wrong GO Term ID

```python
# Try to add "GTPase activity" but use wrong ID
response = client.add_individual_validated(
    model_id,
    "GO:0004674",  # This is actually "protein kinase activity"
    expected_type={"label": "GTPase activity"}
)
# Result: validation_failed = True
# Reason: Term GO:0004674 has label "protein kinase activity", not "GTPase activity"
```

### Typo in Expected Label

```python
response = client.add_individual_validated(
    model_id,
    "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activty"}  # Typo!
)
# Result: validation_failed = True
# Reason: Expected label "GTPase activty" not found
```

### Successful Validation

```python
response = client.add_individual_validated(
    model_id,
    "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)
# Result: validation_failed = False
# The individual remains in the model
```

## Error Handling

### When Undo Is Not Available

If validation fails but undo is not available (rare), a `BaristaError` is raised:

```python
try:
    # If someone manually calls validate without enable_undo
    response = client.m3_batch(requests, enable_undo=False)
    response.validate_and_rollback([{"id": "GO:0003924"}])
except BaristaError as e:
    print(f"Cannot rollback: {e}")
```

### Checking Before Using Validation Results

Always check `succeeded` (not just `ok`!) before using the response:

```python
response = client.add_individual_validated(model_id, class_id, expected_type)

if response.succeeded:  # ✅ Use succeeded, NOT ok!
    # Safe to use the results
    new_id = response.individual_id
    print(f"Created: {new_id}")
else:
    # Don't use response.individual_id - it might not exist!
    print("Operation failed or was rolled back")
    if response.validation_failed:
        print(f"Validation issue: {response.validation_reason}")
    print(f"Created individual: {new_id}")
```

## Best Practices

1. **Always Check Validation Status**: Check `validation_failed` before using response data
2. **Use Specific Expectations**: Be as specific as possible in your validation criteria
3. **Handle Both Outcomes**: Write code that handles both success and rollback scenarios
4. **Log Validation Failures**: Log `validation_reason` for debugging
5. **Test with Dev Server**: Test validation logic on dev server before production

## Implementation Notes

- Validation uses the model state after the operation completes
- Rollback is atomic - either all changes are reverted or none are
- The undo operation itself cannot be undone
- Validation currently supports individual type checking; fact validation is planned
- Performance impact is minimal as validation reuses the response data