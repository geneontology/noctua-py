"""Tests for validation and auto-rollback functionality."""

from unittest.mock import patch, MagicMock
from noctua.barista import BaristaClient, BaristaResponse, BaristaError
import pytest


def test_validate_individuals_basic():
    """Test basic individual validation."""
    # Response with matching individuals
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "ind-123",
                        "type": [
                            {
                                "type": "class",
                                "id": "GO:0004672",
                                "label": "protein kinase activity"
                            }
                        ]
                    },
                    {
                        "id": "ind-456",
                        "type": [
                            {
                                "type": "class",
                                "id": "GO:0003924",
                                "label": "GTPase activity"
                            }
                        ]
                    }
                ]
            }
        }
    )

    # Test validation by ID
    assert response.validate_individuals([{"id": "GO:0004672"}])
    assert response.validate_individuals([{"id": "GO:0003924"}])

    # Test validation by label
    assert response.validate_individuals([{"label": "protein kinase activity"}])
    assert response.validate_individuals([{"label": "GTPase activity"}])

    # Test validation by both ID and label
    assert response.validate_individuals([
        {"id": "GO:0004672", "label": "protein kinase activity"}
    ])

    # Test multiple validations
    assert response.validate_individuals([
        {"id": "GO:0004672"},
        {"id": "GO:0003924"}
    ])

    # Test validation failure
    assert not response.validate_individuals([{"id": "GO:9999999"}])
    assert not response.validate_individuals([{"label": "nonexistent activity"}])


def test_validate_individuals_empty():
    """Test validation with empty or error responses."""
    # Error response
    error_response = BaristaResponse(raw={"message-type": "error"})
    assert not error_response.validate_individuals([{"id": "GO:0004672"}])

    # Empty individuals
    empty_response = BaristaResponse(
        raw={"message-type": "success", "data": {"individuals": []}}
    )
    assert not empty_response.validate_individuals([{"id": "GO:0004672"}])

    # No data
    no_data_response = BaristaResponse(raw={"message-type": "success"})
    assert not no_data_response.validate_individuals([{"id": "GO:0004672"}])


def test_validate_and_rollback():
    """Test validate_and_rollback method."""
    client = MagicMock(spec=BaristaClient)
    undo_response = BaristaResponse(raw={"message-type": "success"})
    client.m3_batch.return_value = undo_response

    # Create response with validation capability
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "ind-123",
                        "type": [{"id": "GO:0004672", "label": "protein kinase activity"}]
                    }
                ]
            }
        },
        _original_requests=[
            {
                "entity": "individual",
                "operation": "add",
                "arguments": {"model-id": "model123", "expressions": [{"type": "class", "id": "GO:0004672"}]}
            }
        ],
        _client=client,
        _before_state={"individuals": []}  # Empty before adding
    )

    # Test successful validation
    result = response.validate_and_rollback(
        [{"id": "GO:0004672"}],
        validation_type="individuals"
    )
    assert result == response  # Should return self
    assert not result.validation_failed
    client.m3_batch.assert_not_called()  # No rollback

    # Test failed validation with rollback
    result = response.validate_and_rollback(
        [{"id": "GO:9999999"}],  # Non-existent
        validation_type="individuals"
    )
    assert result == undo_response  # Should return undo response
    assert result.validation_failed
    assert "Expected ID 'GO:9999999' not found" in result.validation_reason
    client.m3_batch.assert_called_once()  # Rollback executed


def test_validate_and_rollback_no_undo():
    """Test that validation failure without undo capability raises error."""
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {"individuals": []}
        }
        # No undo capability
    )

    with pytest.raises(BaristaError) as exc_info:
        response.validate_and_rollback(
            [{"id": "GO:0004672"}],
            validation_type="individuals"
        )

    assert "cannot undo" in str(exc_info.value).lower()


def test_execute_with_validation():
    """Test execute_with_validation method."""
    client = BaristaClient(token="test-token")

    # Mock successful response with expected individual
    success_response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "ind-new",
                        "type": [{"id": "GO:0003924", "label": "GTPase activity"}]
                    }
                ]
            }
        },
        _original_requests=[],
        _client=client
    )

    with patch.object(client, 'm3_batch', return_value=success_response) as mock_batch:
        requests = [client.req_add_individual("model123", "GO:0003924")]

        # Test successful validation
        response = client.execute_with_validation(
            requests,
            expected_individuals=[{"id": "GO:0003924"}]
        )

        # Should have enabled undo
        mock_batch.assert_called_once()
        assert mock_batch.call_args[1]["enable_undo"] is True

        # Validation should pass
        assert not response.validation_failed


def test_execute_with_validation_rollback():
    """Test execute_with_validation with rollback."""
    client = BaristaClient(token="test-token")

    # Create a response that will fail validation
    wrong_response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "ind-wrong",
                        "type": [{"id": "GO:9999999", "label": "wrong activity"}]
                    }
                ]
            }
        },
        _original_requests=[
            {
                "entity": "individual",
                "operation": "add",
                "arguments": {"model-id": "model123"}
            }
        ],
        _client=client,
        _before_state={"individuals": []}
    )

    # Mock the undo response
    undo_response = BaristaResponse(
        raw={"message-type": "success"},
        validation_failed=True,
        validation_reason="Expected individuals not found"
    )

    with patch.object(client, 'm3_batch') as mock_batch:
        # First call returns wrong response, second call (undo) returns undo response
        mock_batch.side_effect = [wrong_response, undo_response]

        requests = [client.req_add_individual("model123", "GO:0003924")]

        # Execute with validation expecting GO:0003924
        response = client.execute_with_validation(
            requests,
            expected_individuals=[{"id": "GO:0003924"}]
        )

        # Should have called m3_batch twice (execute + undo)
        assert mock_batch.call_count == 2

        # Response should indicate validation failure
        assert response.validation_failed
        assert "Expected ID 'GO:0003924' not found" in response.validation_reason


def test_add_individual_validated():
    """Test add_individual_validated convenience method."""
    client = BaristaClient(token="test-token")

    # Mock successful response
    success_response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "ind-123",
                        "type": [{"id": "GO:0003924"}]
                    }
                ]
            }
        },
        _client=client
    )

    with patch.object(client, 'execute_with_validation', return_value=success_response) as mock_exec:
        client.add_individual_validated(
            "model123",
            "GO:0003924",
            expected_type={"id": "GO:0003924", "label": "GTPase activity"}
        )

        # Should call execute_with_validation
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[1]
        assert call_args["expected_individuals"] == [
            {"id": "GO:0003924", "label": "GTPase activity"}
        ]


def test_add_individual_validated_default_expected():
    """Test add_individual_validated with default expected type."""
    client = BaristaClient(token="test-token")

    success_response = BaristaResponse(
        raw={"message-type": "success", "data": {"individuals": []}}
    )

    with patch.object(client, 'execute_with_validation', return_value=success_response) as mock_exec:
        client.add_individual_validated(
            "model123",
            "GO:0003924"
            # No expected_type provided
        )

        # Should use class_curie as default expected type
        call_args = mock_exec.call_args[1]
        assert call_args["expected_individuals"] == [{"id": "GO:0003924"}]


def test_complex_validation_scenario():
    """Test a complex validation scenario with multiple conditions."""
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {
                "individuals": [
                    {
                        "id": "ind-1",
                        "type": [
                            {"id": "GO:0003924", "label": "GTPase activity"},
                            {"id": "GO:0005525", "label": "GTP binding"}
                        ]
                    },
                    {
                        "id": "ind-2",
                        "type": [
                            {"id": "GO:0004674", "label": "protein serine/threonine kinase activity"}
                        ]
                    },
                    {
                        "id": "ind-3",
                        "type": [
                            {"id": "GO:0005737", "label": "cytoplasm"}
                        ]
                    }
                ]
            }
        }
    )

    # Test multiple conditions all pass
    assert response.validate_individuals([
        {"id": "GO:0003924"},
        {"id": "GO:0004674"},
        {"label": "cytoplasm"}
    ])

    # Test partial match fails
    assert not response.validate_individuals([
        {"id": "GO:0003924"},
        {"id": "GO:9999999"},  # Doesn't exist
        {"label": "cytoplasm"}
    ])

    # Test individual with multiple types
    assert response.validate_individuals([
        {"id": "GO:0005525"}  # Second type of first individual
    ])

    # Test combined ID and label matching
    assert response.validate_individuals([
        {"id": "GO:0003924", "label": "GTPase activity"},
        {"id": "GO:0004674", "label": "protein serine/threonine kinase activity"}
    ])

    # Test wrong label for correct ID fails
    assert not response.validate_individuals([
        {"id": "GO:0003924", "label": "wrong label"}
    ])