"""Amigo client for querying Gene Ontology data via GOlr (Solr)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx


# Default GOlr endpoints (in order of preference)
DEFAULT_GOLR_ENDPOINTS = [
    "http://golr-aux.geneontology.io/solr",
    "http://golr.berkeleybop.org",
    "https://golr.geneontology.org/solr"
]


@dataclass
class BioentityResult:
    """Result for a bioentity (gene/protein) query."""
    id: str
    label: str
    name: str
    type: str
    taxon: str
    taxon_label: str
    source: str
    raw: Dict[str, Any]  # Full Solr document


@dataclass
class AnnotationResult:
    """Result for a GO annotation query."""
    bioentity: str
    bioentity_label: str
    bioentity_name: str
    annotation_class: str
    annotation_class_label: str
    aspect: str
    evidence_type: str
    evidence: str
    evidence_label: str
    taxon: str
    taxon_label: str
    assigned_by: str
    date: str
    # Additional GAF metadata
    reference: str
    qualifier: str
    annotation_extension: str
    gene_product_form_id: str
    raw: Dict[str, Any]  # Full Solr document


class AmigoError(Exception):
    """Exception raised for Amigo-related errors."""
    pass


class AmigoClient:
    """Client for querying Gene Ontology data via GOlr."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        """Initialize Amigo client.

        Args:
            base_url: GOlr endpoint URL. If None, tries default endpoints.
            timeout: HTTP request timeout in seconds.
        """
        self.base_url = base_url
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

        # Test connection if base_url provided, otherwise find working endpoint
        if self.base_url:
            self._test_connection()
        else:
            self._find_working_endpoint()

    def _find_working_endpoint(self):
        """Find the first working GOlr endpoint."""
        for endpoint in DEFAULT_GOLR_ENDPOINTS:
            try:
                self.base_url = endpoint
                self._test_connection()
                return  # Success
            except AmigoError:
                continue

        raise AmigoError("No working GOlr endpoints found")

    def _test_connection(self):
        """Test connection to the GOlr endpoint."""
        try:
            # Simple test query
            response = self._query({"q": "*:*", "rows": "0"})
            if response.get("responseHeader", {}).get("status") != 0:
                raise AmigoError(f"GOlr endpoint returned error: {response}")
        except Exception as e:
            raise AmigoError(f"Cannot connect to GOlr at {self.base_url}: {e}")

    def _query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Solr query.

        Args:
            params: Solr query parameters

        Returns:
            Parsed JSON response

        Raises:
            AmigoError: If query fails
        """
        # Set default parameters
        default_params = {
            "wt": "json",
            "indent": "false"
        }
        default_params.update(params)

        # Build URL
        url = f"{self.base_url}/select"
        query_string = urlencode(default_params, safe=':')
        full_url = f"{url}?{query_string}"

        try:
            response = self._client.get(full_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise AmigoError(f"HTTP error querying GOlr: {e}")
        except json.JSONDecodeError as e:
            raise AmigoError(f"Invalid JSON response from GOlr: {e}")
        except Exception as e:
            raise AmigoError(f"Error querying GOlr: {e}")

    def search_bioentities(
        self,
        text: Optional[str] = None,
        taxon: Optional[str] = None,
        bioentity_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[BioentityResult]:
        """Search for bioentities (genes/proteins) with optional filtering.

        Args:
            text: Text search across names and labels
            taxon: Organism filter (e.g., "NCBITaxon:9606" for human)
            bioentity_type: Type filter (e.g., "protein", "gene")
            source: Source filter (e.g., "UniProtKB", "MGI")
            limit: Maximum number of results
            offset: Starting offset for pagination

        Returns:
            List of bioentity results
        """
        # Build query
        query_parts = ["document_category:bioentity"]

        if text:
            # Search in bioentity_label_searchable and bioentity_name_searchable
            text_query = f"(bioentity_label_searchable:\"{text}\" OR bioentity_name_searchable:\"{text}\")"
            query_parts.append(text_query)

        if taxon:
            query_parts.append(f"taxon:\"{taxon}\"")

        if bioentity_type:
            query_parts.append(f"type:\"{bioentity_type}\"")

        if source:
            query_parts.append(f"source:\"{source}\"")

        query = " AND ".join(query_parts)

        params = {
            "q": query,
            "rows": str(limit),
            "start": str(offset),
            "fl": "bioentity,bioentity_label,bioentity_name,type,taxon,taxon_label,source"
        }

        response = self._query(params)
        docs = response.get("response", {}).get("docs", [])

        return [
            BioentityResult(
                id=doc.get("bioentity", ""),
                label=doc.get("bioentity_label", ""),
                name=doc.get("bioentity_name", ""),
                type=doc.get("type", ""),
                taxon=doc.get("taxon", ""),
                taxon_label=doc.get("taxon_label", ""),
                source=doc.get("source", ""),
                raw=doc
            )
            for doc in docs
        ]

    def get_bioentity(self, bioentity_id: str) -> Optional[BioentityResult]:
        """Get details for a specific bioentity.

        Args:
            bioentity_id: The bioentity ID (e.g., "UniProtKB:P12345")

        Returns:
            Bioentity result or None if not found
        """
        # Use exact ID match
        params = {
            "q": f"document_category:bioentity AND bioentity:\"{bioentity_id}\"",
            "rows": "1",
            "fl": "bioentity,bioentity_label,bioentity_name,type,taxon,taxon_label,source"
        }

        response = self._query(params)
        docs = response.get("response", {}).get("docs", [])

        if not docs:
            return None

        doc = docs[0]
        return BioentityResult(
            id=doc.get("bioentity", ""),
            label=doc.get("bioentity_label", ""),
            name=doc.get("bioentity_name", ""),
            type=doc.get("type", ""),
            taxon=doc.get("taxon", ""),
            taxon_label=doc.get("taxon_label", ""),
            source=doc.get("source", ""),
            raw=doc
        )

    def search_annotations(
        self,
        bioentity: Optional[str] = None,
        go_term: Optional[str] = None,
        go_terms_closure: Optional[List[str]] = None,
        evidence_types: Optional[List[str]] = None,
        taxon: Optional[str] = None,
        aspect: Optional[str] = None,
        assigned_by: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[AnnotationResult]:
        """Search for GO annotations with filtering.

        Args:
            bioentity: Specific bioentity ID to filter by
            go_term: Specific GO term ID to filter by
            go_terms_closure: List of GO terms including closure (child terms)
            evidence_types: List of evidence codes to filter by (e.g., ["IDA", "IPI"])
            taxon: Organism filter (e.g., "NCBITaxon:9606")
            aspect: GO aspect filter ("C", "F", or "P")
            assigned_by: Annotation source filter (e.g., "GOC", "UniProtKB")
            limit: Maximum number of results
            offset: Starting offset for pagination

        Returns:
            List of annotation results
        """
        query_parts = ["document_category:annotation"]

        if bioentity:
            query_parts.append(f"bioentity:\"{bioentity}\"")

        if go_term:
            # Use isa_partof_closure for hierarchical term queries
            query_parts.append(f"isa_partof_closure:\"{go_term}\"")

        if go_terms_closure:
            # Use isa_partof_closure_map for hierarchical queries
            closure_query = " OR ".join([f"isa_partof_closure_map:\"{term}\"" for term in go_terms_closure])
            query_parts.append(f"({closure_query})")

        if evidence_types:
            evidence_query = " OR ".join([f"evidence_type:\"{ecode}\"" for ecode in evidence_types])
            query_parts.append(f"({evidence_query})")

        if taxon:
            query_parts.append(f"taxon:\"{taxon}\"")

        if aspect:
            query_parts.append(f"aspect:\"{aspect}\"")

        if assigned_by:
            query_parts.append(f"assigned_by:\"{assigned_by}\"")

        query = " AND ".join(query_parts)

        params = {
            "q": query,
            "rows": str(limit),
            "start": str(offset),
            "fl": ("bioentity,bioentity_label,bioentity_name,annotation_class,"
                   "annotation_class_label,aspect,evidence_type,evidence,evidence_label,"
                   "taxon,taxon_label,assigned_by,date,reference,qualifier,"
                   "annotation_extension,gene_product_form_id")
        }

        response = self._query(params)
        docs = response.get("response", {}).get("docs", [])

        return [
            AnnotationResult(
                bioentity=doc.get("bioentity", ""),
                bioentity_label=doc.get("bioentity_label", ""),
                bioentity_name=doc.get("bioentity_name", ""),
                annotation_class=doc.get("annotation_class", ""),
                annotation_class_label=doc.get("annotation_class_label", ""),
                aspect=doc.get("aspect", ""),
                evidence_type=doc.get("evidence_type", ""),
                evidence=doc.get("evidence", ""),
                evidence_label=doc.get("evidence_label", ""),
                taxon=doc.get("taxon", ""),
                taxon_label=doc.get("taxon_label", ""),
                assigned_by=doc.get("assigned_by", ""),
                date=doc.get("date", ""),
                reference=doc.get("reference", ""),
                qualifier=doc.get("qualifier", ""),
                annotation_extension=doc.get("annotation_extension", ""),
                gene_product_form_id=doc.get("gene_product_form_id", ""),
                raw=doc
            )
            for doc in docs
        ]

    def get_annotations_for_bioentity(
        self,
        bioentity_id: str,
        go_terms_closure: Optional[List[str]] = None,
        evidence_types: Optional[List[str]] = None,
        aspect: Optional[str] = None,
        limit: int = 100
    ) -> List[AnnotationResult]:
        """Get all annotations for a specific bioentity.

        Args:
            bioentity_id: The bioentity ID
            go_terms_closure: Filter to specific GO terms (including closure)
            evidence_types: Filter by evidence types
            aspect: Filter by GO aspect
            limit: Maximum number of results

        Returns:
            List of annotation results
        """
        return self.search_annotations(
            bioentity=bioentity_id,
            go_terms_closure=go_terms_closure,
            evidence_types=evidence_types,
            aspect=aspect,
            limit=limit
        )

    def get_bioentities_for_term(
        self,
        go_term: str,
        include_closure: bool = True,
        taxon: Optional[str] = None,
        evidence_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[AnnotationResult]:
        """Get all bioentities annotated to a GO term.

        Args:
            go_term: The GO term ID
            include_closure: If True, include annotations to child terms
            taxon: Filter by organism
            evidence_types: Filter by evidence types
            limit: Maximum number of results

        Returns:
            List of annotation results
        """
        if include_closure:
            # Use isa_partof_closure for hierarchical search (includes child terms)
            return self.search_annotations(
                go_terms_closure=[go_term],
                taxon=taxon,
                evidence_types=evidence_types,
                limit=limit
            )
        else:
            # Use direct annotation_class match for exact term only
            query_parts = ["document_category:annotation", f"annotation_class:\"{go_term}\""]

            if taxon:
                query_parts.append(f"taxon:\"{taxon}\"")

            if evidence_types:
                evidence_query = " OR ".join([f"evidence_type:\"{ecode}\"" for ecode in evidence_types])
                query_parts.append(f"({evidence_query})")

            query = " AND ".join(query_parts)

            params = {
                "q": query,
                "rows": str(limit),
                "fl": ("bioentity,bioentity_label,bioentity_name,annotation_class,"
                       "annotation_class_label,aspect,evidence_type,evidence,evidence_label,"
                       "taxon,taxon_label,assigned_by,date,reference,qualifier,"
                       "annotation_extension,gene_product_form_id")
            }

            response = self._query(params)
            docs = response.get("response", {}).get("docs", [])

            return [
                AnnotationResult(
                    bioentity=doc.get("bioentity", ""),
                    bioentity_label=doc.get("bioentity_label", ""),
                    bioentity_name=doc.get("bioentity_name", ""),
                    annotation_class=doc.get("annotation_class", ""),
                    annotation_class_label=doc.get("annotation_class_label", ""),
                    aspect=doc.get("aspect", ""),
                    evidence_type=doc.get("evidence_type", ""),
                    evidence=doc.get("evidence", ""),
                    evidence_label=doc.get("evidence_label", ""),
                    taxon=doc.get("taxon", ""),
                    taxon_label=doc.get("taxon_label", ""),
                    assigned_by=doc.get("assigned_by", ""),
                    date=doc.get("date", ""),
                    reference=doc.get("reference", ""),
                    qualifier=doc.get("qualifier", ""),
                    annotation_extension=doc.get("annotation_extension", ""),
                    gene_product_form_id=doc.get("gene_product_form_id", ""),
                    raw=doc
                )
                for doc in docs
            ]

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()