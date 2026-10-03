"""Base class shared by all Pydantic configuration sections."""

from pydantic import BaseModel, ConfigDict


class _Section(BaseModel):
    """Base class enabling assignment validation for every configuration section."""

    model_config = ConfigDict(validate_assignment=True, extra="ignore")
