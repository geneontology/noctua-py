#!/usr/bin/env python
"""
Quick demo script showing noctua-py functionality.
Run with: python docs/examples/run_demo.py
"""

import os
from noctua.barista import BaristaClient

def main():
    # Ensure BARISTA_TOKEN is set in environment
    if not os.environ.get("BARISTA_TOKEN"):
        print("ERROR: BARISTA_TOKEN environment variable not set")
        print("Please set: export BARISTA_TOKEN=your-token-here")
        print("\nFor development: Contact the GO team for a dev token")
        print("For production: Get token from Noctua login")
        return 1

    print("GO-CAM AI Demo")
    print("=" * 50)

    # Create client
    client = BaristaClient()
    print(f"Connected to: {client.base_url}")
    print(f"Namespace: {client.namespace}")
    print()

    # List some models
    print("Fetching models...")
    result = client.list_models(limit=3, state="development")
    models = result.get("models", [])
    total = result.get("n", 0)

    print(f"Found {total} total models, showing {len(models)}:")
    for model in models:
        model_id = model.get("id", "")
        title = model.get("title", "(no title)")
        print(f"  - {model_id}: {title[:60]}...")
    print()

    # Create a new model
    print("Creating a new model...")
    response = client.create_model(title="Demo Model from Script")
    if response.ok:
        model_id = response.model_id
        print(f"Created model: {model_id}")

        # Add some individuals
        print("Adding molecular functions...")
        response = client.add_individual(model_id, "GO:0003924", assign_var="gtpase")
        if response.ok:
            print("  - Added GTPase activity")

        response = client.add_individual(model_id, "GO:0004674", assign_var="kinase")
        if response.ok:
            print("  - Added protein kinase activity")

        # Get model details
        print("\nModel summary:")
        response = client.get_model(model_id)
        if response.ok:
            print(f"  - Individuals: {len(response.individuals)}")
            print(f"  - Facts: {len(response.facts)}")
    else:
        print(f"Failed to create model: {response.raw.get('message', 'Unknown error')}")

    print()
    print("Demo complete! Use the Jupyter notebook for interactive exploration.")

if __name__ == "__main__":
    main()