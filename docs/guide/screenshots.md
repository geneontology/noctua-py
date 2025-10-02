# Screenshot Automation

## Overview

The screenshot automation feature allows you to capture visual documentation of GO-CAM models as they're being built or modified through the API.

## Requirements

- Chrome or Firefox browser
- ChromeDriver or GeckoDriver
- Python packages: `selenium`, `pillow`

## Basic Usage

### Simple Screenshot Capture

```python
from noctua import NoctuaScreenshotCapture

# Initialize capture
capture = NoctuaScreenshotCapture(
    headless=False,  # Show browser window
    screenshot_dir="screenshots"
)

# Start browser
capture.start()

# Open a model
capture.open_model("gomodel:6796b94c00003233")

# Take screenshot
capture.capture(filename="model.png", description="Initial state")

# Clean up
capture.close()
```

### Context Manager

```python
from noctua import NoctuaScreenshotCapture

with NoctuaScreenshotCapture() as capture:
    capture.open_model("gomodel:6796b94c00003233")
    capture.capture("screenshot.png")
    # Browser closes automatically
```

## Configuration Options

```python
capture = NoctuaScreenshotCapture(
    headless=True,           # No GUI (for CI/CD)
    screenshot_dir="imgs",   # Output directory
    dev_mode=True,           # Use dev server
    token="your-token",      # Auth token
    noctua_base="http://noctua-dev.berkeleybop.org"
)
```

## Tracking Model Changes

### Manual Tracking

```python
from noctua import BaristaClient, NoctuaScreenshotCapture

client = BaristaClient()
model_id = "gomodel:6796b94c00003233"

with NoctuaScreenshotCapture() as capture:
    # Open model
    capture.open_model(model_id)
    capture.capture("01_initial.png")

    # Make API change
    client.add_individual(model_id, "GO:0003924")

    # Refresh and capture
    capture.refresh_model()
    capture.capture("02_after_add.png")
```

### Automated Tracking

```python
from noctua import NoctuaModelTracker, NoctuaScreenshotCapture

# Setup tracker
with NoctuaScreenshotCapture() as capture:
    capture.open_model(model_id)

    tracker = NoctuaModelTracker(model_id, capture)

    # Automatically captures before/after
    tracker.track_operation(
        "add_gtpase",
        client.add_individual,
        model_id,
        "GO:0003924"
    )
```

## Advanced Features

### Highlighted Screenshots

```python
# Capture with element highlighted
capture.capture_with_highlight(
    element_id="node-123",
    filename="highlighted.png",
    description="Highlighting specific node"
)
```

### Post-Processing

Screenshots are automatically:
- Resized if too large (max width 1200px)
- Optimized for file size
- Named with sequential numbers if no name provided

## Headless Mode

For CI/CD or server environments:

```python
# No GUI required
capture = NoctuaScreenshotCapture(headless=True)

# Works identically
capture.start()
capture.open_model(model_id)
capture.capture("headless.png")
capture.close()
```

## Browser Compatibility

### Chrome (Recommended)

```python
# Automatically uses Chrome if available
capture = NoctuaScreenshotCapture()
```

### Firefox Fallback

```python
# Falls back to Firefox if Chrome unavailable
# Or force Firefox by uninstalling Chrome driver
```

## Complete Example

```python
from noctua import BaristaClient, NoctuaScreenshotCapture
import time

def document_model_creation():
    """Create model with visual documentation."""

    client = BaristaClient()

    # Create new model
    response = client.create_model(title="Visual Demo")
    model_id = response.model_id

    # Setup screenshot capture
    with NoctuaScreenshotCapture(screenshot_dir="docs/imgs") as capture:

        # Open in browser
        if not capture.open_model(model_id):
            print("Browser not available")
            return

        # Document each step
        steps = [
            ("Empty model", lambda: None),
            ("Add GTPase", lambda: client.add_individual(
                model_id, "GO:0003924", "gtpase"
            )),
            ("Add Kinase", lambda: client.add_individual(
                model_id, "GO:0004674", "kinase"
            )),
            ("Add edge", lambda: client.add_fact(
                model_id, "gtpase", "kinase", "RO:0002413"
            ))
        ]

        for i, (description, action) in enumerate(steps):
            # Execute action
            action()

            # Refresh browser
            if i > 0:
                capture.refresh_model()
                time.sleep(2)

            # Capture state
            capture.capture(
                filename=f"step_{i:02d}_{description.lower().replace(' ', '_')}.png",
                description=description
            )

        print(f"Documentation saved to {capture.screenshot_dir}")

    return model_id

# Run the documentation
if __name__ == "__main__":
    document_model_creation()
```

## Troubleshooting

### Browser Not Starting

```bash
# Check Chrome installation
which chrome
which chromedriver

# Install if missing
brew install --cask google-chrome
brew install chromedriver
```

### Timeout Issues

```python
# Increase wait times
capture.open_model(model_id, wait_time=10)
capture.refresh_model(wait_time=5)
```

### Headless Mode Issues

```python
# Add window size for headless
capture = NoctuaScreenshotCapture(headless=True)
# Window size is set automatically to 1920x1080
```

## Best Practices

1. **Use descriptive filenames**: Include step numbers and descriptions
2. **Allow refresh time**: Wait 2-3 seconds after API changes
3. **Organize screenshots**: Use subdirectories for different models
4. **Handle failures gracefully**: Check if browser is available
5. **Clean up resources**: Always close the browser when done

## Integration Examples

### With Jupyter Notebooks

See [Screenshot Demo Notebook](../examples/noctua_demo_with_screenshots.ipynb) for interactive examples.

### In Documentation

Generated screenshots can be included in documentation:

```markdown
![Model State](screenshots/model_complete.png)
```

### In Tests

```python
def test_model_visualization():
    """Test with visual verification."""
    with NoctuaScreenshotCapture(headless=True) as capture:
        # Test code here
        capture.capture("test_result.png")
```

## Next Steps

- See [Complete Example](../examples/noctua_demo_with_screenshots.ipynb) with screenshots
- Check [Python API](python-api.md) for model manipulation
- Review [CLI Guide](cli.md) for command-line usage