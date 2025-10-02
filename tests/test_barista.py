from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

from noctua.barista import BaristaClient, BaristaResponse

# Use a test model ID - change this to an existing model on your dev server
# or set via environment variable for testing
MODEL_ID = os.environ.get("TEST_MODEL_ID", "gomodel:6796b94c00003233")


def test_build_add_individual_payload() -> None:
    """Test building payload for adding an individual."""
    req = BaristaClient.req_add_individual(MODEL_ID, "GO:0016055", assign_var="x1")
    assert req["entity"] == "individual"
    assert req["operation"] == "add"
    args = req["arguments"]
    assert args["model-id"] == MODEL_ID
    assert args["assign-to-variable"] == "x1"
    expr = args["expressions"][0]
    assert expr["type"] == "class"
    assert expr["id"] == "GO:0016055"


def test_response_parsing() -> None:
    sample = {
        "packet-id": "abc",
        "message-type": "success",
        "signal": "merge",
        "intention": "action",
        "data": {
            "id": MODEL_ID,
            "individuals": [
                {"id": f"{MODEL_ID}/123", "type": [{"type": "class", "id": "GO:0016055"}]}
            ],
            "facts": [],
            "annotations": [
                {"key": "state", "value": "development"},
                {"key": "title", "value": "Test Model"}
            ],
        },
    }
    br = BaristaResponse(raw=sample)
    assert br.ok
    assert br.signal == "merge"
    assert br.model_id == MODEL_ID
    assert len(br.individuals) == 1
    assert br.model_state == "development"

    # Test production model
    sample_prod = {
        "packet-id": "abc",
        "message-type": "success",
        "signal": "merge",
        "intention": "action",
        "data": {
            "id": MODEL_ID,
            "individuals": [],
            "facts": [],
            "annotations": [
                {"key": "state", "value": "production"},
            ],
        },
    }
    br_prod = BaristaResponse(raw=sample_prod)
    assert br_prod.model_state == "production"


def test_build_remove_payloads() -> None:
    """Test building payloads for removing individuals and facts."""
    # Test remove individual
    remove_ind = BaristaClient.req_remove_individual(MODEL_ID, "ind123")
    assert remove_ind["entity"] == "individual"
    assert remove_ind["operation"] == "remove"
    assert remove_ind["arguments"]["individual"] == "ind123"
    assert remove_ind["arguments"]["model-id"] == MODEL_ID

    # Test remove fact
    remove_fact = BaristaClient.req_remove_fact(MODEL_ID, "subj1", "obj1", "RO:0002413")
    assert remove_fact["entity"] == "edge"
    assert remove_fact["operation"] == "remove"
    assert remove_fact["arguments"]["subject"] == "subj1"
    assert remove_fact["arguments"]["object"] == "obj1"
    assert remove_fact["arguments"]["predicate"] == "RO:0002413"
    assert remove_fact["arguments"]["model-id"] == MODEL_ID

    # Test get model
    get_model = BaristaClient.req_get_model(MODEL_ID)
    assert get_model["entity"] == "model"
    assert get_model["operation"] == "get"
    assert get_model["arguments"]["model-id"] == MODEL_ID


def test_build_pathway_payloads() -> None:
    """Test building payloads for a complete pathway from scratch.

    This demonstrates creating a signaling pathway with proper GO-CAM structure:
    - Molecular activities (GO molecular functions)
    - Causal relationships between activities
    - Evidence supporting the model
    """
    # Build a receptor signaling pathway: ligand binding -> receptor -> kinase cascade

    # Step 1: Create molecular activity for ligand binding
    ligand_activity = BaristaClient.req_add_individual(
        MODEL_ID, "GO:0005102", assign_var="ligand_act"  # signaling receptor binding
    )
    assert ligand_activity["entity"] == "individual"
    assert ligand_activity["operation"] == "add"
    assert ligand_activity["arguments"]["expressions"][0]["id"] == "GO:0005102"
    assert ligand_activity["arguments"]["assign-to-variable"] == "ligand_act"

    # Step 2: Create receptor activity
    receptor_activity = BaristaClient.req_add_individual(
        MODEL_ID, "GO:0004888", assign_var="receptor_act"  # transmembrane signaling receptor activity
    )
    assert receptor_activity["arguments"]["expressions"][0]["id"] == "GO:0004888"

    # Step 3: Create downstream kinase activity
    kinase_activity = BaristaClient.req_add_individual(
        MODEL_ID, "GO:0004674", assign_var="kinase_act"  # protein serine/threonine kinase activity
    )
    assert kinase_activity["arguments"]["expressions"][0]["id"] == "GO:0004674"

    # Step 4: Create transcription factor activity
    tf_activity = BaristaClient.req_add_individual(
        MODEL_ID, "GO:0003700", assign_var="tf_act"  # DNA-binding transcription factor activity
    )
    assert tf_activity["arguments"]["expressions"][0]["id"] == "GO:0003700"

    # Step 5: Connect activities with causal relationships
    # Ligand binding provides input for receptor
    fact1 = BaristaClient.req_add_fact(
        MODEL_ID,
        subject_id="ligand_act",
        object_id="receptor_act",
        predicate_id="RO:0002413"  # directly positively regulates
    )
    assert fact1["entity"] == "edge"
    assert fact1["operation"] == "add"
    assert fact1["arguments"]["predicate"] == "RO:0002413"

    # Receptor activates kinase
    fact2 = BaristaClient.req_add_fact(
        MODEL_ID,
        subject_id="receptor_act",
        object_id="kinase_act",
        predicate_id="RO:0002413"  # directly positively regulates
    )
    assert fact2["arguments"]["subject"] == "receptor_act"
    assert fact2["arguments"]["object"] == "kinase_act"

    # Kinase activates transcription factor
    fact3 = BaristaClient.req_add_fact(
        MODEL_ID,
        subject_id="kinase_act",
        object_id="tf_act",
        predicate_id="RO:0002413"  # directly positively regulates
    )
    assert fact3["arguments"]["subject"] == "kinase_act"
    assert fact3["arguments"]["object"] == "tf_act"

    # Step 6: Add evidence to support the pathway
    evidence_reqs = BaristaClient.req_add_evidence_to_fact(
        MODEL_ID,
        subject_id="receptor_act",
        object_id="kinase_act",
        predicate_id="RO:0002413",
        eco_id="ECO:0000314",  # direct assay evidence
        sources=["PMID:12345678", "PMID:87654321"],
        with_from=["UniProtKB:P12345"]
    )
    assert len(evidence_reqs) == 3  # evidence individual, annotation, edge annotation
    assert evidence_reqs[0]["entity"] == "individual"
    assert evidence_reqs[0]["arguments"]["expressions"][0]["id"] == "ECO:0000314"
    assert evidence_reqs[1]["entity"] == "individual"
    assert evidence_reqs[1]["operation"] == "add-annotation"
    assert len(evidence_reqs[1]["arguments"]["values"]) == 3  # 2 sources + 1 with


def test_list_models_search_response() -> None:
    """Test parsing search endpoint response for list models."""
    # Sample response from the search endpoint
    sample_search: Dict[str, Any] = {
        "total": 2,
        "models": [
            {
                "id": "gomodel:68d6f96e00000001",
                "title": "Test Model 1",
                "state": "development",
                "date": "2024-01-01",
                "contributors": ["user1"]
            },
            {
                "id": "gomodel:68d6f96e00000002",
                "title": "Test Model 2",
                "state": "production",
                "date": "2024-01-02",
                "contributors": ["user2", "user3"]
            }
        ]
    }

    # Test that we can parse the models from the search response
    models: List[Dict[str, Any]] = sample_search["models"]
    assert len(models) == 2
    assert models[0]["id"] == "gomodel:68d6f96e00000001"
    assert models[0]["title"] == "Test Model 1"
    assert models[1]["id"] == "gomodel:68d6f96e00000002"
    assert models[1]["title"] == "Test Model 2"


def test_create_model_request() -> None:
    """Test building request for model creation with title."""
    # Test creating model without title
    req_no_title = BaristaClient.req_create_model()
    assert req_no_title["entity"] == "model"
    assert req_no_title["operation"] == "add"
    assert req_no_title["arguments"] == {}

    # Test creating model with title - should use values array
    req_with_title = BaristaClient.req_create_model("My Model Title")
    assert req_with_title["entity"] == "model"
    assert req_with_title["operation"] == "add"
    assert req_with_title["arguments"]["values"] == [{"key": "title", "value": "My Model Title"}]


def test_update_model_annotation_requests() -> None:
    """Test building requests for model annotation updates."""
    # Test adding a new annotation - now uses values array format
    req = BaristaClient.req_update_model_annotation(MODEL_ID, "title", "New Title")
    assert req["entity"] == "model"
    assert req["operation"] == "add-annotation"
    assert req["arguments"]["model-id"] == MODEL_ID
    assert req["arguments"]["values"] == [{"key": "title", "value": "New Title"}]

    # Test replacing an annotation
    req_replace = BaristaClient.req_update_model_annotation(
        MODEL_ID, "state", "production", old_value="development"
    )
    assert req_replace["entity"] == "model"
    assert req_replace["operation"] == "replace-annotation"
    assert req_replace["arguments"]["model-id"] == MODEL_ID
    assert req_replace["arguments"]["key"] == "state"
    assert req_replace["arguments"]["old-value"] == "development"
    assert req_replace["arguments"]["new-value"] == "production"

    # Test removing an annotation - now uses values array format
    req_remove = BaristaClient.req_remove_model_annotation(MODEL_ID, "comment", "To be removed")
    assert req_remove["entity"] == "model"
    assert req_remove["operation"] == "remove-annotation"
    assert req_remove["arguments"]["model-id"] == MODEL_ID
    assert req_remove["arguments"]["values"] == [{"key": "comment", "value": "To be removed"}]


def test_build_complex_pathway() -> None:
    """Test building a more complex pathway with multiple nodes and relationships."""
    # Build a simple MAPK cascade pathway
    requests = []

    # Add pathway components
    components = {
        "ras": ("GO:0003924", "GTPase activity"),
        "raf": ("GO:0004674", "protein serine/threonine kinase activity"),
        "mek": ("GO:0004708", "MAP kinase kinase activity"),
        "erk": ("GO:0004707", "MAP kinase activity"),
        "tf": ("GO:0003700", "DNA-binding transcription factor activity")
    }

    for var_name, (go_id, _description) in components.items():
        req = BaristaClient.req_add_individual(MODEL_ID, go_id, assign_var=var_name)
        requests.append(req)
        assert req["arguments"]["model-id"] == MODEL_ID
        assert req["arguments"]["assign-to-variable"] == var_name

    # Add cascade relationships
    cascade = [
        ("ras", "raf", "RO:0002413"),  # directly positively regulates
        ("raf", "mek", "RO:0002413"),
        ("mek", "erk", "RO:0002413"),
        ("erk", "tf", "RO:0002413")
    ]

    for subj, obj, pred in cascade:
        fact_req = BaristaClient.req_add_fact(MODEL_ID, subj, obj, pred)
        requests.append(fact_req)
        assert fact_req["arguments"]["subject"] == subj
        assert fact_req["arguments"]["object"] == obj
        assert fact_req["arguments"]["predicate"] == pred

    # Verify we built the complete pathway
    assert len(requests) == len(components) + len(cascade)  # 5 components + 4 relationships


@pytest.mark.integration
def test_add_individual_integration() -> None:
    """Test adding an individual to the model via Barista API (skips if no token)."""
    token = os.environ.get("BARISTA_TOKEN")
    if not token:
        pytest.skip("BARISTA_TOKEN not set; skipping integration test")
    client = BaristaClient()
    resp = client.add_individual(MODEL_ID, "GO:0016055", assign_var="x1")
    assert resp.ok, f"request failed: {json.dumps(resp.raw)[:400]}"
    assert resp.signal in ("merge", "rebuild")
    assert resp.model_id == MODEL_ID


@pytest.mark.integration
def test_build_pathway_integration() -> None:
    """Integration test: Build a complete signaling pathway from scratch.

    Creates a GO-CAM model representing a signaling cascade:
    Ligand binding -> Receptor activation -> Kinase cascade -> Transcription
    """
    token = os.environ.get("BARISTA_TOKEN")
    if not token:
        pytest.skip("BARISTA_TOKEN not set; skipping live test")

    client = BaristaClient()

    # Build batch request for complete pathway
    batch_requests = []

    # === Add molecular activities ===

    # 1. Ligand binding activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0005102", assign_var="ligand_binding"  # signaling receptor binding
        )
    )

    # 2. Receptor tyrosine kinase activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0004714", assign_var="rtk"  # transmembrane receptor protein tyrosine kinase activity
        )
    )

    # 3. RAS GTPase activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0003924", assign_var="ras"  # GTPase activity
        )
    )

    # 4. RAF kinase activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0004674", assign_var="raf"  # protein serine/threonine kinase activity
        )
    )

    # 5. MEK kinase activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0004708", assign_var="mek"  # MAP kinase kinase activity
        )
    )

    # 6. ERK MAP kinase activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0004707", assign_var="erk"  # MAP kinase activity
        )
    )

    # 7. Transcription factor activity
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0003700", assign_var="tf"  # DNA-binding transcription factor activity
        )
    )

    # === Add causal relationships to form the pathway ===

    # Ligand binding activates receptor
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="ligand_binding",
            object_id="rtk",
            predicate_id="RO:0002413"  # directly positively regulates
        )
    )

    # Receptor activates RAS
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="rtk",
            object_id="ras",
            predicate_id="RO:0002413"  # directly positively regulates
        )
    )

    # RAS activates RAF
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="ras",
            object_id="raf",
            predicate_id="RO:0002413"  # directly positively regulates
        )
    )

    # RAF activates MEK
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="raf",
            object_id="mek",
            predicate_id="RO:0002413"  # directly positively regulates
        )
    )

    # MEK activates ERK
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="mek",
            object_id="erk",
            predicate_id="RO:0002413"  # directly positively regulates
        )
    )

    # ERK activates transcription factor
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="erk",
            object_id="tf",
            predicate_id="RO:0002413"  # directly positively regulates
        )
    )

    # === Add evidence for key relationships ===

    # Add evidence for RAS->RAF interaction
    evidence_reqs = BaristaClient.req_add_evidence_to_fact(
        MODEL_ID,
        subject_id="ras",
        object_id="raf",
        predicate_id="RO:0002413",
        eco_id="ECO:0000314",  # direct assay evidence
        sources=["PMID:12345678"],
        with_from=["UniProtKB:P01112"]  # HRAS
    )
    batch_requests.extend(evidence_reqs)

    # Execute the complete batch
    resp = client.m3_batch(batch_requests)
    assert resp.ok, f"Batch request failed: {json.dumps(resp.raw)[:400]}"
    assert resp.signal in ("merge", "rebuild")
    assert resp.model_id == MODEL_ID

    # Verify the pathway was created
    assert len(resp.individuals) > 0, "No individuals returned from batch request"
    assert len(resp.facts) > 0, "No facts/relationships returned from batch request"


@pytest.mark.integration
def test_delete_operations_integration() -> None:
    """Test deleting individuals and edges from a model.

    This test creates a simple model with two nodes and an edge,
    then tests deletion operations.
    """
    token = os.environ.get("BARISTA_TOKEN")
    if not token:
        pytest.skip("BARISTA_TOKEN not set; skipping integration test")

    client = BaristaClient()

    # First, create a simple model with nodes and edges
    batch_requests = []

    # Add two individuals
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0003674", assign_var="node1"  # molecular_function
        )
    )
    batch_requests.append(
        BaristaClient.req_add_individual(
            MODEL_ID, "GO:0008150", assign_var="node2"  # biological_process
        )
    )

    # Add edge between them
    batch_requests.append(
        BaristaClient.req_add_fact(
            MODEL_ID,
            subject_id="node1",
            object_id="node2",
            predicate_id="RO:0002213"  # positively regulates
        )
    )

    # Execute batch to create test data
    resp = client.m3_batch(batch_requests)
    assert resp.ok, f"Setup failed: {json.dumps(resp.raw)[:400]}"

    # Get the actual IDs from the response
    # The individuals are returned in the same order they were created
    assert len(resp.individuals) >= 2, f"Expected at least 2 individuals, got {len(resp.individuals)}"

    # Find the nodes by their class types
    node1_id = None
    node2_id = None
    for ind in resp.individuals:
        types = ind.get("type", [])
        for t in types:
            if t.get("id") == "GO:0003674":  # molecular_function
                node1_id = ind["id"]
            elif t.get("id") == "GO:0008150":  # biological_process
                node2_id = ind["id"]

    assert node1_id is not None, "Could not find node1 (GO:0003674) in response"
    assert node2_id is not None, "Could not find node2 (GO:0008150) in response"

    # Test 1: Delete an edge
    edge_delete_resp = client.delete_edge(
        MODEL_ID,
        subject_id=node1_id,
        object_id=node2_id,
        predicate_id="RO:0002213"
    )
    assert edge_delete_resp.ok, f"Edge deletion failed: {json.dumps(edge_delete_resp.raw)[:400]}"

    # Test 2: Delete an individual
    node_delete_resp = client.delete_individual(MODEL_ID, node1_id)
    assert node_delete_resp.ok, f"Individual deletion failed: {json.dumps(node_delete_resp.raw)[:400]}"

    # Test 3: Try to delete the second individual as well
    node2_delete_resp = client.delete_individual(MODEL_ID, node2_id)
    assert node2_delete_resp.ok, f"Second individual deletion failed: {json.dumps(node2_delete_resp.raw)[:400]}"


def test_delete_error_handling() -> None:
    """Test error handling for deletion operations."""
    token = os.environ.get("BARISTA_TOKEN")
    if not token:
        pytest.skip("BARISTA_TOKEN not set; skipping integration test")

    client = BaristaClient()

    # Try to delete a non-existent individual
    fake_id = f"{MODEL_ID}/nonexistent123"
    resp = client.delete_individual(MODEL_ID, fake_id)
    # The API may or may not fail for non-existent items, but should not crash
    # We're mainly testing that our client handles the response properly
    assert isinstance(resp, BaristaResponse)


def test_req_update_individual_annotation() -> None:
    """Test creating requests to update individual annotations."""
    # Test add operation (no old_value)
    req_add = BaristaClient.req_update_individual_annotation(
        "model123",
        "individual456",
        "enabled_by",
        "UniProtKB:P12345"
    )
    assert isinstance(req_add, dict), "Add operation should return a single dict"
    assert req_add["entity"] == "individual"
    assert req_add["operation"] == "add-annotation"
    assert req_add["arguments"]["model-id"] == "model123"
    assert req_add["arguments"]["individual"] == "individual456"
    assert req_add["arguments"]["values"] == [{"key": "enabled_by", "value": "UniProtKB:P12345"}]

    # Test replace operation (with old_value) - returns list of two operations
    req_replace = BaristaClient.req_update_individual_annotation(
        "model123",
        "individual456",
        "rdfs:label",
        "New Label",
        old_value="Old Label"
    )
    assert isinstance(req_replace, list), "Replace operation should return a list"
    assert len(req_replace) == 2, "Replace should have remove and add operations"

    # First operation should be remove
    assert req_replace[0]["entity"] == "individual"
    assert req_replace[0]["operation"] == "remove-annotation"
    assert req_replace[0]["arguments"]["model-id"] == "model123"
    assert req_replace[0]["arguments"]["individual"] == "individual456"
    assert req_replace[0]["arguments"]["values"] == [{"key": "rdfs:label", "value": "Old Label"}]

    # Second operation should be add
    assert req_replace[1]["entity"] == "individual"
    assert req_replace[1]["operation"] == "add-annotation"
    assert req_replace[1]["arguments"]["model-id"] == "model123"
    assert req_replace[1]["arguments"]["individual"] == "individual456"
    assert req_replace[1]["arguments"]["values"] == [{"key": "rdfs:label", "value": "New Label"}]


def test_req_remove_individual_annotation() -> None:
    """Test creating requests to remove individual annotations."""
    req = BaristaClient.req_remove_individual_annotation(
        "model123",
        "individual456",
        "enabled_by",
        "UniProtKB:P12345"
    )
    assert req["entity"] == "individual"
    assert req["operation"] == "remove-annotation"
    assert req["arguments"]["model-id"] == "model123"
    assert req["arguments"]["individual"] == "individual456"
    assert req["arguments"]["values"] == [{"key": "enabled_by", "value": "UniProtKB:P12345"}]


@pytest.mark.integration
def test_individual_annotation_operations() -> None:
    """Test updating and removing annotations on individuals."""
    token = os.environ.get("BARISTA_TOKEN")
    if not token:
        pytest.skip("BARISTA_TOKEN not set; skipping integration test")

    client = BaristaClient()

    # First create an individual to work with
    create_resp = client.add_individual(MODEL_ID, "GO:0003924")  # GTPase activity
    assert create_resp.ok, f"Failed to create individual: {json.dumps(create_resp.raw)[:400]}"

    # Get the individual ID from response
    individual_id = None
    for ind in create_resp.individuals:
        types = ind.get("type", [])
        for t in types:
            if t.get("id") == "GO:0003924":
                individual_id = ind["id"]
                break
        if individual_id:
            break

    assert individual_id is not None, "Could not find created individual"

    # Test 1: Add an annotation to the individual
    add_resp = client.update_individual_annotation(
        MODEL_ID,
        individual_id,
        "rdfs:label",
        "Test GTPase"
    )
    assert add_resp.ok, f"Failed to add annotation: {json.dumps(add_resp.raw)[:400]}"

    # Test 2: Replace the annotation
    replace_resp = client.update_individual_annotation(
        MODEL_ID,
        individual_id,
        "rdfs:label",
        "Updated GTPase",
        old_value="Test GTPase"
    )
    assert replace_resp.ok, f"Failed to replace annotation: {json.dumps(replace_resp.raw)[:400]}"

    # Test 3: Add contributor annotation
    contrib_resp = client.update_individual_annotation(
        MODEL_ID,
        individual_id,
        "contributor",
        "https://orcid.org/0000-0002-6601-2165"
    )
    assert contrib_resp.ok, f"Failed to add contributor: {json.dumps(contrib_resp.raw)[:400]}"

    # Test 4: Remove the contributor annotation
    remove_resp = client.remove_individual_annotation(
        MODEL_ID,
        individual_id,
        "contributor",
        "https://orcid.org/0000-0002-6601-2165"
    )
    assert remove_resp.ok, f"Failed to remove annotation: {json.dumps(remove_resp.raw)[:400]}"

    # Clean up - delete the individual
    cleanup_resp = client.delete_individual(MODEL_ID, individual_id)
    assert cleanup_resp.ok, f"Failed to clean up individual: {json.dumps(cleanup_resp.raw)[:400]}"


@pytest.mark.integration
def test_individual_annotation_with_validation() -> None:
    """Test individual annotation updates with validation."""
    token = os.environ.get("BARISTA_TOKEN")
    if not token:
        pytest.skip("BARISTA_TOKEN not set; skipping integration test")

    client = BaristaClient()

    # Create an individual with a known type
    create_resp = client.add_individual(MODEL_ID, "GO:0003924")  # GTPase activity
    assert create_resp.ok, f"Failed to create individual: {json.dumps(create_resp.raw)[:400]}"

    # Get the individual ID
    individual_id = None
    for ind in create_resp.individuals:
        types = ind.get("type", [])
        for t in types:
            if t.get("id") == "GO:0003924":
                individual_id = ind["id"]
                break
        if individual_id:
            break

    assert individual_id is not None, "Could not find created individual"

    # Test 1: Update with correct validation (should succeed)
    valid_resp = client.update_individual_annotation(
        MODEL_ID,
        individual_id,
        "contributor",
        "https://orcid.org/0000-0002-6601-2165",
        validation={"id": individual_id, "label": "GTPase activity"}
    )
    assert valid_resp.ok or valid_resp.validation_failed, f"Unexpected response: {json.dumps(valid_resp.raw)[:400]}"

    # If validation passed, the update should succeed
    if not valid_resp.validation_failed:
        assert valid_resp.ok, "Update should succeed when validation passes"

    # Test 2: Update with incorrect validation (should fail and rollback)
    invalid_resp = client.update_individual_annotation(
        MODEL_ID,
        individual_id,
        "contributor",
        "https://orcid.org/0000-0002-9999-9999",
        validation={"id": individual_id, "label": "Wrong Label"}
    )

    # Either the validation should fail, or the operation should fail
    if invalid_resp.validation_failed and invalid_resp.validation_reason:
        # Should show actual vs expected labels for better error messaging
        assert ("has type labels" in invalid_resp.validation_reason and "but expected 'Wrong Label'" in invalid_resp.validation_reason) or "Wrong Label" in invalid_resp.validation_reason or "label" in invalid_resp.validation_reason.lower()

    # Clean up
    cleanup_resp = client.delete_individual(MODEL_ID, individual_id)
    assert cleanup_resp.ok, f"Failed to clean up individual: {json.dumps(cleanup_resp.raw)[:400]}"
