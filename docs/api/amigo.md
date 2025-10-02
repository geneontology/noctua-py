# AmigoClient API Reference

## Overview

The AmigoClient provides access to Gene Ontology data via GOlr (Gene Ontology Solr). It enables two main types of queries:

1. **Bioentity queries**: Search for genes/proteins with text search and taxonomic filtering
2. **Annotation queries**: Find GO annotations with precise filtering by bioentity, GO terms, and evidence

## Class: AmigoClient

Main client for querying Gene Ontology data via GOlr.

### Constructor

```python
AmigoClient(
    base_url: Optional[str] = None,
    timeout: float = 30.0
)
```

**Parameters:**
- `base_url`: GOlr endpoint URL. If None, tries default endpoints automatically
- `timeout`: HTTP request timeout in seconds

**Default Endpoints (tried in order):**
- `http://golr-aux.geneontology.io/solr`
- `http://golr.berkeleybop.org`
- `https://golr.geneontology.org/solr`

### Bioentity Query Methods

#### search_bioentities

```python
search_bioentities(
    text: Optional[str] = None,
    taxon: Optional[str] = None,
    bioentity_type: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[BioentityResult]
```

Search for bioentities (genes/proteins) with optional filtering.

**Parameters:**
- `text`: Text search across names and labels
- `taxon`: Organism filter (e.g., "NCBITaxon:9606" for human)
- `bioentity_type`: Type filter (e.g., "protein", "gene")
- `source`: Source filter (e.g., "UniProtKB", "MGI")
- `limit`: Maximum number of results
- `offset`: Starting offset for pagination

**Example:**
```python
# Find human kinases
results = client.search_bioentities(
    text="kinase",
    taxon="NCBITaxon:9606",
    bioentity_type="protein",
    limit=20
)

for result in results:
    print(f"{result.id}: {result.name} ({result.taxon_label})")
```

#### get_bioentity

```python
get_bioentity(bioentity_id: str) -> Optional[BioentityResult]
```

Get details for a specific bioentity.

**Parameters:**
- `bioentity_id`: The bioentity ID (e.g., "UniProtKB:P12345")

**Returns:** BioentityResult or None if not found

### Annotation Query Methods

#### search_annotations

```python
search_annotations(
    bioentity: Optional[str] = None,
    go_term: Optional[str] = None,
    go_terms_closure: Optional[List[str]] = None,
    evidence_types: Optional[List[str]] = None,
    taxon: Optional[str] = None,
    aspect: Optional[str] = None,
    assigned_by: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[AnnotationResult]
```

Search for GO annotations with filtering.

**Parameters:**
- `bioentity`: Specific bioentity ID to filter by
- `go_term`: Specific GO term ID to filter by (uses hierarchical search including child terms)
- `go_terms_closure`: List of GO terms including closure (child terms)
- `evidence_types`: List of evidence codes to filter by (e.g., ["IDA", "IPI"])
- `taxon`: Organism filter (e.g., "NCBITaxon:9606")
- `aspect`: GO aspect filter ("C", "F", or "P")
- `assigned_by`: Annotation source filter (e.g., "GOC", "UniProtKB")
- `limit`: Maximum number of results
- `offset`: Starting offset for pagination

**Note:** When using `go_term`, the search automatically includes annotations to child terms in the GO hierarchy using `isa_partof_closure`. For exact term matches only, use `get_bioentities_for_term` with `include_closure=False`.

**Example:**
```python
# Find annotations for kinase activity with direct evidence
annotations = client.search_annotations(
    go_terms_closure=["GO:0016301"],  # kinase activity + children
    evidence_types=["IDA", "IPI"],    # Direct evidence
    taxon="NCBITaxon:9606",          # Human
    limit=50
)
```

#### get_annotations_for_bioentity

```python
get_annotations_for_bioentity(
    bioentity_id: str,
    go_terms_closure: Optional[List[str]] = None,
    evidence_types: Optional[List[str]] = None,
    aspect: Optional[str] = None,
    limit: int = 100
) -> List[AnnotationResult]
```

Get all annotations for a specific bioentity.

**Parameters:**
- `bioentity_id`: The bioentity ID
- `go_terms_closure`: Filter to specific GO terms (including closure)
- `evidence_types`: Filter by evidence types
- `aspect`: Filter by GO aspect
- `limit`: Maximum number of results

#### get_bioentities_for_term

```python
get_bioentities_for_term(
    go_term: str,
    include_closure: bool = True,
    taxon: Optional[str] = None,
    evidence_types: Optional[List[str]] = None,
    limit: int = 100
) -> List[AnnotationResult]
```

Get all bioentities annotated to a GO term.

**Parameters:**
- `go_term`: The GO term ID
- `include_closure`: If True, include annotations to child terms
- `taxon`: Filter by organism
- `evidence_types`: Filter by evidence types
- `limit`: Maximum number of results

## Data Classes

### BioentityResult

Result for a bioentity (gene/protein) query.

**Properties:**
- `id`: Bioentity ID (e.g., "UniProtKB:P12345")
- `label`: Short name/symbol (e.g., "INSULIN")
- `name`: Full descriptive name
- `type`: Entity type (e.g., "protein", "gene")
- `taxon`: Organism ID (e.g., "NCBITaxon:9606")
- `taxon_label`: Organism name (e.g., "Homo sapiens")
- `source`: Source database (e.g., "UniProtKB")
- `raw`: Full Solr document

### AnnotationResult

Result for a GO annotation query.

**Properties:**
- `bioentity`: Bioentity ID
- `bioentity_label`: Bioentity short name
- `bioentity_name`: Bioentity full name
- `annotation_class`: GO term ID
- `annotation_class_label`: GO term name
- `aspect`: GO aspect ("C", "F", or "P")
- `evidence_type`: Evidence code (e.g., "IDA", "IBA")
- `evidence`: ECO evidence ID
- `evidence_label`: Evidence description
- `taxon`: Organism ID
- `taxon_label`: Organism name
- `assigned_by`: Annotation source
- `date`: Annotation date
- `reference`: Literature reference (e.g., "PMID:12345")
- `qualifier`: Annotation qualifier (e.g., "NOT", "contributes_to")
- `annotation_extension`: Annotation extensions for additional context
- `gene_product_form_id`: Specific gene product form if applicable
- `raw`: Full Solr document

## Common Filters and Parameters

### Taxonomic Filters

Common organism identifiers:
- Human: `NCBITaxon:9606`
- Mouse: `NCBITaxon:10090`
- Rat: `NCBITaxon:10116`
- Fly: `NCBITaxon:7227`
- Worm: `NCBITaxon:6239`
- Yeast: `NCBITaxon:559292`
- Arabidopsis: `NCBITaxon:3702`

### Evidence Types

Common evidence codes:
- `IDA`: Inferred from Direct Assay
- `IPI`: Inferred from Physical Interaction
- `IMP`: Inferred from Mutant Phenotype
- `IGI`: Inferred from Genetic Interaction
- `IEP`: Inferred from Expression Pattern
- `IBA`: Inferred from Biological aspect of Ancestor
- `ISS`: Inferred from Sequence or structural Similarity
- `TAS`: Traceable Author Statement

### GO Aspects

- `F`: Molecular Function
- `P`: Biological Process
- `C`: Cellular Component

## Usage Examples

### Basic Bioentity Search

```python
from noctua.amigo import AmigoClient

# Initialize client
client = AmigoClient()

# Search for human insulin-related proteins
results = client.search_bioentities(
    text="insulin",
    taxon="NCBITaxon:9606",
    bioentity_type="protein"
)

for result in results:
    print(f"{result.id}: {result.name}")
```

### Complex Annotation Query

```python
# Find all human proteins with kinase activity (including child terms)
# that have direct experimental evidence
annotations = client.search_annotations(
    go_terms_closure=["GO:0016301"],  # protein kinase activity + children
    evidence_types=["IDA", "IPI", "IMP"],  # Direct evidence only
    taxon="NCBITaxon:9606",  # Human
    limit=100
)

# Group by bioentity
from collections import defaultdict
by_protein = defaultdict(list)
for ann in annotations:
    by_protein[ann.bioentity].append(ann)

for protein_id, protein_annotations in by_protein.items():
    print(f"\n{protein_id}:")
    for ann in protein_annotations:
        print(f"  {ann.annotation_class}: {ann.annotation_class_label}")
```

### Finding Evidence for Specific Interactions

```python
# Get all annotations for a specific protein
protein_id = "UniProtKB:P01308"  # Human insulin
annotations = client.get_annotations_for_bioentity(
    bioentity_id=protein_id,
    evidence_types=["IDA", "IPI"],  # Direct evidence only
    aspect="F"  # Molecular functions only
)

print(f"Direct experimental evidence for {protein_id}:")
for ann in annotations:
    print(f"  {ann.annotation_class_label} ({ann.evidence_type})")
```

### Cross-Species Comparison

```python
# Compare kinase activity across species
organisms = {
    "Human": "NCBITaxon:9606",
    "Mouse": "NCBITaxon:10090",
    "Fly": "NCBITaxon:7227"
}

for org_name, taxon_id in organisms.items():
    annotations = client.get_bioentities_for_term(
        go_term="GO:0016301",  # protein kinase activity
        include_closure=True,
        taxon=taxon_id,
        evidence_types=["IDA", "IPI"],  # Direct evidence
        limit=10
    )

    print(f"\n{org_name} kinases with direct evidence:")
    for ann in annotations:
        print(f"  {ann.bioentity_label}: {ann.bioentity_name}")
```

## Error Handling

All methods may raise `AmigoError` for connection or query failures:

```python
from noctua.amigo import AmigoError

try:
    results = client.search_bioentities(text="kinase")
except AmigoError as e:
    print(f"Query failed: {e}")
```

## Context Manager Usage

The client supports context manager syntax for automatic cleanup:

```python
with AmigoClient() as client:
    results = client.search_bioentities(text="insulin")
    # Client automatically closed
```