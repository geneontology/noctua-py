"""Pydantic models for Barista/Minerva API request structures.

This module defines the request models used by the BaristaClient to interact
with the Noctua/Minerva/Barista API stack.

This is based on the source specification:

 - https://github.com/berkeleybop/bbop-manager-minerva/wiki/MinervaRequestAPI
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Type aliases for semantic clarity
# These provide documentation and IDE support while remaining lightweight (no runtime validation)

# CURIEs (Compact URIs) - identifiers with prefix:localid format
CURIE = Annotated[str, Field(description="Compact URI (e.g., GO:0003924, RO:0002413, UniProtKB:P12345)")]

# Model identifiers
ModelId = Annotated[str, Field(description="GO-CAM model identifier (e.g., gomodel:68d6f96e00000003)")]

# Individual identifiers - can be full IDs or CURIEs
IndividualId = Annotated[str, Field(description="Individual identifier (e.g., gomodel:123/individual-456) or CURIE")]

# Variable names - simple names without ':' or '/' used for tracking within a session
VariableName = Annotated[str, Field(description="Variable name for tracking (e.g., 'activity1', 'x1')")]

# Identifiers that can be either variables or actual IDs
IdentifierOrVariable = IndividualId | VariableName

# Predicate/relation identifiers
PredicateId = Annotated[str, Field(description="Relation/predicate CURIE (e.g., RO:0002413 for 'directly provides input for')")]

# Evidence code identifiers
EvidenceCode = Annotated[str, Field(description="Evidence code CURIE (e.g., ECO:0000314 for 'direct assay evidence')")]


class Expression(BaseModel):
    """Expression in an individual's type definition.

    Examples:
        >>> Expression(type="class", id="GO:0003924")
        Expression(type='class', id='GO:0003924')
    """
    type: Literal["class"] = "class"
    id: CURIE


class AnnotationValue(BaseModel):
    """Key-value pair for annotations.

    Examples:
        >>> AnnotationValue(key="title", value="My Model")
        AnnotationValue(key='title', value='My Model')
        >>> AnnotationValue(key="source", value="PMID:12345")
        AnnotationValue(key='source', value='PMID:12345')
    """
    key: str = Field(..., description="Annotation key (e.g., 'title', 'source', 'with')")
    value: str = Field(..., description="Annotation value")


class ProteinComplexComponent(BaseModel):
    """Component of a protein complex.

    Used by higher-level methods like add_protein_complex to specify
    individual components with optional metadata and evidence.

    Examples:
        >>> # Simple component with just entity ID
        >>> ProteinComplexComponent(entity_id="UniProtKB:P12345")
        ProteinComplexComponent(entity_id='UniProtKB:P12345', label=None, evidence_type=None, reference=None)

        >>> # Component with label
        >>> ProteinComplexComponent(
        ...     entity_id="UniProtKB:P12345",
        ...     label="Ras protein"
        ... )
        ProteinComplexComponent(entity_id='UniProtKB:P12345', label='Ras protein', evidence_type=None, reference=None)

        >>> # Component with evidence
        >>> ProteinComplexComponent(
        ...     entity_id="UniProtKB:P12345",
        ...     label="Ras protein",
        ...     evidence_type="ECO:0000314",
        ...     reference="PMID:12345678"
        ... )
        ProteinComplexComponent(entity_id='UniProtKB:P12345', label='Ras protein', evidence_type='ECO:0000314', reference='PMID:12345678')
    """
    entity_id: CURIE = Field(..., description="Entity identifier (e.g., UniProtKB:P12345)")
    label: Optional[str] = Field(None, description="Human-readable label for the component")
    evidence_type: Optional[EvidenceCode] = Field(None, description="Evidence code (e.g., ECO:0000314)")
    reference: Optional[str] = Field(None, description="Reference CURIE (e.g., PMID:12345)")


class EntitySetMember(BaseModel):
    """Member of an entity set - functionally interchangeable gene products.

    Used by higher-level methods like add_entity_set to specify members of
    a paralogy group or other set of functionally interchangeable entities.

    Examples:
        >>> # Simple member with just entity ID
        >>> EntitySetMember(entity_id="UniProtKB:P27361")
        EntitySetMember(entity_id='UniProtKB:P27361', label=None, evidence_type=None, reference=None)

        >>> # Member with label
        >>> EntitySetMember(
        ...     entity_id="UniProtKB:P27361",
        ...     label="MAPK3 (ERK1)"
        ... )
        EntitySetMember(entity_id='UniProtKB:P27361', label='MAPK3 (ERK1)', evidence_type=None, reference=None)

        >>> # Member with evidence
        >>> EntitySetMember(
        ...     entity_id="UniProtKB:P27361",
        ...     label="MAPK3 (ERK1)",
        ...     evidence_type="ECO:0000314",
        ...     reference="PMID:12345678"
        ... )
        EntitySetMember(entity_id='UniProtKB:P27361', label='MAPK3 (ERK1)', evidence_type='ECO:0000314', reference='PMID:12345678')
    """
    entity_id: CURIE = Field(..., description="Entity identifier (e.g., UniProtKB:P27361)")
    label: Optional[str] = Field(None, description="Human-readable label for the member")
    evidence_type: Optional[EvidenceCode] = Field(None, description="Evidence code (e.g., ECO:0000314)")
    reference: Optional[str] = Field(None, description="Reference CURIE (e.g., PMID:12345)")


class BaseRequest(BaseModel):
    """Base class for all Minerva API requests."""
    entity: str = Field(..., description="Entity type (e.g., 'individual', 'edge', 'model')")
    operation: str = Field(..., description="Operation to perform (e.g., 'add', 'remove', 'get')")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific arguments")


# Individual Operations

class AddIndividualArguments(BaseModel):
    """Arguments for adding an individual to a model.

    Examples:
        >>> args = AddIndividualArguments(
        ...     expressions=[{"type": "class", "id": "GO:0003924"}],
        ...     model_id="gomodel:68d6f96e00000003",
        ...     assign_to_variable="activity1"
        ... )
        >>> args.model_id
        'gomodel:68d6f96e00000003'
    """
    expressions: List[Expression] = Field(..., description="Type expressions for the individual")
    model_id: ModelId = Field(..., serialization_alias="model-id")
    assign_to_variable: Optional[VariableName] = Field(
        None,
        serialization_alias="assign-to-variable"
    )
    expected_label: Optional[str] = Field(
        None,
        exclude=True,
        description="Expected label for validation. Not serialized to API."
    )

    model_config = ConfigDict(populate_by_name=True)


class RemoveIndividualArguments(BaseModel):
    """Arguments for removing an individual from a model.

    Examples:
        >>> RemoveIndividualArguments(
        ...     individual="gomodel:123/individual-456",
        ...     model_id="gomodel:123"
        ... )
        RemoveIndividualArguments(individual='gomodel:123/individual-456', model_id='gomodel:123')
    """
    individual: IndividualId
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)


class AddIndividualAnnotationArguments(BaseModel):
    """Arguments for adding annotations to an individual.

    Examples:
        >>> AddIndividualAnnotationArguments(
        ...     individual="gomodel:123/individual-456",
        ...     values=[{"key": "source", "value": "PMID:12345"}],
        ...     model_id="gomodel:123"
        ... )
        AddIndividualAnnotationArguments(individual='gomodel:123/individual-456', values=[AnnotationValue(key='source', value='PMID:12345')], model_id='gomodel:123')
    """
    individual: IdentifierOrVariable
    values: List[AnnotationValue] = Field(..., description="Annotation key-value pairs")
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)



class RemoveIndividualAnnotationArguments(BaseModel):
    """Arguments for removing annotations from an individual.

    Examples:
        >>> RemoveIndividualAnnotationArguments(
        ...     individual="gomodel:123/individual-456",
        ...     values=[{"key": "source", "value": "PMID:12345"}],
        ...     model_id="gomodel:123"
        ... )
        RemoveIndividualAnnotationArguments(individual='gomodel:123/individual-456', values=[AnnotationValue(key='source', value='PMID:12345')], model_id='gomodel:123')
    """
    individual: IdentifierOrVariable
    values: List[AnnotationValue] = Field(..., description="Annotation key-value pairs to remove")
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)



# Edge/Fact Operations

class AddEdgeArguments(BaseModel):
    """Arguments for adding an edge (fact) between individuals.

    Examples:
        >>> AddEdgeArguments(
        ...     subject="gomodel:123/individual-1",
        ...     object="gomodel:123/individual-2",
        ...     predicate="RO:0002413",
        ...     model_id="gomodel:123"
        ... )
        AddEdgeArguments(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', predicate='RO:0002413', model_id='gomodel:123')
    """
    subject: IdentifierOrVariable
    object: IdentifierOrVariable
    predicate: PredicateId
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)



class RemoveEdgeArguments(BaseModel):
    """Arguments for removing an edge (fact) between individuals.

    Examples:
        >>> RemoveEdgeArguments(
        ...     subject="gomodel:123/individual-1",
        ...     object="gomodel:123/individual-2",
        ...     predicate="RO:0002413",
        ...     model_id="gomodel:123"
        ... )
        RemoveEdgeArguments(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', predicate='RO:0002413', model_id='gomodel:123')
    """
    subject: IdentifierOrVariable
    object: IdentifierOrVariable
    predicate: PredicateId
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)



class AddEdgeAnnotationArguments(BaseModel):
    """Arguments for adding annotations to an edge.

    Examples:
        >>> AddEdgeAnnotationArguments(
        ...     subject="gomodel:123/individual-1",
        ...     object="gomodel:123/individual-2",
        ...     predicate="RO:0002413",
        ...     values=[{"key": "evidence", "value": "e1"}],
        ...     model_id="gomodel:123"
        ... )
        AddEdgeAnnotationArguments(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', predicate='RO:0002413', values=[AnnotationValue(key='evidence', value='e1')], model_id='gomodel:123')
    """
    subject: IdentifierOrVariable
    object: IdentifierOrVariable
    predicate: PredicateId
    values: List[AnnotationValue] = Field(..., description="Annotation key-value pairs")
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)



# Model Operations

class CreateModelArguments(BaseModel):
    """Arguments for creating a new model.

    Examples:
        >>> CreateModelArguments(values=[{"key": "title", "value": "My New Model"}])
        CreateModelArguments(values=[AnnotationValue(key='title', value='My New Model')])
        >>> CreateModelArguments()
        CreateModelArguments(values=None)
    """
    values: Optional[List[AnnotationValue]] = Field(
        None,
        description="Optional initial annotations (e.g., title)"
    )


class GetModelArguments(BaseModel):
    """Arguments for retrieving a model.

    Examples:
        >>> GetModelArguments(model_id="gomodel:68d6f96e00000003")
        GetModelArguments(model_id='gomodel:68d6f96e00000003')
    """
    model_id: ModelId = Field(..., serialization_alias="model-id")

    model_config = ConfigDict(populate_by_name=True)



class ExportModelArguments(BaseModel):
    """Arguments for exporting a model.

    Examples:
        >>> ExportModelArguments(model_id="gomodel:123", format="owl")
        ExportModelArguments(model_id='gomodel:123', format='owl')
        >>> ExportModelArguments(model_id="gomodel:123", format="ttl")
        ExportModelArguments(model_id='gomodel:123', format='ttl')
    """
    model_id: ModelId = Field(..., serialization_alias="model-id")
    format: str = Field(
        default="owl",
        description="Export format (owl, ttl, json-ld, gaf, etc.)"
    )

    model_config = ConfigDict(populate_by_name=True)



class AddModelAnnotationArguments(BaseModel):
    """Arguments for adding annotations to a model.

    Examples:
        >>> AddModelAnnotationArguments(
        ...     model_id="gomodel:123",
        ...     values=[{"key": "title", "value": "Updated Title"}]
        ... )
        AddModelAnnotationArguments(model_id='gomodel:123', values=[AnnotationValue(key='title', value='Updated Title')])
    """
    model_id: ModelId = Field(..., serialization_alias="model-id")
    values: List[AnnotationValue] = Field(..., description="Annotation key-value pairs")

    model_config = ConfigDict(populate_by_name=True)



class RemoveModelAnnotationArguments(BaseModel):
    """Arguments for removing annotations from a model.

    Examples:
        >>> RemoveModelAnnotationArguments(
        ...     model_id="gomodel:123",
        ...     values=[{"key": "title", "value": "Old Title"}]
        ... )
        RemoveModelAnnotationArguments(model_id='gomodel:123', values=[AnnotationValue(key='title', value='Old Title')])
    """
    model_id: ModelId = Field(..., serialization_alias="model-id")
    values: List[AnnotationValue] = Field(..., description="Annotation key-value pairs to remove")

    model_config = ConfigDict(populate_by_name=True)



class ReplaceModelAnnotationArguments(BaseModel):
    """Arguments for replacing a model annotation.

    Examples:
        >>> ReplaceModelAnnotationArguments(
        ...     model_id="gomodel:123",
        ...     key="title",
        ...     old_value="Old Title",
        ...     new_value="New Title"
        ... )
        ReplaceModelAnnotationArguments(model_id='gomodel:123', key='title', old_value='Old Title', new_value='New Title')
    """
    model_id: ModelId = Field(..., serialization_alias="model-id")
    key: str = Field(..., description="Annotation key to replace")
    old_value: str = Field(..., serialization_alias="old-value", description="Current value")
    new_value: str = Field(..., serialization_alias="new-value", description="New value")

    model_config = ConfigDict(populate_by_name=True)



# Request Models

class AddIndividualRequest(BaseModel):
    """Request to add an individual to a model.

    Examples:
        >>> req = AddIndividualRequest(
        ...     arguments=AddIndividualArguments(
        ...         expressions=[Expression(type="class", id="GO:0003924")],
        ...         model_id="gomodel:123",
        ...         assign_to_variable="x1"
        ...     )
        ... )
        >>> req.entity
        'individual'
        >>> req.operation
        'add'
    """
    entity: Literal["individual"] = "individual"
    operation: Literal["add"] = "add"
    arguments: AddIndividualArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['RemoveIndividualRequest']:
        """Generate the reverse operation to undo this request.

        Args:
            before_state: Model state before this request executed
            after_state: Model state after this request executed

        Returns:
            RemoveIndividualRequest to undo the addition, or None if not reversible
        """
        # Find the newly created individual(s)
        before_ids = {ind["id"] for ind in before_state.get("individuals", [])}
        after_individuals = after_state.get("individuals", [])

        new_individuals = [ind for ind in after_individuals if ind["id"] not in before_ids]
        if not new_individuals:
            return None  # Nothing was added

        # Remove the first new individual (should only be one)
        new_id = new_individuals[0]["id"]

        return RemoveIndividualRequest(
            arguments=RemoveIndividualArguments(
                model_id=self.arguments.model_id,
                individual=new_id
            )
        )


class RemoveIndividualRequest(BaseModel):
    """Request to remove an individual from a model.

    Examples:
        >>> RemoveIndividualRequest(
        ...     arguments=RemoveIndividualArguments(
        ...         individual="gomodel:123/individual-456",
        ...         model_id="gomodel:123"
        ...     )
        ... )
        RemoveIndividualRequest(entity='individual', operation='remove', arguments=RemoveIndividualArguments(individual='gomodel:123/individual-456', model_id='gomodel:123'))
    """
    entity: Literal["individual"] = "individual"
    operation: Literal["remove"] = "remove"
    arguments: RemoveIndividualArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['AddIndividualRequest']:
        """Generate the reverse operation to undo this request.

        Args:
            before_state: Model state before this request executed
            after_state: Model state after this request executed

        Returns:
            AddIndividualRequest to re-add the removed individual, or None if not reversible
        """
        individual_id = self.arguments.individual

        # Find the removed individual in before_state
        removed_individual = None
        for ind in before_state.get("individuals", []):
            if ind["id"] == individual_id:
                removed_individual = ind
                break

        if not removed_individual:
            return None  # Individual wasn't in before state

        # Extract its types
        types = removed_individual.get("type", [])
        if not types:
            return None  # Can't restore without type info

        # Build expressions from all types
        expressions = [
            Expression(type="class", id=t["id"])
            for t in types
        ]

        return AddIndividualRequest(
            arguments=AddIndividualArguments(
                model_id=self.arguments.model_id,
                expressions=expressions,
                assign_to_variable=None,
                expected_label=None
            )
        )


class AddIndividualAnnotationRequest(BaseModel):
    """Request to add annotations to an individual.

    Examples:
        >>> AddIndividualAnnotationRequest(
        ...     arguments=AddIndividualAnnotationArguments(
        ...         individual="gomodel:123/individual-456",
        ...         values=[AnnotationValue(key="source", value="PMID:12345")],
        ...         model_id="gomodel:123"
        ...     )
        ... )
        AddIndividualAnnotationRequest(entity='individual', operation='add-annotation', arguments=AddIndividualAnnotationArguments(individual='gomodel:123/individual-456', values=[AnnotationValue(key='source', value='PMID:12345')], model_id='gomodel:123'))
    """
    entity: Literal["individual"] = "individual"
    operation: Literal["add-annotation"] = "add-annotation"
    arguments: AddIndividualAnnotationArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['RemoveIndividualAnnotationRequest']:
        """Generate the reverse operation to undo this request."""
        return RemoveIndividualAnnotationRequest(
            arguments=RemoveIndividualAnnotationArguments(
                model_id=self.arguments.model_id,
                individual=self.arguments.individual,
                values=self.arguments.values
            )
        )


class RemoveIndividualAnnotationRequest(BaseModel):
    """Request to remove annotations from an individual.

    Examples:
        >>> RemoveIndividualAnnotationRequest(
        ...     arguments=RemoveIndividualAnnotationArguments(
        ...         individual="gomodel:123/individual-456",
        ...         values=[AnnotationValue(key="source", value="PMID:12345")],
        ...         model_id="gomodel:123"
        ...     )
        ... )
        RemoveIndividualAnnotationRequest(entity='individual', operation='remove-annotation', arguments=RemoveIndividualAnnotationArguments(individual='gomodel:123/individual-456', values=[AnnotationValue(key='source', value='PMID:12345')], model_id='gomodel:123'))
    """
    entity: Literal["individual"] = "individual"
    operation: Literal["remove-annotation"] = "remove-annotation"
    arguments: RemoveIndividualAnnotationArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['AddIndividualAnnotationRequest']:
        """Generate the reverse operation to undo this request."""
        return AddIndividualAnnotationRequest(
            arguments=AddIndividualAnnotationArguments(
                model_id=self.arguments.model_id,
                individual=self.arguments.individual,
                values=self.arguments.values
            )
        )


class AddEdgeRequest(BaseModel):
    """Request to add an edge between individuals.

    Examples:
        >>> AddEdgeRequest(
        ...     arguments=AddEdgeArguments(
        ...         subject="gomodel:123/individual-1",
        ...         object="gomodel:123/individual-2",
        ...         predicate="RO:0002413",
        ...         model_id="gomodel:123"
        ...     )
        ... )
        AddEdgeRequest(entity='edge', operation='add', arguments=AddEdgeArguments(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', predicate='RO:0002413', model_id='gomodel:123'))
    """
    entity: Literal["edge"] = "edge"
    operation: Literal["add"] = "add"
    arguments: AddEdgeArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['RemoveEdgeRequest']:
        """Generate the reverse operation to undo this request."""
        return RemoveEdgeRequest(
            arguments=RemoveEdgeArguments(
                model_id=self.arguments.model_id,
                subject=self.arguments.subject,
                object=self.arguments.object,
                predicate=self.arguments.predicate
            )
        )


class RemoveEdgeRequest(BaseModel):
    """Request to remove an edge between individuals.

    Examples:
        >>> RemoveEdgeRequest(
        ...     arguments=RemoveEdgeArguments(
        ...         subject="gomodel:123/individual-1",
        ...         object="gomodel:123/individual-2",
        ...         predicate="RO:0002413",
        ...         model_id="gomodel:123"
        ...     )
        ... )
        RemoveEdgeRequest(entity='edge', operation='remove', arguments=RemoveEdgeArguments(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', predicate='RO:0002413', model_id='gomodel:123'))
    """
    entity: Literal["edge"] = "edge"
    operation: Literal["remove"] = "remove"
    arguments: RemoveEdgeArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['AddEdgeRequest']:
        """Generate the reverse operation to undo this request."""
        return AddEdgeRequest(
            arguments=AddEdgeArguments(
                model_id=self.arguments.model_id,
                subject=self.arguments.subject,
                object=self.arguments.object,
                predicate=self.arguments.predicate
            )
        )


class AddEdgeAnnotationRequest(BaseModel):
    """Request to add annotations to an edge.

    Examples:
        >>> AddEdgeAnnotationRequest(
        ...     arguments=AddEdgeAnnotationArguments(
        ...         subject="gomodel:123/individual-1",
        ...         object="gomodel:123/individual-2",
        ...         predicate="RO:0002413",
        ...         values=[AnnotationValue(key="evidence", value="e1")],
        ...         model_id="gomodel:123"
        ...     )
        ... )
        AddEdgeAnnotationRequest(entity='edge', operation='add-annotation', arguments=AddEdgeAnnotationArguments(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', predicate='RO:0002413', values=[AnnotationValue(key='evidence', value='e1')], model_id='gomodel:123'))
    """
    entity: Literal["edge"] = "edge"
    operation: Literal["add-annotation"] = "add-annotation"
    arguments: AddEdgeAnnotationArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> None:
        """Edge annotations cannot be reversed automatically.

        Note: RemoveEdgeAnnotationRequest doesn't exist in the API.
        """
        return None


class CreateModelRequest(BaseModel):
    """Request to create a new model.

    Examples:
        >>> CreateModelRequest(
        ...     arguments=CreateModelArguments(
        ...         values=[AnnotationValue(key="title", value="My Model")]
        ...     )
        ... )
        CreateModelRequest(entity='model', operation='add', arguments=CreateModelArguments(values=[AnnotationValue(key='title', value='My Model')]))
        >>> CreateModelRequest(arguments=CreateModelArguments())
        CreateModelRequest(entity='model', operation='add', arguments=CreateModelArguments(values=None))
    """
    entity: Literal["model"] = "model"
    operation: Literal["add"] = "add"
    arguments: CreateModelArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> None:
        """Model creation cannot be reversed automatically."""
        return None


class GetModelRequest(BaseModel):
    """Request to get a model.

    Examples:
        >>> GetModelRequest(
        ...     arguments=GetModelArguments(model_id="gomodel:123")
        ... )
        GetModelRequest(entity='model', operation='get', arguments=GetModelArguments(model_id='gomodel:123'))
    """
    entity: Literal["model"] = "model"
    operation: Literal["get"] = "get"
    arguments: GetModelArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> None:
        """Read-only operation, no reverse needed."""
        return None


class ExportModelRequest(BaseModel):
    """Request to export a model.

    Examples:
        >>> ExportModelRequest(
        ...     arguments=ExportModelArguments(model_id="gomodel:123", format="owl")
        ... )
        ExportModelRequest(entity='model', operation='export', arguments=ExportModelArguments(model_id='gomodel:123', format='owl'))
    """
    entity: Literal["model"] = "model"
    operation: Literal["export"] = "export"
    arguments: ExportModelArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> None:
        """Read-only operation, no reverse needed."""
        return None


class AddModelAnnotationRequest(BaseModel):
    """Request to add annotations to a model.

    Examples:
        >>> AddModelAnnotationRequest(
        ...     arguments=AddModelAnnotationArguments(
        ...         model_id="gomodel:123",
        ...         values=[AnnotationValue(key="title", value="New Title")]
        ...     )
        ... )
        AddModelAnnotationRequest(entity='model', operation='add-annotation', arguments=AddModelAnnotationArguments(model_id='gomodel:123', values=[AnnotationValue(key='title', value='New Title')]))
    """
    entity: Literal["model"] = "model"
    operation: Literal["add-annotation"] = "add-annotation"
    arguments: AddModelAnnotationArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['RemoveModelAnnotationRequest']:
        """Generate the reverse operation to undo this request."""
        return RemoveModelAnnotationRequest(
            arguments=RemoveModelAnnotationArguments(
                model_id=self.arguments.model_id,
                values=self.arguments.values
            )
        )


class RemoveModelAnnotationRequest(BaseModel):
    """Request to remove annotations from a model.

    Examples:
        >>> RemoveModelAnnotationRequest(
        ...     arguments=RemoveModelAnnotationArguments(
        ...         model_id="gomodel:123",
        ...         values=[AnnotationValue(key="title", value="Old Title")]
        ...     )
        ... )
        RemoveModelAnnotationRequest(entity='model', operation='remove-annotation', arguments=RemoveModelAnnotationArguments(model_id='gomodel:123', values=[AnnotationValue(key='title', value='Old Title')]))
    """
    entity: Literal["model"] = "model"
    operation: Literal["remove-annotation"] = "remove-annotation"
    arguments: RemoveModelAnnotationArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['AddModelAnnotationRequest']:
        """Generate the reverse operation to undo this request."""
        return AddModelAnnotationRequest(
            arguments=AddModelAnnotationArguments(
                model_id=self.arguments.model_id,
                values=self.arguments.values
            )
        )


class ReplaceModelAnnotationRequest(BaseModel):
    """Request to replace a model annotation.

    Examples:
        >>> ReplaceModelAnnotationRequest(
        ...     arguments=ReplaceModelAnnotationArguments(
        ...         model_id="gomodel:123",
        ...         key="title",
        ...         old_value="Old Title",
        ...         new_value="New Title"
        ...     )
        ... )
        ReplaceModelAnnotationRequest(entity='model', operation='replace-annotation', arguments=ReplaceModelAnnotationArguments(model_id='gomodel:123', key='title', old_value='Old Title', new_value='New Title'))
    """
    entity: Literal["model"] = "model"
    operation: Literal["replace-annotation"] = "replace-annotation"
    arguments: ReplaceModelAnnotationArguments

    def reverse(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Optional['ReplaceModelAnnotationRequest']:
        """Generate the reverse operation to undo this request."""
        return ReplaceModelAnnotationRequest(
            arguments=ReplaceModelAnnotationArguments(
                model_id=self.arguments.model_id,
                key=self.arguments.key,
                old_value=self.arguments.new_value,  # Swap!
                new_value=self.arguments.old_value   # Swap!
            )
        )


# Union type for all requests
MinervaRequest = Union[
    AddIndividualRequest,
    RemoveIndividualRequest,
    AddIndividualAnnotationRequest,
    RemoveIndividualAnnotationRequest,
    AddEdgeRequest,
    RemoveEdgeRequest,
    AddEdgeAnnotationRequest,
    CreateModelRequest,
    GetModelRequest,
    ExportModelRequest,
    AddModelAnnotationRequest,
    RemoveModelAnnotationRequest,
    ReplaceModelAnnotationRequest,
]


# ============================================================================
# Response Data Models
# ============================================================================
# These models represent the data structures returned by the Barista API


class TypeInfo(BaseModel):
    """Type information for an individual.

    Examples:
        >>> TypeInfo(type="class", id="GO:0003924", label="GTPase activity")
        TypeInfo(type='class', id='GO:0003924', label='GTPase activity')
        >>> TypeInfo(type="class", id="GO:0003924")
        TypeInfo(type='class', id='GO:0003924', label=None)
        >>> TypeInfo(id="GO:0003924", label="GTPase activity")  # type defaults to 'class'
        TypeInfo(type='class', id='GO:0003924', label='GTPase activity')
    """
    type: str = Field(default="class", description="Type category (usually 'class')")
    id: str = Field(..., description="CURIE for the type")
    label: Optional[str] = Field(None, description="Human-readable label")

    model_config = ConfigDict(extra="allow")  # Allow extra fields from API


class Individual(BaseModel):
    """An individual (instance) in a GO-CAM model.

    Examples:
        >>> Individual(
        ...     id="gomodel:123/individual-1",
        ...     type=[TypeInfo(type="class", id="GO:0003924", label="GTPase activity")]
        ... )
        Individual(id='gomodel:123/individual-1', type=[TypeInfo(type='class', id='GO:0003924', label='GTPase activity')], annotations=[])
    """
    id: str = Field(..., description="Individual identifier")
    type: List[TypeInfo] = Field(default_factory=list, description="Type expressions for this individual")
    annotations: List[AnnotationValue] = Field(default_factory=list, description="Annotations on this individual")

    @field_validator('type', mode='before')
    @classmethod
    def normalize_type(cls, v: Any) -> List[Any]:
        """Normalize type field to always be a list (handle test data with single dict)."""
        if isinstance(v, dict):
            return [v]
        return v if isinstance(v, list) else []

    model_config = ConfigDict(extra="allow")


class Fact(BaseModel):
    """A fact (edge/relationship) between individuals in a GO-CAM model.

    Examples:
        >>> Fact(
        ...     subject="gomodel:123/individual-1",
        ...     object="gomodel:123/individual-2",
        ...     property="RO:0002413",
        ...     property_label="directly positively regulates"
        ... )
        Fact(subject='gomodel:123/individual-1', object='gomodel:123/individual-2', property='RO:0002413', property_label='directly positively regulates', annotations=[])
    """
    subject: str = Field(..., description="Subject individual ID")
    object: str = Field(..., alias="object", description="Object individual ID")  # 'object' is Python keyword
    property: str = Field(..., alias="property", description="Predicate/relation ID")
    property_label: Optional[str] = Field(None, alias="property-label", description="Human-readable predicate label")
    annotations: List[AnnotationValue] = Field(default_factory=list, description="Annotations on this fact")

    @model_validator(mode='before')
    @classmethod
    def normalize_predicate_field(cls, data: Any) -> Any:
        """Handle both 'property' and 'predicate' field names, and extract from dict if needed."""
        if isinstance(data, dict):
            # Handle 'predicate' field name (test data) vs 'property' (real API)
            if 'predicate' in data and 'property' not in data:
                pred_value = data['predicate']
                # If it's a dict, extract id and label
                if isinstance(pred_value, dict):
                    data['property'] = pred_value.get('id', '')
                    if 'property-label' not in data and 'property_label' not in data:
                        data['property_label'] = pred_value.get('label')
                else:
                    data['property'] = pred_value
                del data['predicate']  # Remove the old field name
            elif 'property' in data:
                # Property field exists, check if it's a dict
                prop_value = data['property']
                if isinstance(prop_value, dict):
                    data['property'] = prop_value.get('id', '')
                    if 'property-label' not in data and 'property_label' not in data:
                        data['property_label'] = prop_value.get('label')
        return data

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ModelData(BaseModel):
    """The data section of a Barista API response containing model information.

    Examples:
        >>> ModelData(
        ...     id="gomodel:123",
        ...     individuals=[],
        ...     facts=[],
        ...     annotations=[AnnotationValue(key="state", value="development")]
        ... )
        ModelData(id='gomodel:123', individuals=[], facts=[], annotations=[AnnotationValue(key='state', value='development')])
    """
    id: Optional[str] = Field(None, description="Model ID")
    individuals: List[Individual] = Field(default_factory=list, description="Individuals in the model")
    facts: List[Fact] = Field(default_factory=list, description="Facts/edges in the model")
    annotations: List[AnnotationValue] = Field(default_factory=list, description="Model-level annotations")

    model_config = ConfigDict(extra="allow")

    def get_state(self) -> Optional[str]:
        """Get the model state annotation (e.g., 'production', 'development').

        Returns:
            The state value, or None if not found

        Examples:
            >>> data = ModelData(
            ...     id="gomodel:123",
            ...     annotations=[AnnotationValue(key="state", value="production")]
            ... )
            >>> data.get_state()
            'production'
        """
        for annotation in self.annotations:
            if annotation.key == "state":
                return annotation.value
        return None
