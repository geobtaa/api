"""Typed administrative read contracts for Resource association rows."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssociationRow(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationshipsRow(AssociationRow):
    id: int
    subject_id: str
    predicate: str
    object_id: str


class DownloadsRow(AssociationRow):
    id: int
    resource_id: str
    label: str | None
    value: str | None
    position: int
    import_download_id: str | None
    created_at: datetime
    updated_at: datetime


class LicensedAccessesRow(AssociationRow):
    id: int
    resource_id: str
    institution_code: str
    access_url: str
    legacy_friendlier_id: str | None
    created_at: datetime
    updated_at: datetime


class AssetsRow(AssociationRow):
    id: int
    resource_id: str
    bridge_asset_id: str | None
    bridge_parent_id: str | None
    friendlier_id: str | None
    title: str | None
    label: str | None
    thumbnail: bool
    dct_references_uri_key: str | None
    position: int
    file_url: str | None
    file_mime_type: str | None
    file_size: int | None
    file_width: int | None
    file_height: int | None
    file_md5: str | None
    file_sha1: str | None
    file_sha512: str | None
    created_at: datetime
    updated_at: datetime


class DataDictionariesRow(AssociationRow):
    id: int
    resource_id: str
    legacy_document_data_dictionary_id: int | None
    name: str | None
    description: str | None
    staff_notes: str | None
    tags: str
    position: int
    created_at: datetime
    updated_at: datetime


class DictionaryEntriesRow(AssociationRow):
    id: int
    resource_data_dictionary_id: int
    legacy_document_data_dictionary_entry_id: int | None
    field_name: str
    field_type: str | None
    values: str | None
    definition: str | None
    definition_source: str | None
    parent_field_name: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class AssociationPage(BaseModel):
    items: list[
        RelationshipsRow
        | DownloadsRow
        | LicensedAccessesRow
        | AssetsRow
        | DataDictionariesRow
        | DictionaryEntriesRow
    ]
    total: int
    offset: int
    limit: int
