# Command Line Interface

## Overview

The `noctua-py` CLI provides command-line access to all GO-CAM manipulation features.

## Installation

After installing the package, the CLI is available as:

```bash
noctua --help
```

## Global Options

```bash
# Use development server (default)
noctua barista --dev [command]

# Use production server
noctua barista --live [command]

# Dry run (show request without executing)
noctua barista --dry-run [command]

# Specify token
noctua barista --token YOUR_TOKEN [command]
```

## Model Management

### Create Model

```bash
# Create empty model
noctua barista create-model

# With title
noctua barista create-model --title "My Pathway Model"
```

### List Models

```bash
# List all models
noctua barista list-models

# With filters
noctua barista list-models \
    --limit 10 \
    --state development \
    --title kinase
```

### Get Model

```bash
# Get model details
noctua barista get-model --model 6796b94c00003233
```

### Clear Model

```bash
# Clear model content
noctua barista clear-model --model 6796b94c00003233

# Force clear (bypass protection)
noctua barista clear-model --model 6796b94c00003233 --force
```

## Individual Operations

### Add Individual

```bash
# Basic usage
noctua barista add-individual \
    --model 6796b94c00003233 \
    --class GO:0003924

# With validation (auto-rollback if validation fails)
noctua barista add-individual \
    --model 6796b94c00003233 \
    --class GO:0003924 \
    --validate "GO:0003924" \
    --validate "GO:0003924=GTPase activity"
```

### Delete Individual

```bash
noctua barista delete-individual \
    --model 6796b94c00003233 \
    --individual individual-id
```

### Update Individual Annotation

```bash
# Update or add an annotation
noctua barista update-individual-annotation \
    --model 6796b94c00003233 \
    --individual ind-123 \
    --key "rdfs:label" \
    --value "RAS protein"

# Update enabled_by annotation
noctua barista update-individual-annotation \
    --model 6796b94c00003233 \
    --individual ind-456 \
    --key "enabled_by" \
    --value "UniProtKB:P12345"
```

### Remove Individual Annotation

```bash
# Remove specific annotation
noctua barista remove-individual-annotation \
    --model 6796b94c00003233 \
    --individual ind-123 \
    --key "rdfs:label" \
    --value "Old Label"
```

## Fact/Edge Operations

### Add Fact

```bash
# Basic usage
noctua barista add-fact \
    --model 6796b94c00003233 \
    --subject subject-id \
    --object object-id \
    --predicate RO:0002413

# With validation (auto-rollback if validation fails)
noctua barista add-fact \
    --model 6796b94c00003233 \
    --subject subject-id \
    --object object-id \
    --predicate RO:0002413 \
    --validate "GO:0003924=GTPase activity"
```

### Add Fact with Evidence

```bash
# Add fact with evidence annotations
noctua barista add-fact-evidence \
    --model 6796b94c00003233 \
    --subject subject-id \
    --object object-id \
    --predicate RO:0002413 \
    --eco ECO:0000314 \
    --source PMID:12345

# With validation
noctua barista add-fact-evidence \
    --model 6796b94c00003233 \
    --subject subject-id \
    --object object-id \
    --predicate RO:0002413 \
    --eco ECO:0000314 \
    --source PMID:12345 \
    --validate "GO:0003924"
```

### Delete Edge

```bash
noctua barista delete-edge \
    --model 6796b94c00003233 \
    --subject subject-id \
    --object object-id \
    --predicate RO:0002413
```

## Export Operations

### Export Model

```bash
# Native Minerva JSON
noctua barista export-model \
    --model 6796b94c00003233 \
    --format minerva-json \
    --output model.json

# GO-CAM JSON
noctua barista export-model \
    --model 6796b94c00003233 \
    --format gocam-json \
    --output model-gocam.json

# YAML format
noctua barista export-model \
    --model 6796b94c00003233 \
    --format gocam-yaml \
    --output model.yaml

# Human-readable Markdown
noctua barista export-model \
    --model 6796b94c00003233 \
    --format markdown \
    --output model.md
```

## Common Workflows

### Build a Simple Model

```bash
# 1. Create model
MODEL_ID=$(noctua barista create-model --title "Demo" | grep "Created" | cut -d: -f2)

# 2. Add individuals
noctua barista add-individual --model $MODEL_ID --class GO:0003924
noctua barista add-individual --model $MODEL_ID --class GO:0004674

# 3. Export
noctua barista export-model --model $MODEL_ID --format minerva-json
```

### Work with Existing Model

```bash
# List available models
noctua barista list-models --state development

# Get model details
noctua barista get-model --model 6796b94c00003233

# Export to file
noctua barista export-model \
    --model 6796b94c00003233 \
    --format minerva-json \
    --output my-model.json
```

## Validation

The CLI supports validation for insert and update operations. If validation fails, the operation is automatically rolled back.

### Validation Formats

```bash
# Validate by ID only
--validate "GO:0003924"

# Validate by ID and label
--validate "GO:0003924=GTPase activity"

# Validate by label only (no colon)
--validate "cytoplasm"

# Multiple validations
--validate "GO:0003924" --validate "GO:0004674=protein kinase activity"
```

### Examples with Validation

```bash
# Add individual with validation
noctua barista add-individual \
    --model 6796b94c00003233 \
    --class GO:0003924 \
    --validate "GO:0003924=GTPase activity"

# Add fact with validation
noctua barista add-fact \
    --model 6796b94c00003233 \
    --subject ind-123 \
    --object ind-456 \
    --predicate RO:0002413 \
    --validate "GO:0003924" \
    --validate "GO:0004674"
```

## Tips and Tricks

### Using Environment Variables

```bash
# Set token once (required)
export BARISTA_TOKEN=your-token-here

# All commands use this token
noctua barista list-models
```

### Dry Run Mode

Test commands before executing:

```bash
noctua barista --dry-run create-model --title "Test"

# Dry run with validation shows what would be validated
noctua barista --dry-run add-individual \
    --model 6796b94c00003233 \
    --class GO:0003924 \
    --validate "GO:0003924"
```

### Output Formatting

```bash
# Pretty JSON output
noctua barista get-model --model 6796b94c00003233 | jq '.'

# Save to file
noctua barista get-model --model 6796b94c00003233 > model.json
```

## Error Handling

Common error messages and solutions:

| Error | Solution |
|-------|----------|
| "BARISTA token not provided" | Set `BARISTA_TOKEN` environment variable |
| "Model is in production state" | Use `--force` flag (carefully!) or work with dev model |
| "Failed to connect" | Check network, verify server URL |
| "Invalid GO term" | Verify GO/RO identifier format |

## Amigo/GOlr Query Commands

The `amigo` subcommand provides access to Gene Ontology data via GOlr for searching bioentities and annotations.

### Search Bioentities

```bash
# Search for human insulin-related proteins
noctua amigo search-bioentities \
    --text "insulin" \
    --taxon "NCBITaxon:9606" \
    --type "protein"

# Search for mouse kinases from UniProtKB
noctua amigo search-bioentities \
    --text "kinase" \
    --taxon "NCBITaxon:10090" \
    --source "UniProtKB" \
    --limit 20
```

### Get Bioentity Details

```bash
# Get details for a specific protein
noctua amigo get-bioentity "UniProtKB:P01308"
```

### Search Annotations

```bash
# Find annotations for kinase activity with direct evidence
noctua amigo search-annotations \
    --closure "GO:0016301" \
    --evidence "IDA" \
    --evidence "IPI" \
    --taxon "NCBITaxon:9606"

# Search annotations for a specific bioentity
noctua amigo search-annotations \
    --bioentity "UniProtKB:P01308" \
    --aspect "F"
```

### Bioentity Annotations

```bash
# Get all annotations for a specific bioentity
noctua amigo bioentity-annotations "UniProtKB:P01308"

# Filter by specific GO terms and evidence
noctua amigo bioentity-annotations "UniProtKB:P01308" \
    --closure "GO:0005179" \
    --evidence "IDA" \
    --aspect "F"
```

### Term Bioentities

```bash
# Find all human proteins with kinase activity (including child terms)
noctua amigo term-bioentities "GO:0016301" \
    --taxon "NCBITaxon:9606" \
    --evidence "IDA" \
    --evidence "IPI"

# Find bioentities for exact term only (no closure)
noctua amigo term-bioentities "GO:0006915" \
    --no-closure \
    --taxon "NCBITaxon:10090"
```

### Common Filters

**Taxonomic Filters:**
- Human: `NCBITaxon:9606`
- Mouse: `NCBITaxon:10090`
- Rat: `NCBITaxon:10116`
- Fly: `NCBITaxon:7227`
- Worm: `NCBITaxon:6239`
- Yeast: `NCBITaxon:559292`

**Evidence Types:**
- `IDA`: Direct Assay
- `IPI`: Physical Interaction
- `IMP`: Mutant Phenotype
- `IGI`: Genetic Interaction
- `IEP`: Expression Pattern
- `IBA`: Biological aspect of Ancestor

**GO Aspects:**
- `F`: Molecular Function
- `P`: Biological Process
- `C`: Cellular Component

### Output Format

All commands output tab-separated values that can be processed with standard Unix tools:

```bash
# Count human kinases with direct evidence
noctua amigo term-bioentities "GO:0016301" \
    --taxon "NCBITaxon:9606" \
    --evidence "IDA" | wc -l

# Extract just the bioentity IDs
noctua amigo search-bioentities --text "insulin" \
    --taxon "NCBITaxon:9606" | cut -f1

# Find unique evidence types for a protein
noctua amigo bioentity-annotations "UniProtKB:P01308" | cut -f4 | sort | uniq
```

## Next Steps

- See [Python API](python-api.md) for programmatic usage
- Check [Amigo API Reference](../api/amigo.md) for detailed Python documentation
- Review [Examples](../examples/noctua_demo.ipynb) for complete workflows