"""CLI interface for noctua-py.

Guidelines followed:
- Typer-based single entry with subcommands
- No broad try/except; fail fast on unexpected errors
- Provide a --dry-run mode for safe payload inspection

Examples (doctest-style):

>>> # Dry-run add an individual (no network required)
>>> from typer.testing import CliRunner
>>> runner = CliRunner()
>>> result = runner.invoke(app, [
...     "barista", "add-individual",
...     "--model", "gomodel:TEST",
...     "--class", "GO:0016055",
...     "--dry-run",
... ])
>>> result.exit_code == 0
True
>>> "m3BatchPrivileged" in result.stdout
True
>>> "GO:0016055" in result.stdout
True
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Dict, List, Optional

import typer
import yaml

from .barista import (
    BARISTA_TOKEN_ENV,
    DEFAULT_BARISTA_BASE,
    DEFAULT_NAMESPACE,
    DEFAULT_PROVIDED_BY,
    LIVE_BARISTA_BASE,
    LIVE_NAMESPACE,
    BaristaClient,
    BaristaError,
)

if TYPE_CHECKING:
    from .amigo import AmigoClient

# Top-level Typer app
app = typer.Typer(help="noctua-py: tools for GO-CAM manipulation")

# Barista sub-app
barista_app = typer.Typer(help="Barista/Minerva convenience commands (defaults to DEV server; use --live to target production)")
app.add_typer(barista_app, name="barista")

# Amigo sub-app
amigo_app = typer.Typer(help="Amigo/GOlr query commands for searching GO annotations and bioentities")
app.add_typer(amigo_app, name="amigo")


def _make_client(
    token: Optional[str],
    base_url: Optional[str],
    namespace: Optional[str],
    provided_by: Optional[str],
    live: bool = False
) -> BaristaClient:
    """Create a BaristaClient with appropriate defaults.

    If live=True, use production servers. Otherwise use dev/test servers.
    Explicit parameters override both defaults and live flag.
    """
    if live and not base_url:
        base_url = LIVE_BARISTA_BASE
    if live and not namespace:
        namespace = LIVE_NAMESPACE

    return BaristaClient(
        token=token,
        base_url=base_url or DEFAULT_BARISTA_BASE,
        namespace=namespace or DEFAULT_NAMESPACE,
        provided_by=provided_by or DEFAULT_PROVIDED_BY,
    )


def _normalize_model_id(model_id: str) -> str:
    """Normalize model ID to include 'gomodel:' prefix if missing.

    Examples:
        6796b94c00003233 -> gomodel:6796b94c00003233
        gomodel:6796b94c00003233 -> gomodel:6796b94c00003233
        68d6f96e00000007 -> gomodel:68d6f96e00000007
    """
    if not model_id.startswith("gomodel:"):
        # Check if it looks like a hex ID (16 chars of hex)
        if len(model_id) == 16 and all(c in "0123456789abcdef" for c in model_id.lower()):
            return f"gomodel:{model_id}"
        # For any other format without prefix, add it
        elif ":" not in model_id:
            return f"gomodel:{model_id}"
    return model_id


def _print_dry_run(url: str, requests: List[dict], intention: str = "action", provided_by: Optional[str] = None) -> None:
    payload = {
        "intention": intention,
        "provided-by": provided_by or os.environ.get("BARISTA_PROVIDED_BY", "http://geneontology.org"),
        "requests": requests,
    }
    typer.echo(f"POST {url}")
    typer.echo(json.dumps(payload, indent=2))


def _parse_validation_spec(validation_specs: Optional[List[str]]) -> Optional[List[Dict[str, str]]]:
    """Parse validation specifications from CLI arguments.

    Accepts formats:
    - "GO:0003924" (just ID)
    - "GO:0003924=GTPase activity" (ID=label)
    - "GTPase activity" (just label, if no colon)

    Returns:
        List of dicts with 'id' and/or 'label' keys, or None if no specs
    """
    if not validation_specs:
        return None

    result = []
    for spec in validation_specs:
        if '=' in spec:
            # ID=label format
            parts = spec.split('=', 1)
            result.append({"id": parts[0].strip(), "label": parts[1].strip()})
        elif ':' in spec:
            # Just ID (CURIE format)
            result.append({"id": spec.strip()})
        else:
            # Just label (no colon, so not a CURIE)
            result.append({"label": spec.strip()})

    return result


@barista_app.command("create-model")
def create_model(
    title: Optional[str] = typer.Option(None, "--title", help="Title for the new model"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL (overrides --live flag)"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace (overrides --live flag)"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Create a new empty GO-CAM model."""
    client = _make_client(token, base_url, namespace, provided_by, live)

    typer.echo(f"Creating new model{' with title: ' + title if title else ''}...", err=True)
    resp = client.create_model(title)

    if resp.ok:
        model_id = resp.model_id
        typer.echo(f"Successfully created model: {model_id}")
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to create model: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("add-individual")
def add_individual(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    class_curie: str = typer.Option(..., "--class", help="Class CURIE to instantiate (e.g., GO:0016055)"),
    assign: str = typer.Option("x1", "--assign", help="Assign-to-variable identifier"),
    validate: Optional[List[str]] = typer.Option(None, "--validate", help="Expected types (e.g., 'GO:0003924' or 'GO:0003924=GTPase activity')"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL (overrides --live flag)"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace (overrides --live flag)"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the request and do not POST"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Add an individual of CLASS to MODEL via Barista m3BatchPrivileged.

    Optionally validate that expected types are present after creation.
    If validation fails, the operation is automatically rolled back.

    Examples:
        # Add without validation
        noctua-py barista add-individual --model MODEL --class GO:0003924

        # Add with validation (auto-rollback if not created)
        noctua-py barista add-individual --model MODEL --class GO:0003924 --validate GO:0003924

        # Validate with label
        noctua-py barista add-individual --model MODEL --class GO:0003924 --validate "GO:0003924=GTPase activity"
    """
    model = _normalize_model_id(model)
    req = BaristaClient.req_add_individual(model, class_curie, assign)
    if dry_run:
        # Determine URL for dry run display
        if base_url:
            actual_base = base_url
        elif live:
            actual_base = LIVE_BARISTA_BASE
        else:
            actual_base = DEFAULT_BARISTA_BASE

        if namespace:
            actual_namespace = namespace
        elif live:
            actual_namespace = LIVE_NAMESPACE
        else:
            actual_namespace = DEFAULT_NAMESPACE

        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        if validate:
            typer.echo(f"Note: Validation specs would be checked: {validate}")
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    # Parse validation specs if provided
    expected_individuals = _parse_validation_spec(validate)

    if expected_individuals:
        # Use validation-enabled execution
        resp = client.execute_with_validation([req], expected_individuals=expected_individuals)
        if resp.validation_failed:
            typer.echo(f"❌ Validation failed and rolled back: {resp.validation_reason}", err=True)
            typer.echo(json.dumps(resp.raw, indent=2))
            raise typer.Exit(code=1)
        else:
            typer.echo("✓ Operation succeeded and passed validation")
    else:
        # Standard execution without validation
        resp = client.m3_batch([req])

    typer.echo(json.dumps(resp.raw, indent=2))
    if not resp.ok:
        raise typer.Exit(code=1)


@barista_app.command("add-fact")
def add_fact(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    subject: str = typer.Option(..., "--subject", help="Subject individual id (CURIE/IRI in model)"),
    object_: str = typer.Option(..., "--object", help="Object individual id (CURIE/IRI in model)"),
    predicate: str = typer.Option(..., "--predicate", help="Predicate CURIE (e.g., RO:0002333)"),
    validate: Optional[List[str]] = typer.Option(None, "--validate", help="Expected types after operation"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV),
    base_url: Optional[str] = typer.Option(None),
    namespace: Optional[str] = typer.Option(None),
    provided_by: Optional[str] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Add an edge (fact) between two individuals in MODEL.

    Optionally validate that expected types are present after creation.
    If validation fails, the operation is automatically rolled back.
    """
    model = _normalize_model_id(model)
    req = BaristaClient.req_add_fact(model, subject, object_, predicate)
    if dry_run:
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        if validate:
            typer.echo(f"Note: Validation specs would be checked: {validate}")
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    # Parse validation specs if provided
    expected_individuals = _parse_validation_spec(validate)

    if expected_individuals:
        # Use validation-enabled execution
        resp = client.execute_with_validation([req], expected_individuals=expected_individuals)
        if resp.validation_failed:
            typer.echo(f"❌ Validation failed and rolled back: {resp.validation_reason}", err=True)
            typer.echo(json.dumps(resp.raw, indent=2))
            raise typer.Exit(code=1)
        else:
            typer.echo("✓ Operation succeeded and passed validation")
    else:
        # Standard execution without validation
        resp = client.m3_batch([req])

    typer.echo(json.dumps(resp.raw, indent=2))
    if not resp.ok:
        raise typer.Exit(code=1)


@barista_app.command("add-fact-evidence")
def add_fact_evidence(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    subject: str = typer.Option(..., "--subject", help="Subject individual id"),
    object_: str = typer.Option(..., "--object", help="Object individual id"),
    predicate: str = typer.Option(..., "--predicate", help="Predicate CURIE (e.g., RO:0002333)"),
    eco: str = typer.Option(..., "--eco", help="ECO evidence code (e.g., ECO:0000353)"),
    source: List[str] = typer.Option(..., "--source", help="One or more source CURIEs, e.g., PMID:...", rich_help_panel="Evidence"),
    with_from: List[str] = typer.Option(None, "--with", help="Optional with/from CURIEs", rich_help_panel="Evidence"),
    validate: Optional[List[str]] = typer.Option(None, "--validate", help="Expected types after operation"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV),
    base_url: Optional[str] = typer.Option(None),
    namespace: Optional[str] = typer.Option(None),
    provided_by: Optional[str] = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Add evidence annotation to an edge in MODEL (creates evidence individual and binds).

    Optionally validate that expected types are present after creation.
    If validation fails, the operation is automatically rolled back.
    """
    model = _normalize_model_id(model)
    reqs = BaristaClient.req_add_evidence_to_fact(model, subject, object_, predicate, eco, list(source), list(with_from) if with_from else None)
    if dry_run:
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, reqs, provided_by=provided_by or DEFAULT_PROVIDED_BY)
        if validate:
            typer.echo(f"Note: Validation specs would be checked: {validate}")
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    # Parse validation specs if provided
    expected_individuals = _parse_validation_spec(validate)

    if expected_individuals:
        # Use validation-enabled execution
        resp = client.execute_with_validation(reqs, expected_individuals=expected_individuals)
        if resp.validation_failed:
            typer.echo(f"❌ Validation failed and rolled back: {resp.validation_reason}", err=True)
            typer.echo(json.dumps(resp.raw, indent=2))
            raise typer.Exit(code=1)
        else:
            typer.echo("✓ Operation succeeded and passed validation")
    else:
        # Standard execution without validation
        resp = client.m3_batch(reqs)

    typer.echo(json.dumps(resp.raw, indent=2))
    if not resp.ok:
        raise typer.Exit(code=1)


@barista_app.command("delete-individual")
def delete_individual(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    individual: str = typer.Option(..., "--individual", help="Individual ID to delete"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the request without executing"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Delete an individual (node) from a model."""
    model = _normalize_model_id(model)
    req = BaristaClient.req_remove_individual(model, individual)
    if dry_run:
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)
    typer.echo(f"Deleting individual {individual} from model {model}...", err=True)
    resp = client.delete_individual(model, individual)

    if resp.ok:
        typer.echo(f"Successfully deleted individual {individual}")
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to delete individual: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("delete-edge")
def delete_edge(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    subject: str = typer.Option(..., "--subject", help="Subject individual id"),
    object_: str = typer.Option(..., "--object", help="Object individual id"),
    predicate: str = typer.Option(..., "--predicate", help="Predicate CURIE (e.g., RO:0002333)"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the request without executing"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Delete an edge (fact) between two individuals in a model."""
    model = _normalize_model_id(model)
    req = BaristaClient.req_remove_fact(model, subject, object_, predicate)
    if dry_run:
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)
    typer.echo(f"Deleting edge from {subject} to {object_} with predicate {predicate}...", err=True)
    resp = client.delete_edge(model, subject, object_, predicate)

    if resp.ok:
        typer.echo("Successfully deleted edge")
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to delete edge: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("clear-model")
def clear_model(
    model: str = typer.Option(..., "--model", help="Target model id to clear (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would be removed without actually removing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    force: bool = typer.Option(False, "--force", help="Force clear even if model is in production state (DANGEROUS)"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Remove all nodes and edges from a model, leaving it empty.

    Production models are protected by default and cannot be cleared without --force flag.
    """
    model = _normalize_model_id(model)
    client = _make_client(token, base_url, namespace, provided_by, live)

    # Get current model state to show what will be removed
    typer.echo(f"Fetching model {model}...")
    model_resp = client.get_model(model)
    if not model_resp.ok:
        typer.echo(f"Failed to get model: {json.dumps(model_resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)

    # Check model state
    model_state = model_resp.model_state
    if model_state:
        typer.echo(f"Model state: {model_state}")
        if model_state == "production" and not force:
            typer.echo(
                typer.style(
                    f"ERROR: Model {model} is in production state and cannot be cleared.",
                    fg=typer.colors.RED,
                    bold=True
                ),
                err=True
            )
            typer.echo(
                "Production models are protected from accidental deletion.\n"
                "If you really need to clear a production model, use --force flag (DANGEROUS!)",
                err=True
            )
            raise typer.Exit(code=1)

    num_individuals = len(model_resp.individuals)
    num_facts = len(model_resp.facts)

    if num_individuals == 0 and num_facts == 0:
        typer.echo(f"Model {model} is already empty.")
        raise typer.Exit(code=0)

    typer.echo(f"Model {model} contains:")
    typer.echo(f"  - {num_individuals} individuals/nodes")
    typer.echo(f"  - {num_facts} facts/edges")

    if dry_run:
        typer.echo("\n[DRY RUN] Would remove:")
        for individual in model_resp.individuals:
            typer.echo(f"  - Individual: {individual.get('id')}")
        for fact in model_resp.facts:
            typer.echo(f"  - Fact: {fact.get('subject')} -> {fact.get('object')} [{fact.get('property')}]")
        raise typer.Exit(code=0)

    # Confirm before clearing
    if not yes:
        warning_msg = f"Are you sure you want to remove all {num_individuals} nodes and {num_facts} edges from model {model}?"
        if model_state == "production":
            warning_msg = typer.style(
                f"WARNING: {model} is a PRODUCTION model! ",
                fg=typer.colors.YELLOW,
                bold=True
            ) + warning_msg
        confirm = typer.confirm(warning_msg)
        if not confirm:
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

    # Clear the model
    typer.echo(f"Clearing model {model}...")
    try:
        resp = client.clear_model(model, force=force)
    except BaristaError as e:
        typer.echo(typer.style(f"ERROR: {e}", fg=typer.colors.RED, bold=True), err=True)
        raise typer.Exit(code=1)

    if resp.ok:
        typer.echo(f"Successfully cleared model {model}")
        typer.echo(f"Removed {num_individuals} individuals and {num_facts} facts")
    else:
        typer.echo(f"Failed to clear model: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("export-model")
def export_model(
    model: str = typer.Option(..., "--model", help="Target model id to export (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    format: str = typer.Option("minerva-json", "--format", "-f", help="Export format: minerva-json (native), gocam-json, gocam-yaml, markdown"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Export a model in various formats (minerva-json, gocam-json, gocam-yaml, markdown)."""
    model = _normalize_model_id(model)
    client = _make_client(token, base_url, namespace, provided_by, live)

    typer.echo(f"Exporting model {model} as {format}...", err=True)

    # Handle markdown format using the client's export_model method
    if format == "markdown":
        resp = client.export_model(model, format="markdown")
        if not resp.ok:
            typer.echo(f"Failed to export model: {json.dumps(resp.raw, indent=2)}", err=True)
            raise typer.Exit(code=1)
        exported_content = resp.raw.get("data", "")
    else:
        # Use get_model to get the native Minerva JSON format
        resp = client.get_model(model)

        if not resp.ok:
            typer.echo(f"Failed to export model: {json.dumps(resp.raw, indent=2)}", err=True)
            raise typer.Exit(code=1)

        # Get the data portion of the response (contains the model)
        minerva_data = resp.raw.get("data", {})

        if format == "minerva-json":
            # Native Minerva JSON format (full response)
            exported_content = json.dumps(resp.raw, indent=2)
        elif format in ["gocam-json", "gocam-yaml"]:
            # Convert to GO-CAM model using the gocam package
            try:
                from gocam.translation.minerva_wrapper import MinervaWrapper  # type: ignore

                # Ensure the model has required fields
                if "id" not in minerva_data:
                    minerva_data["id"] = model

                # Extract title from annotations if not at top level
                if "title" not in minerva_data:
                    for annotation in minerva_data.get("annotations", []):
                        if annotation.get("key") == "title":
                            minerva_data["title"] = annotation.get("value", "Untitled Model")
                            break
                    else:
                        minerva_data["title"] = "Untitled Model"

                # Convert Minerva JSON to GO-CAM Model
                # Note: Some models may not have enabled_by facts, which will generate warnings
                gocam_model = MinervaWrapper.minerva_object_to_model(minerva_data)

                if format == "gocam-json":
                    # Export as GO-CAM JSON
                    exported_content = gocam_model.model_dump_json(indent=2, exclude_none=True)
                else:  # gocam-yaml
                    # Export as GO-CAM YAML
                    model_dict = gocam_model.model_dump(exclude_none=True)
                    exported_content = yaml.dump(model_dict, default_flow_style=False, sort_keys=False)
            except ImportError as e:
                typer.echo(f"Error: gocam package required for {format} export: {e}", err=True)
                raise typer.Exit(code=1)
            except Exception as e:
                typer.echo(f"Error converting to {format}: {e}", err=True)
                typer.echo("Note: This model may not follow standard GO-CAM structure (e.g., missing enabled_by facts)", err=True)
                raise typer.Exit(code=1)
        else:
            typer.echo(f"Unknown format: {format}. Supported: minerva-json, gocam-json, gocam-yaml, markdown", err=True)
            raise typer.Exit(code=1)

    # Write to file or stdout
    if output:
        with open(output, "w") as f:
            f.write(exported_content)
        typer.echo(f"Model exported to {output}", err=True)
    else:
        # Write to stdout (no message, just the content)
        typer.echo(exported_content)


@barista_app.command("get-model")
def get_model(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Get details of a specific model."""
    model = _normalize_model_id(model)
    client = _make_client(token, base_url, namespace, provided_by, live)

    typer.echo(f"Getting model {model}...", err=True)
    resp = client.get_model(model)

    if resp.ok:
        typer.echo(json.dumps(resp.raw["data"], indent=2))
    else:
        typer.echo(f"Failed to get model: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("update-metadata")
def update_metadata(
    model: str = typer.Option(..., "--model", help="Target model id to update (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    title: Optional[str] = typer.Option(None, "--title", help="New title for the model"),
    state: Optional[str] = typer.Option(None, "--state", help="New state (e.g., 'production', 'development', 'internal_test')"),
    comment: Optional[str] = typer.Option(None, "--comment", help="New comment for the model"),
    replace: bool = typer.Option(True, "--replace/--add", help="Replace existing values (default) or add new ones"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Update model metadata (title, state, comment).

    Examples:
    - Update title: noctua-py barista update-metadata --model 6796b94c00003233 --title "New title"
    - Change state: noctua-py barista update-metadata --model 6796b94c00003233 --state production
    - Add comment: noctua-py barista update-metadata --model 6796b94c00003233 --comment "Review needed" --add
    """
    model = _normalize_model_id(model)

    # Check that at least one update is specified
    if not any([title, state, comment]):
        typer.echo("Error: Must specify at least one of --title, --state, or --comment", err=True)
        raise typer.Exit(code=1)

    client = _make_client(token, base_url, namespace, provided_by, live)

    # Show current values
    typer.echo(f"Fetching current metadata for {model}...", err=True)
    current_resp = client.get_model(model)
    if not current_resp.ok:
        typer.echo(f"Failed to get model: {json.dumps(current_resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)

    # Display current values
    data = current_resp.raw.get("data", {})
    annotations = data.get("annotations", [])

    current_values: Dict[str, List[str]] = {"title": [], "state": [], "comment": []}
    for ann in annotations:
        key = ann.get("key")
        value = ann.get("value")
        if key in current_values:
            current_values[key].append(value)

    typer.echo("\nCurrent metadata:", err=True)
    for key, values in current_values.items():
        if values:
            for value in values:
                typer.echo(f"  {key}: {value}", err=True)

    # Show what will be updated
    typer.echo("\nUpdates to apply:", err=True)
    if title:
        typer.echo(f"  title: {title} ({'replace' if replace else 'add'})", err=True)
    if state:
        typer.echo(f"  state: {state} ({'replace' if replace else 'add'})", err=True)
    if comment:
        typer.echo(f"  comment: {comment} ({'replace' if replace else 'add'})", err=True)

    if dry_run:
        typer.echo("\n[DRY RUN] No changes applied", err=True)
        return

    # Confirm if updating state to production
    if state == "production" and not dry_run:
        if not typer.confirm(
            "\n⚠️  Setting state to 'production' will protect the model from deletion. Continue?"
        ):
            typer.echo("Update cancelled", err=True)
            raise typer.Exit(code=0)

    # Apply updates
    typer.echo("\nApplying updates...", err=True)
    resp = client.update_model_metadata(
        model,
        title=title,
        state=state,
        comment=comment,
        replace=replace
    )

    if resp.ok:
        typer.echo("✓ Metadata updated successfully", err=True)
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to update metadata: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("add-annotation")
def add_annotation(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    key: str = typer.Option(..., "--key", help="Annotation key (e.g., 'comment', 'status', custom keys)"),
    value: str = typer.Option(..., "--value", help="Annotation value"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Add a custom annotation to a model.

    This is for adding arbitrary key-value annotations beyond the standard
    title/state/comment metadata.
    """
    model = _normalize_model_id(model)

    if dry_run:
        req = BaristaClient.req_update_model_annotation(model, key, value)
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    typer.echo(f"Adding annotation {key}={value} to {model}...", err=True)
    resp = client.add_model_annotation(model, key, value)

    if resp.ok:
        typer.echo("✓ Annotation added successfully", err=True)
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to add annotation: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("remove-annotation")
def remove_annotation(
    model: str = typer.Option(..., "--model", help="Target model id (e.g., gomodel:6796b94c00003233 or just 6796b94c00003233)"),
    key: str = typer.Option(..., "--key", help="Annotation key to remove"),
    value: str = typer.Option(..., "--value", help="Specific value to remove"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Remove a specific annotation from a model.

    You must specify both the key and the exact value to remove.
    """
    model = _normalize_model_id(model)

    if dry_run:
        req = BaristaClient.req_remove_model_annotation(model, key, value)
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    typer.echo(f"Removing annotation {key}={value} from {model}...", err=True)
    resp = client.remove_model_annotation(model, key, value)

    if resp.ok:
        typer.echo("✓ Annotation removed successfully", err=True)
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to remove annotation: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("update-individual-annotation")
def update_individual_annotation(
    model: str = typer.Option(..., "--model", help="Target model id"),
    individual: str = typer.Option(..., "--individual", help="Individual ID to update"),
    key: str = typer.Option(..., "--key", help="Annotation key (e.g., 'enabled_by', 'rdfs:label')"),
    value: str = typer.Option(..., "--value", help="New value for the annotation"),
    old_value: Optional[str] = typer.Option(None, "--old-value", help="Current value to replace (if not provided, adds new)"),
    validate: Optional[str] = typer.Option(None, "--validate", help="Validation spec: 'id:label' to verify individual"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Update an annotation on an individual within a model.

    Use validation to prevent updating the wrong individual by checking its label.
    If validation fails, the operation will be automatically rolled back.

    Examples:
        # Update enabled_by annotation with validation
        --individual gomodel:xyz123 --key enabled_by --value UniProtKB:P12345 \\
        --validate "gomodel:xyz123:GTPase activity"

        # Replace an existing annotation
        --individual gomodel:xyz123 --key rdfs:label --value "New label" \\
        --old-value "Old label"
    """
    model = _normalize_model_id(model)

    if dry_run:
        req_result = BaristaClient.req_update_individual_annotation(model, individual, key, value, old_value)
        # req_result can be either a single request or a list of requests
        requests = req_result if isinstance(req_result, list) else [req_result]
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, requests, provided_by=provided_by or DEFAULT_PROVIDED_BY)
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    # Parse validation spec if provided
    validation_dict = None
    if validate:
        parsed = _parse_validation_spec([validate])
        validation_dict = parsed[0] if parsed else None
        typer.echo(f"Updating annotation with validation: {validation_dict}", err=True)

    action = "Replacing" if old_value else "Adding"
    typer.echo(f"{action} annotation {key}={value} on individual {individual}...", err=True)

    resp = client.update_individual_annotation(
        model,
        individual,
        key,
        value,
        old_value=old_value,
        validation=validation_dict
    )

    if resp.validation_failed:
        typer.echo(f"✗ Validation failed and changes rolled back: {resp.validation_reason}", err=True)
        raise typer.Exit(code=1)
    elif resp.ok:
        typer.echo("✓ Annotation updated successfully", err=True)
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to update annotation: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("remove-individual-annotation")
def remove_individual_annotation(
    model: str = typer.Option(..., "--model", help="Target model id"),
    individual: str = typer.Option(..., "--individual", help="Individual ID"),
    key: str = typer.Option(..., "--key", help="Annotation key to remove"),
    value: str = typer.Option(..., "--value", help="Specific value to remove"),
    validate: Optional[str] = typer.Option(None, "--validate", help="Validation spec: 'id:label' to verify individual"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """Remove a specific annotation from an individual within a model.

    Use validation to prevent modifying the wrong individual by checking its label.
    If validation fails, the operation will be automatically rolled back.

    Example:
        --individual gomodel:xyz123 --key enabled_by --value UniProtKB:P12345 \\
        --validate "gomodel:xyz123:GTPase activity"
    """
    model = _normalize_model_id(model)

    if dry_run:
        req = BaristaClient.req_remove_individual_annotation(model, individual, key, value)
        actual_base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)
        actual_namespace = namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE)
        url = f"{actual_base.rstrip('/')}/api/{actual_namespace}/m3BatchPrivileged"
        _print_dry_run(url, [req], provided_by=provided_by or DEFAULT_PROVIDED_BY)
        raise typer.Exit(code=0)

    client = _make_client(token, base_url, namespace, provided_by, live)

    # Parse validation spec if provided
    validation_dict = None
    if validate:
        parsed = _parse_validation_spec([validate])
        validation_dict = parsed[0] if parsed else None
        typer.echo(f"Removing annotation with validation: {validation_dict}", err=True)

    typer.echo(f"Removing annotation {key}={value} from individual {individual}...", err=True)

    resp = client.remove_individual_annotation(
        model,
        individual,
        key,
        value,
        validation=validation_dict
    )

    if resp.validation_failed:
        typer.echo(f"✗ Validation failed and changes rolled back: {resp.validation_reason}", err=True)
        raise typer.Exit(code=1)
    elif resp.ok:
        typer.echo("✓ Annotation removed successfully", err=True)
        typer.echo(json.dumps(resp.raw, indent=2))
    else:
        typer.echo(f"Failed to remove annotation: {json.dumps(resp.raw, indent=2)}", err=True)
        raise typer.Exit(code=1)


@barista_app.command("list-models")
def list_models(
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of models returned"),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination"),
    title: Optional[str] = typer.Option(None, "--title", help="Filter by title (searches for models containing this text)"),
    state: Optional[str] = typer.Option(None, "--state", help="Filter by state (e.g., 'production', 'development', 'internal_test')"),
    contributor: Optional[str] = typer.Option(None, "--contributor", help="Filter by contributor (ORCID URL, e.g., 'https://orcid.org/0000-0002-6601-2165')"),
    group: Optional[str] = typer.Option(None, "--group", help="Filter by group/provider (e.g., 'http://www.wormbase.org')"),
    pmid: Optional[str] = typer.Option(None, "--pmid", help="Filter by PubMed ID (e.g., 'PMID:12345678')"),
    gp: Optional[str] = typer.Option(None, "--gp", "--gene", help="Filter by gene product (e.g., 'UniProtKB:Q9BRQ8', 'MGI:MGI:97490')"),
    token: Optional[str] = typer.Option(None, envvar=BARISTA_TOKEN_ENV, help=f"Barista token (env {BARISTA_TOKEN_ENV})"),
    base_url: Optional[str] = typer.Option(None, help="Barista base URL"),
    namespace: Optional[str] = typer.Option(None, help="Minerva namespace"),
    provided_by: Optional[str] = typer.Option(None, help="provided-by agent"),
    live: bool = typer.Option(False, "--live", help="Use production server instead of dev server"),
):
    """List all models with their IDs and titles.

    Available filters:
    - title: Search in model titles
    - state: Filter by state (production, development, internal_test)
    - contributor: Filter by contributor ORCID
    - group: Filter by group/provider
    - pmid: Filter by PubMed ID reference
    - gp/gene: Filter by gene product ID (UniProtKB, MGI, WB, SGD, etc.)

    Examples of gene product IDs:
    - UniProtKB:Q9BRQ8 (human AIFM2)
    - MGI:MGI:97490 (mouse Pax6)
    - WB:WBGene00000912 (C. elegans daf-16)
    - SGD:S000000479 (yeast CDC28)
    """
    # Note: This doesn't require authentication since it uses the search endpoint
    # But we still create a client to get the correct base URL
    base = base_url or (LIVE_BARISTA_BASE if live else DEFAULT_BARISTA_BASE)

    # If token is not provided, use a dummy one for client initialization
    # The search endpoint doesn't require auth
    if not token:
        token = "dummy-token-for-search"

    client = BaristaClient(
        token=token,
        base_url=base,
        namespace=namespace or (LIVE_NAMESPACE if live else DEFAULT_NAMESPACE),
        provided_by=provided_by or DEFAULT_PROVIDED_BY,
    )


    try:
        result = client.list_models(
            limit=limit,
            offset=offset,
            title=title,
            state=state,
            contributor=contributor,
            group=group,
            pmid=pmid,
            gp=gp
        )
    except Exception as e:
        typer.echo(f"Failed to list models: {e}", err=True)
        raise typer.Exit(code=1)

    # Parse the search results
    models = result.get("models", [])
    total = result.get("n", len(models))

    if not models:
        typer.echo("No models found", err=True)
        return

    if total == len(models):
        typer.echo(f"Found {total} models:")
    else:
        typer.echo(f"Showing {len(models)} of {total} models:")

    # Display models in a formatted table
    for model in models:
        model_id = model.get("id", "")
        title = model.get("title", "(no title)")
        state = model.get("state", "")

        # Format output line
        line = f"{model_id}\t{title}"
        if state:
            line += f"\t[{state}]"

        # Show gene matches if searching by gene
        if gp and model.get("query_match"):
            match_count = sum(len(nodes) for nodes in model["query_match"].values())
            if match_count > 0:
                line += f"\t({match_count} node matches)"

        typer.echo(line)


# Amigo commands
def _make_amigo_client(base_url: Optional[str] = None) -> "AmigoClient":
    """Create an Amigo client."""
    from noctua.amigo import AmigoClient
    return AmigoClient(base_url=base_url)


@amigo_app.command("search-bioentities")
def search_bioentities(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Text search in bioentity names/labels"),
    taxon: Optional[str] = typer.Option(None, "--taxon", help="Organism filter (e.g., NCBITaxon:9606 for human)"),
    bioentity_type: Optional[str] = typer.Option(None, "--type", help="Entity type filter (e.g., protein, gene)"),
    source: Optional[str] = typer.Option(None, "--source", help="Source database filter (e.g., UniProtKB, MGI)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Custom GOlr endpoint URL"),
):
    """Search for bioentities (genes/proteins) with optional filtering."""
    client = _make_amigo_client(base_url)

    try:
        results = client.search_bioentities(
            text=text,
            taxon=taxon,
            bioentity_type=bioentity_type,
            source=source,
            limit=limit
        )

        if not results:
            typer.echo("No bioentities found.")
            return

        typer.echo(f"Found {len(results)} bioentities:")
        # Print header
        typer.echo("BIOENTITY\tLABEL\tNAME\tTAXON\tTYPE\tSOURCE")

        for result in results:
            typer.echo(f"{result.id}\t{result.label}\t{result.name}\t{result.taxon_label}\t{result.type}\t{result.source}")

    except Exception as e:
        typer.echo(f"Error searching bioentities: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


@amigo_app.command("get-bioentity")
def get_bioentity(
    bioentity_id: str = typer.Argument(..., help="Bioentity ID (e.g., UniProtKB:P12345)"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Custom GOlr endpoint URL"),
):
    """Get details for a specific bioentity."""
    client = _make_amigo_client(base_url)

    try:
        result = client.get_bioentity(bioentity_id)

        if not result:
            typer.echo(f"Bioentity not found: {bioentity_id}")
            raise typer.Exit(1)

        typer.echo(f"ID: {result.id}")
        typer.echo(f"Label: {result.label}")
        typer.echo(f"Name: {result.name}")
        typer.echo(f"Type: {result.type}")
        typer.echo(f"Organism: {result.taxon_label} ({result.taxon})")
        typer.echo(f"Source: {result.source}")

    except Exception as e:
        typer.echo(f"Error getting bioentity: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


@amigo_app.command("search-annotations")
def search_annotations(
    bioentity: Optional[str] = typer.Option(None, "--bioentity", "-b", help="Bioentity ID to filter by"),
    go_term: Optional[str] = typer.Option(None, "--go-term", "-g", help="GO term ID to filter by"),
    go_terms_closure: Optional[List[str]] = typer.Option(None, "--closure", "-c", help="GO terms including closure (can repeat)"),
    evidence_types: Optional[List[str]] = typer.Option(None, "--evidence", "-e", help="Evidence types to filter by (can repeat)"),
    taxon: Optional[str] = typer.Option(None, "--taxon", help="Organism filter"),
    aspect: Optional[str] = typer.Option(None, "--aspect", "-a", help="GO aspect (C, F, or P)"),
    assigned_by: Optional[str] = typer.Option(None, "--assigned-by", help="Annotation source filter"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Custom GOlr endpoint URL"),
):
    """Search for GO annotations with filtering."""
    client = _make_amigo_client(base_url)

    try:
        results = client.search_annotations(
            bioentity=bioentity,
            go_term=go_term,
            go_terms_closure=go_terms_closure,
            evidence_types=evidence_types,
            taxon=taxon,
            aspect=aspect,
            assigned_by=assigned_by,
            limit=limit
        )

        if not results:
            typer.echo("No annotations found.")
            return

        typer.echo(f"Found {len(results)} annotations:")
        # Print header
        typer.echo("BIOENTITY\tLABEL\tGO_TERM\tGO_NAME\tASPECT\tEVIDENCE\tREFERENCE\tWITH\tQUALIFIER\tTAXON\tASSIGNED_BY\tDATE")

        for result in results:
            # Handle WITH field from annotation_extension or gene_product_form_id
            with_field = result.gene_product_form_id or "-"
            reference = result.reference or "-"
            qualifier = result.qualifier or "-"

            typer.echo(
                f"{result.bioentity}\t"
                f"{result.bioentity_label}\t"
                f"{result.annotation_class}\t"
                f"{result.annotation_class_label}\t"
                f"{result.aspect}\t"
                f"{result.evidence_type}\t"
                f"{reference}\t"
                f"{with_field}\t"
                f"{qualifier}\t"
                f"{result.taxon_label}\t"
                f"{result.assigned_by}\t"
                f"{result.date}"
            )

    except Exception as e:
        typer.echo(f"Error searching annotations: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


@amigo_app.command("bioentity-annotations")
def bioentity_annotations(
    bioentity_id: str = typer.Argument(..., help="Bioentity ID"),
    go_terms_closure: Optional[List[str]] = typer.Option(None, "--closure", "-c", help="Filter to specific GO terms (can repeat)"),
    evidence_types: Optional[List[str]] = typer.Option(None, "--evidence", "-e", help="Evidence types to filter by (can repeat)"),
    aspect: Optional[str] = typer.Option(None, "--aspect", "-a", help="GO aspect (C, F, or P)"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of results"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Custom GOlr endpoint URL"),
):
    """Get all annotations for a specific bioentity."""
    client = _make_amigo_client(base_url)

    try:
        results = client.get_annotations_for_bioentity(
            bioentity_id=bioentity_id,
            go_terms_closure=go_terms_closure,
            evidence_types=evidence_types,
            aspect=aspect,
            limit=limit
        )

        if not results:
            typer.echo(f"No annotations found for {bioentity_id}")
            return

        typer.echo(f"Found {len(results)} annotations for {bioentity_id}:")
        # Print header
        typer.echo("GO_TERM\tGO_NAME\tASPECT\tEVIDENCE\tREFERENCE\tWITH\tQUALIFIER\tASSIGNED_BY\tDATE")

        for result in results:
            with_field = result.gene_product_form_id or "-"
            reference = result.reference or "-"
            qualifier = result.qualifier or "-"

            typer.echo(
                f"{result.annotation_class}\t"
                f"{result.annotation_class_label}\t"
                f"{result.aspect}\t"
                f"{result.evidence_type}\t"
                f"{reference}\t"
                f"{with_field}\t"
                f"{qualifier}\t"
                f"{result.assigned_by}\t"
                f"{result.date}"
            )

    except Exception as e:
        typer.echo(f"Error getting annotations: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


@amigo_app.command("term-bioentities")
def term_bioentities(
    go_term: str = typer.Argument(..., help="GO term ID"),
    include_closure: bool = typer.Option(True, "--closure/--no-closure", help="Include child terms"),
    taxon: Optional[str] = typer.Option(None, "--taxon", help="Organism filter"),
    evidence_types: Optional[List[str]] = typer.Option(None, "--evidence", "-e", help="Evidence types to filter by (can repeat)"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of results"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Custom GOlr endpoint URL"),
):
    """Get all bioentities annotated to a GO term."""
    client = _make_amigo_client(base_url)

    try:
        results = client.get_bioentities_for_term(
            go_term=go_term,
            include_closure=include_closure,
            taxon=taxon,
            evidence_types=evidence_types,
            limit=limit
        )

        if not results:
            typer.echo(f"No bioentities found for {go_term}")
            return

        typer.echo(f"Found {len(results)} bioentities for {go_term}:")
        # Print header
        typer.echo("BIOENTITY\tLABEL\tNAME\tEVIDENCE\tREFERENCE\tWITH\tQUALIFIER\tTAXON\tASSIGNED_BY\tDATE")

        for result in results:
            with_field = result.gene_product_form_id or "-"
            reference = result.reference or "-"
            qualifier = result.qualifier or "-"

            typer.echo(
                f"{result.bioentity}\t"
                f"{result.bioentity_label}\t"
                f"{result.bioentity_name}\t"
                f"{result.evidence_type}\t"
                f"{reference}\t"
                f"{with_field}\t"
                f"{qualifier}\t"
                f"{result.taxon_label}\t"
                f"{result.assigned_by}\t"
                f"{result.date}"
            )

    except Exception as e:
        typer.echo(f"Error getting bioentities: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
