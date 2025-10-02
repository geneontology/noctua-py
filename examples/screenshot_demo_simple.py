#!/usr/bin/env python
"""
Simple demonstration of model building with simulated screenshot points.

This version doesn't require browser automation but shows where screenshots
would be captured in a real workflow.
"""

import os
from datetime import datetime
from noctua.barista import BaristaClient


class ScreenshotSimulator:
    """Simulates screenshot capture points without requiring browser."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.step_count = 0
        # Get token from environment
        token = os.environ.get("BARISTA_TOKEN", "")
        self.noctua_url = f"http://noctua-dev.berkeleybop.org/editor/graph/{model_id}"
        if token:
            self.noctua_url += f"?barista_token={token}"

    def capture(self, description: str):
        """Simulate a screenshot capture."""
        self.step_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"📸 [{timestamp}] Step {self.step_count}: {description}")
        print(f"   View in Noctua: {self.noctua_url}")
        return f"screenshot_{self.step_count:02d}.png"


def main():
    """Demonstrate model building with screenshot points."""

    # Ensure BARISTA_TOKEN is set in environment
    if not os.environ.get("BARISTA_TOKEN"):
        print("ERROR: BARISTA_TOKEN environment variable not set")
        print("Please set: export BARISTA_TOKEN=your-token-here")
        print("\nFor development: Contact the GO team for a dev token")
        print("For production: Get token from Noctua login")
        return 1

    client = BaristaClient()

    print("=" * 60)
    print("GO-CAM Model Building with Screenshot Points")
    print("=" * 60)
    print()

    # Create model
    print("Creating new model...")
    response = client.create_model(title="Demo: Signal Transduction with Screenshots")
    if not response.ok:
        print(f"Failed to create model: {response.raw}")
        return

    model_id = response.model_id
    print(f"✅ Created model: {model_id}")
    print()

    # Initialize screenshot simulator
    screenshots = ScreenshotSimulator(model_id)

    # Capture initial state
    screenshots.capture("Empty model created")
    print()

    # Track individuals
    individuals = {}

    # Step 1: Add receptor
    print("Step 1: Adding receptor activity...")
    response = client.add_individual(
        model_id,
        "GO:0004888",  # transmembrane signaling receptor activity
        assign_var="receptor"
    )
    if response.ok:
        for ind in response.individuals:
            types = ind.get("type", [])
            for t in types:
                if t.get("id") == "GO:0004888":
                    individuals["receptor"] = ind["id"]
                    print(f"✅ Added receptor: {ind['id']}")
                    break

    screenshots.capture("Receptor activity added")
    print()

    # Step 2: Add GTPase
    print("Step 2: Adding GTPase activity...")
    response = client.add_individual(
        model_id,
        "GO:0003924",  # GTPase activity
        assign_var="gtpase"
    )
    if response.ok:
        for ind in response.individuals:
            types = ind.get("type", [])
            for t in types:
                if t.get("id") == "GO:0003924":
                    individuals["gtpase"] = ind["id"]
                    print(f"✅ Added GTPase: {ind['id']}")
                    break

    screenshots.capture("GTPase activity added")
    print()

    # Step 3: Add kinase
    print("Step 3: Adding kinase activity...")
    response = client.add_individual(
        model_id,
        "GO:0004674",  # protein serine/threonine kinase activity
        assign_var="kinase"
    )
    if response.ok:
        for ind in response.individuals:
            types = ind.get("type", [])
            for t in types:
                if t.get("id") == "GO:0004674":
                    individuals["kinase"] = ind["id"]
                    print(f"✅ Added kinase: {ind['id']}")
                    break

    screenshots.capture("Kinase activity added - all nodes present")
    print()

    # Step 4: Add relationships
    print("Step 4: Adding causal relationships...")

    # Receptor -> GTPase
    if "receptor" in individuals and "gtpase" in individuals:
        response = client.add_fact(
            model_id,
            subject_id=individuals["receptor"],
            object_id=individuals["gtpase"],
            predicate_id="RO:0002413"  # directly positively regulates
        )
        if response.ok:
            print("✅ Added edge: Receptor → GTPase")
            screenshots.capture("First edge added (Receptor → GTPase)")

    # GTPase -> Kinase
    if "gtpase" in individuals and "kinase" in individuals:
        response = client.add_fact(
            model_id,
            subject_id=individuals["gtpase"],
            object_id=individuals["kinase"],
            predicate_id="RO:0002413"
        )
        if response.ok:
            print("✅ Added edge: GTPase → Kinase")
            screenshots.capture("Second edge added (GTPase → Kinase)")
    print()

    # Step 5: Add evidence
    print("Step 5: Adding evidence...")
    if "gtpase" in individuals and "kinase" in individuals:
        evidence_requests = client.req_add_evidence_to_fact(
            model_id,
            subject_id=individuals["gtpase"],
            object_id=individuals["kinase"],
            predicate_id="RO:0002413",
            eco_id="ECO:0000314",  # direct assay evidence
            sources=["PMID:12345678"],
            with_from=["UniProtKB:P01112"]  # HRAS
        )

        response = client.m3_batch(evidence_requests)
        if response.ok:
            print("✅ Added evidence to GTPase → Kinase edge")
            screenshots.capture("Evidence added to pathway")
    print()

    # Final summary
    print("=" * 60)
    print("Model Construction Complete!")
    print("=" * 60)

    response = client.get_model(model_id)
    if response.ok:
        print(f"Model ID: {model_id}")
        print(f"Individuals: {len(response.individuals)}")
        print(f"Facts/Edges: {len(response.facts)}")
        print()
        print("🌐 View in Noctua:")
        print(f"   {screenshots.noctua_url}")
        print()
        print(f"📸 Screenshot points captured: {screenshots.step_count}")
        print()
        print("In a real browser automation setup, these screenshots would show:")
        print("  1. Empty model canvas")
        print("  2. Individual nodes appearing")
        print("  3. Edges connecting nodes")
        print("  4. Evidence annotations")

    print()
    print("To enable real screenshots:")
    print("  1. Install Chrome/Firefox")
    print("  2. Install chromedriver/geckodriver")
    print("  3. Use the noctua_demo_with_screenshots.ipynb notebook")


if __name__ == "__main__":
    main()