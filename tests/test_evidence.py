"""Tests for Barista evidence-finding methods that use Amigo."""

import pytest
from unittest.mock import MagicMock, patch

from noctua.barista import BaristaClient, BaristaResponse


class TestEvidenceMethods:
    """Test suite for evidence-finding methods."""

    @pytest.fixture
    def barista_client(self):
        """Create a BaristaClient with mocked token."""
        with patch.dict('os.environ', {'BARISTA_TOKEN': 'test-token'}):
            client = BaristaClient(
                base_url="http://test.barista",
                namespace="test",
                provided_by="test"
            )
            return client

    @pytest.fixture
    def mock_model_response(self):
        """Create a mock model response with typical GO-CAM structure."""
        return BaristaResponse(raw={
            "message-type": "success",
            "data": {
                "id": "gomodel:test123",
                "title": "Test model",
                "individuals": [
                    {
                        "id": "ind1",
                        "type": {"id": "GO:0003924", "label": "GTPase activity"},
                        "annotations": [
                            {"key": "enabled_by", "value": "UniProtKB:P12345"}
                        ]
                    },
                    {
                        "id": "ind2",
                        "type": {"id": "UniProtKB:P12345", "label": "RAS protein"},
                        "annotations": [
                            {"key": "id", "value": "UniProtKB:P12345"}
                        ]
                    },
                    {
                        "id": "ind3",
                        "type": {"id": "GO:0007264", "label": "small GTPase mediated signal transduction"},
                        "annotations": []
                    },
                    {
                        "id": "ind4",
                        "type": {"id": "GO:0005886", "label": "plasma membrane"},
                        "annotations": []
                    }
                ],
                "facts": [
                    {
                        "subject": "ind1",
                        "object": "ind2",
                        "property": "RO:0002333"  # enabled_by
                    },
                    {
                        "subject": "ind1",
                        "object": "ind3",
                        "property": "RO:0002213"  # positively regulates
                    },
                    {
                        "subject": "ind1",
                        "object": "ind4",
                        "property": "BFO:0000066"  # occurs_in
                    }
                ]
            }
        })

    def test_find_evidence_for_enabled_by_edge(self, barista_client, mock_model_response):
        """Test finding evidence for an enabled_by edge (MF annotation)."""
        # Mock the get_model call
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        # Mock Amigo client
        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo

            # Mock annotation results
            mock_annotation = MagicMock()
            mock_annotation.bioentity = "UniProtKB:P12345"
            mock_annotation.bioentity_label = "RAS"
            mock_annotation.annotation_class = "GO:0003924"
            mock_annotation.annotation_class_label = "GTPase activity"
            mock_annotation.evidence_type = "IDA"
            mock_annotation.reference = "PMID:12345678"
            mock_annotation.assigned_by = "UniProtKB"
            mock_annotation.date = "20230101"
            mock_annotation.qualifier = ""
            mock_annotation.gene_product_form_id = ""

            mock_amigo.search_annotations.return_value = [mock_annotation]

            # Call the method
            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "ind1",  # GTPase activity
                "ind2",  # RAS protein
                "RO:0002333"  # enabled_by
            )

            # Verify the result
            assert result["mapping_type"] == "enabled_by"
            assert result["edge"]["subject"] == "ind1"
            assert result["edge"]["object"] == "ind2"
            assert result["edge"]["predicate"] == "RO:0002333"
            assert len(result["annotations"]) == 1
            assert result["annotations"][0]["bioentity"] == "UniProtKB:P12345"
            assert result["annotations"][0]["evidence_type"] == "IDA"
            assert "MF annotations" in result["summary"]

            # Verify Amigo was called correctly
            mock_amigo.search_annotations.assert_called_once_with(
                bioentity="UniProtKB:P12345",
                go_term="GO:0003924",
                aspect="F",
                evidence_types=None,
                limit=50
            )

    def test_find_evidence_for_activity_to_process_edge(self, barista_client, mock_model_response):
        """Test finding evidence for activity->process edge (BP annotation)."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo

            mock_annotation = MagicMock()
            mock_annotation.bioentity = "UniProtKB:P12345"
            mock_annotation.annotation_class = "GO:0007264"
            mock_annotation.annotation_class_label = "small GTPase mediated signal transduction"
            mock_annotation.evidence_type = "IMP"
            mock_annotation.reference = "PMID:87654321"
            mock_annotation.assigned_by = "GOC"
            mock_annotation.date = "20230201"
            mock_annotation.qualifier = ""
            mock_annotation.gene_product_form_id = ""

            mock_amigo.search_annotations.return_value = [mock_annotation]

            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "ind1",  # GTPase activity
                "ind3",  # signal transduction process
                "RO:0002213"  # positively regulates
            )

            assert result["mapping_type"] == "activity_to_process"
            assert len(result["annotations"]) == 1
            assert result["annotations"][0]["annotation_class"] == "GO:0007264"
            assert "BP annotations" in result["summary"]

            # Verify Amigo was called with BP aspect
            mock_amigo.search_annotations.assert_called_once_with(
                bioentity="UniProtKB:P12345",  # From enabled_by of ind1
                go_term="GO:0007264",
                aspect="P",
                evidence_types=None,
                limit=50
            )

    def test_find_evidence_for_activity_to_location_edge(self, barista_client, mock_model_response):
        """Test finding evidence for activity->location edge (CC annotation)."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo

            mock_annotation = MagicMock()
            mock_annotation.bioentity = "UniProtKB:P12345"
            mock_annotation.annotation_class = "GO:0005886"
            mock_annotation.annotation_class_label = "plasma membrane"
            mock_annotation.evidence_type = "IDA"
            mock_annotation.reference = "PMID:11111111"
            mock_annotation.assigned_by = "UniProtKB"
            mock_annotation.date = "20230301"
            mock_annotation.qualifier = ""
            mock_annotation.gene_product_form_id = ""

            mock_amigo.search_annotations.return_value = [mock_annotation]

            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "ind1",  # GTPase activity
                "ind4",  # plasma membrane
                "BFO:0000066"  # occurs_in
            )

            assert result["mapping_type"] == "activity_to_location"
            assert len(result["annotations"]) == 1
            assert result["annotations"][0]["annotation_class"] == "GO:0005886"
            assert "CC annotations" in result["summary"]

            # Verify Amigo was called with CC aspect
            mock_amigo.search_annotations.assert_called_once_with(
                bioentity="UniProtKB:P12345",
                go_term="GO:0005886",
                aspect="C",
                evidence_types=None,
                limit=50
            )

    def test_find_evidence_with_filters(self, barista_client, mock_model_response):
        """Test finding evidence with evidence type filters."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo
            mock_amigo.search_annotations.return_value = []

            barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "ind1",
                "ind2",
                "RO:0002333",
                evidence_types=["IDA", "IPI"],
                limit=20
            )

            # Verify filters were passed through
            mock_amigo.search_annotations.assert_called_once()
            call_args = mock_amigo.search_annotations.call_args
            assert call_args[1]["evidence_types"] == ["IDA", "IPI"]
            assert call_args[1]["limit"] == 20

    def test_find_evidence_for_model(self, barista_client, mock_model_response):
        """Test finding evidence for all edges in a model."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo

            # Return different annotations for each edge type
            def mock_search(bioentity=None, go_term=None, aspect=None, **kwargs):
                if aspect == "F":  # MF for enabled_by
                    ann = MagicMock()
                    ann.bioentity = "UniProtKB:P12345"
                    ann.annotation_class = "GO:0003924"
                    ann.evidence_type = "IDA"
                    ann.reference = "PMID:111"
                    ann.assigned_by = "UniProtKB"
                    ann.date = "20230101"
                    ann.qualifier = ""
                    ann.gene_product_form_id = ""
                    ann.bioentity_label = "RAS"
                    ann.annotation_class_label = "GTPase activity"
                    return [ann]
                elif aspect == "P":  # BP
                    ann = MagicMock()
                    ann.bioentity = "UniProtKB:P12345"
                    ann.annotation_class = "GO:0007264"
                    ann.evidence_type = "IMP"
                    ann.reference = "PMID:222"
                    ann.assigned_by = "GOC"
                    ann.date = "20230201"
                    ann.qualifier = ""
                    ann.gene_product_form_id = ""
                    ann.bioentity_label = "RAS"
                    ann.annotation_class_label = "signal transduction"
                    return [ann, ann]  # Return 2 annotations
                elif aspect == "C":  # CC
                    ann = MagicMock()
                    ann.bioentity = "UniProtKB:P12345"
                    ann.annotation_class = "GO:0005886"
                    ann.evidence_type = "IDA"
                    ann.reference = "PMID:333"
                    ann.assigned_by = "UniProtKB"
                    ann.date = "20230301"
                    ann.qualifier = ""
                    ann.gene_product_form_id = ""
                    ann.bioentity_label = "RAS"
                    ann.annotation_class_label = "plasma membrane"
                    return [ann, ann, ann]  # Return 3 annotations
                return []

            mock_amigo.search_annotations.side_effect = mock_search

            result = barista_client.find_evidence_for_model(
                "gomodel:test123",
                evidence_types=["IDA", "IMP"],
                limit_per_edge=5
            )

            assert result["model_id"] == "gomodel:test123"
            assert result["model_title"] == "Test model"
            assert len(result["edges_with_evidence"]) == 3  # All 3 edges
            assert result["total_annotations"] == 6  # 1 + 2 + 3
            assert "3 of 3 relevant edges" in result["summary"]

            # Check individual edge results
            enabled_by_edge = next(e for e in result["edges_with_evidence"]
                                  if e["mapping_type"] == "enabled_by")
            assert len(enabled_by_edge["annotations"]) == 1

            process_edge = next(e for e in result["edges_with_evidence"]
                               if e["mapping_type"] == "activity_to_process")
            assert len(process_edge["annotations"]) == 2

            location_edge = next(e for e in result["edges_with_evidence"]
                                if e["mapping_type"] == "activity_to_location")
            assert len(location_edge["annotations"]) == 3

    def test_find_evidence_with_variable_names(self, barista_client, mock_model_response):
        """Test that variable names are resolved correctly."""
        # Add variable mapping to client
        barista_client._variables = {"gtpase": "ind1", "ras": "ind2"}
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo
            mock_amigo.search_annotations.return_value = []

            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "gtpase",  # Should resolve to ind1
                "ras",     # Should resolve to ind2
                "RO:0002333"
            )

            assert result["edge"]["subject"] == "ind1"
            assert result["edge"]["object"] == "ind2"
            assert result["mapping_type"] == "enabled_by"

    def test_find_evidence_for_unknown_edge(self, barista_client, mock_model_response):
        """Test handling of unknown/unsupported edge types."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo

            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "ind1",
                "ind2",
                "RO:9999999"  # Unknown predicate
            )

            assert result["mapping_type"] == "unknown"
            assert result["annotations"] == []
            assert "Found 0 annotations" in result["summary"]

            # Amigo should not be called for unknown predicates
            mock_amigo.search_annotations.assert_not_called()

    def test_find_evidence_with_missing_individuals(self, barista_client, mock_model_response):
        """Test error handling when individuals cannot be resolved."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo

            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "nonexistent1",
                "nonexistent2",
                "RO:0002333"
            )

            assert result["mapping_type"] == "unknown"
            assert result["annotations"] == []
            assert "Could not resolve individual IDs" in result["summary"]

            # Amigo should not be called if individuals can't be resolved
            mock_amigo.search_annotations.assert_not_called()

    def test_find_evidence_with_amigo_error(self, barista_client, mock_model_response):
        """Test graceful handling of Amigo errors."""
        barista_client.get_model = MagicMock(return_value=mock_model_response)

        with patch('noctua.amigo.AmigoClient') as MockAmigoClient:
            mock_amigo = MagicMock()
            MockAmigoClient.return_value = mock_amigo
            mock_amigo.search_annotations.side_effect = Exception("Connection error")

            result = barista_client.find_evidence_for_edge(
                "gomodel:test123",
                "ind1",
                "ind2",
                "RO:0002333"
            )

            # Should return empty annotations but still have correct structure
            assert result["mapping_type"] == "enabled_by"
            assert result["annotations"] == []
            assert result["edge"]["subject"] == "ind1"