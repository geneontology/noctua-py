#!/usr/bin/env python
"""
Demonstration of validation with auto-rollback functionality in noctua-py.

This feature allows you to specify expected conditions and automatically
rollback operations if those conditions are not met.
"""

import os
from noctua import BaristaClient, BaristaError


def demo_validation():
    """Demonstrate validation with auto-rollback."""

    # Ensure token is set
    if not os.environ.get("BARISTA_TOKEN"):
        print("Please set BARISTA_TOKEN environment variable")
        return

    print("=" * 60)
    print("Validation with Auto-Rollback Demo")
    print("=" * 60)
    print()

    try:
        # Create client
        client = BaristaClient()
        print("✓ Client created")
        print()

        # Create a new model for testing
        print("Creating test model...")
        response = client.create_model(title="Validation Demo Model")
        if not response.ok:
            print(f"Failed to create model: {response.raw}")
            return

        model_id = response.model_id
        print(f"✓ Created model: {model_id}")
        print()

        # ========================================
        # Example 1: Simple validation
        # ========================================
        print("Example 1: Add individual with validation")
        print("-" * 40)

        # Add an individual and validate it was created correctly
        print("Adding GTPase activity with validation...")
        response = client.add_individual_validated(
            model_id,
            "GO:0003924",
            expected_type={"id": "GO:0003924", "label": "GTPase activity"}
        )

        if response._validation_failed:
            print(f"❌ Validation failed and rolled back: {response._validation_reason}")
        else:
            print("✓ Individual added and validated successfully")
            model = client.get_model(model_id)
            print(f"  Individuals in model: {len(model.individuals)}")
        print()

        # ========================================
        # Example 2: Batch operations with validation
        # ========================================
        print("Example 2: Batch operations with validation")
        print("-" * 40)

        # Build multiple requests
        requests = [
            client.req_add_individual(model_id, "GO:0004674", "kinase"),  # protein kinase
            client.req_add_individual(model_id, "GO:0005737", "cytoplasm"),  # cytoplasm
        ]

        print("Adding protein kinase and cytoplasm with validation...")
        response = client.execute_with_validation(
            requests,
            expected_individuals=[
                {"id": "GO:0004674", "label": "protein serine/threonine kinase activity"},
                {"id": "GO:0005737", "label": "cytoplasm"}
            ]
        )

        if response._validation_failed:
            print(f"❌ Validation failed: {response._validation_reason}")
        else:
            print("✓ Both individuals added and validated")
            model = client.get_model(model_id)
            print(f"  Total individuals: {len(model.individuals)}")
        print()

        # ========================================
        # Example 3: Demonstrating rollback
        # ========================================
        print("Example 3: Intentional validation failure to show rollback")
        print("-" * 40)

        # Count current individuals
        model_before = client.get_model(model_id)
        count_before = len(model_before.individuals)
        print(f"Individuals before operation: {count_before}")

        # Try to add an individual but validate for wrong type
        print("Adding GO:0003924 but validating for GO:9999999...")
        response = client.add_individual_validated(
            model_id,
            "GO:0003924",
            expected_type={"id": "GO:9999999"}  # Wrong ID!
        )

        if response._validation_failed:
            print(f"✓ Validation correctly failed: {response._validation_reason}")
            print("✓ Operation was automatically rolled back")

            # Check that rollback worked
            model_after = client.get_model(model_id)
            count_after = len(model_after.individuals)
            print(f"Individuals after rollback: {count_after}")
            assert count_before == count_after, "Rollback didn't work!"
        else:
            print("❌ Validation should have failed but didn't")
        print()

        # ========================================
        # Example 4: Complex validation scenario
        # ========================================
        print("Example 4: Complex validation with multiple conditions")
        print("-" * 40)

        # Build a more complex set of operations
        requests = [
            client.req_add_individual(model_id, "GO:0003924", "ras"),  # GTPase
            client.req_add_individual(model_id, "GO:0004674", "raf"),  # kinase
            client.req_add_fact(model_id, "ras", "raf", "RO:0002413"),  # add edge
        ]

        print("Building RAS-RAF interaction with validation...")

        # Note: We're only validating individuals here, not the fact
        # Fact validation could be added as a future enhancement
        response = client.execute_with_validation(
            requests,
            expected_individuals=[
                {"id": "GO:0003924"},  # GTPase must be present
                {"id": "GO:0004674"},  # Kinase must be present
            ]
        )

        if response._validation_failed:
            print(f"❌ Complex operation failed: {response._validation_reason}")
        else:
            print("✓ Complex operation succeeded with validation")
            model = client.get_model(model_id)
            print(f"  Individuals: {len(model.individuals)}")
            print(f"  Facts: {len(model.facts)}")
        print()

        # ========================================
        # Example 5: Manual validation
        # ========================================
        print("Example 5: Manual validation without auto-rollback")
        print("-" * 40)

        # Get current model state
        model_response = client.get_model(model_id)

        # Manually check validation
        print("Checking if model contains GTPase activity...")
        has_gtpase = model_response.validate_individuals([
            {"id": "GO:0003924", "label": "GTPase activity"}
        ])

        if has_gtpase:
            print("✓ Model contains GTPase activity")
        else:
            print("✗ Model does not contain GTPase activity")

        print("Checking if model contains DNA binding...")
        has_dna_binding = model_response.validate_individuals([
            {"id": "GO:0003677", "label": "DNA binding"}
        ])

        if has_dna_binding:
            print("✓ Model contains DNA binding")
        else:
            print("✗ Model does not contain DNA binding (expected)")
        print()

        # ========================================
        # Summary
        # ========================================
        print("=" * 60)
        print("✅ Demo complete!")
        print()
        print("Key takeaways:")
        print("  • Use execute_with_validation() for operations with validation")
        print("  • Use add_individual_validated() for single individuals")
        print("  • Validation failures trigger automatic rollback")
        print("  • Check response._validation_failed to detect rollbacks")
        print("  • Manual validation is available via validate_individuals()")
        print()
        print(f"Test model {model_id} remains for inspection")
        from noctua import get_noctua_url
        print(f"View at: {get_noctua_url(model_id, dev=True)}")

    except BaristaError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    demo_validation()