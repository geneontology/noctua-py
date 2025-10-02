# GO-CAM AI Examples

This directory contains example notebooks and scripts demonstrating the noctua library functionality.

## Notebooks

### noctua_demo.ipynb
A comprehensive Jupyter notebook demonstrating:
- Setting up the BaristaClient
- Creating and managing GO-CAM models
- Adding individuals (molecular functions, biological processes)
- Creating causal relationships between activities
- Adding evidence annotations
- Exporting models in different formats (Minerva JSON, GO-CAM JSON/YAML)
- Using the CLI interface

## Running the Notebooks

1. Install Jupyter dependencies:
```bash
uv add --dev jupyter ipykernel
# or
pip install jupyter ipykernel
```

2. Start Jupyter:
```bash
jupyter notebook docs/examples/
```

3. Set your Barista token:
- For development: Contact the GO team for a dev token
- For production: Obtain a token from your Noctua login

## Environment Variables

- `BARISTA_TOKEN`: Your authentication token (required)
- `BARISTA_BASE`: Base URL (defaults to dev server)
- `BARISTA_NAMESPACE`: Namespace (defaults to minerva_public_dev)

## Key Concepts

- **Individuals**: Nodes in the model representing molecular functions, biological processes, etc.
- **Facts**: Edges connecting individuals with causal relationships
- **Evidence**: Annotations supporting facts with references and evidence codes
- **Models**: Complete GO-CAM models containing individuals, facts, and metadata

## CLI Examples

The notebook also demonstrates CLI usage. Here are some quick examples:

```bash
# List models
noctua barista list-models --limit 10

# Create a new model
noctua barista create-model --title "My Model"

# Add an individual
noctua barista add-individual --model gomodel:XXX --class GO:0003924

# Export model
noctua barista export-model --model gomodel:XXX --format gocam-json
```

## Further Documentation

- [GO-CAM Overview](http://geneontology.org/docs/gocam-overview/)
- [noctua API Documentation](https://geneontology.github.io/noctua-py)
- [Noctua Editor](http://noctua.geneontology.org/)