# Screenshot API Reference

## Class: NoctuaScreenshotCapture

Captures screenshots of Noctua models during API operations.

### Constructor

```python
NoctuaScreenshotCapture(
    headless: bool = False,
    screenshot_dir: str = "screenshots",
    noctua_base: str = "http://noctua.berkeleybop.org",
    dev_mode: bool = True,
    token: Optional[str] = None
)
```

**Parameters:**
- `headless`: Run browser without GUI
- `screenshot_dir`: Directory to save screenshots
- `noctua_base`: Base URL for Noctua
- `dev_mode`: Use dev server if True
- `token`: Barista token (reads from BARISTA_TOKEN env if not provided)

### Methods

#### start

```python
start() -> None
```

Start the browser driver. Tries Chrome first, falls back to Firefox.

#### close

```python
close() -> None
```

Close the browser driver.

#### open_model

```python
open_model(
    model_id: str,
    wait_time: int = 5
) -> bool
```

Open a model in Noctua browser window.

**Returns:** `True` if successful, `False` otherwise

#### capture

```python
capture(
    filename: Optional[str] = None,
    description: str = "",
    wait_time: int = 2
) -> Optional[str]
```

Capture screenshot of current page.

**Returns:** Path to saved screenshot or `None` if failed

#### capture_with_highlight

```python
capture_with_highlight(
    element_id: str,
    filename: Optional[str] = None,
    description: str = ""
) -> Optional[str]
```

Capture screenshot with specific element highlighted.

#### refresh_model

```python
refresh_model(wait_time: int = 3) -> None
```

Refresh current page to show API changes.

### Context Manager

```python
with NoctuaScreenshotCapture() as capture:
    capture.open_model("gomodel:12345")
    # Browser closes automatically
```

## Class: NoctuaModelTracker

Track model changes with automatic screenshots.

### Constructor

```python
NoctuaModelTracker(
    model_id: str,
    screenshot_capture: Optional[NoctuaScreenshotCapture] = None,
    auto_refresh: bool = True
)
```

**Parameters:**
- `model_id`: Model to track
- `screenshot_capture`: Screenshot capture instance
- `auto_refresh`: Automatically refresh after API calls

### Methods

#### track_operation

```python
track_operation(
    operation_name: str,
    operation_func: Callable,
    *args,
    **kwargs
) -> Any
```

Execute an operation and capture before/after screenshots.

**Returns:** Result of the operation function

## Examples

### Basic Screenshot

```python
from noctua import NoctuaScreenshotCapture

capture = NoctuaScreenshotCapture(screenshot_dir="docs/images")
capture.start()

if capture.open_model("gomodel:12345"):
    capture.capture("model.png", "Current state")

capture.close()
```

### Headless Mode

```python
# For CI/CD environments
capture = NoctuaScreenshotCapture(headless=True)
```

### With Model Tracking

```python
from noctua import (
    BaristaClient,
    NoctuaScreenshotCapture,
    NoctuaModelTracker
)

client = BaristaClient()
model_id = "gomodel:12345"

with NoctuaScreenshotCapture() as capture:
    capture.open_model(model_id)

    tracker = NoctuaModelTracker(model_id, capture)

    # Automatically captures before/after
    result = tracker.track_operation(
        "add_activity",
        client.add_individual,
        model_id,
        "GO:0003924"
    )
```

### Complete Workflow

```python
from noctua import BaristaClient, NoctuaScreenshotCapture

def document_pathway():
    client = BaristaClient()

    # Create model
    response = client.create_model(title="Documented Pathway")
    model_id = response.model_id

    with NoctuaScreenshotCapture() as capture:
        # Open in browser
        if not capture.open_model(model_id):
            return

        # Initial state
        capture.capture("01_empty.png")

        # Add nodes
        client.add_individual(model_id, "GO:0003924", "ras")
        capture.refresh_model()
        capture.capture("02_ras_added.png")

        client.add_individual(model_id, "GO:0004674", "raf")
        capture.refresh_model()
        capture.capture("03_raf_added.png")

        # Add edge
        client.add_fact(model_id, "ras", "raf", "RO:0002413")
        capture.refresh_model()
        capture.capture("04_edge_added.png")

    return model_id
```

## Browser Configuration

### Chrome Options

The module sets these Chrome options by default:
- `--no-sandbox`: Required for some environments
- `--disable-dev-shm-usage`: Prevents shared memory issues
- `--window-size=1920,1080`: Standard resolution
- `--headless`: When `headless=True`
- `--log-level=3`: Suppress verbose logging

### Firefox Fallback

If Chrome is unavailable, automatically falls back to Firefox with compatible options.

## Error Handling

### Browser Not Available

```python
capture = NoctuaScreenshotCapture()
capture.start()  # Logs warning if no browser found

# Check if driver is available
if capture.driver is None:
    print("No browser available for screenshots")
```

### Model Loading Timeout

```python
# Increase wait time for slow connections
success = capture.open_model(model_id, wait_time=10)
if not success:
    print("Could not open model")
```

## File Management

### Automatic Naming

Screenshots are automatically named if filename not provided:
- Format: `noctua_001.png`, `noctua_002.png`, etc.
- Counter increments per session

### Post-Processing

Images are automatically:
- Resized if width > 1200px
- Optimized for file size
- Saved as PNG format

## Performance Tips

1. **Use headless mode** for faster execution
2. **Batch operations** before refreshing
3. **Allow adequate wait times** for page loads
4. **Reuse capture instances** for multiple models
5. **Close browsers** when done to free resources