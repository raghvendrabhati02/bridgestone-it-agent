"""
models/request_models.py
------------------------
Pydantic v2 request schemas for all Device Agent API endpoints.

All user-supplied data is validated here before reaching business logic.
"""

from pydantic import BaseModel, Field, field_validator


class SoftwareRequest(BaseModel):
    """
    Request body for software-related endpoints (install, verify).

    Attributes
    ----------
    software:
        A short, lowercase slug that identifies the software.
        Examples: "7zip", "vlc", "git", "notepadplusplus", "vscode"

    The slug is normalised to lowercase and stripped of surrounding
    whitespace before any catalog look-up, so the caller may supply
    "7zip", "7Zip", or "  7ZIP  " and all will resolve correctly.
    """

    software: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Software slug as listed in the approved software catalog "
            "(e.g. '7zip', 'vlc', 'git', 'notepadplusplus', 'vscode')."
        ),
        examples=["7zip", "vlc", "git"],
    )

    @field_validator("software", mode="before")
    @classmethod
    def normalise_slug(cls, value: str) -> str:
        """Strip whitespace and convert to lowercase for consistent lookups."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"software": "7zip"},
                {"software": "vlc"},
                {"software": "vscode"},
            ]
        }
    }
