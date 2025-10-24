from __future__ import annotations

import os
import json
import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union, Tuple

import httpx

from .models import (
    AddIndividualRequest,
    AddIndividualArguments,
    RemoveIndividualRequest,
    RemoveIndividualArguments,
    AddEdgeRequest,
    AddEdgeArguments,
    RemoveEdgeRequest,
    RemoveEdgeArguments,
    AddIndividualAnnotationRequest,
    AddIndividualAnnotationArguments,
    RemoveIndividualAnnotationRequest,
    RemoveIndividualAnnotationArguments,
    CreateModelRequest,
    CreateModelArguments,
    GetModelRequest,
    GetModelArguments,
    ExportModelRequest,
    ExportModelArguments,
    AddModelAnnotationRequest,
    AddModelAnnotationArguments,
    RemoveModelAnnotationRequest,
    RemoveModelAnnotationArguments,
    ReplaceModelAnnotationRequest,
    ReplaceModelAnnotationArguments,
    Expression,
    AnnotationValue,
    ProteinComplexComponent,
    EntitySetMember,
    MinervaRequest,
    ModelData,
    Individual,
    Fact,
    TypeInfo,
)

logger = logging.getLogger(__name__)

# Default to test/dev server for safety
DEFAULT_BARISTA_BASE = os.environ.get("BARISTA_BASE", "http://barista-dev.berkeleybop.org")
DEFAULT_NAMESPACE = os.environ.get("BARISTA_NAMESPACE", "minerva_public_dev")
DEFAULT_PROVIDED_BY = os.environ.get("BARISTA_PROVIDED_BY", "http://geneontology.org")

# Production/live server settings
LIVE_BARISTA_BASE = os.environ.get("BARISTA_LIVE_BASE", "http://barista.berkeleybop.org")
LIVE_NAMESPACE = os.environ.get("BARISTA_LIVE_NAMESPACE", "minerva_public")

BARISTA_TOKEN_ENV = "BARISTA_TOKEN"


class BaristaError(Exception):
    """Base exception for Barista client errors."""
    pass


class BatchExecutionError(BaristaError):
    """Raised when a request in a batch fails at the API level."""

    def __init__(
        self,
        message: str,
        executed_requests: List['MinervaRequest'],
        failed_request: 'MinervaRequest',
        failed_response: 'BaristaResponse'
    ):
        super().__init__(message)
        self.executed_requests = executed_requests
        self.failed_request = failed_request
        self.failed_response = failed_response


class BatchValidationError(BaristaError):
    """Raised when a request in a batch fails validation."""

    def __init__(
        self,
        message: str,
        executed_requests: List['MinervaRequest'],
        failed_request: 'MinervaRequest',
        validation_reason: str
    ):
        super().__init__(message)
        self.executed_requests = executed_requests
        self.failed_request = failed_request
        self.validation_reason = validation_reason


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
    failed_request_index: Optional[int] = None  # Index of the failed request in a batch
    model_vars: Dict[str, str] = field(default_factory=dict)
    _original_requests: Optional[List[Dict[str, Any]]] = None
    _client: Optional['BaristaClient'] = None
    _before_state: Optional[Dict[str, Any]] = None
    _parsed_data: Optional[ModelData] = None  # Cached parsed response data

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
    def data(self) -> ModelData:
        """Get parsed model data from the response.

        Returns:
            Pydantic ModelData object with typed access to individuals, facts, etc.

        Examples:
            >>> # Access individuals with full type safety
            >>> # for individual in response.data.individuals:
            >>> #     print(f"ID: {individual.id}")
            >>> #     for type_info in individual.type:
            >>> #         print(f"  Type: {type_info.id} - {type_info.label}")
            ... # doctest: +SKIP
        """
        if self._parsed_data is None:
            raw_data = self.raw.get("data") or {}
            self._parsed_data = ModelData.model_validate(raw_data)
        return self._parsed_data

    @property
    def model_id(self) -> Optional[str]:
        """Get the model ID from the response."""
        return self.data.id

    @property
    def individuals(self) -> List[Individual]:
        """Get the list of individuals from the response.

        Returns:
            List of Individual objects with typed access
        """
        return self.data.individuals

    @property
    def facts(self) -> List[Fact]:
        """Get the list of facts/edges from the response.

        Returns:
            List of Fact objects with typed access
        """
        return self.data.facts

    @property
    def model_state(self) -> Optional[str]:
        """Get the model state (e.g., 'production', 'development')."""
        return self.data.get_state()

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

        # Use typed Pydantic models instead of dicts
        individuals = self.individuals
        mismatches = []

        for expected_item in expected:
            expected_id = expected_item.get("id")
            expected_label = expected_item.get("label")

            # Check if this is an individual ID (like gomodel:123/ind456) or a type ID (like GO:0003924)
            is_individual_id = expected_id and ("/" in expected_id or expected_id.startswith("gomodel:"))

            found = False
            closest_matches: List[TypeInfo] = []
            target_individual: Optional[Individual] = None
            available_individual_ids: List[str] = []

            if is_individual_id:
                # Individual-based validation: check if the specific individual has the expected type label
                for individual in individuals:
                    if individual.id == expected_id:
                        target_individual = individual
                        break

                if target_individual:
                    for type_info in target_individual.type:
                        if not expected_label or type_info.label == expected_label:
                            found = True
                            break
                        else:
                            # Collect all types for this individual for better error reporting
                            closest_matches.append(type_info)

                if not target_individual:
                    # Individual ID not found
                    available_individual_ids = [ind.id for ind in individuals]
            else:
                # Type-based validation: check if any individual has this type
                for individual in individuals:
                    for type_info in individual.type:
                        # Check ID match
                        id_match = not expected_id or type_info.id == expected_id
                        # Check label match
                        label_match = not expected_label or type_info.label == expected_label

                        if id_match and label_match:
                            found = True
                            break

                        # Collect potential matches for better error reporting
                        if expected_id and type_info.id == expected_id:
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
                            actual_labels = [t.label or "unknown" for t in closest_matches]
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
                        mismatch_info["actual"] = {"id": actual_match.id, "label": actual_match.label}
                        if expected_label:
                            mismatch_info["details"] = f"Expected label '{expected_label}' but found '{actual_match.label or 'unknown'}' for ID {expected_id}"
                        else:
                            mismatch_info["details"] = f"Found ID {expected_id} with label '{actual_match.label or 'unknown'}'"
                    else:
                        # No matching ID found at all
                        available_ids = []
                        for individual in individuals:
                            for type_info in individual.type:
                                if type_info.id:
                                    available_ids.append(f"{type_info.id} ({type_info.label or 'no label'})")

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
        # For atomic batch operations: maps model_id -> {variable_name: actual_id}
        self._variable_map: Dict[str, Dict[str, str]] = {}
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
        """Take a snapshot of the current model state.

        Returns the full data structure (not just IDs) for validation and rollback.
        """
        response = self.get_model(model_id)
        if response.ok:
            return response.raw.get("data", {})
        return {"individuals": [], "facts": []}

    def _track_new_individual(self, model_id: str, before_state: Dict[str, Any],
                             after_response: BaristaResponse, variable: str) -> Optional[str]:
        """Track a new individual by diffing before/after states."""
        if not after_response.ok or not self.track_variables:
            return None

        after_data = after_response.raw.get("data", {})

        # Convert to sets of IDs for comparison
        before_ids = {ind.get("id") for ind in before_state.get("individuals", []) if ind.get("id")}
        after_individuals = {ind.get("id") for ind in after_data.get("individuals", []) if ind.get("id")}

        # Find new individuals (in after but not in before)
        new_individuals = after_individuals - before_ids

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
    def _extract_model_id(self, requests: Sequence[MinervaRequest]) -> Optional[str]:
        """Extract model_id from the first request that has one."""
        for req in requests:
            if hasattr(req, 'arguments') and hasattr(req.arguments, 'model_id'):
                return req.arguments.model_id
        return None

    def _execute_single_request(
        self,
        req: MinervaRequest,
        privileged: bool
    ) -> BaristaResponse:
        """Execute a single request and return response."""
        dict_request = req.model_dump(by_alias=True, exclude_none=True)

        url = self.privileged_url if privileged else self.batch_url
        data = {
            "intention": "action",
            "token": self.token,
            "provided-by": self.provided_by,
            "requests": json.dumps([dict_request]),
        }
        resp = self._client.post(url, data=data)
        resp.raise_for_status()
        raw = resp.json()

        return BaristaResponse(raw=raw)

    def _validate_individual_label(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        expected_label: str
    ) -> Optional[str]:
        """Validate that the created individual has the expected label.

        Returns:
            Error message if validation fails, None if passes
        """
        # Find newly created individual
        before_ids = {ind["id"] for ind in before_state.get("individuals", [])}
        after_individuals = after_state.get("individuals", [])

        new_individuals = [ind for ind in after_individuals if ind["id"] not in before_ids]

        if not new_individuals:
            return "No new individual was created"

        new_individual = new_individuals[0]

        # Check if any type has the expected label
        types = new_individual.get("type", [])
        for type_info in types:
            if type_info.get("label") == expected_label:
                return None  # Validation passed!

        # Validation failed
        actual_labels = [t.get("label", "?") for t in types]
        return f"Expected label '{expected_label}', but got {actual_labels}"

    def _rollback_executed_requests(
        self,
        executed_requests: List[Tuple[MinervaRequest, Dict, Dict]],
        privileged: bool = True
    ) -> BaristaResponse:
        """Rollback executed requests using their reverse operations.

        Args:
            executed_requests: List of (request, before_state, after_state) tuples
            privileged: Whether to use privileged endpoint for rollback

        Returns:
            BaristaResponse from executing the rollback
        """
        undo_requests = []

        # Generate reverses in reverse order
        for req, before_state, after_state in reversed(executed_requests):
            reverse_req = req.reverse(before_state, after_state)
            if reverse_req:
                undo_requests.append(reverse_req)
            else:
                logger.warning(f"Could not generate reverse for {req.__class__.__name__}")

        # Execute rollback (simple batch, no validation)
        if undo_requests:
            return self._execute_simple_batch(undo_requests, privileged=privileged)
        else:
            return BaristaResponse(raw={"message-type": "success", "message": "Rollback complete (no-op)"})

    def _execute_simple_batch(
        self,
        requests: Sequence[MinervaRequest],
        privileged: bool
    ) -> BaristaResponse:
        """Execute requests as a simple batch - no validation, no rollback."""
        dict_requests = [req.model_dump(by_alias=True, exclude_none=True) for req in requests]

        url = self.privileged_url if privileged else self.batch_url
        data = {
            "intention": "action",
            "token": self.token,
            "provided-by": self.provided_by,
            "requests": json.dumps(dict_requests),
        }
        resp = self._client.post(url, data=data)
        resp.raise_for_status()
        raw = resp.json()

        return BaristaResponse(raw=raw)

    def _track_variable_for_request(
        self,
        req: AddIndividualRequest,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> None:
        """Track variable assignment for an AddIndividual request."""
        variable = req.arguments.assign_to_variable
        if not variable:
            return

        model_id = req.arguments.model_id

        # Find the newly created individual
        before_ids = {ind["id"] for ind in before_state.get("individuals", [])}
        after_individuals = after_state.get("individuals", [])

        new_individuals = [ind for ind in after_individuals if ind["id"] not in before_ids]
        if new_individuals:
            new_id = new_individuals[0]["id"]

            # Store in both variable tracking systems
            self._variable_registry[(model_id, variable)] = new_id
            if model_id not in self._variable_map:
                self._variable_map[model_id] = {}
            self._variable_map[model_id][variable] = new_id

    def m3_batch(
        self,
        requests: Sequence[MinervaRequest],
        privileged: bool = True
    ) -> BaristaResponse:
        """Execute requests atomically with automatic validation and rollback.

        Behavior:
        - If ANY request needs validation: executes ONE AT A TIME with rollback
        - If NO validation needed: sends all requests together (Barista handles variables)
        - For AddIndividual requests with expected_label: validates after creation
        - On ANY failure (API or validation): rolls back ALL executed requests
        - Variable tracking happens after each successful validated request

        Args:
            requests: List of Pydantic request models
            privileged: Whether to use the privileged endpoint

        Returns:
            BaristaResponse - either success or rollback response
            Check response.validation_failed to determine if rollback occurred

        Examples:
            >>> # Single request with validation
            >>> # req = BaristaClient.req_add_individual(
            >>> #     "gomodel:123", "GO:0003924", "x1",
            >>> #     expected_label="GTPase activity"
            >>> # )
            >>> # response = client.m3_batch([req])
            >>> # if response.validation_failed:
            >>> #     print(f"Rolled back: {response.validation_reason}")
            ... # doctest: +SKIP
        """
        # Check if any request needs validation
        needs_validation = any(
            isinstance(req, AddIndividualRequest) and req.arguments.expected_label
            for req in requests
        )

        # If no validation needed, use simple batch (Barista handles variables)
        if not needs_validation:
            return self._execute_simple_batch(requests, privileged)

        # Extract model_id for validation/rollback mode
        model_id = self._extract_model_id(requests)
        if not model_id:
            # No model_id found, fall back to simple batch execution
            return self._execute_simple_batch(requests, privileged)

        # Track what we've executed for rollback
        executed_requests: List[Tuple[MinervaRequest, Dict, Dict]] = []

        # Take initial variable snapshot for rollback
        initial_variables = copy.deepcopy(self._variable_map.get(model_id, {}))

        # For accumulating the final response
        final_response = None

        try:
            for i, req in enumerate(requests):
                # Take before snapshot for this request
                before_snapshot = self._snapshot_model(model_id)

                # Execute single request
                single_response = self._execute_single_request(req, privileged)

                # Get after state
                after_state = single_response.raw.get("data", {})

                # Check if API call failed
                if not single_response.ok:
                    raise BatchExecutionError(
                        f"Request {i+1}/{len(requests)} failed: {single_response.error}",
                        executed_requests=[r for r, _, _ in executed_requests],
                        failed_request=req,
                        failed_response=single_response
                    )

                # VALIDATION (for AddIndividual with expected_label)
                if isinstance(req, AddIndividualRequest):
                    expected_label = req.arguments.expected_label
                    if expected_label:
                        validation_error = self._validate_individual_label(
                            before_snapshot, after_state, expected_label
                        )
                        if validation_error:
                            raise BatchValidationError(
                                f"Request {i+1}/{len(requests)} validation failed: {validation_error}",
                                executed_requests=[r for r, _, _ in executed_requests] + [req],
                                failed_request=req,
                                validation_reason=validation_error
                            )

                    # VARIABLE TRACKING (after successful validation or no validation)
                    if self.track_variables and req.arguments.assign_to_variable:
                        self._track_variable_for_request(req, before_snapshot, after_state)

                # Track this execution
                executed_requests.append((req, before_snapshot, after_state))
                final_response = single_response

            # ALL SUCCESSFUL
            if final_response is None:
                # No requests were executed - return a success response
                return BaristaResponse(raw={"message-type": "success", "message": "No requests executed"})
            return final_response

        except (BatchExecutionError, BatchValidationError) as e:
            # ROLLBACK ALL EXECUTED REQUESTS
            logger.error(f"Batch execution failed: {e}")
            logger.info(f"Rolling back {len(executed_requests)} request(s)...")

            rollback_response = self._rollback_executed_requests(executed_requests, privileged=privileged)

            # RESTORE VARIABLES
            if self.track_variables:
                self._variable_map[model_id] = initial_variables

            # Mark as failed with details
            rollback_response.validation_failed = True
            rollback_response.validation_reason = str(e)
            rollback_response.failed_request_index = len(executed_requests) - 1

            return rollback_response

    # Builders
    @staticmethod
    def req_add_individual(
        model_id: str,
        class_id: str,
        assign_var: str = "x1",
        expected_label: Optional[str] = None
    ) -> AddIndividualRequest:
        """Build a request to add an individual to a model.

        Args:
            model_id: The model ID
            class_id: The class/type CURIE (e.g., "GO:0003924")
            assign_var: Variable name to assign
            expected_label: If provided, validates the created individual has this label

        Returns:
            AddIndividualRequest object

        Examples:
            >>> # Without validation
            >>> req = BaristaClient.req_add_individual("gomodel:123", "GO:0003924", "activity1")
            >>> req.entity
            'individual'
            >>> req.operation
            'add'

            >>> # With validation
            >>> req = BaristaClient.req_add_individual(
            ...     "gomodel:123", "GO:0003924", "activity1",
            ...     expected_label="GTPase activity"
            ... )
            >>> req.arguments.expected_label
            'GTPase activity'
        """
        return AddIndividualRequest(
            arguments=AddIndividualArguments(
                expressions=[Expression(type="class", id=class_id)],
                model_id=model_id,
                assign_to_variable=assign_var,
                expected_label=expected_label
            )
        )

    @staticmethod
    def req_remove_individual(model_id: str, individual_id: str) -> RemoveIndividualRequest:
        """Build a request to remove an individual from a model.

        Examples:
            >>> req = BaristaClient.req_remove_individual("gomodel:123", "gomodel:123/individual-456")
            >>> req.entity
            'individual'
            >>> req.operation
            'remove'
        """
        return RemoveIndividualRequest(
            arguments=RemoveIndividualArguments(
                individual=individual_id,
                model_id=model_id
            )
        )

    @staticmethod
    def req_add_fact(model_id: str, subject_id: str, object_id: str, predicate_id: str) -> AddEdgeRequest:
        """Build a request to add an edge (fact) between individuals.

        Examples:
            >>> req = BaristaClient.req_add_fact("gomodel:123", "ind1", "ind2", "RO:0002413")
            >>> req.entity
            'edge'
            >>> req.operation
            'add'
        """
        return AddEdgeRequest(
            arguments=AddEdgeArguments(
                subject=subject_id,
                object=object_id,
                predicate=predicate_id,
                model_id=model_id
            )
        )

    @staticmethod
    def req_remove_fact(model_id: str, subject_id: str, object_id: str, predicate_id: str) -> RemoveEdgeRequest:
        """Build a request to remove an edge (fact) between individuals.

        Examples:
            >>> req = BaristaClient.req_remove_fact("gomodel:123", "ind1", "ind2", "RO:0002413")
            >>> req.entity
            'edge'
            >>> req.operation
            'remove'
        """
        return RemoveEdgeRequest(
            arguments=RemoveEdgeArguments(
                subject=subject_id,
                object=object_id,
                predicate=predicate_id,
                model_id=model_id
            )
        )

    @staticmethod
    def req_update_model_annotation(
        model_id: str, key: str, value: str, old_value: Optional[str] = None
    ) -> Union[AddModelAnnotationRequest, ReplaceModelAnnotationRequest]:
        """Request to update a model annotation.

        Args:
            model_id: The model ID
            key: The annotation key (e.g., 'title', 'state', 'comment')
            value: The new value for the annotation
            old_value: The current value (optional, for replacement)

        Returns:
            AddModelAnnotationRequest or ReplaceModelAnnotationRequest

        Examples:
            >>> req = BaristaClient.req_update_model_annotation("gomodel:123", "title", "New Title")
            >>> req.entity
            'model'
            >>> req.operation
            'add-annotation'
        """
        # If old_value is provided, this is a replace operation
        if old_value is not None:
            return ReplaceModelAnnotationRequest(
                arguments=ReplaceModelAnnotationArguments(
                    model_id=model_id,
                    key=key,
                    old_value=old_value,
                    new_value=value
                )
            )
        else:
            # Otherwise, it's an add operation using values array format
            return AddModelAnnotationRequest(
                arguments=AddModelAnnotationArguments(
                    model_id=model_id,
                    values=[AnnotationValue(key=key, value=value)]
                )
            )

    @staticmethod
    def req_update_individual_annotation(
        model_id: str,
        individual_id: str,
        key: str,
        value: str,
        old_value: Optional[str] = None
    ) -> Union[AddIndividualAnnotationRequest, List[Union[RemoveIndividualAnnotationRequest, AddIndividualAnnotationRequest]]]:
        """Request to update an annotation on an individual.

        Args:
            model_id: The model ID
            individual_id: The individual to annotate
            key: The annotation key
            value: The new value for the annotation
            old_value: The current value (optional, for replacement)

        Returns:
            AddIndividualAnnotationRequest or list of [RemoveIndividualAnnotationRequest, AddIndividualAnnotationRequest]

        Examples:
            >>> req = BaristaClient.req_update_individual_annotation("gomodel:123", "ind1", "label", "New Label")
            >>> req.entity
            'individual'
            >>> req.operation
            'add-annotation'
        """
        if old_value is not None:
            # Replace operation: remove old and add new
            # Since there's no replace-annotation for individuals,
            # we need to do this as two operations
            return [
                RemoveIndividualAnnotationRequest(
                    arguments=RemoveIndividualAnnotationArguments(
                        model_id=model_id,
                        individual=individual_id,
                        values=[AnnotationValue(key=key, value=old_value)]
                    )
                ),
                AddIndividualAnnotationRequest(
                    arguments=AddIndividualAnnotationArguments(
                        model_id=model_id,
                        individual=individual_id,
                        values=[AnnotationValue(key=key, value=value)]
                    )
                )
            ]
        else:
            # Add operation
            return AddIndividualAnnotationRequest(
                arguments=AddIndividualAnnotationArguments(
                    model_id=model_id,
                    individual=individual_id,
                    values=[AnnotationValue(key=key, value=value)]
                )
            )

    @staticmethod
    def req_remove_individual_annotation(
        model_id: str,
        individual_id: str,
        key: str,
        value: str
    ) -> RemoveIndividualAnnotationRequest:
        """Request to remove an annotation from an individual.

        Args:
            model_id: The model ID
            individual_id: The individual ID
            key: The annotation key to remove
            value: The value to remove

        Returns:
            RemoveIndividualAnnotationRequest

        Examples:
            >>> req = BaristaClient.req_remove_individual_annotation("gomodel:123", "ind1", "label", "Old Label")
            >>> req.entity
            'individual'
            >>> req.operation
            'remove-annotation'
        """
        return RemoveIndividualAnnotationRequest(
            arguments=RemoveIndividualAnnotationArguments(
                model_id=model_id,
                individual=individual_id,
                values=[AnnotationValue(key=key, value=value)]
            )
        )

    @staticmethod
    def req_remove_model_annotation(model_id: str, key: str, value: str) -> RemoveModelAnnotationRequest:
        """Request to remove a model annotation.

        Args:
            model_id: The model ID
            key: The annotation key to remove
            value: The value to remove (required for multi-value keys)

        Returns:
            RemoveModelAnnotationRequest

        Examples:
            >>> req = BaristaClient.req_remove_model_annotation("gomodel:123", "title", "Old Title")
            >>> req.entity
            'model'
            >>> req.operation
            'remove-annotation'
        """
        return RemoveModelAnnotationRequest(
            arguments=RemoveModelAnnotationArguments(
                model_id=model_id,
                values=[AnnotationValue(key=key, value=value)]
            )
        )

    @staticmethod
    def req_add_evidence_to_fact(
        model_id: str,
        subject_id: str,
        object_id: str,
        predicate_id: str,
        eco_id: str,
        sources: List[str],
        with_from: Optional[List[str]] = None,
    ) -> List[MinervaRequest]:
        """
        Compose the three-step evidence add sequence:
        1) add evidence individual
        2) add source (+ with) to evidence individual
        3) add evidence annotation to the edge

        Returns a list of Pydantic request models that can be appended into the batch.
        """
        from .models import (
            AddIndividualRequest,
            AddIndividualArguments,
            AddIndividualAnnotationRequest,
            AddIndividualAnnotationArguments,
            AddEdgeAnnotationRequest,
            AddEdgeAnnotationArguments,
            Expression,
            AnnotationValue,
        )

        ev_var = "e1"
        reqs: List[MinervaRequest] = []

        # 1) evidence individual
        reqs.append(
            AddIndividualRequest(
                arguments=AddIndividualArguments(
                    expressions=[Expression(type="class", id=eco_id)],
                    model_id=model_id,
                    assign_to_variable=ev_var,
                    expected_label=None,
                )
            )
        )

        # 2) add annotations to evidence individual
        values = [AnnotationValue(key="source", value=s) for s in sources]
        if with_from:
            values.extend([AnnotationValue(key="with", value=w) for w in with_from])

        reqs.append(
            AddIndividualAnnotationRequest(
                arguments=AddIndividualAnnotationArguments(
                    individual=ev_var,
                    values=values,
                    model_id=model_id,
                )
            )
        )

        # 3) tie evidence to edge
        reqs.append(
            AddEdgeAnnotationRequest(
                arguments=AddEdgeAnnotationArguments(
                    subject=subject_id,
                    object=object_id,
                    predicate=predicate_id,
                    values=[AnnotationValue(key="evidence", value=ev_var)],
                    model_id=model_id,
                )
            )
        )
        return reqs

    @staticmethod
    def req_create_model(title: Optional[str] = None) -> CreateModelRequest:
        """Request to create a new empty model.

        Args:
            title: Optional title for the model

        Returns:
            CreateModelRequest

        Examples:
            >>> req = BaristaClient.req_create_model("My Model")
            >>> req.entity
            'model'
            >>> req.operation
            'add'
        """
        return CreateModelRequest(
            arguments=CreateModelArguments(
                values=[AnnotationValue(key="title", value=title)] if title else None
            )
        )

    @staticmethod
    def req_get_model(model_id: str) -> GetModelRequest:
        """Request to get a model.

        Examples:
            >>> req = BaristaClient.req_get_model("gomodel:123")
            >>> req.entity
            'model'
            >>> req.operation
            'get'
        """
        return GetModelRequest(
            arguments=GetModelArguments(model_id=model_id)
        )

    @staticmethod
    def req_export_model(model_id: str, format: str = "owl") -> ExportModelRequest:
        """Request to export a model in a specific format.

        Args:
            model_id: The model to export
            format: Export format (owl, ttl, json-ld, etc.)

        Examples:
            >>> req = BaristaClient.req_export_model("gomodel:123", "owl")
            >>> req.entity
            'model'
            >>> req.operation
            'export'
        """
        return ExportModelRequest(
            arguments=ExportModelArguments(model_id=model_id, format=format)
        )


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

    def add_individual(
        self,
        model_id: str,
        class_curie: str,
        assign_var: str = "x1",
        expected_label: Optional[str] = None
    ) -> BaristaResponse:
        """Add an individual to the model.

        Validation and variable tracking happen automatically in m3_batch.

        Args:
            model_id: The model ID
            class_curie: The class/type for the individual (e.g., "GO:0003924")
            assign_var: Variable name to assign
            expected_label: If provided, validates the individual has this label
                           and rolls back if validation fails

        Returns:
            BaristaResponse - check .validation_failed for rollback status

        Examples:
            >>> # Simple add (no validation)
            >>> # response = client.add_individual("gomodel:123", "GO:0003924", "kinase")
            ... # doctest: +SKIP

            >>> # Add with validation (safe)
            >>> # response = client.add_individual(
            >>> #     "gomodel:123", "GO:0003924", "kinase",
            >>> #     expected_label="GTPase activity"
            >>> # )
            >>> # if response.validation_failed:
            >>> #     print("Wrong label! Rolled back.")
            ... # doctest: +SKIP
        """
        req = self.req_add_individual(model_id, class_curie, assign_var, expected_label)
        return self.m3_batch([req])

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
        self, model_id: str, subject_id: str, object_id: str, predicate_id: str
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

        Returns:
            BaristaResponse
        """
        # Resolve variables to actual IDs
        resolved_subject = self._resolve_identifier(model_id, subject_id)
        resolved_object = self._resolve_identifier(model_id, object_id)

        req = self.req_add_fact(model_id, resolved_subject, resolved_object, predicate_id)
        return self.m3_batch([req])

    def remove_fact(
        self, model_id: str, subject_id: str, object_id: str, predicate_id: str
    ) -> BaristaResponse:
        """Remove a fact, resolving variables to actual IDs."""
        resolved_subject = self._resolve_identifier(model_id, subject_id)
        resolved_object = self._resolve_identifier(model_id, object_id)
        req = self.req_remove_fact(model_id, resolved_subject, resolved_object, predicate_id)
        return self.m3_batch([req])

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
    ) -> BaristaResponse:
        """Add a fact with evidence, resolving variables to actual IDs.

        Subject and object can be variables, CURIEs, or full IDs.
        """
        # Resolve variables to actual IDs
        resolved_subject = self._resolve_identifier(model_id, subject_id)
        resolved_object = self._resolve_identifier(model_id, object_id)

        reqs: List[MinervaRequest] = [self.req_add_fact(model_id, resolved_subject, resolved_object, predicate_id)]
        reqs.extend(
            self.req_add_evidence_to_fact(
                model_id, resolved_subject, resolved_object, predicate_id, eco_id, sources, with_from
            )
        )
        return self.m3_batch(reqs)

    def add_protein_complex(
        self,
        model_id: str,
        components: List[ProteinComplexComponent],
        complex_class: str = "GO:0032991",  # protein-containing complex
        assign_var: str = "complex1",
        expected_label: Optional[str] = None,
    ) -> BaristaResponse:
        """Add a protein complex with its components.

        This is a higher-level method that creates a protein-containing complex
        and links its components using 'has part' relationships.

        Args:
            model_id: The model ID
            components: List of ProteinComplexComponent instances
            complex_class: The complex class CURIE (default: GO:0032991 for protein-containing complex)
            assign_var: Variable name for the complex
            expected_label: If provided, validates the complex has this label

        Returns:
            BaristaResponse - The complex individual is created first,
                             then components are linked with 'has part' relationships

        Examples:
            >>> from noctua.models import ProteinComplexComponent
            >>> # Simple protein complex with two components
            >>> # components = [
            >>> #     ProteinComplexComponent(entity_id="UniProtKB:P12345", label="Protein A"),
            >>> #     ProteinComplexComponent(entity_id="UniProtKB:P67890", label="Protein B")
            >>> # ]
            >>> # response = client.add_protein_complex("gomodel:123", components)
            ... # doctest: +SKIP

            >>> # Complex with evidence
            >>> # components = [
            >>> #     ProteinComplexComponent(
            >>> #         entity_id="UniProtKB:P12345",
            >>> #         label="Ras protein",
            >>> #         evidence_type="ECO:0000314",
            >>> #         reference="PMID:12345678"
            >>> #     )
            >>> # ]
            >>> # response = client.add_protein_complex(
            >>> #     "gomodel:123",
            >>> #     components,
            >>> #     expected_label="Ras signaling complex"
            >>> # )
            ... # doctest: +SKIP
        """
        if not components:
            raise BaristaError("At least one component is required")

        requests: List[MinervaRequest] = []

        # 1. Create the complex individual
        requests.append(
            self.req_add_individual(model_id, complex_class, assign_var, expected_label)
        )

        # 2. Create individuals for each component and link them
        has_part_predicate = "BFO:0000051"  # has part

        for i, component in enumerate(components):
            entity_id = component.entity_id
            label = component.label
            evidence_type = component.evidence_type
            reference = component.reference

            # Create component individual
            component_var = f"component{i+1}"
            requests.append(
                self.req_add_individual(model_id, entity_id, component_var)
            )

            # Add label annotation if provided
            if label:
                label_req = self.req_update_individual_annotation(
                    model_id, component_var, "rdfs:label", label
                )
                # req_update_individual_annotation returns either a single request or a list
                if isinstance(label_req, list):
                    requests.extend(label_req)
                else:
                    requests.append(label_req)

            # Link component to complex with 'has part'
            requests.append(
                self.req_add_fact(model_id, assign_var, component_var, has_part_predicate)
            )

            # Add evidence to the 'has part' relationship if provided
            if evidence_type and reference:
                requests.extend(
                    self.req_add_evidence_to_fact(
                        model_id,
                        assign_var,
                        component_var,
                        has_part_predicate,
                        evidence_type,
                        [reference],
                        None
                    )
                )

        return self.m3_batch(requests)

    def add_entity_set(
        self,
        model_id: str,
        members: List[EntitySetMember],
        set_class: str = "CHEBI:33695",  # information biomacromolecule
        assign_var: str = "set1",
        expected_label: Optional[str] = None,
    ) -> BaristaResponse:
        """Add an entity set with functionally interchangeable members.

        This is a higher-level method that creates an entity set (typically for
        paralogy groups) and links its members using 'has substitutable entity'
        relationships.

        Args:
            model_id: The model ID
            members: List of EntitySetMember instances
            set_class: The set class CURIE (default: CHEBI:33695 for information biomacromolecule)
            assign_var: Variable name for the set
            expected_label: If provided, validates the set has this label

        Returns:
            BaristaResponse - The set individual is created first,
                             then members are linked with 'has substitutable entity' relationships

        Examples:
            >>> from noctua.models import EntitySetMember
            >>> # Simple entity set with two paralogs (e.g., ERK1/ERK2)
            >>> # members = [
            >>> #     EntitySetMember(entity_id="UniProtKB:P27361", label="MAPK3 (ERK1)"),
            >>> #     EntitySetMember(entity_id="UniProtKB:P28482", label="MAPK1 (ERK2)")
            >>> # ]
            >>> # response = client.add_entity_set("gomodel:123", members)
            ... # doctest: +SKIP

            >>> # Entity set with evidence
            >>> # members = [
            >>> #     EntitySetMember(
            >>> #         entity_id="UniProtKB:P27361",
            >>> #         label="MAPK3 (ERK1)",
            >>> #         evidence_type="ECO:0000314",
            >>> #         reference="PMID:12345678"
            >>> #     )
            >>> # ]
            >>> # response = client.add_entity_set(
            >>> #     "gomodel:123",
            >>> #     members,
            >>> #     expected_label="ERK paralogy group"
            >>> # )
            ... # doctest: +SKIP
        """
        if not members:
            raise BaristaError("At least one member is required")

        requests: List[MinervaRequest] = []

        # 1. Create the set individual
        requests.append(
            self.req_add_individual(model_id, set_class, assign_var, expected_label)
        )

        # 2. Create individuals for each member and link them
        has_substitutable_entity_predicate = "RO:0019003"  # has substitutable entity

        for i, member in enumerate(members):
            entity_id = member.entity_id
            label = member.label
            evidence_type = member.evidence_type
            reference = member.reference

            # Create member individual
            member_var = f"member{i+1}"
            requests.append(
                self.req_add_individual(model_id, entity_id, member_var)
            )

            # Add label annotation if provided
            if label:
                label_req = self.req_update_individual_annotation(
                    model_id, member_var, "rdfs:label", label
                )
                # req_update_individual_annotation returns either a single request or a list
                if isinstance(label_req, list):
                    requests.extend(label_req)
                else:
                    requests.append(label_req)

            # Link member to set with 'has substitutable entity'
            requests.append(
                self.req_add_fact(model_id, assign_var, member_var, has_substitutable_entity_predicate)
            )

            # Add evidence to the relationship if provided
            if evidence_type and reference:
                requests.extend(
                    self.req_add_evidence_to_fact(
                        model_id,
                        assign_var,
                        member_var,
                        has_substitutable_entity_predicate,
                        evidence_type,
                        [reference],
                        None
                    )
                )

        return self.m3_batch(requests)

    def get_model(self, model_id: str) -> BaristaResponse:
        """Get a model by ID.

        Note: Uses simple batch execution to avoid recursion with _snapshot_model.
        """
        req = self.req_get_model(model_id)
        return self._execute_simple_batch([req], privileged=True)

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

        # Use Pydantic model for type-safe access
        model_data = resp.data

        # Build markdown document
        lines = []

        # Title and metadata
        title = "Untitled Model"
        state = None
        comments = []

        # Extract model annotations
        for ann in model_data.annotations:
            if ann.key == "title":
                title = ann.value
            elif ann.key == "state":
                state = ann.value
            elif ann.key == "comment":
                comments.append(ann.value)

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
        individuals = model_data.individuals
        if individuals:
            lines.append("## Activities and Entities")
            lines.append("")

            # Group individuals by their primary type
            for ind in individuals:
                # Get the main type
                if ind.type:
                    main_type = ind.type[0]
                    type_id = main_type.id
                    type_label = main_type.label or type_id
                else:
                    type_id = "unknown"
                    type_label = "Unknown type"

                # Get annotations
                annotations: Dict[str, List[str]] = {}
                for ann in ind.annotations:
                    if ann.key not in annotations:
                        annotations[ann.key] = []
                    annotations[ann.key].append(ann.value)

                # Format individual
                lines.append(f"### {type_label}")
                lines.append(f"- **ID**: `{ind.id}`")
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
        facts = model_data.facts
        if facts:
            lines.append("## Relationships")
            lines.append("")

            # Group facts by predicate type
            fact_groups: Dict[str, List[Dict[str, Any]]] = {}
            for fact in facts:
                pred_label = fact.property_label or fact.property

                if pred_label not in fact_groups:
                    fact_groups[pred_label] = []

                # Find subject and object labels
                subj_label = self._find_individual_label(individuals, fact.subject)
                obj_label = self._find_individual_label(individuals, fact.object)

                # Get evidence annotations
                evidence = []
                for ann in fact.annotations:
                    if ann.key == "evidence":
                        evidence.append(ann.value)

                fact_groups[pred_label].append({
                    "subject": subj_label,
                    "object": obj_label,
                    "subject_id": fact.subject,
                    "object_id": fact.object,
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

    def _find_individual_label(self, individuals: List[Individual], ind_id: str) -> str:
        """Find a readable label for an individual.

        Args:
            individuals: List of Individual objects from the model
            ind_id: The individual ID to look up

        Returns:
            A readable label for the individual
        """
        for ind in individuals:
            if ind.id == ind_id:
                # Try to get rdfs:label first
                for ann in ind.annotations:
                    if ann.key == "rdfs:label":
                        return ann.value

                # Otherwise use the type label
                if ind.type:
                    return ind.type[0].label or ind_id

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

    def remove_individual_annotation(
        self,
        model_id: str,
        individual_id: str,
        key: str,
        value: str,
    ) -> BaristaResponse:
        """Remove an annotation from an individual.

        Args:
            model_id: The model ID
            individual_id: The individual ID
            key: The annotation key to remove
            value: The value to remove

        Returns:
            BaristaResponse
        """
        req = self.req_remove_individual_annotation(
            model_id, individual_id, key, value
        )
        return self.m3_batch([req])

    def update_individual_annotation(
        self,
        model_id: str,
        individual_id: str,
        key: str,
        value: str,
        old_value: Optional[str] = None,
    ) -> BaristaResponse:
        """Update an annotation on an individual.

        Args:
            model_id: The model ID
            individual_id: The individual ID
            key: The annotation key
            value: The new value for the annotation
            old_value: The current value (optional, for replacement)

        Returns:
            BaristaResponse
        """
        req = self.req_update_individual_annotation(
            model_id, individual_id, key, value, old_value
        )
        # req could be a single request or a list
        if isinstance(req, list):
            return self.m3_batch(req)
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

        requests: List[MinervaRequest] = []

        # Remove all facts/edges first (before removing individuals)
        for fact in model_resp.facts:
            if fact.subject and fact.object and fact.property:
                requests.append(self.req_remove_fact(model_id, fact.subject, fact.object, fact.property))

        # Remove all individuals
        for individual in model_resp.individuals:
            requests.append(self.req_remove_individual(model_id, individual.id))

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
            for ann in object_.annotations:
                if ann.key == "id":
                    bioentity_id = ann.value
                    break

            # Get GO term from subject type
            if subject.type:
                go_term = subject.type[0].id
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
            object_type_id = ""
            object_label = ""
            if object_.type:
                object_type_id = object_.type[0].id
                object_label = (object_.type[0].label or "").lower()

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
            for ann in subject.annotations:
                if ann.key == "enabled_by":
                    bioentity_id = ann.value
                    break

            # Get GO term from object type
            go_term = object_type_id

        # Check for activity->location relationship (BFO:0000066 occurs_in)
        elif predicate in ["BFO:0000066", "http://purl.obolibrary.org/obo/BFO_0000066"]:
            mapping_type = "activity_to_location"
            aspect = "C"  # Cellular Component

            # Get the bioentity that enables the subject activity
            for ann in subject.annotations:
                if ann.key == "enabled_by":
                    bioentity_id = ann.value
                    break

            # Get GO term from object type
            if object_.type:
                go_term = object_.type[0].id

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
                "subject": subject.id,
                "subject_label": subject.type[0].label if subject.type else None,
                "object": object_.id,
                "object_label": object_.type[0].label if object_.type else None,
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
            if fact.subject and fact.object and fact.property:
                edge_evidence = self.find_evidence_for_edge(
                    model_id,
                    fact.subject,
                    fact.object,
                    fact.property,
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

    def _resolve_individual(self, model_resp: BaristaResponse, individual_id: str) -> Optional[Individual]:
        """Resolve an individual ID (which might be a variable name) to the actual individual.

        Args:
            model_resp: The model response containing individuals
            individual_id: The individual ID or variable name

        Returns:
            The Individual object, or None if not found
        """
        # First try direct ID match
        for individual in model_resp.individuals:
            if individual.id == individual_id:
                return individual

        # Then try variable name match
        if hasattr(self, '_variables') and individual_id in self._variables:
            resolved_id = self._variables[individual_id]
            for individual in model_resp.individuals:
                if individual.id == resolved_id:
                    return individual

        return None
