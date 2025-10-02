"""Test the new succeeded and validation_passed properties."""

from noctua.barista import BaristaResponse


def test_succeeded_property():
    """Test that succeeded property correctly combines ok and validation status."""

    # Case 1: API succeeded, no validation
    response = BaristaResponse(raw={"message-type": "success"})
    assert response.ok is True
    assert response.validation_failed is False
    assert response.succeeded is True
    assert response.validation_passed is True

    # Case 2: API succeeded, validation failed
    response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=True,
        validation_reason="Expected type not found"
    )
    assert response.ok is True  # API call worked
    assert response.validation_failed is True  # But validation failed
    assert response.succeeded is False  # So overall it didn't succeed
    assert response.validation_passed is False

    # Case 3: API failed
    response = BaristaResponse(raw={"message-type": "error"})
    assert response.ok is False
    assert response.validation_failed is False  # Validation never ran
    assert response.succeeded is False  # Failed because API failed
    assert response.validation_passed is True  # Validation wasn't used, so "passed"

    # Case 4: API succeeded, validation passed
    response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=False
    )
    assert response.ok is True
    assert response.validation_failed is False
    assert response.succeeded is True
    assert response.validation_passed is True


def test_confusing_ok_behavior():
    """Demonstrate the confusing behavior that ok doesn't check validation."""

    # This is the confusing case that trips people up
    response = BaristaResponse(
        raw={"message-type": "success", "data": {"id": "123"}},
        validation_failed=True,
        validation_reason="GO term label doesn't match expected"
    )

    # The API call itself succeeded
    assert response.ok is True  # This is confusing!

    # But validation failed and changes were rolled back
    assert response.validation_failed is True

    # So the overall operation did NOT succeed
    assert response.succeeded is False  # This is what you should check!

    # This would be WRONG code that many people would write:
    if response.ok:  # WRONG!
        # This code would execute even though validation failed!
        # Trying to use response.model_id here would likely fail
        # because the changes were rolled back
        pass

    # This is the CORRECT way:
    if response.succeeded:  # CORRECT!
        # This code will NOT execute because validation failed
        pass
    else:
        # This is where we end up
        assert response.validation_reason == "GO term label doesn't match expected"