"""
Utility for capturing screenshots of Noctua models during API operations.

This module provides functionality to automatically open Noctua in a browser
and capture screenshots as models are modified via the API.
"""

import os
import time
from pathlib import Path
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from PIL import Image as PILImage
import logging

logger = logging.getLogger(__name__)


class NoctuaScreenshotCapture:
    """Capture screenshots of Noctua models as they're being modified."""

    def __init__(
        self,
        headless: bool = False,
        screenshot_dir: str = "screenshots",
        noctua_base: str = "http://noctua.berkeleybop.org",
        dev_mode: bool = True,
        token: Optional[str] = None
    ):
        """
        Initialize the screenshot capture.

        Args:
            headless: Run browser in headless mode (no GUI)
            screenshot_dir: Directory to save screenshots
            noctua_base: Base URL for Noctua
            dev_mode: Use dev server if True
            token: Barista token (will read from BARISTA_TOKEN env if not provided)
        """
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)

        # Use dev or production Noctua
        if dev_mode:
            self.noctua_base = "http://noctua-dev.berkeleybop.org"
        else:
            self.noctua_base = noctua_base

        # Get token from environment if not provided
        self.token = token or os.environ.get("BARISTA_TOKEN", "")

        # Setup Chrome options
        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--window-size=1920,1080")

        # Add options to suppress logs
        self.options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.options.add_argument("--log-level=3")

        self.driver = None
        self.screenshot_count = 0

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def start(self):
        """Start the browser driver."""
        try:
            # Try Chrome first
            self.driver = webdriver.Chrome(options=self.options)
        except Exception as e:
            logger.info(f"Chrome not available: {e}, trying Firefox")
            try:
                # Fallback to Firefox
                firefox_options = webdriver.FirefoxOptions()
                if self.options.arguments:
                    if "--headless" in self.options.arguments:
                        firefox_options.add_argument("--headless")
                self.driver = webdriver.Firefox(options=firefox_options)
            except Exception as e:
                logger.warning(f"Could not start browser: {e}")
                logger.warning("Install Chrome or Firefox and appropriate driver")
                self.driver = None

    def close(self):
        """Close the browser driver."""
        if self.driver:
            self.driver.quit()

    def open_model(self, model_id: str, wait_time: int = 5) -> bool:
        """
        Open a model in Noctua.

        Args:
            model_id: GO-CAM model ID (e.g., "gomodel:12345")
            wait_time: Time to wait for page load

        Returns:
            True if successful
        """
        if not self.driver:
            logger.warning("Browser driver not available")
            return False

        try:
            # Navigate to the model with token
            url = f"{self.noctua_base}/editor/graph/{model_id}"
            if self.token:
                url += f"?barista_token={self.token}"
            logger.info(f"Opening model at: {url}")
            self.driver.get(url)

            # Wait for the canvas to load
            time.sleep(wait_time)

            # Try to wait for specific elements that indicate the model loaded
            try:
                # Wait for the graph canvas or similar element
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "bbop-mme-edit-core"))
                )
            except TimeoutException:
                logger.warning("Timeout waiting for Noctua editor to load")

            return True

        except Exception as e:
            logger.error(f"Error opening model: {e}")
            return False

    def capture(
        self,
        filename: Optional[str] = None,
        description: str = "",
        wait_time: int = 2
    ) -> Optional[str]:
        """
        Capture a screenshot of the current page.

        Args:
            filename: Optional filename (auto-generated if not provided)
            description: Description for logging
            wait_time: Time to wait before capture

        Returns:
            Path to saved screenshot or None
        """
        if not self.driver:
            logger.warning("Browser driver not available")
            return None

        try:
            # Wait a bit for any animations/updates
            time.sleep(wait_time)

            # Generate filename if not provided
            if not filename:
                self.screenshot_count += 1
                filename = f"noctua_{self.screenshot_count:03d}.png"

            filepath = self.screenshot_dir / filename

            # Take screenshot
            self.driver.save_screenshot(str(filepath))

            # Optionally crop/resize
            self._post_process_screenshot(filepath)

            logger.info(f"Screenshot saved: {filepath} - {description}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return None

    def _post_process_screenshot(self, filepath: Path, max_width: int = 1200):
        """
        Post-process screenshot (resize if needed).

        Args:
            filepath: Path to screenshot
            max_width: Maximum width for resize
        """
        try:
            img = PILImage.open(filepath)

            # Resize if too large
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                resized_img = img.resize(new_size, PILImage.Resampling.LANCZOS)
                resized_img.save(filepath, optimize=True)
            img.close()

        except Exception as e:
            logger.warning(f"Could not post-process screenshot: {e}")

    def capture_with_highlight(
        self,
        element_id: str,
        filename: Optional[str] = None,
        description: str = ""
    ) -> Optional[str]:
        """
        Capture screenshot with a specific element highlighted.

        Args:
            element_id: ID of element to highlight
            filename: Optional filename
            description: Description for logging

        Returns:
            Path to saved screenshot or None
        """
        if not self.driver:
            return None

        try:
            # Add highlight via JavaScript
            script = f"""
            var element = document.getElementById('{element_id}');
            if (element) {{
                element.style.border = '3px solid red';
                element.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            }}
            """
            self.driver.execute_script(script)

            # Capture
            result = self.capture(filename, description)

            # Remove highlight
            script = f"""
            var element = document.getElementById('{element_id}');
            if (element) {{
                element.style.border = '';
                element.style.backgroundColor = '';
            }}
            """
            self.driver.execute_script(script)

            return result

        except Exception as e:
            logger.error(f"Error capturing with highlight: {e}")
            return None

    def refresh_model(self, wait_time: int = 3):
        """
        Refresh the current page to show API changes.

        Args:
            wait_time: Time to wait after refresh
        """
        if not self.driver:
            return

        try:
            self.driver.refresh()
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error refreshing: {e}")


class NoctuaModelTracker:
    """Track model changes with automatic screenshots."""

    def __init__(
        self,
        model_id: str,
        screenshot_capture: Optional[NoctuaScreenshotCapture] = None,
        auto_refresh: bool = True
    ):
        """
        Initialize model tracker.

        Args:
            model_id: Model to track
            screenshot_capture: Screenshot capture instance
            auto_refresh: Automatically refresh after API calls
        """
        self.model_id = model_id
        self.capture = screenshot_capture
        self.auto_refresh = auto_refresh
        self.step_count = 0

    def track_operation(
        self,
        operation_name: str,
        operation_func,
        *args,
        **kwargs
    ):
        """
        Execute an operation and capture before/after screenshots.

        Args:
            operation_name: Name of the operation
            operation_func: Function to execute
            *args, **kwargs: Arguments for the function

        Returns:
            Result of the operation
        """
        self.step_count += 1

        # Capture before state
        if self.capture:
            self.capture.capture(
                filename=f"step_{self.step_count:02d}_before_{operation_name}.png",
                description=f"Before: {operation_name}"
            )

        # Execute operation
        result = operation_func(*args, **kwargs)

        # Refresh and capture after state
        if self.capture and self.auto_refresh:
            self.capture.refresh_model()
            self.capture.capture(
                filename=f"step_{self.step_count:02d}_after_{operation_name}.png",
                description=f"After: {operation_name}"
            )

        return result


def demo_screenshot_workflow():
    """Demonstrate screenshot capture workflow."""
    from noctua.barista import BaristaClient

    # Ensure BARISTA_TOKEN is set in environment
    if not os.environ.get("BARISTA_TOKEN"):
        print("ERROR: BARISTA_TOKEN environment variable not set")
        print("Please set: export BARISTA_TOKEN=your-token-here")
        return

    client = BaristaClient()

    # Create a new model
    response = client.create_model(title="Screenshot Demo Model")
    if not response.ok:
        print("Failed to create model")
        return

    model_id = response.model_id
    print(f"Created model: {model_id}")

    # Setup screenshot capture
    with NoctuaScreenshotCapture(headless=False, dev_mode=True) as capture:
        # Open the model in Noctua
        if not capture.open_model(model_id):
            print("Could not open model in browser")
            return

        # Create tracker
        tracker = NoctuaModelTracker(model_id, capture)

        # Track operations with screenshots
        print("Adding individuals with screenshots...")

        # Add first individual
        tracker.track_operation(
            "add_gtpase",
            client.add_individual,
            model_id,
            "GO:0003924",
            assign_var="gtpase"
        )

        # Add second individual
        tracker.track_operation(
            "add_kinase",
            client.add_individual,
            model_id,
            "GO:0004674",
            assign_var="kinase"
        )

        print(f"Screenshots saved in: {capture.screenshot_dir}")


if __name__ == "__main__":
    demo_screenshot_workflow()