"""Author data for the schemas in schema/schema.usda without requiring them to be registered.

Attribute types and variability are read from schema.usda itself, so authored data always matches the schema. Prims
get the schema's type name and applied API names, so the data is recognised as soon as the schema is registered, and
stays readable as plain attributes where it isn't.
"""

import os
from functools import lru_cache

from pxr import Sdf, Usd

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "schema", "schema.usda")


@lru_cache(maxsize=None)
def _schema_layer() -> Sdf.Layer:
    layer = Sdf.Layer.OpenAsAnonymous(SCHEMA_PATH)
    if layer is None:
        raise FileNotFoundError(f"Could not open schema definitions at {SCHEMA_PATH}")
    return layer


def _property_spec(schema: str, name: str):
    spec = _schema_layer().GetPropertyAtPath(Sdf.Path(f"/{schema}.{name}"))
    if spec is None:
        raise KeyError(f"{schema} has no property '{name}' in {SCHEMA_PATH}")
    return spec


def define(stage: Usd.Stage, path, schema: str) -> Usd.Prim:
    """Define a prim of a typed schema (e.g. HumanModifier)."""
    if _schema_layer().GetPrimAtPath(f"/{schema}") is None:
        raise KeyError(f"No schema named {schema} in {SCHEMA_PATH}")
    return stage.DefinePrim(path, schema)


def apply_api(prim: Usd.Prim, schema: str) -> None:
    """Apply a single-apply API schema (e.g. SkelTargetAPI) by name."""
    if _schema_layer().GetPrimAtPath(f"/{schema}") is None:
        raise KeyError(f"No schema named {schema} in {SCHEMA_PATH}")
    prim.AddAppliedSchema(schema)


def has_api(prim: Usd.Prim, schema: str) -> bool:
    """True if `schema` is in the prim's applied schemas, whether or not the schema is registered."""
    list_op = prim.GetMetadata("apiSchemas")
    return bool(list_op) and schema in list_op.ApplyOperations([])


def set_attr(prim: Usd.Prim, schema: str, name: str, value, time=Usd.TimeCode.Default()) -> Usd.Attribute:
    """Create (if needed) and set an attribute declared by `schema`, using the type and variability from schema.usda."""
    spec = _property_spec(schema, name)
    # When the schema is registered the attribute already exists as a builtin; otherwise create it with the schema's type
    attr = prim.GetAttribute(name)
    if not attr.IsValid() or attr.GetTypeName() != spec.typeName:
        attr = prim.CreateAttribute(name, spec.typeName, custom=False, variability=spec.variability)
    attr.Set(value, time)
    return attr


def set_targets(prim: Usd.Prim, schema: str, name: str, targets) -> Usd.Relationship:
    """Explicitly set the targets of a relationship declared by `schema` (order is preserved)."""
    _property_spec(schema, name)
    rel = prim.CreateRelationship(name, custom=False)
    rel.SetTargets(list(targets))
    return rel
