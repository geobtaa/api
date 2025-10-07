INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "dct_title_s": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "normalizer": "lowercase"}},
            },
            "dct_spatial_sm": {"type": "keyword"},
            "gbl_resourceClass_sm": {"type": "keyword"},
            "gbl_resourceType_sm": {"type": "keyword"},
            "gbl_indexYear_im": {"type": "integer"},
            "dct_language_sm": {"type": "keyword"},
            "dct_creator_sm": {"type": "keyword"},
            "schema_provider_s": {"type": "keyword"},
            "dct_accessRights_s": {"type": "keyword"},
            "gbl_georeferenced_b": {"type": "boolean"},
            "dct_alternative_sm": {"type": "text"},
            "dct_description_sm": {"type": "text"},
            "gbl_displaynote_sm": {"type": "text"},
            "dct_publisher_sm": {"type": "text"},
            "dct_subject_sm": {"type": "text"},
            "dcat_theme_sm": {"type": "text"},
            "dcat_keyword_sm": {"type": "text"},
            "dct_temporal_sm": {"type": "text"},
            "dct_issued_s": {"type": "text"},
            "gbl_daterange_drsim": {"type": "text"},
            "locn_geometry": {
                "type": "geo_shape",
                "orientation": "counterclockwise",
                "coerce": True,
            },
            "dcat_bbox": {"type": "geo_shape", "orientation": "counterclockwise", "coerce": True},
            "dcat_centroid": {"type": "geo_point"},
            "dct_references_s": {"type": "object", "enabled": False},
            "gbl_mdmodified_dt": {"type": "date"},
            # BTAA-specific OGM Aardvark fields
            "b1g_code_s": {"type": "keyword"},
            "b1g_status_s": {"type": "keyword"},
            "b1g_dct_accrualMethod_s": {"type": "keyword"},
            "b1g_dct_accrualPeriodicity_s": {"type": "keyword"},
            "b1g_dateAccessioned_s": {"type": "date"},
            "b1g_dateRetired_s": {"type": "date"},
            "b1g_child_record_b": {"type": "boolean"},
            "b1g_dct_mediator_sm": {"type": "keyword"},
            "b1g_access_s": {"type": "object", "enabled": False},
            "b1g_image_ss": {"type": "keyword"},
            "b1g_geonames_sm": {"type": "keyword"},
            "b1g_publication_state_s": {"type": "keyword"},
            "b1g_language_sm": {"type": "keyword"},
            "b1g_creatorID_sm": {"type": "keyword"},
            "b1g_dct_conformsTo_sm": {"type": "keyword"},
            "b1g_dcat_spatialResolutionInMeters_sm": {"type": "keyword"},
            "b1g_geodcat_spatialResolutionAsText_sm": {"type": "keyword"},
            "b1g_dct_provenanceStatement_sm": {"type": "keyword"},
            "b1g_adminTags_sm": {"type": "keyword"},
            "summary": {"type": "text"},
            # Spatial facet fields for faceting
            "geo_global": {"type": "boolean"},
            "geo_country": {"type": "keyword"},
            "geo_region": {"type": "keyword"},
            "geo_county": {"type": "keyword"},
            "suggest": {
                "type": "completion",
                "analyzer": "simple",
                "preserve_separators": True,
                "preserve_position_increments": True,
                "max_input_length": 50,
            },
        }
    },
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "normalizer": {
                    "lowercase": {"type": "custom", "char_filter": [], "filter": ["lowercase"]}
                }
            },
        }
    },
}
