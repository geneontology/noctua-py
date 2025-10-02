"""Tests for client-side variable tracking in BaristaClient."""

from unittest.mock import patch
from noctua.barista import BaristaClient, BaristaResponse


def test_is_variable():
    """Test variable identification logic."""
    client = BaristaClient(token="test-token")

    # Variables (simple names)
    assert client._is_variable("ras")
    assert client._is_variable("kinase1")
    assert client._is_variable("my_var")
    assert client._is_variable("x1")

    # Not variables (CURIEs and IDs)
    assert not client._is_variable("GO:0003924")
    assert not client._is_variable("RO:0002413")
    assert not client._is_variable("gomodel:123/individual-456")
    assert not client._is_variable("http://example.com/id")


def test_variable_registry_operations():
    """Test basic variable registry operations."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    # Set and get variables
    client.set_variable(model_id, "ras", "individual-123")
    client.set_variable(model_id, "raf", "individual-456")

    assert client.get_variable(model_id, "ras") == "individual-123"
    assert client.get_variable(model_id, "raf") == "individual-456"
    assert client.get_variable(model_id, "unknown") is None

    # Get all variables for a model
    vars = client.get_variables(model_id)
    assert vars == {"ras": "individual-123", "raf": "individual-456"}

    # Variables are model-scoped
    other_model = "gomodel:other"
    client.set_variable(other_model, "ras", "different-id")
    assert client.get_variable(model_id, "ras") == "individual-123"
    assert client.get_variable(other_model, "ras") == "different-id"

    # Clear variables for a model
    client.clear_variables(model_id)
    assert client.get_variables(model_id) == {}
    assert client.get_variable(other_model, "ras") == "different-id"

    # Clear all variables
    client.clear_variables()
    assert client.get_variable(other_model, "ras") is None


def test_resolve_identifier():
    """Test identifier resolution (variable vs CURIE/ID)."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    # Set up some variables
    client.set_variable(model_id, "ras", "individual-123")
    client.set_variable(model_id, "raf", "individual-456")

    # Variables get resolved
    assert client._resolve_identifier(model_id, "ras") == "individual-123"
    assert client._resolve_identifier(model_id, "raf") == "individual-456"

    # Unknown variables pass through
    assert client._resolve_identifier(model_id, "unknown") == "unknown"

    # CURIEs and IDs pass through unchanged
    assert client._resolve_identifier(model_id, "GO:0003924") == "GO:0003924"
    assert client._resolve_identifier(model_id, "gomodel:123/ind-456") == "gomodel:123/ind-456"


def test_add_individual_with_tracking():
    """Test that add_individual tracks new variables."""
    client = BaristaClient(token="test-token", track_variables=True)
    model_id = "gomodel:test123"

    # Mock the responses
    before_response = BaristaResponse(raw={
        "message-type": "success",
        "data": {
            "id": model_id,
            "individuals": [
                {"id": "existing-ind-1", "type": [{"id": "GO:0001"}]}
            ],
            "facts": []
        }
    })

    after_response = BaristaResponse(raw={
        "message-type": "success",
        "data": {
            "id": model_id,
            "individuals": [
                {"id": "existing-ind-1", "type": [{"id": "GO:0001"}]},
                {"id": "new-ind-123", "type": [{"id": "GO:0003924"}]}
            ],
            "facts": []
        }
    })

    with patch.object(client, 'get_model', return_value=before_response):
        with patch.object(client, 'm3_batch', return_value=after_response):
            response = client.add_individual(model_id, "GO:0003924", "ras")

    # Check that the variable was tracked
    assert response.ok
    assert client.get_variable(model_id, "ras") == "new-ind-123"


def test_add_fact_with_variables():
    """Test that add_fact resolves variables."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    # Set up variables
    client.set_variable(model_id, "ras", "individual-123")
    client.set_variable(model_id, "raf", "individual-456")

    # Mock the m3_batch method to capture the request
    mock_response = BaristaResponse(raw={"message-type": "success", "data": {}})

    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        client.add_fact(model_id, "ras", "raf", "RO:0002413")

        # Check that the request used resolved IDs
        mock_batch.assert_called_once()
        request = mock_batch.call_args[0][0][0]
        assert request["arguments"]["subject"] == "individual-123"
        assert request["arguments"]["object"] == "individual-456"


def test_add_fact_with_mixed_identifiers():
    """Test add_fact with mix of variables and CURIEs."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    client.set_variable(model_id, "ras", "individual-123")

    mock_response = BaristaResponse(raw={"message-type": "success", "data": {}})

    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        # Variable as subject, CURIE as object
        client.add_fact(model_id, "ras", "gomodel:123/other-ind", "RO:0002413")

        request = mock_batch.call_args[0][0][0]
        assert request["arguments"]["subject"] == "individual-123"
        assert request["arguments"]["object"] == "gomodel:123/other-ind"


def test_remove_operations_with_variables():
    """Test that remove operations resolve variables."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    client.set_variable(model_id, "ras", "individual-123")
    client.set_variable(model_id, "raf", "individual-456")

    mock_response = BaristaResponse(raw={"message-type": "success", "data": {}})

    # Test remove_individual
    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        client.remove_individual(model_id, "ras")
        request = mock_batch.call_args[0][0][0]
        assert request["arguments"]["individual"] == "individual-123"

    # Test remove_fact
    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        client.remove_fact(model_id, "ras", "raf", "RO:0002413")
        request = mock_batch.call_args[0][0][0]
        assert request["arguments"]["subject"] == "individual-123"
        assert request["arguments"]["object"] == "individual-456"


def test_tracking_can_be_disabled():
    """Test that variable tracking can be disabled."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    mock_response = BaristaResponse(raw={
        "message-type": "success",
        "data": {"id": model_id, "individuals": [], "facts": []}
    })

    with patch.object(client, 'get_model') as mock_get:
        with patch.object(client, 'm3_batch', return_value=mock_response):
            client.add_individual(model_id, "GO:0003924", "ras")

        # get_model should not be called when tracking is disabled
        mock_get.assert_not_called()

    # Variable should not be tracked
    assert client.get_variable(model_id, "ras") is None


def test_complex_workflow():
    """Test a complete workflow using variables."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    # Manually simulate what would happen with real API calls
    client.set_variable(model_id, "ras", "ind-001")
    client.set_variable(model_id, "raf", "ind-002")
    client.set_variable(model_id, "mek", "ind-003")

    mock_response = BaristaResponse(raw={"message-type": "success", "data": {}})

    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        # Build a pathway using variables
        client.add_fact(model_id, "ras", "raf", "RO:0002413")
        client.add_fact(model_id, "raf", "mek", "RO:0002413")

        # Add evidence using variables
        client.add_fact_with_evidence(
            model_id,
            "ras",
            "raf",
            "RO:0002413",
            "ECO:0000314",
            ["PMID:12345"]
        )

        # All calls should use resolved IDs
        calls = mock_batch.call_args_list
        assert len(calls) == 3

        # First fact: ras -> raf
        req1 = calls[0][0][0][0]
        assert req1["arguments"]["subject"] == "ind-001"
        assert req1["arguments"]["object"] == "ind-002"

        # Second fact: raf -> mek
        req2 = calls[1][0][0][0]
        assert req2["arguments"]["subject"] == "ind-002"
        assert req2["arguments"]["object"] == "ind-003"

        # Evidence (first request in batch)
        req3 = calls[2][0][0][0]
        assert req3["arguments"]["subject"] == "ind-001"
        assert req3["arguments"]["object"] == "ind-002"