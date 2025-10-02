#!/usr/bin/env python
"""
Demonstration of client-side variable tracking in noctua-py.

Variables allow you to use simple names instead of complex IDs when
building GO-CAM models programmatically.
"""

import os
from noctua import BaristaClient, BaristaError


def demo_variable_tracking():
    """Demonstrate building a model using variable names."""

    # Ensure token is set
    if not os.environ.get("BARISTA_TOKEN"):
        print("Please set BARISTA_TOKEN environment variable")
        return

    print("=" * 60)
    print("Variable Tracking Demo")
    print("=" * 60)
    print()

    try:
        # Create client with variable tracking enabled (default)
        client = BaristaClient()
        print("✓ Client created with variable tracking enabled")
        print()

        # Create a new model
        print("Creating new model...")
        response = client.create_model(title="Variable Tracking Demo")
        if not response.ok:
            print(f"Failed to create model: {response.raw}")
            return

        model_id = response.model_id
        print(f"✓ Created model: {model_id}")
        print()

        # Add individuals using meaningful variable names
        print("Adding molecular activities with variable names...")

        # Instead of tracking complex IDs, use simple variable names
        response = client.add_individual(model_id, "GO:0003924", assign_var="ras")
        print("  Added GTPase activity as 'ras'")

        response = client.add_individual(model_id, "GO:0004674", assign_var="raf")
        print("  Added protein kinase activity as 'raf'")

        response = client.add_individual(model_id, "GO:0004707", assign_var="mek")
        print("  Added MAP kinase activity as 'mek'")

        response = client.add_individual(model_id, "GO:0004709", assign_var="erk")
        print("  Added MAP kinase kinase kinase activity as 'erk'")
        print()

        # Show tracked variables
        print("Tracked variables:")
        variables = client.get_variables(model_id)
        for var, actual_id in variables.items():
            print(f"  {var:10} -> {actual_id}")
        print()

        # Build pathway using variable names instead of IDs!
        print("Building pathway using variable names...")

        # No need to look up IDs - just use the variable names
        response = client.add_fact(model_id, "ras", "raf", "RO:0002413")
        if response.ok:
            print("  ✓ Added: ras → raf")

        response = client.add_fact(model_id, "raf", "mek", "RO:0002413")
        if response.ok:
            print("  ✓ Added: raf → mek")

        response = client.add_fact(model_id, "mek", "erk", "RO:0002413")
        if response.ok:
            print("  ✓ Added: mek → erk")
        print()

        # Add evidence using variables
        print("Adding evidence using variables...")
        response = client.add_fact_with_evidence(
            model_id,
            "ras",  # Using variable name, not ID!
            "raf",  # Using variable name, not ID!
            "RO:0002413",
            "ECO:0000314",  # direct assay evidence
            ["PMID:12345678"],
            with_from=["UniProtKB:P01112"]  # HRAS
        )
        if response.ok:
            print("  ✓ Added evidence to ras → raf edge")
        print()

        # Mix variables with actual IDs/CURIEs
        print("You can also mix variables with CURIEs...")

        # Add a cellular component
        response = client.add_individual(model_id, "GO:0005737", assign_var="cytoplasm")
        print("  Added cytoplasm as 'cytoplasm'")

        # You can use a variable with a CURIE
        response = client.add_fact(
            model_id,
            "ras",  # variable
            "cytoplasm",  # variable
            "BFO:0000066"  # occurs in (CURIE)
        )
        if response.ok:
            print("  ✓ Added: ras occurs_in cytoplasm")
        print()

        # Demonstrate deletion using variables
        print("Deleting edges using variables...")
        response = client.delete_edge(model_id, "mek", "erk", "RO:0002413")
        if response.ok:
            print("  ✓ Deleted: mek → erk")
        print()

        # Final model state
        response = client.get_model(model_id)
        if response.ok:
            print("Final model state:")
            print(f"  Individuals: {len(response.individuals)}")
            print(f"  Facts: {len(response.facts)}")
            print()

        print("✅ Demo complete!")
        print()
        print("Benefits of variable tracking:")
        print("  • No need to search for created IDs")
        print("  • Cleaner, more readable code")
        print("  • Works with all operations (add/remove/delete)")
        print("  • Can mix variables with CURIEs/IDs")
        print("  • Variables are model-scoped (no conflicts)")

    except BaristaError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    demo_variable_tracking()