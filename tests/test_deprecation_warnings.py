"""Test deprecation warnings for old underscore properties."""

import warnings
from noctua.barista import BaristaResponse


def test_deprecated_validation_failed_property():
    """Test that _validation_failed shows deprecation warning."""
    response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=True
    )

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")  # Ensure all warnings are triggered

        # Access the deprecated property
        value = response._validation_failed

        # Check that a deprecation warning was issued
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "_validation_failed is deprecated" in str(w[0].message)
        assert "use validation_failed instead" in str(w[0].message)

        # Check that the value is still correct
        assert value is True


def test_deprecated_validation_reason_property():
    """Test that _validation_reason shows deprecation warning."""
    response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=True,
        validation_reason="Expected type not found"
    )

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Access the deprecated property
        value = response._validation_reason

        # Check that a deprecation warning was issued
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "_validation_reason is deprecated" in str(w[0].message)
        assert "use validation_reason instead" in str(w[0].message)

        # Check that the value is still correct
        assert value == "Expected type not found"


def test_new_properties_no_warnings():
    """Test that new public properties don't show warnings."""
    response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=True,
        validation_reason="Expected type not found"
    )

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Access the new public properties
        failed = response.validation_failed
        reason = response.validation_reason
        error = response.error
        succeeded = response.succeeded

        # Check that NO warnings were issued
        assert len(w) == 0

        # Check values are correct
        assert failed is True
        assert reason == "Expected type not found"
        assert error == "Expected type not found"
        assert succeeded is False