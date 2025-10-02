#!/usr/bin/env python3
"""Demo of markdown export functionality."""

from noctua.barista import BaristaClient


def demo_markdown_export():
    """Demonstrate the markdown export feature."""
    # Initialize client (uses dev server by default)
    client = BaristaClient()

    # Create a simple model
    print("Creating demo model...")
    resp = client.create_model("Markdown Export Demo")
    if not resp.ok:
        print(f"Failed to create model: {resp.raw}")
        return

    model_id = resp.model_id
    print(f"Created model: {model_id}")

    # Add some individuals
    print("\nAdding activities...")
    client.add_individual(model_id, "GO:0003924", assign_var="ras")
    client.add_individual(model_id, "GO:0004674", assign_var="raf")
    client.add_individual(model_id, "GO:0004707", assign_var="mapk")

    # Add annotations
    print("Adding annotations...")
    client.update_individual_annotation(model_id, "ras", "enabled_by", "UniProtKB:P01112")
    client.update_individual_annotation(model_id, "ras", "rdfs:label", "HRAS GTPase")
    client.update_individual_annotation(model_id, "raf", "enabled_by", "UniProtKB:P04049")
    client.update_individual_annotation(model_id, "mapk", "enabled_by", "UniProtKB:P27361")

    # Add relationships
    print("Adding relationships...")
    client.add_fact(model_id, "ras", "raf", "RO:0002413")  # directly positively regulates
    client.add_fact(model_id, "raf", "mapk", "RO:0002413")

    # Add evidence
    print("Adding evidence...")
    client.add_fact_with_evidence(
        model_id,
        "ras",
        "raf",
        "RO:0002413",
        eco_id="ECO:0000314",
        sources=["PMID:8626452"]
    )

    # Export as markdown
    print(f"\nExporting model {model_id} as markdown...")
    export_resp = client.export_model(model_id, format="markdown")

    if export_resp.ok:
        markdown_content = export_resp.raw.get("data", "")
        print("\n" + "=" * 60)
        print("MARKDOWN OUTPUT:")
        print("=" * 60)
        print(markdown_content)
        print("=" * 60)

        # Save to file
        filename = f"{model_id.replace(':', '_')}.md"
        with open(filename, "w") as f:
            f.write(markdown_content)
        print(f"\nMarkdown saved to: {filename}")
    else:
        print(f"Failed to export: {export_resp.raw}")

    # Clean up (optional)
    print(f"\nCleaning up model {model_id}...")
    client.clear_model(model_id)
    print("Done!")


if __name__ == "__main__":
    demo_markdown_export()