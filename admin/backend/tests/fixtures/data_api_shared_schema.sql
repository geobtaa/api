-- Schema-only PostgreSQL fixture. Seed all test metadata synthetically.
CREATE OR REPLACE FUNCTION public.update_distribution_types_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $function$
;
CREATE OR REPLACE FUNCTION public.update_resource_assets_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $function$
;
CREATE OR REPLACE FUNCTION public.update_resource_distributions_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $function$
;
CREATE OR REPLACE FUNCTION public.update_resource_downloads_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $function$
;
CREATE OR REPLACE FUNCTION public.update_resource_licensed_accesses_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $function$
;
CREATE TABLE public.distribution_types (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    distribution_type character varying(255) NOT NULL,
    distribution_uri character varying(500) NOT NULL,
    label boolean DEFAULT false,
    note text,
    "position" integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE SEQUENCE public.distribution_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.distribution_types_id_seq OWNED BY public.distribution_types.id;

CREATE TABLE public.resource_relationships (
    id integer NOT NULL,
    subject_id character varying NOT NULL,
    predicate character varying NOT NULL,
    object_id character varying NOT NULL
);

CREATE SEQUENCE public.item_relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.item_relationships_id_seq OWNED BY public.resource_relationships.id;

CREATE TABLE public.resource_assets (
    id integer NOT NULL,
    resource_id character varying(255) NOT NULL,
    bridge_asset_id character varying(255),
    bridge_parent_id character varying(255),
    friendlier_id character varying(255),
    title character varying(500),
    label character varying(255),
    thumbnail boolean DEFAULT false NOT NULL,
    dct_references_uri_key character varying(255),
    "position" integer DEFAULT 0 NOT NULL,
    file_url text,
    file_mime_type character varying(255),
    file_size integer,
    file_width integer,
    file_height integer,
    file_md5 character varying(64),
    file_sha1 character varying(64),
    file_sha512 character varying(128),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.resource_assets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.resource_assets_id_seq OWNED BY public.resource_assets.id;

CREATE TABLE public.resource_data_dictionaries (
    id integer NOT NULL,
    resource_id character varying(255) NOT NULL,
    legacy_document_data_dictionary_id integer,
    name character varying(255),
    description text,
    staff_notes text,
    tags character varying(4096) DEFAULT ''::character varying NOT NULL,
    "position" integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.resource_data_dictionaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.resource_data_dictionaries_id_seq OWNED BY public.resource_data_dictionaries.id;

CREATE TABLE public.resource_data_dictionary_entries (
    id integer NOT NULL,
    resource_data_dictionary_id integer NOT NULL,
    legacy_document_data_dictionary_entry_id integer,
    field_name character varying(255) NOT NULL,
    field_type character varying(255),
    "values" text,
    definition text,
    definition_source text,
    parent_field_name character varying(255),
    "position" integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.resource_data_dictionary_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.resource_data_dictionary_entries_id_seq OWNED BY public.resource_data_dictionary_entries.id;

CREATE TABLE public.resource_distributions (
    id integer NOT NULL,
    resource_id character varying(255) NOT NULL,
    distribution_type_id integer NOT NULL,
    url text NOT NULL,
    label character varying(255),
    "position" integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    import_distribution_id character varying(255)
);

CREATE SEQUENCE public.resource_distributions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.resource_distributions_id_seq OWNED BY public.resource_distributions.id;

CREATE TABLE public.resource_downloads (
    id integer NOT NULL,
    resource_id character varying(255) NOT NULL,
    label character varying(255),
    value text,
    "position" integer DEFAULT 0 NOT NULL,
    import_download_id character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.resource_downloads_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.resource_downloads_id_seq OWNED BY public.resource_downloads.id;

CREATE TABLE public.resource_licensed_accesses (
    id integer NOT NULL,
    resource_id character varying(255) NOT NULL,
    institution_code character varying(255) NOT NULL,
    access_url text NOT NULL,
    legacy_friendlier_id character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.resource_licensed_accesses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.resource_licensed_accesses_id_seq OWNED BY public.resource_licensed_accesses.id;

CREATE TABLE public.resources (
    id character varying NOT NULL,
    dct_title_s character varying,
    dct_alternative_sm character varying[],
    dct_description_sm text[],
    dct_language_sm character varying[],
    "gbl_displayNote_sm" text[],
    dct_creator_sm character varying[],
    dct_publisher_sm character varying[],
    schema_provider_s character varying,
    "gbl_resourceClass_sm" character varying[],
    "gbl_resourceType_sm" character varying[],
    dct_subject_sm character varying[],
    dcat_theme_sm character varying[],
    dcat_keyword_sm character varying[],
    dct_temporal_sm character varying[],
    dct_issued_s character varying,
    "gbl_indexYear_im" integer[],
    "gbl_dateRange_drsim" character varying[],
    dct_spatial_sm character varying[],
    locn_geometry text,
    dcat_bbox character varying,
    dcat_centroid character varying,
    dct_relation_sm character varying[],
    "pcdm_memberOf_sm" character varying[],
    "dct_isPartOf_sm" character varying[],
    dct_source_sm character varying[],
    "dct_isVersionOf_sm" character varying[],
    dct_replaces_sm character varying[],
    "dct_isReplacedBy_sm" character varying[],
    dct_rights_sm character varying[],
    "dct_rightsHolder_sm" character varying[],
    dct_license_sm text[],
    "dct_accessRights_s" character varying,
    dct_format_s character varying,
    "gbl_fileSize_s" character varying,
    "gbl_wxsIdentifier_s" character varying,
    dct_references_s text,
    dct_identifier_sm character varying[],
    "gbl_mdModified_dt" timestamp without time zone,
    "gbl_mdVersion_s" character varying,
    gbl_suppressed_b boolean,
    gbl_georeferenced_b boolean,
    b1g_code_s character varying,
    b1g_status_s character varying,
    "b1g_dct_accrualMethod_s" character varying,
    "b1g_dct_accrualPeriodicity_s" character varying,
    "b1g_dateAccessioned_s" date,
    "b1g_dateRetired_s" date,
    b1g_child_record_b boolean,
    b1g_dct_mediator_sm character varying[],
    b1g_access_s jsonb,
    b1g_image_ss character varying,
    b1g_geonames_sm character varying[],
    b1g_publication_state_s character varying,
    b1g_language_sm character varying[],
    "b1g_creatorID_sm" character varying[],
    "b1g_dct_conformsTo_sm" character varying[],
    "b1g_dcat_spatialResolutionInMeters_sm" character varying[],
    "b1g_geodcat_spatialResolutionAsText_sm" character varying[],
    "b1g_dct_provenanceStatement_sm" character varying[],
    "b1g_adminTags_sm" character varying[],
    "b1g_adms_supportedSchema_sm" character varying[],
    "b1g_dateAccessioned_sm" character varying[],
    "b1g_dcat_endpointDescription_s" character varying,
    "b1g_dcat_endpointURL_s" character varying,
    "b1g_dcat_inSeries_sm" character varying[],
    "b1g_localCollectionLabel_sm" character varying[],
    "b1g_prov_softwareAgent_sm" character varying[],
    "b1g_prov_wasGeneratedBy_sm" character varying[],
    date_created_dtsi timestamp without time zone,
    date_modified_dtsi timestamp without time zone,
    geomg_id_s character varying,
    publication_state character varying,
    import_id character varying,
    "b1g_adminNote_sm" character varying[],
    "b1g_dateAccessioned_dt" timestamp without time zone,
    "b1g_dateRetired_dt" timestamp without time zone,
    b1g_deprioritized_b boolean,
    "b1g_harvestWorkflow_s" character varying,
    "b1g_isHarvested_b" boolean,
    "b1g_lastHarvested_dt" timestamp without time zone,
    b1g_dct_provenance_sm character varying[],
    "b1g_dcat_spatialResolutionInMeters_s" character varying,
    "b1g_websitePlatform_s" character varying
);

ALTER TABLE ONLY public.distribution_types ALTER COLUMN id SET DEFAULT nextval('public.distribution_types_id_seq'::regclass);

ALTER TABLE ONLY public.resource_assets ALTER COLUMN id SET DEFAULT nextval('public.resource_assets_id_seq'::regclass);

ALTER TABLE ONLY public.resource_data_dictionaries ALTER COLUMN id SET DEFAULT nextval('public.resource_data_dictionaries_id_seq'::regclass);

ALTER TABLE ONLY public.resource_data_dictionary_entries ALTER COLUMN id SET DEFAULT nextval('public.resource_data_dictionary_entries_id_seq'::regclass);

ALTER TABLE ONLY public.resource_distributions ALTER COLUMN id SET DEFAULT nextval('public.resource_distributions_id_seq'::regclass);

ALTER TABLE ONLY public.resource_downloads ALTER COLUMN id SET DEFAULT nextval('public.resource_downloads_id_seq'::regclass);

ALTER TABLE ONLY public.resource_licensed_accesses ALTER COLUMN id SET DEFAULT nextval('public.resource_licensed_accesses_id_seq'::regclass);

ALTER TABLE ONLY public.resource_relationships ALTER COLUMN id SET DEFAULT nextval('public.item_relationships_id_seq'::regclass);

ALTER TABLE ONLY public.distribution_types
    ADD CONSTRAINT distribution_types_name_key UNIQUE (name);

ALTER TABLE ONLY public.distribution_types
    ADD CONSTRAINT distribution_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_assets
    ADD CONSTRAINT resource_assets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_data_dictionaries
    ADD CONSTRAINT resource_data_dictionaries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_data_dictionary_entries
    ADD CONSTRAINT resource_data_dictionary_entries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_distributions
    ADD CONSTRAINT resource_distributions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_downloads
    ADD CONSTRAINT resource_downloads_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_licensed_accesses
    ADD CONSTRAINT resource_licensed_accesses_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_relationships
    ADD CONSTRAINT resource_relationships_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resources
    ADD CONSTRAINT resources_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_data_dictionary_entries
    ADD CONSTRAINT uq_resource_data_dictionary_entries_dict_field_position UNIQUE (resource_data_dictionary_id, field_name, parent_field_name, "position");

CREATE INDEX idx_distribution_types_distribution_uri ON public.distribution_types USING btree (distribution_uri);

CREATE INDEX idx_distribution_types_name ON public.distribution_types USING btree (name);

CREATE INDEX idx_distribution_types_position ON public.distribution_types USING btree ("position");

CREATE INDEX idx_object_id ON public.resource_relationships USING btree (object_id);

CREATE INDEX idx_predicate ON public.resource_relationships USING btree (predicate);

CREATE INDEX idx_resource_distributions_distribution_type_id ON public.resource_distributions USING btree (distribution_type_id);

CREATE INDEX idx_resource_distributions_import_distribution_id ON public.resource_distributions USING btree (import_distribution_id);

CREATE INDEX idx_resource_distributions_position ON public.resource_distributions USING btree ("position");

CREATE INDEX idx_resource_distributions_resource_id ON public.resource_distributions USING btree (resource_id);

CREATE INDEX idx_resource_distributions_resource_id_type ON public.resource_distributions USING btree (resource_id, distribution_type_id);

CREATE UNIQUE INDEX idx_resource_distributions_resource_type_url ON public.resource_distributions USING btree (resource_id, distribution_type_id, url);

CREATE INDEX idx_resource_distributions_url ON public.resource_distributions USING btree (url);

CREATE INDEX idx_resources_dcat_bbox_id ON public.resources USING btree (dcat_bbox, id) WHERE ((dcat_bbox IS NOT NULL) AND ((dcat_bbox)::text <> ''::text));

CREATE INDEX idx_resources_dcat_bbox_not_null ON public.resources USING btree (id) WHERE ((dcat_bbox IS NOT NULL) AND ((dcat_bbox)::text <> ''::text));

CREATE INDEX idx_subject_id ON public.resource_relationships USING btree (subject_id);

CREATE INDEX ix_resource_assets_bridge_asset_id ON public.resource_assets USING btree (bridge_asset_id);

CREATE INDEX ix_resource_assets_bridge_parent_id ON public.resource_assets USING btree (bridge_parent_id);

CREATE INDEX ix_resource_assets_friendlier_id ON public.resource_assets USING btree (friendlier_id);

CREATE INDEX ix_resource_assets_resource_id ON public.resource_assets USING btree (resource_id);

CREATE INDEX ix_resource_assets_thumbnail ON public.resource_assets USING btree (thumbnail);

CREATE UNIQUE INDEX ix_resource_data_dictionaries_legacy_document_data_dict_d34e ON public.resource_data_dictionaries USING btree (legacy_document_data_dictionary_id);

CREATE INDEX ix_resource_data_dictionaries_resource_id ON public.resource_data_dictionaries USING btree (resource_id);

CREATE UNIQUE INDEX ix_resource_data_dictionary_entries_legacy_document_dat_36f1 ON public.resource_data_dictionary_entries USING btree (legacy_document_data_dictionary_entry_id);

CREATE INDEX ix_resource_data_dictionary_entries_resource_data_dictionary_id ON public.resource_data_dictionary_entries USING btree (resource_data_dictionary_id);

CREATE INDEX ix_resource_downloads_import_download_id ON public.resource_downloads USING btree (import_download_id);

CREATE INDEX ix_resource_downloads_resource_id ON public.resource_downloads USING btree (resource_id);

CREATE INDEX ix_resource_licensed_accesses_institution_code ON public.resource_licensed_accesses USING btree (institution_code);

CREATE INDEX ix_resource_licensed_accesses_legacy_friendlier_id ON public.resource_licensed_accesses USING btree (legacy_friendlier_id);

CREATE INDEX ix_resource_licensed_accesses_resource_id ON public.resource_licensed_accesses USING btree (resource_id);

CREATE TRIGGER trigger_update_distribution_types_updated_at BEFORE UPDATE ON public.distribution_types FOR EACH ROW EXECUTE FUNCTION public.update_distribution_types_updated_at();

CREATE TRIGGER trigger_update_resource_assets_updated_at BEFORE UPDATE ON public.resource_assets FOR EACH ROW EXECUTE FUNCTION public.update_resource_assets_updated_at();

CREATE TRIGGER trigger_update_resource_distributions_updated_at BEFORE UPDATE ON public.resource_distributions FOR EACH ROW EXECUTE FUNCTION public.update_resource_distributions_updated_at();

CREATE TRIGGER trigger_update_resource_downloads_updated_at BEFORE UPDATE ON public.resource_downloads FOR EACH ROW EXECUTE FUNCTION public.update_resource_downloads_updated_at();

CREATE TRIGGER trigger_update_resource_licensed_accesses_updated_at BEFORE UPDATE ON public.resource_licensed_accesses FOR EACH ROW EXECUTE FUNCTION public.update_resource_licensed_accesses_updated_at();

ALTER TABLE ONLY public.resource_data_dictionary_entries
    ADD CONSTRAINT resource_data_dictionary_entri_resource_data_dictionary_id_fkey FOREIGN KEY (resource_data_dictionary_id) REFERENCES public.resource_data_dictionaries(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.resource_distributions
    ADD CONSTRAINT resource_distributions_distribution_type_id_fkey FOREIGN KEY (distribution_type_id) REFERENCES public.distribution_types(id) ON DELETE RESTRICT;
