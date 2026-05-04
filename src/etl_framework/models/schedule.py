"""Schedule and dependency metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScheduleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cron: str = Field(
        default="@daily",
        description="Cron expression or Airflow preset (@daily, @hourly, ...)",
    )
    timezone: str = "UTC"
    start_date: str = Field(default="2024-01-01", description="ISO date YYYY-MM-DD")
    catchup: bool = False
    retries: int = Field(default=2, ge=0)
    retry_delay_minutes: int = Field(default=5, ge=1)
    depends_on: list[str] = Field(
        default_factory=list,
        description="Names of upstream entities that must finish before this one",
    )
