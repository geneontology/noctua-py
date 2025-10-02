# Amigo Query Examples

This guide demonstrates how to use the Amigo interface to query Gene Ontology data for biological research.

## Basic Bioentity Searches

### Finding Proteins by Name

```python
from noctua.amigo import AmigoClient

# Initialize client
client = AmigoClient()

# Find insulin-related proteins across all organisms
insulin_proteins = client.search_bioentities(
    text="insulin",
    bioentity_type="protein",
    limit=20
)

print("Insulin-related proteins:")
for protein in insulin_proteins:
    print(f"  {protein.id}: {protein.name} ({protein.taxon_label})")
```

### Species-Specific Searches

```python
# Find human kinases
human_kinases = client.search_bioentities(
    text="kinase",
    taxon="NCBITaxon:9606",  # Human
    bioentity_type="protein",
    source="UniProtKB",
    limit=50
)

print(f"Found {len(human_kinases)} human kinases")
for kinase in human_kinases[:10]:  # Show first 10
    print(f"  {kinase.label}: {kinase.name}")
```

### Cross-Species Comparison

```python
# Compare insulin across model organisms
organisms = {
    "Human": "NCBITaxon:9606",
    "Mouse": "NCBITaxon:10090",
    "Rat": "NCBITaxon:10116",
    "Fly": "NCBITaxon:7227"
}

print("Insulin proteins across species:")
for species, taxon_id in organisms.items():
    results = client.search_bioentities(
        text="insulin",
        taxon=taxon_id,
        bioentity_type="protein",
        limit=5
    )

    print(f"\n{species}:")
    for result in results:
        print(f"  {result.id}: {result.label} - {result.name}")
```

## Annotation Queries

### Finding Direct Experimental Evidence

```python
# Find human proteins with kinase activity backed by direct evidence
kinase_annotations = client.search_annotations(
    go_terms_closure=["GO:0016301"],  # protein kinase activity + children
    evidence_types=["IDA", "IPI", "IMP"],  # Direct experimental evidence
    taxon="NCBITaxon:9606",  # Human
    limit=100
)

# Group by protein
from collections import defaultdict
proteins_with_evidence = defaultdict(list)

for ann in kinase_annotations:
    proteins_with_evidence[ann.bioentity].append(ann)

print("Human proteins with direct kinase evidence:")
for protein_id, annotations in list(proteins_with_evidence.items())[:10]:
    protein_name = annotations[0].bioentity_label
    evidence_types = set(ann.evidence_type for ann in annotations)
    go_terms = set(ann.annotation_class_label for ann in annotations)

    print(f"\n{protein_name} ({protein_id}):")
    print(f"  Evidence types: {', '.join(evidence_types)}")
    print(f"  GO terms: {', '.join(list(go_terms)[:3])}...")  # Show first 3
```

### Analyzing Protein Functions

```python
# Get comprehensive functional annotation for human insulin
insulin_id = "UniProtKB:P01308"
insulin_annotations = client.get_annotations_for_bioentity(
    bioentity_id=insulin_id,
    evidence_types=["IDA", "IPI", "IMP", "TAS"],  # High-quality evidence
    limit=200
)

# Organize by GO aspect
by_aspect = defaultdict(list)
for ann in insulin_annotations:
    by_aspect[ann.aspect].append(ann)

print(f"Functional annotations for human insulin ({insulin_id}):")

aspect_names = {"F": "Molecular Function", "P": "Biological Process", "C": "Cellular Component"}
for aspect, name in aspect_names.items():
    if aspect in by_aspect:
        print(f"\n{name}:")
        for ann in by_aspect[aspect][:5]:  # Show top 5
            print(f"  {ann.annotation_class_label} ({ann.evidence_type})")
```

### Disease-Related Pathway Analysis

```python
# Find all human proteins involved in apoptosis with good evidence
apoptosis_proteins = client.get_bioentities_for_term(
    go_term="GO:0006915",  # apoptotic process
    include_closure=True,   # Include child terms
    taxon="NCBITaxon:9606", # Human
    evidence_types=["IDA", "IPI", "IMP", "IGI"],  # Experimental evidence
    limit=200
)

# Analyze evidence quality
evidence_counts = defaultdict(int)
for ann in apoptosis_proteins:
    evidence_counts[ann.evidence_type] += 1

print("Human apoptosis proteins by evidence type:")
for evidence, count in sorted(evidence_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {evidence}: {count} proteins")

# Show some examples
print(f"\nExample apoptosis proteins:")
unique_proteins = {}
for ann in apoptosis_proteins:
    if ann.bioentity not in unique_proteins:
        unique_proteins[ann.bioentity] = ann

for protein_id, ann in list(unique_proteins.items())[:10]:
    print(f"  {ann.bioentity_label}: {ann.bioentity_name}")
```

## Advanced Filtering

### Evidence Quality Analysis

```python
# Compare evidence quality for a specific GO term across organisms
go_term = "GO:0016301"  # protein kinase activity
organisms = ["NCBITaxon:9606", "NCBITaxon:10090", "NCBITaxon:7227"]  # Human, Mouse, Fly

print("Evidence quality comparison for protein kinase activity:")
for taxon in organisms:
    # Get annotations for this organism
    annotations = client.get_bioentities_for_term(
        go_term=go_term,
        include_closure=True,
        taxon=taxon,
        limit=500
    )

    # Count evidence types
    evidence_counts = defaultdict(int)
    for ann in annotations:
        evidence_counts[ann.evidence_type] += 1

    # Get organism name from first result
    organism_name = annotations[0].taxon_label if annotations else "Unknown"

    print(f"\n{organism_name} ({taxon}):")
    print(f"  Total annotations: {len(annotations)}")

    # Show top evidence types
    for evidence, count in sorted(evidence_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {evidence}: {count}")
```

### Temporal Analysis

```python
# Analyze annotation dates for a protein
protein_id = "UniProtKB:P01308"  # Human insulin
annotations = client.get_annotations_for_bioentity(
    bioentity_id=protein_id,
    limit=500
)

# Group by year
from collections import Counter
years = []
for ann in annotations:
    if ann.date and len(ann.date) >= 4:
        try:
            year = ann.date[:4]
            years.append(year)
        except ValueError:
            continue

year_counts = Counter(years)

print(f"Annotation timeline for {protein_id}:")
for year in sorted(year_counts.keys())[-10:]:  # Last 10 years
    print(f"  {year}: {year_counts[year]} annotations")
```

## Functional Enrichment Analysis

### Finding Co-annotated Proteins

```python
# Find proteins that share multiple functions with insulin
insulin_id = "UniProtKB:P01308"

# Get insulin's GO terms
insulin_annotations = client.get_annotations_for_bioentity(
    bioentity_id=insulin_id,
    aspect="F",  # Molecular functions only
    evidence_types=["IDA", "IPI", "IMP"],  # Direct evidence
    limit=100
)

insulin_terms = set(ann.annotation_class for ann in insulin_annotations)
print(f"Insulin has {len(insulin_terms)} molecular functions with direct evidence")

# Find other proteins with similar functions
similar_proteins = defaultdict(set)

for term in list(insulin_terms)[:5]:  # Check top 5 terms
    term_annotations = client.get_bioentities_for_term(
        go_term=term,
        include_closure=False,  # Exact term only
        taxon="NCBITaxon:9606",  # Human only
        evidence_types=["IDA", "IPI", "IMP"],
        limit=50
    )

    for ann in term_annotations:
        if ann.bioentity != insulin_id:  # Exclude insulin itself
            similar_proteins[ann.bioentity].add(term)

# Find proteins with multiple shared functions
print("\nProteins sharing multiple functions with insulin:")
for protein_id, shared_terms in similar_proteins.items():
    if len(shared_terms) >= 2:  # At least 2 shared functions
        # Get protein name
        protein_info = client.get_bioentity(protein_id)
        if protein_info:
            print(f"  {protein_info.label}: {len(shared_terms)} shared functions")
```

## CLI Integration Examples

### Scripted Analysis

```bash
#!/bin/bash
# Script to analyze kinase families across species

# Find human kinases
echo "Human kinases:"
noctua amigo term-bioentities "GO:0016301" \
    --taxon "NCBITaxon:9606" \
    --evidence "IDA" \
    --limit 20 | head -10

echo -e "\nMouse kinases:"
noctua amigo term-bioentities "GO:0016301" \
    --taxon "NCBITaxon:10090" \
    --evidence "IDA" \
    --limit 20 | head -10

# Count total by species
echo -e "\nKinase counts by species:"
for taxon in "NCBITaxon:9606" "NCBITaxon:10090" "NCBITaxon:7227"; do
    count=$(noctua amigo term-bioentities "GO:0016301" \
        --taxon "$taxon" \
        --evidence "IDA" \
        --limit 1000 | wc -l)
    echo "  $taxon: $count"
done
```

### Data Pipeline Integration

```bash
# Export human kinase data for further analysis
noctua amigo term-bioentities "GO:0016301" \
    --taxon "NCBITaxon:9606" \
    --evidence "IDA" \
    --evidence "IPI" \
    --limit 1000 > human_kinases.tsv

# Extract unique protein IDs
cut -f1 human_kinases.tsv | sort | uniq > kinase_ids.txt

# Get detailed annotations for each kinase
while read protein_id; do
    echo "Annotations for $protein_id:"
    noctua amigo bioentity-annotations "$protein_id" \
        --aspect "F" \
        --evidence "IDA" \
        --limit 50
    echo ""
done < kinase_ids.txt > kinase_functions.txt
```

## Best Practices

### 1. Evidence Quality

Always filter by evidence types appropriate for your analysis:

```python
# For high-confidence results
high_confidence = ["IDA", "IPI", "IMP", "IGI"]

# For computational predictions (use with caution)
computational = ["IBA", "ISS", "ISO"]

# For literature-based (variable quality)
literature = ["TAS", "NAS"]
```

### 2. Handling Large Result Sets

```python
# Use pagination for large queries
def get_all_results(client, search_func, **kwargs):
    """Get all results using pagination."""
    all_results = []
    offset = 0
    limit = 100

    while True:
        results = search_func(**kwargs, limit=limit, offset=offset)
        if not results:
            break
        all_results.extend(results)
        offset += limit

        # Prevent infinite loops
        if len(results) < limit:
            break

    return all_results

# Example usage
all_kinases = get_all_results(
    client,
    client.search_bioentities,
    text="kinase",
    taxon="NCBITaxon:9606"
)
```

### 3. Error Handling

```python
from noctua.amigo import AmigoError

def safe_query(client, query_func, **kwargs):
    """Safely execute a query with error handling."""
    try:
        return query_func(**kwargs)
    except AmigoError as e:
        print(f"Query failed: {e}")
        return []

# Example usage
results = safe_query(
    client,
    client.search_bioentities,
    text="insulin",
    taxon="NCBITaxon:9606"
)
```

### 4. Resource Management

```python
# Always use context managers or explicit cleanup
with AmigoClient() as client:
    results = client.search_bioentities(text="kinase")
    # Process results
# Client automatically closed

# Or explicit cleanup
client = AmigoClient()
try:
    results = client.search_bioentities(text="kinase")
    # Process results
finally:
    client.close()
```

## Next Steps

- Explore the [Amigo API Reference](../api/amigo.md) for complete method documentation
- Check the [CLI Guide](../guide/cli.md) for command-line usage
- See [Advanced Features](advanced-features.md) for combining Amigo with Barista for comprehensive GO-CAM analysis