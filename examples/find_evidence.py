#!/usr/bin/env python
"""Example of finding GO annotation evidence for GO-CAM edges.

This example demonstrates how to use the new find_evidence methods that
combine Barista (GO-CAM) and Amigo (GOlr) functionality.
"""

from noctua.barista import BaristaClient

def main():
    # Initialize client
    client = BaristaClient()

    # Example model ID (replace with an actual model)
    model_id = "gomodel:68d6f96e00000003"

    # Example 1: Find evidence for a specific edge
    print("Finding evidence for a single edge...")

    # This would find MF annotations for the bioentity that match the GO term
    evidence = client.find_evidence_for_edge(
        model_id,
        "subject_id",  # The molecular function individual
        "object_id",   # The bioentity individual
        "RO:0002333",  # enabled_by relationship
        evidence_types=["IDA", "IPI", "IMP"],  # Direct evidence only
        limit=5
    )

    print(f"Mapping type: {evidence['mapping_type']}")
    print(f"Summary: {evidence['summary']}")
    print(f"Found {len(evidence['annotations'])} annotations")

    for ann in evidence['annotations'][:3]:
        print(f"  - {ann['annotation_class_label']} ({ann['evidence_type']}) - {ann['reference']}")

    print()

    # Example 2: Find evidence for all edges in a model
    print("Finding evidence for entire model...")

    model_evidence = client.find_evidence_for_model(
        model_id,
        evidence_types=["IDA", "IPI", "IMP", "IGI", "IEP"],
        limit_per_edge=3
    )

    print(f"Model: {model_evidence['model_id']}")
    print(f"Summary: {model_evidence['summary']}")
    print(f"Total annotations found: {model_evidence['total_annotations']}")

    for edge_ev in model_evidence['edges_with_evidence']:
        if edge_ev['annotations']:
            edge_info = edge_ev['edge']
            print(f"\nEdge: {edge_info.get('subject_label', 'unknown')} -> {edge_info.get('object_label', 'unknown')}")
            print(f"  Type: {edge_ev['mapping_type']}")
            print(f"  Annotations: {len(edge_ev['annotations'])}")

            for ann in edge_ev['annotations'][:2]:
                print(f"    - {ann['annotation_class_label']} ({ann['evidence_type']}) - {ann['reference']}")


if __name__ == "__main__":
    main()