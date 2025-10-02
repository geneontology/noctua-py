"""Tests for undo functionality in BaristaClient."""

from unittest.mock import patch, MagicMock
from noctua.barista import BaristaClient, BaristaResponse, BaristaError
import pytest


def test_response_can_undo():
    """Test can_undo method on BaristaResponse."""
    # Response without undo support
    response = BaristaResponse(raw={"message-type": "success"})
    assert not response.can_undo()

    # Response with undo support but failed
    response = BaristaResponse(
        raw={"message-type": "error"},
        _original_requests=[{"entity": "individual", "operation": "add"}],
        _client=MagicMock(),
        _before_state={}
    )
    assert not response.can_undo()  # Not ok

    # Response with undo support and successful
    response = BaristaResponse(
        raw={"message-type": "success"},
        _original_requests=[{"entity": "individual", "operation": "add"}],
        _client=MagicMock(),
        _before_state={}
    )
    assert response.can_undo()


def test_generate_reverse_request_individual():
    """Test reverse operation generation for individuals."""
    client = BaristaClient(token="test")
    response = BaristaResponse(
        raw={"message-type": "success", "data": {"individuals": [{"id": "ind-456"}]}},
        _original_requests=[],
        _client=client,
        _before_state={"individuals": []}
    )

    # Test reversing add individual
    add_request = {
        "entity": "individual",
        "operation": "add",
        "arguments": {
            "expressions": [{"type": "class", "id": "GO:0003924"}],
            "model-id": "model123"
        }
    }
    reverse = response._generate_reverse_request(add_request)
    assert reverse["entity"] == "individual"
    assert reverse["operation"] == "remove"
    assert reverse["arguments"]["individual"] == "ind-456"

    # Test reversing remove individual
    response._before_state = {
        "individuals": [
            {"id": "ind-123", "type": [{"id": "GO:0003924"}]}
        ]
    }
    remove_request = {
        "entity": "individual",
        "operation": "remove",
        "arguments": {
            "individual": "ind-123",
            "model-id": "model123"
        }
    }
    reverse = response._generate_reverse_request(remove_request)
    assert reverse["entity"] == "individual"
    assert reverse["operation"] == "add"
    assert reverse["arguments"]["expressions"][0]["id"] == "GO:0003924"


def test_generate_reverse_request_edge():
    """Test reverse operation generation for edges/facts."""
    response = BaristaResponse(
        raw={"message-type": "success"},
        _original_requests=[],
        _client=MagicMock()
    )

    # Test reversing add edge
    add_edge = {
        "entity": "edge",
        "operation": "add",
        "arguments": {
            "subject": "ind-123",
            "object": "ind-456",
            "predicate": "RO:0002413",
            "model-id": "model123"
        }
    }
    reverse = response._generate_reverse_request(add_edge)
    assert reverse["entity"] == "edge"
    assert reverse["operation"] == "remove"
    assert reverse["arguments"]["subject"] == "ind-123"
    assert reverse["arguments"]["object"] == "ind-456"
    assert reverse["arguments"]["predicate"] == "RO:0002413"

    # Test reversing remove edge
    remove_edge = {
        "entity": "edge",
        "operation": "remove",
        "arguments": {
            "subject": "ind-123",
            "object": "ind-456",
            "predicate": "RO:0002413",
            "model-id": "model123"
        }
    }
    reverse = response._generate_reverse_request(remove_edge)
    assert reverse["entity"] == "edge"
    assert reverse["operation"] == "add"
    assert reverse["arguments"]["subject"] == "ind-123"
    assert reverse["arguments"]["object"] == "ind-456"


def test_generate_reverse_request_annotation():
    """Test reverse operation generation for model annotations."""
    response = BaristaResponse(
        raw={"message-type": "success"},
        _original_requests=[],
        _client=MagicMock()
    )

    # Test reversing add annotation
    add_annotation = {
        "entity": "model",
        "operation": "add-annotation",
        "arguments": {
            "model-id": "model123",
            "key": "title",
            "value": "My Model"
        }
    }
    reverse = response._generate_reverse_request(add_annotation)
    assert reverse["entity"] == "model"
    assert reverse["operation"] == "remove-annotation"
    assert reverse["arguments"]["key"] == "title"
    assert reverse["arguments"]["value"] == "My Model"

    # Test reversing replace annotation
    replace_annotation = {
        "entity": "model",
        "operation": "replace-annotation",
        "arguments": {
            "model-id": "model123",
            "key": "state",
            "value": "production",
            "old-value": "development"
        }
    }
    reverse = response._generate_reverse_request(replace_annotation)
    assert reverse["entity"] == "model"
    assert reverse["operation"] == "replace-annotation"
    assert reverse["arguments"]["value"] == "development"  # Restore old
    assert reverse["arguments"]["old-value"] == "production"  # Current becomes old


def test_undo_method():
    """Test the undo method execution."""
    client = MagicMock(spec=BaristaClient)
    mock_undo_response = BaristaResponse(raw={"message-type": "success"})
    client.m3_batch.return_value = mock_undo_response

    # Create a response with undo capability
    response = BaristaResponse(
        raw={
            "message-type": "success",
            "data": {"individuals": [{"id": "ind-456"}]}
        },
        _original_requests=[
            {
                "entity": "edge",
                "operation": "add",
                "arguments": {
                    "subject": "ind-123",
                    "object": "ind-456",
                    "predicate": "RO:0002413",
                    "model-id": "model123"
                }
            }
        ],
        _client=client,
        _before_state={"individuals": []}
    )

    # Execute undo
    response.undo()

    # Verify the undo was called with reversed operations
    client.m3_batch.assert_called_once()
    undo_requests = client.m3_batch.call_args[0][0]
    assert len(undo_requests) == 1
    assert undo_requests[0]["operation"] == "remove"
    assert undo_requests[0]["entity"] == "edge"


def test_undo_without_capability():
    """Test that undo raises error when not enabled."""
    response = BaristaResponse(raw={"message-type": "success"})

    with pytest.raises(BaristaError) as exc_info:
        response.undo()

    assert "Cannot undo" in str(exc_info.value)


def test_m3_batch_with_undo():
    """Test m3_batch method with undo enabled."""
    client = BaristaClient(token="test-token")

    # Mock the HTTP client
    mock_http_response = MagicMock()
    mock_http_response.json.return_value = {
        "message-type": "success",
        "data": {"id": "model123", "individuals": [{"id": "ind-456"}]}
    }
    client._client.post = MagicMock(return_value=mock_http_response)

    # Mock get_model for before state
    with patch.object(client, 'get_model') as mock_get:
        mock_get.return_value = BaristaResponse(
            raw={
                "message-type": "success",
                "data": {"individuals": [], "facts": []}
            }
        )

        requests = [{
            "entity": "individual",
            "operation": "add",
            "arguments": {
                "expressions": [{"type": "class", "id": "GO:0003924"}],
                "model-id": "model123"
            }
        }]

        # Execute with undo enabled
        response = client.m3_batch(requests, enable_undo=True)

        assert response.can_undo()
        assert response._original_requests == requests
        assert response._client == client
        assert response._before_state is not None


def test_add_individual_with_undo():
    """Test add_individual with undo enabled."""
    client = BaristaClient(token="test-token", track_variables=False)  # Disable variable tracking

    # Mock the m3_batch method
    mock_response = BaristaResponse(
        raw={"message-type": "success", "data": {"individuals": [{"id": "new-ind"}]}},
        _original_requests=[],
        _client=client
    )

    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        client.add_individual("model123", "GO:0003924", enable_undo=True)

        # Verify enable_undo was passed through
        mock_batch.assert_called_once()
        call_args = mock_batch.call_args
        assert call_args[1].get("enable_undo") is True


def test_add_fact_with_undo():
    """Test add_fact with undo enabled."""
    client = BaristaClient(token="test-token")

    mock_response = BaristaResponse(
        raw={"message-type": "success", "data": {"facts": []}},
        _original_requests=[],
        _client=client
    )

    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        client.add_fact(
            "model123", "ind-123", "ind-456", "RO:0002413", enable_undo=True
        )

        # Verify enable_undo was passed through
        mock_batch.assert_called_once()
        assert mock_batch.call_args[1].get("enable_undo") is True


def test_complex_undo_scenario():
    """Test undo with multiple operations."""
    client = MagicMock(spec=BaristaClient)
    mock_undo_response = BaristaResponse(raw={"message-type": "success"})
    client.m3_batch.return_value = mock_undo_response

    # Create response with multiple operations
    response = BaristaResponse(
        raw={"message-type": "success", "data": {"individuals": [{"id": "ind-1"}, {"id": "ind-2"}]}},
        _original_requests=[
            {
                "entity": "individual",
                "operation": "add",
                "arguments": {"model-id": "model123", "expressions": [{"type": "class", "id": "GO:0001"}]}
            },
            {
                "entity": "individual",
                "operation": "add",
                "arguments": {"model-id": "model123", "expressions": [{"type": "class", "id": "GO:0002"}]}
            },
            {
                "entity": "edge",
                "operation": "add",
                "arguments": {"model-id": "model123", "subject": "ind-1", "object": "ind-2", "predicate": "RO:0002413"}
            }
        ],
        _client=client,
        _before_state={"individuals": []}
    )

    # Execute undo
    response.undo()

    # Verify operations are reversed in reverse order
    undo_requests = client.m3_batch.call_args[0][0]
    assert len(undo_requests) == 3
    # Edge removed first (was added last)
    assert undo_requests[0]["entity"] == "edge"
    assert undo_requests[0]["operation"] == "remove"
    # Then individuals in reverse order
    assert undo_requests[1]["entity"] == "individual"
    assert undo_requests[2]["entity"] == "individual"