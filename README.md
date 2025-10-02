
# noctua-py

Python tools for programmatically manipulating GO-CAM (Gene Ontology Causal Activity Models) via the Noctua/Minerva/Barista API stack, with additional support for querying GO annotations and bioentities via GOlr.

## Features

- **Build biological pathways programmatically** - Create GO-CAM models representing signaling cascades, metabolic pathways, and regulatory networks
- **Safe by default** - Uses dev server by default; production requires explicit `--live` flag
- **Production protection** - Models with state="production" are protected from accidental deletion
- **Multiple export formats** - Export models as OWL, Turtle, JSON-LD, GAF, Markdown, and more
- **Python API and CLI** - Use as a library or command-line tool
- **Variable tracking** - Use simple names instead of IDs for better readability
- **Undo/rollback support** - Revert operations if needed
- **Validation with auto-rollback** - Ensure model consistency with automatic rollback on failure
- **Individual annotations** - Update and manage annotations on model elements
- **GO data queries** - Search bioentities and annotations via GOlr with precise filtering
- **Evidence finding** - Automatically find GO annotations that support GO-CAM model edges

## Quick Start

### Installation

```bash
# Install with pip
pip install noctua-py

# Or use uv (recommended)
uv pip install noctua-py
```

### Basic Usage

```bash
# Set token for dev server (safe for testing)
# Set your Barista token (required)
# For development: Contact the GO team for a dev token
export BARISTA_TOKEN=your-token-here

# Create a new model
noctua-py barista create-model --title "My pathway model"

# Add molecular activities (with validation)
noctua-py barista add-individual --model gomodel:XYZ --class GO:0003924 \
    --validate "GO:0003924=GTPase activity"

# Export model
noctua-py barista export-model --model gomodel:XYZ --format ttl -o model.ttl

# Clear a model (dev/test models only)
noctua-py barista clear-model --model gomodel:XYZ
```

### Using Production Server

```bash
# Get token from Noctua login
export BARISTA_TOKEN=your-production-token

# Use --live flag for production
noctua-py barista create-model --title "Production model" --live
```

## CLI Commands

All commands default to the dev server. Add `--live` to use production.

### Model Management
- `create-model` - Create a new empty GO-CAM model
- `clear-model` - Remove all nodes and edges (protected for production models)
- `export-model` - Export model in various formats (OWL, TTL, JSON-LD, GAF, Markdown)

### Building Models
- `add-individual` - Add a molecular activity/biological process/cellular component
- `add-fact` - Create relationships between individuals
- `add-fact-evidence` - Add evidence supporting relationships

### Examples

```bash
# Build a simple signaling pathway
MODEL_ID=gomodel:68d6f96e00000003

# Add receptor activity
noctua-py barista add-individual --model $MODEL_ID --class GO:0004888 --assign receptor

# Add kinase activity
noctua-py barista add-individual --model $MODEL_ID --class GO:0004674 --assign kinase

# Connect them with causal relationship
noctua-py barista add-fact --model $MODEL_ID \
  --subject receptor --object kinase \
  --predicate RO:0002413  # directly positively regulates

# Add evidence
noctua-py barista add-fact-evidence --model $MODEL_ID \
  --subject receptor --object kinase --predicate RO:0002413 \
  --eco ECO:0000314 --source PMID:12345678
```

## Python API

```python
from noctua.barista import BaristaClient

# Initialize client (uses dev server by default)
client = BaristaClient()

# Create a new model
resp = client.create_model("My model")
model_id = resp.model_id

# Add individuals with variable tracking
client.add_individual(model_id, "GO:0003924", assign_var="ras")
client.add_individual(model_id, "GO:0004674", assign_var="raf")

# Add causal relationship using variables
client.add_fact(model_id, "ras", "raf", "RO:0002413")

# Add with validation and auto-rollback
resp = client.add_individual_validated(
    model_id,
    "GO:0003924",
    expected_type={"id": "GO:0003924", "label": "GTPase activity"}
)
if resp._validation_failed:
    print(f"Validation failed: {resp._validation_reason}")

# Add with undo support
resp = client.add_fact(model_id, "ras", "raf", "RO:0002413", enable_undo=True)
# Can undo if needed
if resp.can_undo():
    resp.undo()

# Update individual annotations
client.update_individual_annotation(
    model_id,
    "ras",  # Can use variable name
    "enabled_by",
    "UniProtKB:P12345"
)

# Export model
export_resp = client.export_model(model_id, format="ttl")
```

### Querying GO Data

```python
from noctua.amigo import AmigoClient

# Initialize Amigo client for GO queries
amigo = AmigoClient()

# Find human kinases
kinases = amigo.search_bioentities(
    text="kinase",
    taxon="NCBITaxon:9606",  # Human
    bioentity_type="protein"
)

# Get annotations for a protein
annotations = amigo.get_annotations_for_bioentity(
    "UniProtKB:P12345",
    evidence_types=["IDA", "IPI"]  # Direct evidence
)

# Find proteins with specific GO function
proteins = amigo.get_bioentities_for_term(
    "GO:0016301",  # protein kinase activity
    include_closure=True,  # Include child terms
    taxon="NCBITaxon:9606"
)
```

### Finding Evidence for GO-CAM Models

```python
# Find supporting GO annotations for model edges
evidence = client.find_evidence_for_edge(
    model_id,
    subject_id="activity1",  # Molecular function
    object_id="protein1",     # Bioentity
    predicate="RO:0002333",   # enabled_by
    evidence_types=["IDA", "IPI"]
)

print(f"Found {len(evidence['annotations'])} supporting annotations")

# Find evidence for all edges in a model
model_evidence = client.find_evidence_for_model(
    model_id,
    evidence_types=["IDA", "IPI", "IMP"],
    limit_per_edge=5
)

print(f"Total annotations: {model_evidence['total_annotations']}")
```

## Safety Features

- **Dev server by default** - All commands use the test server unless `--live` is specified
- **Production protection** - Models with `state="production"` cannot be cleared without `--force`
- **Confirmation prompts** - Destructive operations require confirmation
- **Dry-run mode** - Preview operations with `--dry-run`

## Environment Variables

- `BARISTA_TOKEN` - API token (required for mutations)
- `BARISTA_BASE` - Base URL (default: http://barista-dev.berkeleybop.org)
- `BARISTA_NAMESPACE` - Namespace (default: minerva_public_dev)
- `TEST_MODEL_ID` - Model ID for integration tests

## Documentation Website

[https://geneontology.github.io/noctua-py](https://geneontology.github.io/noctua-py)

## Repository Structure

* [docs/](docs/) - mkdocs-managed documentation
* [project/](project/) - project files (these files are auto-generated, do not edit)
* [src/](src/) - source files (edit these)
  * [noctua](src/noctua)
* [tests/](tests/) - Python tests
  * [data/](tests/data) - Example data

## Developer Tools

There are several pre-defined command-recipes available.
They are written for the command runner [just](https://github.com/casey/just/). To list all pre-defined commands, run `just` or `just --list`.

## Credits

This project uses the template [monarch-project-copier](https://github.com/monarch-initiative/monarch-project-copier)

## MCP server (FastMCP)

We expose Barista tools over MCP using FastMCP.

Environment:
- `BARISTA_TOKEN` (required to perform mutations; read once from environment; no runtime config tool)
- `BARISTA_BASE` (default: http://barista-dev.berkeleybop.org)
- `BARISTA_NAMESPACE` (default: minerva_public_dev)
- `BARISTA_PROVIDED_BY` (default: http://geneontology.org)

Run the server:

```
uv run fastmcp run src/noctua/mcp_server.py:mcp
```

Then connect using a compatible MCP client and call tools like:
- `add_individual`
- `add_fact`
- `add_fact_evidence`
