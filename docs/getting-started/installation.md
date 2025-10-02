# Installation

## Requirements

- Python 3.10 or later
- Optional: Chrome or Firefox browser (for screenshot automation)

## Installing with pip

```bash
pip install noctua-py
```

## Installing with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package manager:

```bash
uv add noctua-py
```

## Installing from source

```bash
git clone https://github.com/geneontology/noctua-py
cd noctua-py
uv sync  # or pip install -e .
```

## Optional Dependencies

### For Screenshot Automation

To use the screenshot capture feature, install a browser and driver:

=== "Chrome"

    ```bash
    # macOS with Homebrew
    brew install --cask google-chrome
    brew install chromedriver

    # Ubuntu/Debian
    sudo apt-get install chromium-browser chromium-chromedriver

    # Python packages
    pip install selenium pillow
    ```

=== "Firefox"

    ```bash
    # macOS with Homebrew
    brew install --cask firefox
    brew install geckodriver

    # Ubuntu/Debian
    sudo apt-get install firefox firefox-geckodriver

    # Python packages
    pip install selenium pillow
    ```

### For GO-CAM Conversion

To convert models to GO-CAM structured format:

```bash
pip install gocam
```

## Verify Installation

Check that the CLI is installed:

```bash
noctua --help
```

Test the Python import:

```python
from noctua import BaristaClient
print("noctua installed successfully!")
```

## Next Steps

- Continue to [Quick Start](quickstart.md) to create your first model
- See [Configuration](configuration.md) for environment setup