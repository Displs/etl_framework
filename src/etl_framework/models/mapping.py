"""Column mapping rules.

A ColumnMapping describes how a single target column is produced from one or
more source columns. The framework supports three forms:

* direct copy (``source`` set, ``transform`` and ``expression`` empty)
* scalar transform of a single source column (``transform`` is a Spark SQL
  fragment with ``$`` placeholder substituted by the source column name)
* free expression over multiple source columns (``expression`` is a Spark SQL
  expression evaluated against the source DataFrame)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ColumnMapping(BaseModel):
    """Mapping rule for one target column."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    type: str = Field(description="Target Spark/SQL type, e.g. BIGINT, VARCHAR(120)")
    source: str | None = Field(
        default=None, description="Source column name for direct or scalar-transform mappings"
    )
    transform: str | None = Field(
        default=None,
        description="Single-column transform; '$' is substituted by the source column",
    )
    expression: str | None = Field(
        default=None,
        description="Free Spark SQL expression for multi-source derived columns",
    )
    null_default: str | None = Field(
        default=None, description="SQL literal used to replace NULLs"
    )
    pk: bool = Field(default=False, description="Part of the technical primary key")
    description: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> ColumnMapping:
        if self.expression is not None:
            if self.source or self.transform:
                raise ValueError(
                    f"column '{self.target}': 'expression' is mutually exclusive with "
                    "'source' and 'transform'"
                )
        else:
            if not self.source:
                raise ValueError(
                    f"column '{self.target}': either 'source' or 'expression' must be set"
                )
        return self

    def render_expression(self) -> str:
        """Return the Spark SQL fragment that produces this target column."""
        if self.expression is not None:
            expr = self.expression
        elif self.transform is not None:
            assert self.source is not None  # guaranteed by validator
            expr = self.transform.replace("$", self.source)
        else:
            assert self.source is not None
            expr = self.source

        if self.null_default is not None:
            expr = f"coalesce({expr}, {self.null_default})"
        return f"cast({expr} as {self.type})"

    def source_columns(self) -> list[str]:
        """Return the list of source columns this mapping references.

        Used by the lineage builder. For free expressions we return an empty
        list because static SQL parsing is out of scope for v0.1; users may
        annotate ``expression`` with explicit ``lineage_sources`` in future
        revisions.
        """
        if self.source is not None:
            return [self.source]
        return []
