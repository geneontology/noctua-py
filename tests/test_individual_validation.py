"""Test individual-based validation for annotation updates."""

from noctua.barista import BaristaResponse


def test_individual_based_validation_success():
    """Test validation when individual has expected type label."""
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
                    }
                ]
            }
        }
    )

    # Validate specific individual has expected type label
    expected = [{"id": "gomodel:123/ind1", "label": "GTPase activity"}]
    result = response.validate_individuals_detailed(expected)

    assert result["valid"]
    assert len(result["mismatches"]) == 0
    assert result["error_message"] is None


def test_individual_based_validation_wrong_label():
    """Test validation when individual has wrong type label."""
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
                                "label": "GTPase activity"  # Actual label
                            }
                        ]
                    }
                ]
            }
        }
    )

    # Validate with wrong expected label
    expected = [{"id": "gomodel:123/ind1", "label": "Wrong Label"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1
    assert "has type labels [GTPase activity] but expected 'Wrong Label'" in result["error_message"]


def test_individual_based_validation_individual_not_found():
    """Test validation when individual ID doesn't exist."""
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
                    }
                ]
            }
        }
    )

    # Validate non-existent individual
    expected = [{"id": "gomodel:123/ind999", "label": "Some Label"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1
    assert "Individual ID 'gomodel:123/ind999' not found" in result["error_message"]
    assert "Available: gomodel:123/ind1" in result["error_message"]


def test_type_based_validation_still_works():
    """Test that type-based validation (original behavior) still works."""
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
                    }
                ]
            }
        }
    )

    # Type-based validation (no "/" in ID)
    expected = [{"id": "GO:0003924", "label": "GTPase activity"}]
    result = response.validate_individuals_detailed(expected)

    assert result["valid"]
    assert len(result["mismatches"]) == 0
    assert result["error_message"] is None


def test_type_based_validation_wrong_label():
    """Test type-based validation with wrong label."""
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
                    }
                ]
            }
        }
    )

    # Type-based validation with wrong label
    expected = [{"id": "GO:0003924", "label": "Wrong Label"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1
    assert "Expected label 'Wrong Label' but found 'GTPase activity' for ID GO:0003924" in result["error_message"]