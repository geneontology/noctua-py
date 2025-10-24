"""Tests for higher-level protein complex operations."""

from unittest.mock import patch
from noctua.barista import BaristaClient, BaristaResponse
from noctua.models import ProteinComplexComponent
import pytest


def test_add_protein_complex_simple():
    """Test adding a simple protein complex with two components."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    components = [
        ProteinComplexComponent(entity_id="UniProtKB:P12345", label="Protein A"),
        ProteinComplexComponent(entity_id="UniProtKB:P67890", label="Protein B")
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
        result = client.add_protein_complex(model_id, components)

    assert result.ok


def test_add_protein_complex_with_evidence():
    """Test adding a protein complex with evidence."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    components = [
        ProteinComplexComponent(
            entity_id="UniProtKB:P12345",
            label="Ras protein",
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
        result = client.add_protein_complex(
            model_id,
            components,
            complex_class="GO:0032991",
            assign_var="my_complex",
            expected_label="Ras signaling complex"
        )

    assert result.ok


def test_add_protein_complex_no_components_error():
    """Test that adding a complex with no components raises an error."""
    client = BaristaClient(token="test-token")
    model_id = "gomodel:test123"

    with pytest.raises(Exception, match="At least one component is required"):
        client.add_protein_complex(model_id, [])


def test_add_protein_complex_missing_entity_id():
    """Test that missing entity_id raises an error from Pydantic validation."""
    # This should fail at Pydantic validation level when creating the model
    with pytest.raises(Exception):  # Pydantic ValidationError
        ProteinComplexComponent(label="Protein A")  # Missing required entity_id


def test_add_protein_complex_custom_class():
    """Test adding a complex with a custom complex class."""
    client = BaristaClient(token="test-token", track_variables=False)
    model_id = "gomodel:test123"

    components = [
        ProteinComplexComponent(entity_id="UniProtKB:P12345")
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
        result = client.add_protein_complex(
            model_id,
            components,
            complex_class="GO:1990904"  # ribonucleoprotein complex
        )

    assert result.ok
