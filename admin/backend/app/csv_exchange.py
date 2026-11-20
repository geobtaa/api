"""Shared CSV input, spreadsheet-safe output, and bounded row batches."""

import csv
import io

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CsvInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv: str = Field(min_length=1)

    @field_validator("csv")
    @classmethod
    def text_file(cls, value):
        if "\x00" in value:
            raise ValueError("CSV contains a NUL character. Save as UTF-8 text and retry")
        return value


def csv_line(values):
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerow(values)
    return buffer.getvalue()


def safe_cell(value):
    # Escape formula-like strings and literal leading apostrophes reversibly.
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n", "'")) else value


def chunks(values, size=500):
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]
