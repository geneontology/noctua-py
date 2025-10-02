"""Test the new universal error property."""

from noctua.barista import BaristaResponse


def test_error_property_api_failure():
    """Test error property for API failures."""
    # API failure with message in data
    response = BaristaResponse(
        raw={
            "message-type": "error",
            "data": {"message": "Invalid model ID"}
        }
    )

    assert response.ok is False
    assert response.validation_failed is False
    assert response.error == "Invalid model ID"


def test_error_property_api_failure_no_message():
    """Test error property for API failures without specific message."""
    response = BaristaResponse(
        raw={"message-type": "error"}
    )

    assert response.ok is False
    assert response.validation_failed is False
    assert response.error == "API call failed"


def test_error_property_validation_failure():
    """Test error property for validation failures."""
    response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=True,
        validation_reason="Expected GO:0003924 but got GO:0004674"
    )

    assert response.ok is True  # API succeeded
    assert response.validation_failed is True
    assert response.error == "Expected GO:0003924 but got GO:0004674"


def test_error_property_success():
    """Test error property for successful operations."""
    response = BaristaResponse(
        raw={"message-type": "success"}
    )

    assert response.ok is True
    assert response.validation_failed is False
    assert response.error is None


def test_error_property_comprehensive_example():
    """Test error property covers all failure scenarios."""
    # Example showing how error property simplifies error handling

    responses = [
        # Success
        BaristaResponse(raw={"message-type": "success"}),

        # API failure
        BaristaResponse(raw={"message-type": "error", "data": {"message": "Network error"}}),

        # Validation failure
        BaristaResponse(
            raw={"message-type": "success"},
            validation_failed=True,
            validation_reason="Label mismatch"
        )
    ]

    # Now you can handle ALL errors the same way
    for i, response in enumerate(responses):
        if response.error:
            # Universal error handling
            error_msg = response.error
            if i == 1:
                assert error_msg == "Network error"
            elif i == 2:
                assert error_msg == "Label mismatch"
        else:
            # Success
            assert i == 0