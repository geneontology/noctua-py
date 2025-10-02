from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import httpx

# Default to test/dev server for safety
DEFAULT_BARISTA_BASE = os.environ.get("BARISTA_BASE", "http://barista-dev.berkeleybop.org")
DEFAULT_NAMESPACE = os.environ.get("BARISTA_NAMESPACE", "minerva_public_dev")
DEFAULT_PROVIDED_BY = os.environ.get("BARISTA_PROVIDED_BY", "http://geneontology.org")

# Production/live server settings
LIVE_BARISTA_BASE = os.environ.get("BARISTA_LIVE_BASE", "http://barista.berkeleybop.org")
LIVE_NAMESPACE = os.environ.get("BARISTA_LIVE_NAMESPACE", "minerva_public")

BARISTA_TOKEN_ENV = "BARISTA_TOKEN"


class BaristaError(Exception):
    pass


@dataclass
class BaristaResponse:
    """Response from Barista API operations.

    IMPORTANT: Understanding success vs validation:
    - ok: API call succeeded (but validation may have failed!)
    - succeeded: Both API call AND validation succeeded (use this!)
    - validation_failed: True if validation failed and was rolled back

    Attributes:
        raw: The raw JSON response from the API
        validation_failed: True if validation failed and changes were rolled back
        validation_reason: Human-readable explanation of validation failure
        _original_requests: The original requests sent (for undo support)
        _client: Reference to the client (for undo operations)
        _before_state: Model state before operation (for undo)

    When validation is used (via execute_with_validation or add_individual_validated):
    - If validation passes: validation_failed=False, changes remain in model
    - If validation fails: validation_failed=True, changes are rolled back,
      validation_reason contains explanation

    Example (CORRECT way to check):
        >>> # response = client.add_individual_validated(
        >>> #     model_id, "GO:0003924",
        >>> #     expected_type={"label": "GTPase activity"}
        >>> # )
        >>> # if response.succeeded:  # Use succeeded, NOT ok!
        >>> #     print(f"Success: {response.individual_id}")
        >>> # elif response.validation_failed:
        >>> #     print(f"Rolled back: {response.validation_reason}")
        >>> # else:
        >>> #     print(f"API call failed: {response.error}")
        ... # doctest: +SKIP
    """
    raw: Dict[str, Any]
    validation_failed: bool = False
    validation_reason: Optional[str] = None
    _original_requests: Optional[List[Dict[str, Any]]] = None
    _client: Optional['BaristaClient'] = None
    _before_state: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        """Check if the API call itself succeeded.

        IMPORTANT: This does NOT check validation status!
        - Returns True if the API call succeeded, even if validation failed
        - Returns False only if the API call itself failed

        For validation-aware checks, use:
        - succeeded() to check both API success AND validation pass
        - validation_passed() to check only validation status
        """
        return self.raw.get("message-type") == "success"

    @property
    def succeeded(self) -> bool:
        """Check if operation fully succeeded (API call worked AND validation passed).

        Returns:
            True if both the API call succeeded and validation passed (or wasn't used)
            False if either the API call failed or validation failed

        This is usually what you want to check after a validated operation.
        """
        return self.ok and not self.validation_failed

    @property
    def validation_passed(self) -> bool:
        """Check if validation passed (when validation was used).

        Returns:
            True if validation was not used or validation passed
            False if validation was used and failed
        """
        return not self.validation_failed

    @property
    def error(self) -> Optional[str]:
        """Get error message for any type of failure (API or validation).

        Returns:
            Error message explaining what went wrong, or None if no error
        """
        if not self.ok:
            # API call failed
            error_data = self.raw.get("data", {})
            if isinstance(error_data, dict):
                return error_data.get("message", "API call failed")
            else:
                return "API call failed"
        elif self.validation_failed:
            # Validation failed
            return self.validation_reason
        else:
            # No error
            return None

    # Backward compatibility properties (deprecated)
    @property
    def _validation_failed(self) -> bool:
        """Deprecated: Use validation_failed instead."""
        import warnings
        warnings.warn(
            "_validation_failed is deprecated, use validation_failed instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.validation_failed

    @property
    def _validation_reason(self) -> Optional[str]:
        """Deprecated: Use validation_reason instead."""
        import warnings
        warnings.warn(
            "_validation_reason is deprecated, use validation_reason instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.validation_reason

    @property
    def signal(self) -> Optional[str]:
        return self.raw.get("signal")

    @property
    def intention(self) -> Optional[str]:
        return self.raw.get("intention")

    @property
    def model_id(self) -> Optional[str]:
        data = self.raw.get("data") or {}
        return data.get("id")

    @property
    def individuals(self) -> List[Dict[str, Any]]:
        data = self.raw.get("data") or {}
        return data.get("individuals", [])

    @property
    def facts(self) -> List[Dict[str, Any]]:
        data = self.raw.get("data") or {}
        return data.get("facts", [])

    @property
    def model_state(self) -> Optional[str]:
        """Get the model state (e.g., 'production', 'development')."""
        data = self.raw.get("data") or {}
        annotations = data.get("annotations", [])
        for annotation in annotations:
            if annotation.get("key") == "state":
                return annotation.get("value")
        return None

    def can_undo(self) -> bool:
        """Check if this response can be undone.

        Returns:
            True if undo is possible, False otherwise
        """
        return (
            self.ok
            and self._original_requests is not None
            and self._client is not None
            and len(self._original_requests) > 0
        )

    def _generate_reverse_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate the reverse operation for a single request.

        Args:
            request: The original request to reverse

        Returns:
            The reverse request, or None if not reversible
        """
        entity = request.get("entity")
        operation = request.get("operation")
        arguments = request.get("arguments", {})

        # Handle individual operations
        if entity == "individual":
            if operation == "add":
                # To reverse an add, we need to find what was added
                # This requires looking at the response to find the new individual ID
                if self._before_state and self.raw.get("data"):
                    before_ids = {ind["id"] for ind in self._before_state.get("individuals", [])}
                    after_ids = {ind["id"] for ind in self.raw.get("data", {}).get("individuals", [])}
                    new_ids = after_ids - before_ids
                    if new_ids:
                        # Remove the newly added individual
                        new_id = list(new_ids)[0]  # Take first if multiple
                        return {
                            "entity": "individual",
                            "operation": "remove",
                            "arguments": {
                                "individual": new_id,
                                "model-id": arguments.get("model-id")
                            }
                        }
            elif operation == "remove":
                # To reverse a remove, we need the original individual's type
                # This is harder - we'd need to have captured it before removal
                individual_id = arguments.get("individual")
                if self._before_state:
                    # Find the individual that was removed
                    for ind in self._before_state.get("individuals", []):
                        if ind["id"] == individual_id:
                            # Get the first type (simplification)
                            types = ind.get("type", [])
                            if types and len(types) > 0:
                                class_id = types[0].get("id")
                                if class_id:
                                    return {
                                        "entity": "individual",
                                        "operation": "add",
                                        "arguments": {
                                            "expressions": [{"type": "class", "id": class_id}],
                                            "model-id": arguments.get("model-id"),
                                            "assign-to-variable": "restored"
                                        }
                                    }
            elif operation == "add-annotation":
                # To reverse adding an annotation to an individual, remove it
                values = arguments.get("values", [])
                if values:
                    return {
                        "entity": "individual",
                        "operation": "remove-annotation",
                        "arguments": {
                            "model-id": arguments.get("model-id"),
                            "individual": arguments.get("individual"),
                            "values": values
                        }
                    }
            elif operation == "remove-annotation":
                # To reverse removing an annotation from an individual, add it back
                values = arguments.get("values", [])
                if values:
                    return {
                        "entity": "individual",
                        "operation": "add-annotation",
                        "arguments": {
                            "model-id": arguments.get("model-id"),
                            "individual": arguments.get("individual"),
                            "values": values
                        }
                    }

        # Handle edge/fact operations
        elif entity == "edge":
            if operation == "add":
                # To reverse an add, remove the edge
                return {
                    "entity": "edge",
                    "operation": "remove",
                    "arguments": {
                        "subject": arguments.get("subject"),
                        "object": arguments.get("object"),
                        "predicate": arguments.get("predicate"),
                        "model-id": arguments.get("model-id")
                    }
                }
            elif operation == "remove":
                # To reverse a remove, add the edge back
                return {
                    "entity": "edge",
                    "operation": "add",
                    "arguments": {
                        "subject": arguments.get("subject"),
                        "object": arguments.get("object"),
                        "predicate": arguments.get("predicate"),
                        "model-id": arguments.get("model-id")
                    }
                }

        # Handle model annotation operations
        elif entity == "model":
            if operation == "add-annotation":
                # To reverse an add, remove the annotation
                return {
                    "entity": "model",
                    "operation": "remove-annotation",
                    "arguments": {
                        "model-id": arguments.get("model-id"),
                        "key": arguments.get("key"),
                        "value": arguments.get("value")
                    }
                }
            elif operation == "remove-annotation":
                # To reverse a remove, add the annotation back
                return {
                    "entity": "model",
                    "operation": "add-annotation",
                    "arguments": {
                        "model-id": arguments.get("model-id"),
                        "key": arguments.get("key"),
                        "value": arguments.get("value")
                    }
                }
            elif operation == "replace-annotation":
                # To reverse a replace, restore the old value
                old_value = arguments.get("old-value")
                new_value = arguments.get("value")
                if old_value:
                    return {
                        "entity": "model",
                        "operation": "replace-annotation",
                        "arguments": {
                            "model-id": arguments.get("model-id"),
                            "key": arguments.get("key"),
                            "value": old_value,
                            "old-value": new_value
                        }
                    }

        return None

    def undo(self) -> 'BaristaResponse':
        """Undo the operations that created this response.

        This generates reverse operations for each request that was executed
        and applies them to restore the previous state.

        Returns:
            BaristaResponse from the undo operation

        Raises:
            BaristaError: If undo is not possible or fails
        """
        if not self.can_undo():
            raise BaristaError(
                "Cannot undo: missing required data. "
                "Ensure the response was created with undo support enabled."
            )

        # Generate reverse operations in reverse order
        undo_requests = []
        if self._original_requests:
            for request in reversed(self._original_requests):
                reverse_req = self._generate_reverse_request(request)
                if reverse_req:
                    undo_requests.append(reverse_req)

        if not undo_requests:
            raise BaristaError("No reversible operations found")

        # Execute the undo operations
        if not self._client:
            raise BaristaError("Cannot undo: client reference is missing")
        return self._client.m3_batch(undo_requests)

    def validate_individuals_detailed(self, expected: List[Dict[str, str]]) -> Dict[str, Any]:
        """Validate individuals and return detailed results including mismatches.

        Args:
            expected: List of dicts with 'id' and/or 'label' keys to check
                     e.g., [{"id": "GO:0004672", "label": "protein kinase activity"}]

        Returns:
            Dict with 'valid', 'mismatches', and 'error_message' keys
        """
        if not self.ok or not self.raw.get("data"):
            return {
                "valid": False,
                "mismatches": [],
                "error_message": "No valid response data available"
            }

        individuals = self.raw.get("data", {}).get("individuals", [])
        mismatches = []

        for expected_item in expected:
            expected_id = expected_item.get("id")
            expected_label = expected_item.get("label")

            # Check if this is an individual ID (like gomodel:123/ind456) or a type ID (like GO:0003924)
            is_individual_id = expected_id and ("/" in expected_id or expected_id.startswith("gomodel:"))

            found = False
            closest_matches = []
            target_individual = None
            available_individual_ids: List[str] = []

            if is_individual_id:
                # Individual-based validation: check if the specific individual has the expected type label
                for individual in individuals:
                    if individual.get("id") == expected_id:
                        target_individual = individual
                        break

                if target_individual:
                    types = target_individual.get("type", [])
                    for type_info in types:
                        if not expected_label or type_info.get("label") == expected_label:
                            found = True
                            break
                        else:
                            # Collect all types for this individual for better error reporting
                            closest_matches.append(type_info)

                if not target_individual:
                    # Individual ID not found
                    available_individual_ids = [ind.get("id", "unknown") for ind in individuals]
            else:
                # Type-based validation: check if any individual has this type
                for individual in individuals:
                    types = individual.get("type", [])
                    for type_info in types:
                        # Check ID match
                        id_match = not expected_id or type_info.get("id") == expected_id
                        # Check label match
                        label_match = not expected_label or type_info.get("label") == expected_label

                        if id_match and label_match:
                            found = True
                            break

                        # Collect potential matches for better error reporting
                        if expected_id and type_info.get("id") == expected_id:
                            closest_matches.append(type_info)

                    if found:
                        break

            if not found:
                mismatch_info: Dict[str, Any] = {"expected": expected_item}

                if is_individual_id:
                    # Individual-based validation failed
                    if target_individual:
                        # Individual exists but wrong type
                        if closest_matches:
                            actual_labels = [t.get("label", "unknown") for t in closest_matches]
                            mismatch_info["details"] = f"Individual {expected_id} has type labels [{', '.join(actual_labels)}] but expected '{expected_label}'"
                        else:
                            mismatch_info["details"] = f"Individual {expected_id} has no type labels but expected '{expected_label}'"
                    else:
                        # Individual doesn't exist
                        mismatch_info["details"] = f"Individual ID '{expected_id}' not found. Available: {', '.join(available_individual_ids) if available_individual_ids else 'none'}"
                else:
                    # Type-based validation failed
                    if expected_id and closest_matches:
                        actual_match = closest_matches[0]  # Take the first match
                        mismatch_info["actual"] = actual_match
                        if expected_label:
                            mismatch_info["details"] = f"Expected label '{expected_label}' but found '{actual_match.get('label', 'unknown')}' for ID {expected_id}"
                        else:
                            mismatch_info["details"] = f"Found ID {expected_id} with label '{actual_match.get('label', 'unknown')}'"
                    else:
                        # No matching ID found at all
                        available_ids = []
                        for individual in individuals:
                            for type_info in individual.get("type", []):
                                if type_info.get("id"):
                                    available_ids.append(f"{type_info['id']} ({type_info.get('label', 'no label')})")

                        if expected_id:
                            mismatch_info["details"] = f"Expected ID '{expected_id}' not found. Available: {', '.join(available_ids) if available_ids else 'none'}"
                        else:
                            mismatch_info["details"] = f"Expected label '{expected_label}' not found. Available: {', '.join(available_ids) if available_ids else 'none'}"

                mismatches.append(mismatch_info)

        if mismatches:
            error_parts = []
            for mismatch in mismatches:
                error_parts.append(mismatch["details"])
            error_message = "; ".join(error_parts)
        else:
            error_message = None

        return {
            "valid": len(mismatches) == 0,
            "mismatches": mismatches,
            "error_message": error_message
        }

    def validate_individuals(self, expected: List[Dict[str, str]]) -> bool:
        """Validate that individuals in the response match expected types.

        Args:
            expected: List of dicts with 'id' and/or 'label' keys to check
                     e.g., [{"id": "GO:0004672", "label": "protein kinase activity"}]

        Returns:
            True if all expected types are found in individuals, False otherwise
        """
        return self.validate_individuals_detailed(expected)["valid"]

    def validate_and_rollback(self, expected: List[Dict[str, str]],
                             validation_type: str = "individuals") -> 'BaristaResponse':
        """Validate the response and automatically rollback if validation fails.

        Args:
            expected: List of expected conditions to check
            validation_type: Type of validation ("individuals", "facts", or custom)

        Returns:
            Self if validation passes, or undo response if validation fails

        Raises:
            BaristaError: If validation fails and undo is not possible
        """
        if validation_type == "individuals":
            validation_result = self.validate_individuals_detailed(expected)
            valid = validation_result["valid"]
            error_message = validation_result["error_message"]
        else:
            # Could add more validation types here
            raise BaristaError(f"Unknown validation type: {validation_type}")

        if not valid:
            if not self.can_undo():
                raise BaristaError(
                    "Validation failed but cannot undo. "
                    "Ensure operations were executed with enable_undo=True"
                )

            # Validation failed, rollback
            print(f"Validation failed for {validation_type}. Rolling back...")
            undo_response = self.undo()

            # Mark the undo response as a validation failure
            undo_response.validation_failed = True
            undo_response.validation_reason = error_message or f"Expected {validation_type} not found: {expected}"

            return undo_response

        # Validation passed
        return self


def get_noctua_url(model_id: str, token: Optional[str] = None, dev: bool = True) -> str:
    """Generate a Noctua editor URL for a model.

    Args:
        model_id: The GO-CAM model ID
        token: Barista token (will use BARISTA_TOKEN env var if not provided)
        dev: Use dev server if True, production if False

    Returns:
        Full Noctua URL with authentication token
    """
    if dev:
        base = "http://noctua-dev.berkeleybop.org"
    else:
        base = "http://noctua.berkeleybop.org"

    url = f"{base}/editor/graph/{model_id}"

    # Add token if available
    if token is None:
        token = os.environ.get(BARISTA_TOKEN_ENV)

    if token:
        url += f"?barista_token={token}"

    return url


class BaristaClient:
    """
    Convenience client for Barista/Minerva m3Batch endpoints.

    - Reads BARISTA_TOKEN from environment unless explicitly provided
    - Defaults to barista.berkeleybop.org and namespace minerva_public
    - Convenience helpers to build request payloads
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = DEFAULT_BARISTA_BASE,
        namespace: str = DEFAULT_NAMESPACE,
        provided_by: str = DEFAULT_PROVIDED_BY,
        timeout: float = 30.0,
        track_variables: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.namespace = namespace
        self.provided_by = provided_by
        self.token = token or os.environ.get(BARISTA_TOKEN_ENV)
        if not self.token:
            raise BaristaError(
                f"BARISTA token not provided. Set {BARISTA_TOKEN_ENV} or pass token explicitly."
            )
        self._client = httpx.Client(timeout=timeout)

        # Variable tracking: maps (model_id, variable_name) -> actual_id
        self.track_variables = track_variables
        self._variable_registry: Dict[tuple[str, str], str] = {}
        # Cache for model state before operations (for diffing)
        self._model_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def privileged_url(self) -> str:
        return f"{self.base_url}/api/{self.namespace}/m3BatchPrivileged"

    @property
    def batch_url(self) -> str:
        return f"{self.base_url}/api/{self.namespace}/m3Batch"

    def close(self) -> None:
        self._client.close()

    # Variable management methods
    def _is_variable(self, identifier: str) -> bool:
        """Check if an identifier is a variable name (not a CURIE or ID).

        Variables are simple names without ':' or '/' characters.
        CURIEs have ':' (e.g., GO:0003924)
        IDs have '/' (e.g., gomodel:xxx/individual-123)
        """
        return ':' not in identifier and '/' not in identifier

    def _resolve_identifier(self, model_id: str, identifier: str) -> str:
        """Resolve an identifier to an actual ID.

        If it's a variable, look it up in the registry.
        Otherwise, return as-is (it's already a CURIE or ID).
        """
        if self._is_variable(identifier):
            key = (model_id, identifier)
            if key in self._variable_registry:
                return self._variable_registry[key]
            # Variable not found - return as-is and let the server handle the error
        return identifier

    def set_variable(self, model_id: str, variable: str, actual_id: str) -> None:
        """Manually set a variable mapping."""
        self._variable_registry[(model_id, variable)] = actual_id

    def get_variable(self, model_id: str, variable: str) -> Optional[str]:
        """Get the actual ID for a variable."""
        return self._variable_registry.get((model_id, variable))

    def get_variables(self, model_id: str) -> Dict[str, str]:
        """Get all variables for a model."""
        return {
            var: id for (mid, var), id in self._variable_registry.items()
            if mid == model_id
        }

    def clear_variables(self, model_id: Optional[str] = None) -> None:
        """Clear variable registry for a model or all models."""
        if model_id:
            keys_to_remove = [
                key for key in self._variable_registry
                if key[0] == model_id
            ]
            for key in keys_to_remove:
                del self._variable_registry[key]
        else:
            self._variable_registry.clear()

    def _snapshot_model(self, model_id: str) -> Dict[str, Any]:
        """Take a snapshot of the current model state for diffing."""
        response = self.get_model(model_id)
        if response.ok:
            data = response.raw.get("data", {})
            # Store sets of IDs for efficient diffing
            return {
                "individuals": {ind.get("id") for ind in data.get("individuals", []) if ind.get("id")},
                "facts": {
                    (f.get("subject"), f.get("object"), f.get("property"))
                    for f in data.get("facts", [])
                    if f.get("subject") and f.get("object") and f.get("property")
                }
            }
        return {"individuals": set(), "facts": set()}

    def _track_new_individual(self, model_id: str, before_state: Dict[str, Any],
                             after_response: BaristaResponse, variable: str) -> Optional[str]:
        """Track a new individual by diffing before/after states."""
        if not after_response.ok or not self.track_variables:
            return None

        after_data = after_response.raw.get("data", {})
        after_individuals = {ind.get("id") for ind in after_data.get("individuals", []) if ind.get("id")}

        # Find new individuals (in after but not in before)
        new_individuals = after_individuals - before_state.get("individuals", set())

        if len(new_individuals) == 1:
            # Exactly one new individual - map it to the variable
            new_id = next(iter(new_individuals))
            self.set_variable(model_id, variable, new_id)
            return new_id
        elif len(new_individuals) > 1:
            # Multiple new individuals - can't determine which one maps to the variable
            # This shouldn't happen with single add_individual calls
            pass

        return None

    # Low-level
    def m3_batch(self, requests: List[Dict[str, Any]], privileged: bool = True, enable_undo: bool = False) -> BaristaResponse:
        """Execute a batch of requests against the Minerva API.

        Args:
            requests: List of request dictionaries
            privileged: Whether to use the privileged endpoint
            enable_undo: Whether to enable undo functionality for this response

        Returns:
            BaristaResponse with optional undo support
        """
        # Capture before state if undo is enabled and we have a model
        before_state = None
        if enable_undo and requests:
            # Try to extract model_id from first request
            model_id = None
            for req in requests:
                model_id = req.get("arguments", {}).get("model-id")
                if model_id:
                    break
            if model_id:
                try:
                    before_resp = self.get_model(model_id)
                    if before_resp.ok:
                        before_state = before_resp.raw.get("data")
                except Exception:
                    # If we can't get before state, undo won't work but operation continues
                    pass

        url = self.privileged_url if privileged else self.batch_url
        data = {
            "intention": "action",
            "token": self.token,
            "provided-by": self.provided_by,
            "requests": json.dumps(requests),  # stringified per Barista expectations
        }
        resp = self._client.post(url, data=data)
        resp.raise_for_status()
        raw = resp.json()

        # Create response with undo support if enabled
        if enable_undo:
            return BaristaResponse(
                raw=raw,
                _original_requests=requests.copy(),
                _client=self,
                _before_state=before_state
            )
        else:
            return BaristaResponse(raw=raw)

    # Builders
    @staticmethod
    def req_add_individual(model_id: str, class_id: str, assign_var: str = "x1") -> Dict[str, Any]:
        return {
            "entity": "individual",
            "operation": "add",
            "arguments": {
                "expressions": [{"type": "class", "id": class_id}],
                "model-id": model_id,
                "assign-to-variable": assign_var,
            },
        }

    @staticmethod
    def req_remove_individual(model_id: str, individual_id: str) -> Dict[str, Any]:
        return {
            "entity": "individual",
            "operation": "remove",
            "arguments": {
                "individual": individual_id,
                "model-id": model_id,
            },
        }

    @staticmethod
    def req_add_fact(model_id: str, subject_id: str, object_id: str, predicate_id: str) -> Dict[str, Any]:
        return {
            "entity": "edge",
            "operation": "add",
            "arguments": {
                "subject": subject_id,
                "object": object_id,
                "predicate": predicate_id,
                "model-id": model_id,
            },
        }

    @staticmethod
    def req_remove_fact(model_id: str, subject_id: str, object_id: str, predicate_id: str) -> Dict[str, Any]:
        return {
            "entity": "edge",
            "operation": "remove",
            "arguments": {
                "subject": subject_id,
                "object": object_id,
                "predicate": predicate_id,
                "model-id": model_id,
            },
        }

    @staticmethod
    def req_update_model_annotation(model_id: str, key: str, value: str, old_value: Optional[str] = None) -> Dict[str, Any]:
        """Request to update a model annotation.

        Args:
            model_id: The model ID
            key: The annotation key (e.g., 'title', 'state', 'comment')
            value: The new value for the annotation
            old_value: The current value (optional, for replacement)

        Returns:
            Request dictionary for updating model annotation
        """
        # If old_value is provided, this is a replace operation
        if old_value is not None:
            return {
                "entity": "model",
                "operation": "replace-annotation",
                "arguments": {
                    "model-id": model_id,
                    "key": key,
                    "old-value": old_value,
                    "new-value": value,
                }
            }
        else:
            # Otherwise, it's an add operation using values array format
            return {
                "entity": "model",
                "operation": "add-annotation",
                "arguments": {
                    "model-id": model_id,
                    "values": [{"key": key, "value": value}]
                }
            }

    @staticmethod
    def req_update_individual_annotation(
        model_id: str,
        individual_id: str,
        key: str,
        value: str,
        old_value: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Request to update an annotation on an individual.

        Args:
            model_id: The model ID
            individual_id: The individual to annotate
            key: The annotation key
            value: The new value for the annotation
            old_value: The current value (optional, for replacement)

        Returns:
            Request dictionary (or list of requests) for updating individual annotation
        """
        if old_value is not None:
            # Replace operation: remove old and add new
            # Since there's no replace-annotation for individuals,
            # we need to do this as two operations
            return [
                {
                    "entity": "individual",
                    "operation": "remove-annotation",
                    "arguments": {
                        "model-id": model_id,
                        "individual": individual_id,
                        "values": [{"key": key, "value": old_value}]
                    }
                },
                {
                    "entity": "individual",
                    "operation": "add-annotation",
                    "arguments": {
                        "model-id": model_id,
                        "individual": individual_id,
                        "values": [{"key": key, "value": value}]
                    }
                }
            ]
        else:
            # Add operation
            return {
                "entity": "individual",
                "operation": "add-annotation",
                "arguments": {
                    "model-id": model_id,
                    "individual": individual_id,
                    "values": [{"key": key, "value": value}]
                }
            }

    @staticmethod
    def req_remove_individual_annotation(
        model_id: str,
        individual_id: str,
        key: str,
        value: str
    ) -> Dict[str, Any]:
        """Request to remove an annotation from an individual.

        Args:
            model_id: The model ID
            individual_id: The individual ID
            key: The annotation key to remove
            value: The value to remove

        Returns:
            Request dictionary for removing individual annotation
        """
        return {
            "entity": "individual",
            "operation": "remove-annotation",
            "arguments": {
                "model-id": model_id,
                "individual": individual_id,
                "values": [{"key": key, "value": value}]
            }
        }

    @staticmethod
    def req_remove_model_annotation(model_id: str, key: str, value: str) -> Dict[str, Any]:
        """Request to remove a model annotation.

        Args:
            model_id: The model ID
            key: The annotation key to remove
            value: The value to remove (required for multi-value keys)

        Returns:
            Request dictionary for removing model annotation
        """
        return {
            "entity": "model",
            "operation": "remove-annotation",
            "arguments": {
                "model-id": model_id,
                "values": [{"key": key, "value": value}]
            }
        }

    @staticmethod
    def req_add_evidence_to_fact(
        model_id: str,
        subject_id: str,
        object_id: str,
        predicate_id: str,
        eco_id: str,
        sources: List[str],
        with_from: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compose the three-step evidence add sequence:
        1) add evidence individual
        2) add source (+ with) to evidence individual
        3) add evidence annotation to the edge

        Returns a list of requests that can be appended into the batch.
        """
        ev_var = "e1"
        reqs: List[Dict[str, Any]] = []
        # 1) evidence individual
        reqs.append(
            {
                "entity": "individual",
                "operation": "add",
                "arguments": {
                    "expressions": [{"type": "class", "id": eco_id}],
                    "model-id": model_id,
                    "assign-to-variable": ev_var,
                },
            }
        )
        # 2) add annotations to evidence individual
        values = [{"key": "source", "value": s} for s in sources]
        if with_from:
            values.extend({"key": "with", "value": w} for w in with_from)
        reqs.append(
            {
                "entity": "individual",
                "operation": "add-annotation",
                "arguments": {
                    "individual": ev_var,
                    "values": values,
                    "model-id": model_id,
                },
            }
        )
        # 3) tie evidence to edge
        reqs.append(
            {
                "entity": "edge",
                "operation": "add-annotation",
                "arguments": {
                    "subject": subject_id,
                    "object": object_id,
                    "predicate": predicate_id,
                    "values": [{"key": "evidence", "value": ev_var}],
                    "model-id": model_id,
                },
            }
        )
        return reqs

    @staticmethod
    def req_create_model(title: Optional[str] = None) -> Dict[str, Any]:
        """Request to create a new empty model.

        Args:
            title: Optional title for the model

        Returns:
            Request dictionary for model creation
        """
        arguments = {}
        if title:
            # Add title as an annotation value
            arguments["values"] = [{"key": "title", "value": title}]
        return {
            "entity": "model",
            "operation": "add",
            "arguments": arguments,
        }

    @staticmethod
    def req_get_model(model_id: str) -> Dict[str, Any]:
        return {
            "entity": "model",
            "operation": "get",
            "arguments": {
                "model-id": model_id,
            },
        }

    @staticmethod
    def req_export_model(model_id: str, format: str = "owl") -> Dict[str, Any]:
        """Request to export a model in a specific format.

        Args:
            model_id: The model to export
            format: Export format (owl, ttl, json-ld, etc.)
        """
        return {
            "entity": "model",
            "operation": "export",
            "arguments": {
                "model-id": model_id,
                "format": format,
            },
        }


    # High-level convenience
    def create_model(self, title: Optional[str] = None) -> BaristaResponse:
        """Create a new empty model.

        Args:
            title: Optional title for the model

        Returns:
            BaristaResponse containing the new model ID
        """
        req = self.req_create_model(title)
        return self.m3_batch([req])

    def add_individual(self, model_id: str, class_curie: str, assign_var: str = "x1", enable_undo: bool = False) -> BaristaResponse:
        """Add an individual to the model and optionally track its variable.

        If track_variables is enabled, this will diff the model before/after
        to identify the new individual and map it to the variable name.

        Args:
            model_id: The model ID
            class_curie: The class/type for the individual (e.g., "GO:0003924")
            assign_var: Variable name to assign (if track_variables is enabled)
            enable_undo: If True, the returned response will support undo()

        Returns:
            BaristaResponse that may support undo() if enable_undo=True
        """
        # Take snapshot before operation if tracking is enabled
        before_state = None
        if self.track_variables and assign_var:
            before_state = self._snapshot_model(model_id)

        req = self.req_add_individual(model_id, class_curie, assign_var)
        response = self.m3_batch([req], enable_undo=enable_undo)

        # Track the new individual if successful
        if before_state is not None and response.ok:
            self._track_new_individual(model_id, before_state, response, assign_var)

        return response

    def remove_individual(self, model_id: str, individual_id: str) -> BaristaResponse:
        """Remove an individual, resolving variables to actual IDs."""
        resolved_id = self._resolve_identifier(model_id, individual_id)
        req = self.req_remove_individual(model_id, resolved_id)
        return self.m3_batch([req])

    def delete_individual(self, model_id: str, individual_id: str) -> BaristaResponse:
        """Delete an individual from the model.

        Alias for remove_individual for consistency.
        Individual ID can be a variable name, CURIE, or full ID.

        Args:
            model_id: The model ID
            individual_id: The individual ID or variable name to delete

        Returns:
            BaristaResponse from the API
        """
        return self.remove_individual(model_id, individual_id)

    def add_fact(
        self, model_id: str, subject_id: str, object_id: str, predicate_id: str, enable_undo: bool = False
    ) -> BaristaResponse:
        """Add a fact (edge) between two individuals.

        Subject and object can be either:
        - Variable names (e.g., "ras", "kinase")
        - CURIEs (e.g., "GO:0003924")
        - Full IDs (e.g., "gomodel:xxx/individual-123")

        Variables are automatically resolved to their actual IDs.

        Args:
            model_id: The model ID
            subject_id: Subject individual (variable, CURIE, or ID)
            object_id: Object individual (variable, CURIE, or ID)
            predicate_id: The relation/predicate (e.g., "RO:0002413")
            enable_undo: If True, the returned response will support undo()

        Returns:
            BaristaResponse that may support undo() if enable_undo=True
        """
        # Resolve variables to actual IDs
        resolved_subject = self._resolve_identifier(model_id, subject_id)
        resolved_object = self._resolve_identifier(model_id, object_id)

        req = self.req_add_fact(model_id, resolved_subject, resolved_object, predicate_id)
        return self.m3_batch([req], enable_undo=enable_undo)

    def remove_fact(
        self, model_id: str, subject_id: str, object_id: str, predicate_id: str, enable_undo: bool = False
    ) -> BaristaResponse:
        """Remove a fact, resolving variables to actual IDs."""
        resolved_subject = self._resolve_identifier(model_id, subject_id)
        resolved_object = self._resolve_identifier(model_id, object_id)
        req = self.req_remove_fact(model_id, resolved_subject, resolved_object, predicate_id)
        return self.m3_batch([req], enable_undo=enable_undo)

    def delete_edge(
        self, model_id: str, subject_id: str, object_id: str, predicate_id: str
    ) -> BaristaResponse:
        """Delete an edge (fact) from the model.

        Alias for remove_fact for consistency.
        Subject and object can be variables, CURIEs, or full IDs.

        Args:
            model_id: The model ID
            subject_id: Subject individual ID or variable name
            object_id: Object individual ID or variable name
            predicate_id: Predicate (relation) ID

        Returns:
            BaristaResponse from the API
        """
        return self.remove_fact(model_id, subject_id, object_id, predicate_id)

    def add_fact_with_evidence(
        self,
        model_id: str,
        subject_id: str,
        object_id: str,
        predicate_id: str,
        eco_id: str,
        sources: List[str],
        with_from: Optional[List[str]] = None,
        enable_undo: bool = False,
    ) -> BaristaResponse:
        """Add a fact with evidence, resolving variables to actual IDs.

        Subject and object can be variables, CURIEs, or full IDs.
        """
        # Resolve variables to actual IDs
        resolved_subject = self._resolve_identifier(model_id, subject_id)
        resolved_object = self._resolve_identifier(model_id, object_id)

        reqs = [self.req_add_fact(model_id, resolved_subject, resolved_object, predicate_id)]
        reqs.extend(
            self.req_add_evidence_to_fact(
                model_id, resolved_subject, resolved_object, predicate_id, eco_id, sources, with_from
            )
        )
        return self.m3_batch(reqs, enable_undo=enable_undo)

    def get_model(self, model_id: str) -> BaristaResponse:
        req = self.req_get_model(model_id)
        return self.m3_batch([req])

    def export_model(self, model_id: str, format: str = "owl") -> BaristaResponse:
        """Export a model in the specified format.

        Args:
            model_id: The model to export
            format: Export format (owl, ttl, json-ld, gaf, markdown, etc.)

        Returns:
            BaristaResponse containing the exported model data
        """
        # Handle markdown format specially
        if format == "markdown":
            return self._export_as_markdown(model_id)

        req = self.req_export_model(model_id, format)
        return self.m3_batch([req])

    def _export_as_markdown(self, model_id: str) -> BaristaResponse:
        """Export model as human-readable markdown.

        Args:
            model_id: The model to export

        Returns:
            BaristaResponse with markdown content
        """
        # Get the model JSON
        resp = self.get_model(model_id)
        if not resp.ok:
            return resp

        data = resp.raw.get("data", {})

        # Build markdown document
        lines = []

        # Title and metadata
        title = "Untitled Model"
        state = None
        comments = []

        # Extract model annotations
        for ann in data.get("annotations", []):
            key = ann.get("key", "")
            value = ann.get("value", "")
            if key == "title":
                title = value
            elif key == "state":
                state = value
            elif key == "comment":
                comments.append(value)

        lines.append(f"# {title}")
        lines.append("")

        # Model metadata
        lines.append("## Model Information")
        lines.append("")
        lines.append(f"- **Model ID**: `{model_id}`")
        if state:
            lines.append(f"- **State**: {state}")
        if comments:
            lines.append(f"- **Comments**: {'; '.join(comments)}")
        lines.append("")

        # Individuals/Activities
        individuals = data.get("individuals", [])
        if individuals:
            lines.append("## Activities and Entities")
            lines.append("")

            # Group individuals by their primary type
            for ind in individuals:
                ind_id = ind.get("id", "unknown")

                # Get the main type
                types = ind.get("type", [])
                if types:
                    main_type = types[0]
                    type_id = main_type.get("id", "unknown")
                    type_label = main_type.get("label", type_id)
                else:
                    type_id = "unknown"
                    type_label = "Unknown type"

                # Get annotations
                annotations: Dict[str, List[str]] = {}
                for ann in ind.get("annotations", []):
                    key = ann.get("key", "")
                    value = ann.get("value", "")
                    if key not in annotations:
                        annotations[key] = []
                    annotations[key].append(value)

                # Format individual
                lines.append(f"### {type_label}")
                lines.append(f"- **ID**: `{ind_id}`")
                lines.append(f"- **Type**: [{type_label}]({type_id})")

                # Show enabled_by if present
                if "enabled_by" in annotations:
                    for val in annotations["enabled_by"]:
                        lines.append(f"- **Enabled by**: {val}")

                # Show label if present
                if "rdfs:label" in annotations:
                    for val in annotations["rdfs:label"]:
                        lines.append(f"- **Label**: {val}")

                # Show other annotations
                skip_keys = {"enabled_by", "rdfs:label"}
                for key, values in annotations.items():
                    if key not in skip_keys:
                        for val in values:
                            lines.append(f"- **{key}**: {val}")

                lines.append("")

        # Facts/Relationships
        facts = data.get("facts", [])
        if facts:
            lines.append("## Relationships")
            lines.append("")

            # Group facts by predicate type
            fact_groups: Dict[str, List[Dict[str, Any]]] = {}
            for fact in facts:
                subject = fact.get("subject", "")
                object = fact.get("object", "")
                predicate = fact.get("predicate", {})
                pred_id = predicate.get("id", "unknown")
                pred_label = predicate.get("label", pred_id)

                if pred_label not in fact_groups:
                    fact_groups[pred_label] = []

                # Find subject and object labels
                subj_label = self._find_individual_label(individuals, subject)
                obj_label = self._find_individual_label(individuals, object)

                # Get evidence annotations
                evidence = []
                for ann in fact.get("annotations", []):
                    key = ann.get("key", "")
                    value = ann.get("value", "")
                    if key == "evidence":
                        evidence.append(value)

                fact_groups[pred_label].append({
                    "subject": subj_label,
                    "object": obj_label,
                    "subject_id": subject,
                    "object_id": object,
                    "evidence": evidence
                })

            # Output facts by group
            for pred_label, facts_list in fact_groups.items():
                lines.append(f"### {pred_label}")
                lines.append("")

                for fact_info in facts_list:
                    lines.append(f"- **{fact_info['subject']}** → **{fact_info['object']}**")
                    if fact_info['evidence']:
                        for ev in fact_info['evidence']:
                            lines.append(f"  - Evidence: {ev}")
                lines.append("")

        # Create response with markdown content
        markdown_content = "\n".join(lines)

        # Create a response that mimics the export format
        export_response = BaristaResponse(
            raw={
                "message-type": "success",
                "data": markdown_content
            }
        )

        return export_response

    def _find_individual_label(self, individuals: List[Dict], ind_id: str) -> str:
        """Find a readable label for an individual.

        Args:
            individuals: List of individuals from the model
            ind_id: The individual ID to look up

        Returns:
            A readable label for the individual
        """
        for ind in individuals:
            if ind.get("id") == ind_id:
                # Try to get rdfs:label first
                for ann in ind.get("annotations", []):
                    if ann.get("key") == "rdfs:label":
                        return ann.get("value", ind_id)

                # Otherwise use the type label
                types = ind.get("type", [])
                if types:
                    return types[0].get("label", ind_id)

        return ind_id

    def list_models(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        title: Optional[str] = None,
        state: Optional[str] = None,
        contributor: Optional[str] = None,
        group: Optional[str] = None,
        pmid: Optional[str] = None,
        gp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all models using the search endpoint.

        Args:
            limit: Optional limit on number of models to return (default: 50)
            offset: Offset for pagination (default: 0)
            title: Optional title filter (searches for models containing this text)
            state: Optional state filter (e.g., 'production', 'development', 'internal_test')
            contributor: Optional contributor filter (ORCID URL, e.g., 'https://orcid.org/0000-0002-6601-2165')
            group: Optional group/provider filter (e.g., 'http://www.wormbase.org')
            pmid: Optional PubMed ID filter (e.g., 'PMID:12345678')
            gp: Optional gene product filter (e.g., 'UniProtKB:Q9BRQ8', 'MGI:MGI:97490')

        Returns:
            Dict containing the search results with models

        Raises:
            BaristaError: If the request fails
        """
        # Use search endpoint instead of m3Batch
        search_url = f"{self.base_url}/search/models"

        params: Dict[str, Any] = {
            "offset": offset,
            "limit": limit or 50,
            "expand": "",  # Include expanded information
        }

        # Add optional filters
        if title:
            params["title"] = title
        if state:
            params["state"] = state
        if contributor:
            params["contributor"] = contributor
        if group:
            params["group"] = group
        if pmid:
            params["pmid"] = pmid
        if gp:
            params["gp"] = gp

        resp = self._client.get(search_url, params=params)
        resp.raise_for_status()
        return resp.json()

    def update_model_metadata(
        self,
        model_id: str,
        title: Optional[str] = None,
        state: Optional[str] = None,
        comment: Optional[str] = None,
        replace: bool = True
    ) -> BaristaResponse:
        """Update model metadata (title, state, comment).

        Args:
            model_id: The model ID
            title: New title for the model
            state: New state (e.g., 'production', 'development', 'internal_test')
            comment: New comment for the model
            replace: If True, replaces existing values; if False, adds new values

        Returns:
            BaristaResponse from the API
        """
        requests = []

        # Get current model to find existing values if replacing
        current_annotations: Dict[str, List[str]] = {}
        if replace:
            resp = self.get_model(model_id)
            if resp.ok:
                data = resp.raw.get("data", {})
                for ann in data.get("annotations", []):
                    key = ann.get("key")
                    value = ann.get("value")
                    if key in ["title", "state", "comment"]:
                        if key not in current_annotations:
                            current_annotations[key] = []
                        current_annotations[key].append(value)

        # Update title
        if title is not None:
            if replace and "title" in current_annotations:
                # Replace existing title(s)
                for old_title in current_annotations["title"]:
                    requests.append(
                        self.req_update_model_annotation(model_id, "title", title, old_title)
                    )
                    break  # Only replace the first one
            else:
                # Add new title
                requests.append(
                    self.req_update_model_annotation(model_id, "title", title)
                )

        # Update state
        if state is not None:
            if replace and "state" in current_annotations:
                # Replace existing state(s)
                for old_state in current_annotations["state"]:
                    requests.append(
                        self.req_update_model_annotation(model_id, "state", state, old_state)
                    )
                    break  # Only replace the first one
            else:
                # Add new state
                requests.append(
                    self.req_update_model_annotation(model_id, "state", state)
                )

        # Update comment
        if comment is not None:
            if replace and "comment" in current_annotations:
                # Replace existing comment(s)
                for old_comment in current_annotations["comment"]:
                    requests.append(
                        self.req_update_model_annotation(model_id, "comment", comment, old_comment)
                    )
                    break  # Only replace the first one
            else:
                # Add new comment
                requests.append(
                    self.req_update_model_annotation(model_id, "comment", comment)
                )

        if not requests:
            raise BaristaError("No metadata updates specified")

        return self.m3_batch(requests)

    def add_model_annotation(
        self,
        model_id: str,
        key: str,
        value: str
    ) -> BaristaResponse:
        """Add a single annotation to the model.

        Args:
            model_id: The model ID
            key: The annotation key
            value: The annotation value

        Returns:
            BaristaResponse from the API
        """
        req = self.req_update_model_annotation(model_id, key, value)
        return self.m3_batch([req])

    def remove_model_annotation(
        self,
        model_id: str,
        key: str,
        value: str
    ) -> BaristaResponse:
        """Remove a specific annotation from the model.

        Args:
            model_id: The model ID
            key: The annotation key
            value: The specific value to remove

        Returns:
            BaristaResponse from the API
        """
        req = self.req_remove_model_annotation(model_id, key, value)
        return self.m3_batch([req])

    def execute_with_validation(
        self,
        requests: List[Dict[str, Any]],
        expected_individuals: Optional[List[Dict[str, str]]] = None,
        expected_facts: Optional[List[Dict[str, str]]] = None,
        privileged: bool = True
    ) -> BaristaResponse:
        """Execute requests with validation and automatic rollback on failure.

        This method executes a batch of requests with undo enabled, then validates
        the result against expected conditions. If validation fails, it automatically
        rolls back the changes.

        Args:
            requests: List of request dictionaries to execute
            expected_individuals: List of expected individual types after execution
                                e.g., [{"id": "GO:0004672", "label": "protein kinase activity"}]
            expected_facts: List of expected facts (not yet implemented)
            privileged: Whether to use the privileged endpoint

        Returns:
            BaristaResponse - either the successful response or the rollback response
            Check response.validation_failed to determine if rollback occurred

        Example:
            >>> # req = client.req_add_individual(model_id, "GO:0003924")
            >>> # response = client.execute_with_validation(
            >>> #     [req],
            >>> #     expected_individuals=[{"id": "GO:0003924"}]
            >>> # )
            >>> # if response.validation_failed:
            >>> #     print(f"Rolled back: {response.validation_reason}")
            ... # doctest: +SKIP
        """
        # Always enable undo for validation
        response = self.m3_batch(requests, privileged=privileged, enable_undo=True)

        if not response.ok:
            return response  # Operation failed, no validation needed

        # Perform validation checks
        if expected_individuals:
            response = response.validate_and_rollback(
                expected_individuals,
                validation_type="individuals"
            )

        if expected_facts and not response.validation_failed:
            # TODO: Implement fact validation
            pass

        return response

    def add_individual_validated(
        self,
        model_id: str,
        class_curie: str,
        expected_type: Optional[Dict[str, str]] = None,
        assign_var: str = "x1"
    ) -> BaristaResponse:
        """Add an individual with validation that it was created with the expected type.

        Args:
            model_id: The model ID
            class_curie: The class/type for the individual
            expected_type: Expected type dict with 'id' and/or 'label'
                         If not provided, validates against class_curie
            assign_var: Variable name to assign

        Returns:
            BaristaResponse - rolls back automatically if validation fails
        """
        if expected_type is None:
            expected_type = {"id": class_curie}

        req = self.req_add_individual(model_id, class_curie, assign_var)
        return self.execute_with_validation(
            [req],
            expected_individuals=[expected_type]
        )

    def update_individual_annotation(
        self,
        model_id: str,
        individual_id: str,
        key: str,
        value: str,
        old_value: Optional[str] = None,
        validation: Optional[Dict[str, str]] = None,
    ) -> BaristaResponse:
        """Update an annotation on an individual with optional validation.

        Args:
            model_id: The model ID
            individual_id: The individual to annotate
            key: The annotation key (e.g., 'rdfs:label', 'enabled_by')
            value: The new value for the annotation
            old_value: The current value (for replacement)
            validation: Optional validation dict with 'id' and/or 'label'
                       to verify the individual before updating

        Returns:
            BaristaResponse - rolls back automatically if validation fails

        Example:
            >>> # Update contributor with validation
            >>> # response = client.update_individual_annotation(
            >>> #     model_id,
            >>> #     individual_id,
            >>> #     "contributor",
            >>> #     "https://orcid.org/0000-0002-6601-2165",
            >>> #     validation={"id": individual_id, "label": "GTPase activity"}
            >>> # )
            >>> # if response.validation_failed:
            >>> #     print(f"Wrong individual! Expected label 'GTPase activity'")
            ... # doctest: +SKIP
        """
        req_result = self.req_update_individual_annotation(
            model_id, individual_id, key, value, old_value
        )

        # req_result can be either a single request or a list of requests
        requests = req_result if isinstance(req_result, list) else [req_result]

        if validation:
            return self.execute_with_validation(
                requests,
                expected_individuals=[validation]
            )
        else:
            return self.m3_batch(requests)

    def remove_individual_annotation(
        self,
        model_id: str,
        individual_id: str,
        key: str,
        value: str,
        validation: Optional[Dict[str, str]] = None,
    ) -> BaristaResponse:
        """Remove an annotation from an individual with optional validation.

        Args:
            model_id: The model ID
            individual_id: The individual ID
            key: The annotation key to remove
            value: The value to remove
            validation: Optional validation dict with 'id' and/or 'label'
                       to verify the individual before removing

        Returns:
            BaristaResponse - rolls back automatically if validation fails
        """
        req = self.req_remove_individual_annotation(
            model_id, individual_id, key, value
        )

        if validation:
            return self.execute_with_validation(
                [req],
                expected_individuals=[validation]
            )
        else:
            return self.m3_batch([req])

    def clear_model(self, model_id: str, force: bool = False) -> BaristaResponse:
        """Clear all nodes and edges from a model.

        First retrieves the model to get all individuals and facts,
        then removes them all in a batch operation.

        Args:
            model_id: The model to clear
            force: If True, bypass production state check (use with extreme caution)

        Raises:
            BaristaError: If the model is in production state (unless force=True)
        """
        # Get the current model state
        model_resp = self.get_model(model_id)
        if not model_resp.ok:
            raise BaristaError(f"Failed to get model {model_id}: {model_resp.raw}")

        # Check if model is in production state
        if not force and model_resp.model_state == "production":
            raise BaristaError(
                f"Model {model_id} is in production state and cannot be cleared. "
                "Production models are protected from accidental deletion. "
                "If you really need to clear a production model, use force=True (dangerous!)"
            )

        requests = []

        # Remove all facts/edges first (before removing individuals)
        for fact in model_resp.facts:
            subject = fact.get("subject")
            object_ = fact.get("object")
            predicate = fact.get("property")
            if subject and object_ and predicate:
                requests.append(self.req_remove_fact(model_id, subject, object_, predicate))

        # Remove all individuals
        for individual in model_resp.individuals:
            individual_id = individual.get("id")
            if individual_id:
                requests.append(self.req_remove_individual(model_id, individual_id))

        if not requests:
            # Model is already empty
            return BaristaResponse(raw={"message-type": "success", "signal": "merge", "data": {"id": model_id}})

        return self.m3_batch(requests)

    def find_evidence_for_edge(
        self,
        model_id: str,
        subject_id: str,
        object_id: str,
        predicate: str,
        amigo_base_url: Optional[str] = None,
        evidence_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Find GO annotation evidence that could support an edge in a GO-CAM model.

        Uses the standard GO-CAM to GAF mapping logic:
        - enabled_by edges: Look for MF annotations on the bioentity
        - activity->process edges: Look for BP annotations on the activity's enabled_by bioentity
        - activity->location edges: Look for CC annotations on the activity's enabled_by bioentity

        Args:
            model_id: The model ID
            subject_id: Subject individual ID (can be variable name)
            object_id: Object individual ID (can be variable name)
            predicate: The predicate/relation (e.g., "RO:0002333" for enabled_by)
            amigo_base_url: Optional custom GOlr endpoint
            evidence_types: Optional list of evidence codes to filter (e.g., ["IDA", "IPI"])
            limit: Maximum number of annotations to return per query

        Returns:
            Dictionary with found evidence:
            {
                "edge": {"subject": ..., "object": ..., "predicate": ...},
                "mapping_type": "enabled_by"|"activity_to_process"|"activity_to_location"|"unknown",
                "annotations": [list of AnnotationResult objects as dicts],
                "summary": "Human-readable summary"
            }
        """
        from .amigo import AmigoClient

        # Get the model to resolve variables and get types
        model_resp = self.get_model(model_id)
        if not model_resp.ok:
            raise BaristaError(f"Failed to get model: {model_resp.raw}")

        # Resolve subject and object IDs
        subject = self._resolve_individual(model_resp, subject_id)
        object_ = self._resolve_individual(model_resp, object_id)

        if not subject or not object_:
            return {
                "edge": {"subject": subject_id, "object": object_id, "predicate": predicate},
                "mapping_type": "unknown",
                "annotations": [],
                "summary": "Could not resolve individual IDs"
            }

        # Initialize Amigo client
        amigo = AmigoClient(base_url=amigo_base_url)

        # Determine the mapping type and search strategy
        annotations = []
        mapping_type = "unknown"
        bioentity_id = None
        go_term = None
        aspect = None

        # Check for enabled_by relationship (RO:0002333)
        if predicate in ["RO:0002333", "http://purl.obolibrary.org/obo/RO_0002333"]:
            mapping_type = "enabled_by"
            # Subject should be a molecular function, object should be a bioentity
            # Look for MF annotations on the bioentity

            # Get bioentity ID from object annotations
            for ann in object_.get("annotations", []):
                if ann.get("key") == "id":
                    bioentity_id = ann.get("value")
                    break

            # Get GO term from subject type
            subject_type = subject.get("type", {})
            if subject_type:
                go_term = subject_type.get("id")
                aspect = "F"  # Molecular Function

        # Check for activity->process relationship (RO:0002211, RO:0002212, RO:0002213, RO:0002578, etc.)
        elif predicate in [
            "RO:0002211", "http://purl.obolibrary.org/obo/RO_0002211",  # regulates
            "RO:0002212", "http://purl.obolibrary.org/obo/RO_0002212",  # negatively regulates
            "RO:0002213", "http://purl.obolibrary.org/obo/RO_0002213",  # positively regulates
            "RO:0002578", "http://purl.obolibrary.org/obo/RO_0002578",  # directly regulates
            "BFO:0000066", "http://purl.obolibrary.org/obo/BFO_0000066",  # occurs in
            "RO:0002234", "http://purl.obolibrary.org/obo/RO_0002234",  # has output
            "RO:0002233", "http://purl.obolibrary.org/obo/RO_0002233",  # has input
        ]:
            # Determine if object is a process or location
            object_type = object_.get("type", {})
            object_type_id = object_type.get("id", "")
            object_label = object_type.get("label", "").lower()

            # Better heuristic: check the label for process vs location keywords
            # Process terms often contain: process, regulation, pathway, signaling, metabolism, etc.
            # Location terms often contain: membrane, complex, nucleus, cytoplasm, organelle, etc.
            process_keywords = ["process", "regulation", "pathway", "signal", "metabolism",
                              "transport", "biosynthesis", "catabolism", "response"]
            location_keywords = ["membrane", "complex", "nucleus", "cytoplasm", "organelle",
                               "vesicle", "ribosome", "chromosome", "mitochondri", "golgi",
                               "reticulum", "peroxisome", "lysosome", "cytoskeleton"]

            if any(keyword in object_label for keyword in process_keywords):
                mapping_type = "activity_to_process"
                aspect = "P"  # Biological Process
            elif any(keyword in object_label for keyword in location_keywords):
                mapping_type = "activity_to_location"
                aspect = "C"  # Cellular Component
            else:
                # Default to process if unclear
                mapping_type = "activity_to_process"
                aspect = "P"  # Biological Process

            # Get the bioentity that enables the subject activity
            for ann in subject.get("annotations", []):
                if ann.get("key") == "enabled_by":
                    bioentity_id = ann.get("value")
                    break

            # Get GO term from object type
            go_term = object_type_id

        # Check for activity->location relationship (BFO:0000066 occurs_in)
        elif predicate in ["BFO:0000066", "http://purl.obolibrary.org/obo/BFO_0000066"]:
            mapping_type = "activity_to_location"
            aspect = "C"  # Cellular Component

            # Get the bioentity that enables the subject activity
            for ann in subject.get("annotations", []):
                if ann.get("key") == "enabled_by":
                    bioentity_id = ann.get("value")
                    break

            # Get GO term from object type
            object_type = object_.get("type", {})
            go_term = object_type.get("id")

        # If we have enough information, search for annotations
        if bioentity_id and go_term:
            try:
                results = amigo.search_annotations(
                    bioentity=bioentity_id,
                    go_term=go_term,  # Uses isa_partof_closure for hierarchical search
                    aspect=aspect,
                    evidence_types=evidence_types,
                    limit=limit
                )

                # Convert to dicts for JSON serialization
                annotations = [
                    {
                        "bioentity": r.bioentity,
                        "bioentity_label": r.bioentity_label,
                        "annotation_class": r.annotation_class,
                        "annotation_class_label": r.annotation_class_label,
                        "evidence_type": r.evidence_type,
                        "reference": r.reference,
                        "assigned_by": r.assigned_by,
                        "date": r.date,
                        "qualifier": r.qualifier,
                        "with": r.gene_product_form_id
                    }
                    for r in results
                ]
            except Exception:
                annotations = []

        # Create summary
        summary = f"Found {len(annotations)} annotations"
        if mapping_type == "enabled_by":
            summary = f"Found {len(annotations)} MF annotations for {bioentity_id or 'unknown bioentity'} with {go_term or 'unknown function'}"
        elif mapping_type == "activity_to_process":
            summary = f"Found {len(annotations)} BP annotations for {bioentity_id or 'unknown bioentity'} with {go_term or 'unknown process'}"
        elif mapping_type == "activity_to_location":
            summary = f"Found {len(annotations)} CC annotations for {bioentity_id or 'unknown bioentity'} with {go_term or 'unknown location'}"

        return {
            "edge": {
                "subject": subject.get("id"),
                "subject_label": subject.get("type", {}).get("label"),
                "object": object_.get("id"),
                "object_label": object_.get("type", {}).get("label"),
                "predicate": predicate
            },
            "mapping_type": mapping_type,
            "search_params": {
                "bioentity": bioentity_id,
                "go_term": go_term,
                "aspect": aspect
            },
            "annotations": annotations,
            "summary": summary
        }

    def find_evidence_for_model(
        self,
        model_id: str,
        amigo_base_url: Optional[str] = None,
        evidence_types: Optional[List[str]] = None,
        limit_per_edge: int = 10
    ) -> Dict[str, Any]:
        """Find GO annotation evidence for all edges in a GO-CAM model.

        Args:
            model_id: The model ID
            amigo_base_url: Optional custom GOlr endpoint
            evidence_types: Optional list of evidence codes to filter (e.g., ["IDA", "IPI"])
            limit_per_edge: Maximum number of annotations to return per edge

        Returns:
            Dictionary with evidence for all edges:
            {
                "model_id": "...",
                "edges_with_evidence": [list of edge evidence dicts],
                "total_annotations": total count,
                "summary": "Human-readable summary"
            }
        """
        # Get the model
        model_resp = self.get_model(model_id)
        if not model_resp.ok:
            raise BaristaError(f"Failed to get model: {model_resp.raw}")

        edges_with_evidence = []
        total_annotations = 0

        # Process each fact/edge in the model
        for fact in model_resp.facts:
            subject = fact.get("subject")
            object_ = fact.get("object")
            predicate = fact.get("property")

            if subject and object_ and predicate:
                edge_evidence = self.find_evidence_for_edge(
                    model_id,
                    subject,
                    object_,
                    predicate,
                    amigo_base_url=amigo_base_url,
                    evidence_types=evidence_types,
                    limit=limit_per_edge
                )

                # Only include edges that have evidence or are of known mapping types
                if edge_evidence["annotations"] or edge_evidence["mapping_type"] != "unknown":
                    edges_with_evidence.append(edge_evidence)
                    total_annotations += len(edge_evidence["annotations"])

        # Create summary
        edges_with_annotations = sum(1 for e in edges_with_evidence if e["annotations"])
        summary = (
            f"Found {total_annotations} total annotations supporting "
            f"{edges_with_annotations} of {len(edges_with_evidence)} relevant edges"
        )

        # Get model title from data
        model_title = model_resp.raw.get("data", {}).get("title", "")

        return {
            "model_id": model_id,
            "model_title": model_title,
            "edges_with_evidence": edges_with_evidence,
            "total_annotations": total_annotations,
            "summary": summary
        }

    def _resolve_individual(self, model_resp: BaristaResponse, individual_id: str) -> Optional[Dict[str, Any]]:
        """Resolve an individual ID (which might be a variable name) to the actual individual.

        Args:
            model_resp: The model response containing individuals
            individual_id: The individual ID or variable name

        Returns:
            The individual dict, or None if not found
        """
        # First try direct ID match
        for individual in model_resp.individuals:
            if individual.get("id") == individual_id:
                return individual

        # Then try variable name match
        if hasattr(self, '_variables') and individual_id in self._variables:
            resolved_id = self._variables[individual_id]
            for individual in model_resp.individuals:
                if individual.get("id") == resolved_id:
                    return individual

        return None
