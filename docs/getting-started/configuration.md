# Configuration

## Environment Variables

### Required: BARISTA_TOKEN

The Barista API requires authentication via a token:

```bash
# Set your Barista token (required)
export BARISTA_TOKEN=your-token-here

# For development: Contact the GO team for a dev token
# For production: Get token from Noctua login
```

!!! warning "Production Access"
    Production tokens must be obtained by logging into Noctua. Never commit tokens to version control.

### Optional Configuration

```bash
# Server endpoints (defaults shown)
export BARISTA_BASE=http://barista-dev.berkeleybop.org
export BARISTA_NAMESPACE=minerva_public_dev
export BARISTA_PROVIDED_BY=http://geneontology.org

# Production server settings
export BARISTA_LIVE_BASE=http://barista.berkeleybop.org
export BARISTA_LIVE_NAMESPACE=minerva_public
```

## Python Configuration

### Basic Setup

```python
from noctua import BaristaClient

# Use defaults (dev server)
client = BaristaClient()

# Explicit configuration
client = BaristaClient(
    token="your-token",
    base_url="http://barista-dev.berkeleybop.org",
    namespace="minerva_public_dev",
    timeout=30.0
)
```

### Production Setup

```python
# Use production server
client = BaristaClient(
    base_url="http://barista.berkeleybop.org",
    namespace="minerva_public"
)
```

!!! danger "Production Warning"
    Production models with `state="production"` are protected from deletion. Always test on dev server first.

## CLI Configuration

### Default Behavior

The CLI uses the dev server by default for safety:

```bash
# Uses dev server
noctua barista list-models

# Explicit dev server
noctua barista list-models --dev
```

### Production Usage

Use the `--live` flag for production:

```bash
# Use production server
noctua barista list-models --live

# With explicit token
noctua barista list-models --live --token your-token
```

### Dry Run Mode

Test commands without executing:

```bash
noctua barista create-model --title "Test" --dry-run
```

## Screenshot Configuration

### Browser Setup

```python
from noctua import NoctuaScreenshotCapture

# Configure screenshot capture
capture = NoctuaScreenshotCapture(
    headless=False,           # Set True for no GUI
    screenshot_dir="screens", # Output directory
    dev_mode=True,            # Use dev server
    token="your-token"        # Or from BARISTA_TOKEN env
)
```

### Headless Mode

For CI/CD or server environments:

```python
capture = NoctuaScreenshotCapture(headless=True)
```

## Server Endpoints

### Development Server

- **Barista API**: http://barista-dev.berkeleybop.org
- **Noctua UI**: http://noctua-dev.berkeleybop.org
- **Namespace**: minerva_public_dev
- **Token**: Contact the GO team for dev access

### Production Server

- **Barista API**: http://barista.berkeleybop.org
- **Noctua UI**: http://noctua.geneontology.org
- **Namespace**: minerva_public
- **Token**: Requires authentication

## Best Practices

### Development Workflow

1. Always start with the dev server
2. Use descriptive model titles
3. Test thoroughly before production
4. Keep tokens secure

### Token Security

```python
import os
from noctua import BaristaClient

# Read from environment (recommended)
client = BaristaClient(token=os.environ.get("BARISTA_TOKEN"))

# Never hardcode production tokens
# BAD: client = BaristaClient(token="abc123...")
```

### Error Handling

```python
from noctua import BaristaClient, BaristaError

try:
    client = BaristaClient()
except BaristaError as e:
    print(f"Configuration error: {e}")
    # Handle missing token, network issues, etc.
```

## Troubleshooting

### Common Issues

**Missing Token**
```bash
# Check if token is set
echo $BARISTA_TOKEN

# Set token
export BARISTA_TOKEN=0wikitmf1vch103exckj
```

**Network Errors**
```python
# Increase timeout for slow connections
client = BaristaClient(timeout=60.0)
```

**Permission Denied**
```python
# Check model state
response = client.get_model(model_id)
if response.model_state == "production":
    print("Model is protected - use dev server for testing")
```

## Next Steps

- Start with the [Quick Start Guide](quickstart.md)
- Explore the [Python API](../guide/python-api.md)
- See [Working Examples](../examples/noctua_demo.ipynb)