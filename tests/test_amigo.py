"""Tests for AmigoClient."""

import pytest
from unittest.mock import MagicMock, patch
import json

from noctua.amigo import (
    AmigoClient,
    AmigoError,
    BioentityResult,
    AnnotationResult
)


class TestAmigoClient:
    """Test suite for AmigoClient."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        with patch('noctua.amigo.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def amigo_client(self, mock_httpx_client):
        """Create an AmigoClient with mocked HTTP client."""
        # Mock successful connection test
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0}
        }
        mock_httpx_client.get.return_value = mock_response

        client = AmigoClient(base_url="http://test.solr.endpoint")
        return client

    def test_client_initialization(self, mock_httpx_client):
        """Test client initialization with custom base URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0}
        }
        mock_httpx_client.get.return_value = mock_response

        client = AmigoClient(base_url="http://test.endpoint", timeout=60.0)
        assert client.base_url == "http://test.endpoint"
        assert client.timeout == 60.0

    def test_client_initialization_finds_working_endpoint(self, mock_httpx_client):
        """Test client finds working endpoint from defaults when none provided."""
        # First endpoint fails, second succeeds
        mock_responses = [
            AmigoError("Connection failed"),
            MagicMock()
        ]
        mock_responses[1].json.return_value = {
            "responseHeader": {"status": 0}
        }

        def side_effect(*args, **kwargs):
            if "golr-aux" in args[0]:
                raise Exception("Connection failed")
            return mock_responses[1]

        mock_httpx_client.get.side_effect = side_effect

        client = AmigoClient()  # No base_url provided
        assert client.base_url in [
            "http://golr-aux.geneontology.io/solr",
            "http://golr.berkeleybop.org",
            "https://golr.geneontology.org/solr"
        ]

    def test_search_bioentities(self, amigo_client, mock_httpx_client):
        """Test searching for bioentities."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {
                "docs": [
                    {
                        "bioentity": "UniProtKB:P12345",
                        "bioentity_label": "INS",
                        "bioentity_name": "Insulin",
                        "type": "protein",
                        "taxon": "NCBITaxon:9606",
                        "taxon_label": "Homo sapiens",
                        "source": "UniProtKB"
                    }
                ]
            }
        }
        mock_httpx_client.get.return_value = mock_response

        results = amigo_client.search_bioentities(
            text="insulin",
            taxon="NCBITaxon:9606",
            bioentity_type="protein",
            limit=10
        )

        assert len(results) == 1
        assert isinstance(results[0], BioentityResult)
        assert results[0].id == "UniProtKB:P12345"
        assert results[0].label == "INS"
        assert results[0].name == "Insulin"
        assert results[0].type == "protein"
        assert results[0].taxon == "NCBITaxon:9606"
        assert results[0].taxon_label == "Homo sapiens"

    def test_search_bioentities_with_filters(self, amigo_client, mock_httpx_client):
        """Test bioentity search builds correct query with all filters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_httpx_client.get.return_value = mock_response

        amigo_client.search_bioentities(
            text="kinase",
            taxon="NCBITaxon:10090",
            bioentity_type="gene",
            source="MGI",
            limit=5,
            offset=10
        )

        # Check the URL was built correctly
        call_args = mock_httpx_client.get.call_args
        url = call_args[0][0]
        assert "bioentity_label_searchable" in url
        assert "kinase" in url
        assert "NCBITaxon:10090" in url
        assert "gene" in url
        assert "MGI" in url
        assert "rows=5" in url
        assert "start=10" in url

    def test_get_bioentity(self, amigo_client, mock_httpx_client):
        """Test getting a specific bioentity."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {
                "docs": [
                    {
                        "bioentity": "UniProtKB:P12345",
                        "bioentity_label": "INS",
                        "bioentity_name": "Insulin",
                        "type": "protein",
                        "taxon": "NCBITaxon:9606",
                        "taxon_label": "Homo sapiens",
                        "source": "UniProtKB"
                    }
                ]
            }
        }
        mock_httpx_client.get.return_value = mock_response

        result = amigo_client.get_bioentity("UniProtKB:P12345")

        assert result is not None
        assert isinstance(result, BioentityResult)
        assert result.id == "UniProtKB:P12345"

    def test_get_bioentity_not_found(self, amigo_client, mock_httpx_client):
        """Test getting a bioentity that doesn't exist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_httpx_client.get.return_value = mock_response

        result = amigo_client.get_bioentity("UniProtKB:NOTFOUND")
        assert result is None

    def test_search_annotations(self, amigo_client, mock_httpx_client):
        """Test searching for annotations."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {
                "docs": [
                    {
                        "bioentity": "UniProtKB:P12345",
                        "bioentity_label": "INS",
                        "bioentity_name": "Insulin",
                        "annotation_class": "GO:0005179",
                        "annotation_class_label": "hormone activity",
                        "aspect": "F",
                        "evidence_type": "IDA",
                        "evidence": "ECO:0000314",
                        "evidence_label": "direct assay evidence",
                        "taxon": "NCBITaxon:9606",
                        "taxon_label": "Homo sapiens",
                        "assigned_by": "UniProtKB",
                        "date": "20230101",
                        "reference": "PMID:12345678",
                        "qualifier": "",
                        "annotation_extension": "",
                        "gene_product_form_id": "UniProtKB:P67890"
                    }
                ]
            }
        }
        mock_httpx_client.get.return_value = mock_response

        results = amigo_client.search_annotations(
            bioentity="UniProtKB:P12345",
            go_term="GO:0005179",
            evidence_types=["IDA"],
            taxon="NCBITaxon:9606",
            aspect="F",
            limit=10
        )

        assert len(results) == 1
        assert isinstance(results[0], AnnotationResult)
        assert results[0].bioentity == "UniProtKB:P12345"
        assert results[0].annotation_class == "GO:0005179"
        assert results[0].evidence_type == "IDA"
        assert results[0].reference == "PMID:12345678"
        assert results[0].gene_product_form_id == "UniProtKB:P67890"

    def test_search_annotations_with_closure(self, amigo_client, mock_httpx_client):
        """Test annotation search uses isa_partof_closure for hierarchical search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_httpx_client.get.return_value = mock_response

        amigo_client.search_annotations(
            go_term="GO:0016301"  # This should use isa_partof_closure
        )

        # Check that isa_partof_closure is used
        call_args = mock_httpx_client.get.call_args
        url = call_args[0][0]
        assert "isa_partof_closure" in url
        assert "GO:0016301" in url

    def test_search_annotations_with_terms_closure(self, amigo_client, mock_httpx_client):
        """Test annotation search with multiple terms in closure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_httpx_client.get.return_value = mock_response

        amigo_client.search_annotations(
            go_terms_closure=["GO:0016301", "GO:0004674"]
        )

        # Check that isa_partof_closure_map is used for multiple terms
        call_args = mock_httpx_client.get.call_args
        url = call_args[0][0]
        assert "isa_partof_closure_map" in url
        assert "GO:0016301" in url
        assert "GO:0004674" in url

    def test_get_annotations_for_bioentity(self, amigo_client, mock_httpx_client):
        """Test getting annotations for a specific bioentity."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {
                "docs": [
                    {
                        "bioentity": "UniProtKB:P12345",
                        "bioentity_label": "INS",
                        "bioentity_name": "Insulin",
                        "annotation_class": "GO:0005179",
                        "annotation_class_label": "hormone activity",
                        "aspect": "F",
                        "evidence_type": "IDA",
                        "evidence": "ECO:0000314",
                        "evidence_label": "direct assay evidence",
                        "taxon": "NCBITaxon:9606",
                        "taxon_label": "Homo sapiens",
                        "assigned_by": "UniProtKB",
                        "date": "20230101",
                        "reference": "PMID:12345678",
                        "qualifier": "NOT",
                        "annotation_extension": "occurs_in(CL:0000169)",
                        "gene_product_form_id": ""
                    }
                ]
            }
        }
        mock_httpx_client.get.return_value = mock_response

        results = amigo_client.get_annotations_for_bioentity(
            "UniProtKB:P12345",
            evidence_types=["IDA"],
            aspect="F"
        )

        assert len(results) == 1
        assert results[0].bioentity == "UniProtKB:P12345"
        assert results[0].qualifier == "NOT"
        assert results[0].annotation_extension == "occurs_in(CL:0000169)"

    def test_get_bioentities_for_term_with_closure(self, amigo_client, mock_httpx_client):
        """Test getting bioentities for a term with closure (default)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_httpx_client.get.return_value = mock_response

        amigo_client.get_bioentities_for_term(
            "GO:0016301",
            include_closure=True,  # Default
            taxon="NCBITaxon:9606"
        )

        # Should use isa_partof_closure_map for hierarchical search
        call_args = mock_httpx_client.get.call_args
        url = call_args[0][0]
        assert "isa_partof_closure_map" in url

    def test_get_bioentities_for_term_without_closure(self, amigo_client, mock_httpx_client):
        """Test getting bioentities for exact term match only."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_httpx_client.get.return_value = mock_response

        amigo_client.get_bioentities_for_term(
            "GO:0016301",
            include_closure=False,  # Exact match only
            taxon="NCBITaxon:9606"
        )

        # Should use annotation_class for exact match
        call_args = mock_httpx_client.get.call_args
        url = call_args[0][0]
        assert "annotation_class" in url
        assert "isa_partof_closure" not in url

    def test_query_error_handling(self, amigo_client, mock_httpx_client):
        """Test error handling for failed queries."""
        mock_httpx_client.get.side_effect = Exception("Connection error")

        with pytest.raises(AmigoError) as exc_info:
            amigo_client.search_bioentities(text="test")

        assert "Error querying GOlr" in str(exc_info.value)

    def test_json_decode_error(self, amigo_client, mock_httpx_client):
        """Test handling of invalid JSON responses."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_httpx_client.get.return_value = mock_response

        with pytest.raises(AmigoError) as exc_info:
            amigo_client.search_bioentities(text="test")

        assert "Invalid JSON response" in str(exc_info.value)

    def test_context_manager(self, mock_httpx_client):
        """Test using client as context manager."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0}
        }
        mock_httpx_client.get.return_value = mock_response

        with AmigoClient(base_url="http://test.endpoint") as client:
            assert client.base_url == "http://test.endpoint"

        # Check that close was called
        mock_httpx_client.close.assert_called_once()


class TestDataclasses:
    """Test data classes."""

    def test_bioentity_result(self):
        """Test BioentityResult dataclass."""
        result = BioentityResult(
            id="UniProtKB:P12345",
            label="INS",
            name="Insulin",
            type="protein",
            taxon="NCBITaxon:9606",
            taxon_label="Homo sapiens",
            source="UniProtKB",
            raw={"test": "data"}
        )

        assert result.id == "UniProtKB:P12345"
        assert result.label == "INS"
        assert result.raw == {"test": "data"}

    def test_annotation_result(self):
        """Test AnnotationResult dataclass with GAF metadata."""
        result = AnnotationResult(
            bioentity="UniProtKB:P12345",
            bioentity_label="INS",
            bioentity_name="Insulin",
            annotation_class="GO:0005179",
            annotation_class_label="hormone activity",
            aspect="F",
            evidence_type="IDA",
            evidence="ECO:0000314",
            evidence_label="direct assay evidence",
            taxon="NCBITaxon:9606",
            taxon_label="Homo sapiens",
            assigned_by="UniProtKB",
            date="20230101",
            reference="PMID:12345678",
            qualifier="NOT",
            annotation_extension="occurs_in(CL:0000169)",
            gene_product_form_id="UniProtKB:P67890",
            raw={"test": "data"}
        )

        assert result.bioentity == "UniProtKB:P12345"
        assert result.reference == "PMID:12345678"
        assert result.qualifier == "NOT"
        assert result.annotation_extension == "occurs_in(CL:0000169)"
        assert result.gene_product_form_id == "UniProtKB:P67890"


@pytest.mark.parametrize("text,taxon,expected_query_parts", [
    ("kinase", None, ["bioentity_label_searchable", "kinase"]),
    (None, "NCBITaxon:9606", ["NCBITaxon:9606"]),
    ("insulin", "NCBITaxon:10090", ["insulin", "NCBITaxon:10090"]),
])
def test_bioentity_query_building(text, taxon, expected_query_parts):
    """Test that bioentity queries are built correctly."""
    with patch('noctua.amigo.httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_client.get.return_value = mock_response

        client = AmigoClient(base_url="http://test.endpoint")
        client.search_bioentities(text=text, taxon=taxon)

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        for part in expected_query_parts:
            assert part in url


@pytest.mark.parametrize("evidence_types,expected", [
    (["IDA"], ["evidence_type", "IDA"]),
    (["IDA", "IPI"], ["evidence_type", "IDA", "IPI"]),
    (None, []),
])
def test_evidence_type_filtering(evidence_types, expected):
    """Test evidence type filtering in annotation queries."""
    with patch('noctua.amigo.httpx.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "responseHeader": {"status": 0},
            "response": {"docs": []}
        }
        mock_client.get.return_value = mock_response

        client = AmigoClient(base_url="http://test.endpoint")
        client.search_annotations(evidence_types=evidence_types)

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        for part in expected:
            assert part in url