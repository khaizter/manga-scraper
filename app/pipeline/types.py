from pydantic import BaseModel, Field


class PipelineOptions(BaseModel):
    """Cross-cutting options shared by all pipelines."""

    delay_seconds: float = 30.0
    dry_run: bool = False
    verbose: bool = False
