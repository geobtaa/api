INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "dct_title_s": {
                "type": "text",
                # Guard against "immense term" failures for very long titles:
                # keyword terms > 32766 bytes cause document_parsing_exception.
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "normalizer": "lowercase",
                        "ignore_above": 8191,
                    }
                },
            },
            "dct_spatial_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "gbl_resourceClass_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "gbl_resourceType_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "gbl_indexYear_im": {"type": "integer"},
            "time_period": {"type": "keyword"},
            "dct_language_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "dct_creator_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "schema_provider_s": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            # OpenGeoMetadata repo facet/filter (derived at index-time from b1g_adminTags_sm)
            "ogm_repo": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "dct_accessRights_s": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "gbl_georeferenced_b": {"type": "boolean"},
            "dct_alternative_sm": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "normalizer": "lowercase",
                        "ignore_above": 8191,
                    }
                },
            },
            "dct_description_sm": {
                "type": "text",
                # NOTE: descriptions can be extremely long; ensure oversized terms are dropped
                # rather than rejecting the entire document.
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "normalizer": "lowercase",
                        "ignore_above": 8191,
                    }
                },
            },
            "gbl_displaynote_sm": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "normalizer": "lowercase",
                        "ignore_above": 8191,
                    }
                },
            },
            "dct_publisher_sm": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "normalizer": "lowercase",
                        "ignore_above": 8191,
                    }
                },
            },
            "dct_subject_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "dcat_theme_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            "dcat_keyword_sm": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
            },
            # Date-ish fields that often contain free-form or fuzzy text (e.g. "1656-1677?" or
            # "2021-08-31 to *"). We index them as keywords so Elasticsearch never tries to parse
            # them as strict dates.
            "dct_temporal_sm": {
                "type": "keyword",
                "normalizer": "lowercase",
                "ignore_above": 8191,
            },
            "dct_issued_s": {
                "type": "keyword",
                "normalizer": "lowercase",
                "ignore_above": 8191,
            },
            "gbl_daterange_drsim": {
                "type": "keyword",
                "normalizer": "lowercase",
                "ignore_above": 8191,
            },
            "locn_geometry": {
                "type": "geo_shape",
                "orientation": "counterclockwise",
                "coerce": True,
                "ignore_malformed": True,
            },
            "dcat_bbox": {
                "type": "geo_shape",
                "orientation": "counterclockwise",
                "coerce": True,
                "ignore_malformed": True,
            },
            "dcat_centroid": {"type": "geo_point", "ignore_malformed": True},
            "bbox_minx": {"type": "double"},
            "bbox_maxx": {"type": "double"},
            "bbox_miny": {"type": "double"},
            "bbox_maxy": {"type": "double"},
            "bbox_diagonal_km": {"type": "double"},
            "gbl_mdmodified_dt": {"type": "date", "ignore_malformed": True},
            # Legacy references blob retained for compatibility (disabled indexing)
            "dct_references_s": {"type": "object", "enabled": False},
            # BTAA-specific OGM Aardvark fields
            "b1g_code_s": {"type": "keyword"},
            "b1g_status_s": {"type": "keyword"},
            "b1g_dct_accrualMethod_s": {"type": "keyword"},
            "b1g_dct_accrualPeriodicity_s": {"type": "keyword"},
            "b1g_dateAccessioned_s": {"type": "date", "ignore_malformed": True},
            "b1g_dateRetired_s": {"type": "date", "ignore_malformed": True},
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
            "b1g_adminTags_sm": {"type": "keyword", "ignore_above": 256},
            "summary": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "normalizer": "lowercase",
                        "ignore_above": 8191,
                    }
                },
            },
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
            "number_of_replicas": 0,  # 0 for single-node development clusters
            "analysis": {
                "normalizer": {
                    "lowercase": {"type": "custom", "char_filter": [], "filter": ["lowercase"]}
                }
            },
        }
    },
}
