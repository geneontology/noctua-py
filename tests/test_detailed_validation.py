"""Test detailed validation error messages."""

from noctua.barista import BaristaResponse


def test_detailed_validation_label_mismatch():
    """Test detailed validation shows actual vs expected labels."""
    # Response with individual that has wrong label
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
                                "label": "Calmodulin-1"  # Actual label
                            }
                        ]
                    }
                ]
            }
        }
    )

    # Test detailed validation
    expected = [{"id": "UniProtKB:P0DP23", "label": "Expected Label"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1
    assert "Expected label 'Expected Label' but found 'Calmodulin-1' for ID UniProtKB:P0DP23" in result["error_message"]


def test_detailed_validation_id_not_found():
    """Test detailed validation when ID is not found."""
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

    # Test with non-existent ID
    expected = [{"id": "GO:9999999", "label": "Nonexistent activity"}]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 1
    assert "Expected ID 'GO:9999999' not found" in result["error_message"]
    assert "Available: GO:0003924 (GTPase activity)" in result["error_message"]


def test_detailed_validation_multiple_mismatches():
    """Test detailed validation with multiple mismatches."""
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

    # Test with multiple wrong expectations
    expected = [
        {"id": "GO:0003924", "label": "Wrong Label"},
        {"id": "UniProtKB:P0DP23", "label": "Another Wrong Label"}
    ]
    result = response.validate_individuals_detailed(expected)

    assert not result["valid"]
    assert len(result["mismatches"]) == 2
    assert "Expected label 'Wrong Label' but found 'GTPase activity'" in result["error_message"]
    assert "Expected label 'Another Wrong Label' but found 'Calmodulin-1'" in result["error_message"]


def test_detailed_validation_success():
    """Test detailed validation when everything matches."""
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

    expected = [{"id": "GO:0003924", "label": "GTPase activity"}]
    result = response.validate_individuals_detailed(expected)

    assert result["valid"]
    assert len(result["mismatches"]) == 0
    assert result["error_message"] is None


def test_validation_backwards_compatibility():
    """Test that the old validate_individuals method still works."""
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

    # Should still work the same way
    assert response.validate_individuals([{"id": "GO:0003924", "label": "GTPase activity"}])
    assert not response.validate_individuals([{"id": "GO:0003924", "label": "Wrong Label"}])