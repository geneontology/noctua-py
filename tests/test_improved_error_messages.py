"""Test that error messages show what label SHOULD be used vs what was found."""

from noctua.barista import BaristaResponse


def test_label_mismatch_shows_expected_vs_actual():
    """Test that label mismatches show actual vs expected labels clearly."""
    # Example from user's request: UniProtKB:P0DP23 with "Calmodulin-1" but expected different label
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "gomodel:123/ind1",
                        "type": [
                            {
                                "id": "UniProtKB:P0DP23",
                                "label": "Calmodulin-1"  # What we actually have
                            }
                        ]
                    }
                ]
            }
        }
    )

    # Try to validate with wrong expected label
    expected = [{"id": "UniProtKB:P0DP23", "label": "Some Other Protein"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1

    error_message = result["error_message"]

    # Should show what we expected vs what we found
    assert "Expected label 'Some Other Protein'" in error_message
    assert "but found 'Calmodulin-1'" in error_message
    assert "for ID UniProtKB:P0DP23" in error_message

    print(f"Improved error message: {error_message}")


def test_individual_annotation_mismatch_shows_expected_vs_actual():
    """Test individual annotation validation shows actual vs expected labels."""
    # Individual has one type but we expect different label
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "gomodel:123/ind456",
                        "type": [
                            {
                                "id": "GO:0003924",
                                "label": "GTPase activity"  # Actual label
                            }
                        ]
                    }
                ]
            }
        }
    )

    # Validate individual with wrong expected label
    expected = [{"id": "gomodel:123/ind456", "label": "kinase activity"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1

    error_message = result["error_message"]

    # Should show the individual and its actual vs expected type labels
    assert "Individual gomodel:123/ind456" in error_message
    assert "has type labels [GTPase activity]" in error_message
    assert "but expected 'kinase activity'" in error_message

    print(f"Individual validation error: {error_message}")


def test_id_not_found_shows_available_options():
    """Test that missing IDs show what's available."""
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "gomodel:123/ind1",
                        "type": [
                            {
                                "id": "GO:0003924",
                                "label": "GTPase activity"
                            }
                        ]
                    },
                    {
                        "id": "gomodel:123/ind2",
                        "type": [
                            {
                                "id": "UniProtKB:P0DP23",
                                "label": "Calmodulin-1"
                            }
                        ]
                    }
                ]
            }
        }
    )

    # Try to find non-existent ID
    expected = [{"id": "GO:9999999", "label": "Nonexistent protein"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    error_message = result["error_message"]

    # Should show what IDs are available
    assert "Expected ID 'GO:9999999' not found" in error_message
    assert "Available:" in error_message
    assert "GO:0003924 (GTPase activity)" in error_message
    assert "UniProtKB:P0DP23 (Calmodulin-1)" in error_message

    print(f"ID not found error: {error_message}")


def test_before_and_after_comparison():
    """Compare old vs new error message style."""
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "gomodel:123/ind1",
                        "type": [
                            {
                                "id": "UniProtKB:P0DP23",
                                "label": "Calmodulin-1"
                            }
                        ]
                    }
                ]
            }
        }
    )

    expected = [{"id": "UniProtKB:P0DP23", "label": "Expected Label"}]
    result = response.validate_individuals_detailed(expected)

    # OLD message would have been: "Expected individuals not found: [{'id': 'UniProtKB:P0DP23', 'label': 'Expected Label'}]"
    # NEW message should be much more informative
    error_message = result["error_message"]

    print(f"\nOLD style: Expected individuals not found: {expected}")
    print(f"NEW style: {error_message}")

    # New message is much more informative
    assert "Expected label 'Expected Label' but found 'Calmodulin-1' for ID UniProtKB:P0DP23" == error_message