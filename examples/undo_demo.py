#!/usr/bin/env python
"""
Demonstration of undo functionality in noctua-py.

This feature allows you to execute operations and then reverse them,
useful for experimentation and testing.
"""

import os
from noctua import BaristaClient, BaristaError


def demo_undo():
    """Demonstrate the undo functionality."""

    # Ensure token is set
    if not os.environ.get("BARISTA_TOKEN"):
        print("Please set BARISTA_TOKEN environment variable")
        return

    print("=" * 60)
    print("Undo Functionality Demo")
    print("=" * 60)
    print()

    try:
        # Create client
        client = BaristaClient()
        print("✓ Client created")
        print()

        # Create a new model for testing
        print("Creating test model...")
        response = client.create_model(title="Undo Demo Model")
        if not response.ok:
            print(f"Failed to create model: {response.raw}")
            return

        model_id = response.model_id
        print(f"✓ Created model: {model_id}")
        print()

        # ========================================
        # Example 1: Add and undo an individual
        # ========================================
        print("Example 1: Adding an individual with undo support...")

        # Add individual with undo enabled
        response = client.add_individual(
            model_id,
            "GO:0003924",  # GTPase activity
            enable_undo=True
        )

        if response.ok:
            print("✓ Added GTPase activity individual")
            print(f"  Can undo: {response.can_undo()}")

            # Check the model state
            model = client.get_model(model_id)
            print(f"  Individuals in model: {len(model.individuals)}")

            # Now undo the operation
            print("  Undoing the add operation...")
            undo_response = response.undo()

            if undo_response.ok:
                print("  ✓ Successfully undone!")

                # Check model state again
                model = client.get_model(model_id)
                print(f"  Individuals in model after undo: {len(model.individuals)}")
        print()

        # ========================================
        # Example 2: Add a fact and undo it
        # ========================================
        print("Example 2: Adding a fact with undo support...")

        # First add two individuals (without undo)
        print("  Setting up: Adding two individuals...")
        client.add_individual(model_id, "GO:0003924", assign_var="gtpase")
        client.add_individual(model_id, "GO:0004674", assign_var="kinase")

        # Now add a fact with undo enabled
        print("  Adding fact with undo enabled...")
        response = client.add_fact(
            model_id,
            "gtpase",
            "kinase",
            "RO:0002413",  # directly positively regulates
            enable_undo=True
        )

        if response.ok:
            print("  ✓ Added fact: gtpase → kinase")

            # Check facts
            model = client.get_model(model_id)
            print(f"  Facts in model: {len(model.facts)}")

            # Undo the fact
            print("  Undoing the fact...")
            undo_response = response.undo()

            if undo_response.ok:
                print("  ✓ Fact undone!")
                model = client.get_model(model_id)
                print(f"  Facts in model after undo: {len(model.facts)}")
        print()

        # ========================================
        # Example 3: Complex operation with undo
        # ========================================
        print("Example 3: Complex operation with evidence...")

        # Add fact with evidence (multiple operations in one)
        print("  Adding fact with evidence (undo enabled)...")
        response = client.add_fact_with_evidence(
            model_id,
            "gtpase",
            "kinase",
            "RO:0002413",
            "ECO:0000314",  # direct assay evidence
            ["PMID:12345678"],
            enable_undo=True
        )

        if response.ok:
            print("  ✓ Added fact with evidence")
            model = client.get_model(model_id)
            print(f"  Facts in model: {len(model.facts)}")

            # Show the fact details
            if model.facts:
                fact = model.facts[0]
                print(f"  Fact has evidence: {bool(fact.get('evidence'))}")

            # Undo everything
            print("  Undoing the entire operation...")
            undo_response = response.undo()

            if undo_response.ok:
                print("  ✓ Operation undone!")
                model = client.get_model(model_id)
                print(f"  Facts after undo: {len(model.facts)}")
        print()

        # ========================================
        # Example 4: Operations without undo
        # ========================================
        print("Example 4: Operations without undo support...")

        # Add without undo (default behavior)
        response = client.add_individual(model_id, "GO:0005737")  # cytoplasm

        if response.ok:
            print("✓ Added individual without undo support")
            print(f"  Can undo: {response.can_undo()}")

            # Trying to undo will raise an error
            try:
                response.undo()
            except BaristaError as e:
                print(f"  Expected error when trying to undo: {e}")
        print()

        # ========================================
        # Clean up
        # ========================================
        print("Cleaning up...")
        print(f"Note: Test model {model_id} remains for inspection")
        print("You can view it at:", end=" ")
        from noctua import get_noctua_url
        print(get_noctua_url(model_id, dev=True))
        print()

        print("✅ Demo complete!")
        print()
        print("Key takeaways:")
        print("  • Use enable_undo=True to make operations reversible")
        print("  • Check response.can_undo() before calling undo()")
        print("  • Undo reverses all operations in the batch")
        print("  • Complex operations (like add_fact_with_evidence) can be undone atomically")
        print("  • Undo is useful for experimentation and testing")

    except BaristaError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    demo_undo()