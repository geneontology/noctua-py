"""Tests for markdown export functionality."""

from unittest.mock import patch
from noctua.barista import BaristaClient, BaristaResponse


def test_export_model_markdown():
    """Test that markdown format triggers special handling."""
    client = BaristaClient(token="test-token")

    # Mock get_model response
    mock_model_data = {
        "message-type": "success",
        "data": {
            "id": "gomodel:test123",
            "annotations": [
                {"key": "title", "value": "Test Model"},
                {"key": "state", "value": "development"},
                {"key": "comment", "value": "Test comment"}
            ],
            "individuals": [
                {
                    "id": "ind-123",
                    "type": [
                        {
                            "id": "GO:0003924",
                            "label": "GTPase activity"
                        }
                    ],
                    "annotations": [
                        {"key": "enabled_by", "value": "UniProtKB:P12345"},
                        {"key": "rdfs:label", "value": "RAS protein"}
                    ]
                },
                {
                    "id": "ind-456",
                    "type": [
                        {
                            "id": "GO:0004674",
                            "label": "protein serine/threonine kinase activity"
                        }
                    ],
                    "annotations": []
                }
            ],
            "facts": [
                {
                    "subject": "ind-123",
                    "object": "ind-456",
                    "predicate": {
                        "id": "RO:0002413",
                        "label": "directly positively regulates"
                    },
                    "annotations": [
                        {"key": "evidence", "value": "ECO:0000314"}
                    ]
                }
            ]
        }
    }

    with patch.object(client, 'get_model') as mock_get:
        mock_get.return_value = BaristaResponse(raw=mock_model_data)

        # Export as markdown
        resp = client.export_model("gomodel:test123", format="markdown")

        # Verify get_model was called
        mock_get.assert_called_once_with("gomodel:test123")

        # Check response
        assert resp.ok
        markdown_content = resp.raw.get("data", "")
        assert isinstance(markdown_content, str)

        # Check content includes expected elements
        assert "# Test Model" in markdown_content
        assert "Model ID**: `gomodel:test123`" in markdown_content
        assert "State**: development" in markdown_content
        assert "GTPase activity" in markdown_content
        assert "protein serine/threonine kinase activity" in markdown_content
        assert "directly positively regulates" in markdown_content
        assert "RAS protein" in markdown_content
        assert "UniProtKB:P12345" in markdown_content


def test_export_model_markdown_minimal():
    """Test markdown export with minimal model."""
    client = BaristaClient(token="test-token")

    # Minimal model with no annotations or facts
    mock_model_data = {
        "message-type": "success",
        "data": {
            "id": "gomodel:minimal",
            "annotations": [],
            "individuals": [
                {
                    "id": "ind-1",
                    "type": [{"id": "GO:0003924", "label": "GTPase activity"}],
                    "annotations": []
                }
            ],
            "facts": []
        }
    }

    with patch.object(client, 'get_model') as mock_get:
        mock_get.return_value = BaristaResponse(raw=mock_model_data)

        resp = client.export_model("gomodel:minimal", format="markdown")

        assert resp.ok
        markdown_content = resp.raw.get("data", "")

        # Should have default title
        assert "# Untitled Model" in markdown_content
        assert "Model ID**: `gomodel:minimal`" in markdown_content
        assert "GTPase activity" in markdown_content
        # Should not have relationships section if no facts
        assert "## Relationships" not in markdown_content


def test_export_model_markdown_empty():
    """Test markdown export with empty model."""
    client = BaristaClient(token="test-token")

    # Empty model
    mock_model_data = {
        "message-type": "success",
        "data": {
            "id": "gomodel:empty",
            "annotations": [{"key": "title", "value": "Empty Model"}],
            "individuals": [],
            "facts": []
        }
    }

    with patch.object(client, 'get_model') as mock_get:
        mock_get.return_value = BaristaResponse(raw=mock_model_data)

        resp = client.export_model("gomodel:empty", format="markdown")

        assert resp.ok
        markdown_content = resp.raw.get("data", "")

        assert "# Empty Model" in markdown_content
        # Should not have activities or relationships sections
        assert "## Activities and Entities" not in markdown_content
        assert "## Relationships" not in markdown_content


def test_export_model_markdown_with_multiple_facts():
    """Test markdown export groups facts by predicate."""
    client = BaristaClient(token="test-token")

    mock_model_data = {
        "message-type": "success",
        "data": {
            "id": "gomodel:complex",
            "annotations": [{"key": "title", "value": "Complex Model"}],
            "individuals": [
                {
                    "id": "ind-1",
                    "type": [{"id": "GO:0003924", "label": "GTPase activity"}],
                    "annotations": []
                },
                {
                    "id": "ind-2",
                    "type": [{"id": "GO:0004674", "label": "kinase activity"}],
                    "annotations": []
                },
                {
                    "id": "ind-3",
                    "type": [{"id": "GO:0004707", "label": "MAP kinase activity"}],
                    "annotations": []
                }
            ],
            "facts": [
                {
                    "subject": "ind-1",
                    "object": "ind-2",
                    "predicate": {"id": "RO:0002413", "label": "directly positively regulates"},
                    "annotations": []
                },
                {
                    "subject": "ind-2",
                    "object": "ind-3",
                    "predicate": {"id": "RO:0002413", "label": "directly positively regulates"},
                    "annotations": []
                },
                {
                    "subject": "ind-1",
                    "object": "ind-3",
                    "predicate": {"id": "RO:0002212", "label": "negatively regulates"},
                    "annotations": []
                }
            ]
        }
    }

    with patch.object(client, 'get_model') as mock_get:
        mock_get.return_value = BaristaResponse(raw=mock_model_data)

        resp = client.export_model("gomodel:complex", format="markdown")

        assert resp.ok
        markdown_content = resp.raw.get("data", "")

        # Check that facts are grouped by predicate
        assert "### directly positively regulates" in markdown_content
        assert "### negatively regulates" in markdown_content

        # Check relationships are shown
        assert "GTPase activity** → **kinase activity**" in markdown_content
        assert "kinase activity** → **MAP kinase activity**" in markdown_content
        assert "GTPase activity** → **MAP kinase activity**" in markdown_content


def test_export_model_other_formats_unchanged():
    """Test that non-markdown formats still work normally."""
    client = BaristaClient(token="test-token")

    # Mock response for non-markdown format
    mock_response = BaristaResponse(
        raw={"message-type": "success", "data": "exported content"}
    )

    with patch.object(client, 'm3_batch', return_value=mock_response) as mock_batch:
        # Test OWL format (default)
        resp = client.export_model("gomodel:test", format="owl")
        assert resp == mock_response
        mock_batch.assert_called_once()

        # Test TTL format
        mock_batch.reset_mock()
        resp = client.export_model("gomodel:test", format="ttl")
        assert resp == mock_response
        mock_batch.assert_called_once()


def test_find_individual_label():
    """Test the helper method for finding individual labels."""
    client = BaristaClient(token="test-token")

    individuals = [
        {
            "id": "ind-1",
            "type": [{"id": "GO:0003924", "label": "GTPase activity"}],
            "annotations": [{"key": "rdfs:label", "value": "Custom Label"}]
        },
        {
            "id": "ind-2",
            "type": [{"id": "GO:0004674", "label": "kinase activity"}],
            "annotations": []
        }
    ]

    # Should prefer rdfs:label
    label = client._find_individual_label(individuals, "ind-1")
    assert label == "Custom Label"

    # Should fallback to type label
    label = client._find_individual_label(individuals, "ind-2")
    assert label == "kinase activity"

    # Should return ID if not found
    label = client._find_individual_label(individuals, "ind-999")
    assert label == "ind-999"


def test_export_model_markdown_error_handling():
    """Test markdown export handles errors properly."""
    client = BaristaClient(token="test-token")

    # Mock failed get_model
    error_response = BaristaResponse(raw={"message-type": "error", "message": "Model not found"})

    with patch.object(client, 'get_model', return_value=error_response):
        resp = client.export_model("gomodel:nonexistent", format="markdown")

        # Should return the error response
        assert not resp.ok
        assert resp.raw["message-type"] == "error"