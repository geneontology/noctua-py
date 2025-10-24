"""Tests for higher-level entity set operations."""

from unittest.mock import patch
from noctua.barista import BaristaClient, BaristaResponse
from noctua.models import EntitySetMember
import pytest


def test_add_entity_set_simple():
    """Test adding a simple entity set with two members."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    members = [
        EntitySetMember(entity_id="UniProtKB:P27361", label="MAPK3 (ERK1)"),
        EntitySetMember(entity_id="UniProtKB:P28482", label="MAPK1 (ERK2)")
    ]

    # Mock the response
    response = BaristaResponse(raw={
        "message-type": "success",
        "data": {
            "id": model_id,
            "individuals": [],
            "facts": []
        }
    })

    with patch.object(client, '_execute_simple_batch', return_value=response):
        result = client.add_entity_set(model_id, members)

    assert result.ok


def test_add_entity_set_with_evidence():
    """Test adding an entity set with evidence."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    members = [
        EntitySetMember(
            entity_id="UniProtKB:P27361",
            label="MAPK3 (ERK1)",
            evidence_type="ECO:0000314",
            reference="PMID:12345678"
        )
    ]

    response = BaristaResponse(raw={
        "message-type": "success",
        "data": {
            "id": model_id,
            "individuals": [],
            "facts": []
        }
    })

    with patch.object(client, '_execute_simple_batch', return_value=response):
        result = client.add_entity_set(
            model_id,
            members,
            set_class="CHEBI:33695",
            assign_var="my_set",
            expected_label="ERK paralogy group"
        )

    assert result.ok


def test_add_entity_set_no_members_error():
    """Test that adding a set with no members raises an error."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    with pytest.raises(Exception, match="At least one member is required"):
        client.add_entity_set(model_id, [])


def test_add_entity_set_missing_entity_id():
    """Test that missing entity_id raises an error from Pydantic validation."""
    # This should fail at Pydantic validation level when creating the model
    with pytest.raises(Exception):  # Pydantic ValidationError
        EntitySetMember(label="MAPK3")  # Missing required entity_id


def test_add_entity_set_custom_class():
    """Test adding an entity set with a custom set class."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    members = [
        EntitySetMember(entity_id="UniProtKB:P27361")
    ]

    response = BaristaResponse(raw={
        "message-type": "success",
        "data": {
            "id": model_id,
            "individuals": [],
            "facts": []
        }
    })

    with patch.object(client, '_execute_simple_batch', return_value=response):
        result = client.add_entity_set(
            model_id,
            members,
            set_class="CHEBI:33695"  # information biomacromolecule
        )

    assert result.ok


def test_add_entity_set_paralogy_group():
    """Test adding a paralogy group (typical use case for entity sets)."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    # Example: ERK1 and ERK2 are paralogs (functionally interchangeable)
    members = [
        EntitySetMember(
            entity_id="UniProtKB:P27361",
            label="MAPK3 (ERK1)",
            evidence_type="ECO:0000314",
            reference="PMID:12345678"
        ),
        EntitySetMember(
            entity_id="UniProtKB:P28482",
            label="MAPK1 (ERK2)",
            evidence_type="ECO:0000314",
            reference="PMID:12345678"
        )
    ]

    response = BaristaResponse(raw={
        "message-type": "success",
        "data": {
            "id": model_id,
            "individuals": [],
            "facts": []
        }
    })

    with patch.object(client, '_execute_simple_batch', return_value=response):
        result = client.add_entity_set(
            model_id,
            members,
            assign_var="erk_paralogs",
            expected_label="ERK paralogy group"
        )

    assert result.ok
