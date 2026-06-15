from __future__ import annotations

import json

from conftest import invoke


def test_validate_accepts_core_aardvark_record(runner, mock_client, tmp_path):
    mock_client({})
    record = {
        "id": "test-1",
        "dct_title_s": "Test record",
        "gbl_resourceClass_sm": ["Datasets"],
        "dct_accessRights_s": "Public",
        "gbl_mdVersion_s": "Aardvark",
    }
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")

    result = invoke(runner, ["--no-analytics", "validate", str(path), "--output", "json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["valid"] is True


def test_validate_reports_missing_required_field(runner, mock_client, tmp_path):
    mock_client({})
    path = tmp_path / "record.json"
    path.write_text(json.dumps({"id": "test-1"}), encoding="utf-8")

    result = invoke(runner, ["--no-analytics", "validate", str(path), "--output", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any("dct_title_s" in error["message"] for error in payload["errors"])


def test_crosswalk_fgdc_outputs_valid_aardvark(runner, mock_client, tmp_path):
    mock_client({})
    path = tmp_path / "fgdc.xml"
    path.write_text(
        """<?xml version="1.0"?>
<metadata>
  <idinfo>
    <citation>
      <citeinfo>
        <origin>BTAA Test Lab</origin>
        <pubdate>20200115</pubdate>
        <title>County roads</title>
        <geoform>vector digital data</geoform>
        <onlink>https://example.test/roads</onlink>
        <pubinfo><publish>Test Publisher</publish></pubinfo>
      </citeinfo>
    </citation>
    <descript><abstract>Road centerlines.</abstract></descript>
    <keywords>
      <theme><themekey>transportation</themekey></theme>
      <place><placekey>Iowa</placekey></place>
    </keywords>
    <spdom><bounding>
      <westbc>-94</westbc><eastbc>-90</eastbc>
      <northbc>44</northbc><southbc>40</southbc>
    </bounding></spdom>
    <accconst>None</accconst>
  </idinfo>
  <spdoinfo><ptvctinf><sdtsterm>
    <sdtstype>String</sdtstype>
  </sdtsterm></ptvctinf></spdoinfo>
  <distinfo><distrib><cntinfo><cntorgp>
    <cntorg>Test Provider</cntorg>
  </cntorgp></cntinfo></distrib></distinfo>
</metadata>
""",
        encoding="utf-8",
    )

    result = invoke(
        runner,
        ["--no-analytics", "crosswalk", str(path), "--from", "fgdc", "--validate"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    record = payload["record"]
    assert payload["validation"]["valid"] is True
    assert record["dct_title_s"] == "County roads"
    assert record["gbl_resourceType_sm"] == ["Line data"]
    assert record["gbl_indexYear_im"] == [2020]


def test_crosswalk_iso_outputs_valid_aardvark(runner, mock_client, tmp_path):
    mock_client({})
    path = tmp_path / "iso.xml"
    path.write_text(
        """<?xml version="1.0"?>
<gmd:MD_Metadata
  xmlns:gmd="http://www.isotc211.org/2005/gmd"
  xmlns:gco="http://www.isotc211.org/2005/gco">
  <gmd:fileIdentifier>
    <gco:CharacterString>iso-test-1</gco:CharacterString>
  </gmd:fileIdentifier>
  <gmd:contact><gmd:CI_ResponsibleParty>
    <gmd:organisationName>
      <gco:CharacterString>Test Provider</gco:CharacterString>
    </gmd:organisationName>
  </gmd:CI_ResponsibleParty></gmd:contact>
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification>
      <gmd:citation>
        <gmd:CI_Citation>
          <gmd:title>
            <gco:CharacterString>County parcels</gco:CharacterString>
          </gmd:title>
          <gmd:date><gmd:CI_Date>
            <gmd:date><gco:Date>2021-02-03</gco:Date></gmd:date>
          </gmd:CI_Date></gmd:date>
          <gmd:citedResponsibleParty>
            <gmd:CI_ResponsibleParty>
              <gmd:organisationName>
                <gco:CharacterString>Creator Org</gco:CharacterString>
              </gmd:organisationName>
              <gmd:role>
                <gmd:CI_RoleCode codeListValue="originator">originator</gmd:CI_RoleCode>
              </gmd:role>
            </gmd:CI_ResponsibleParty>
          </gmd:citedResponsibleParty>
        </gmd:CI_Citation>
      </gmd:citation>
      <gmd:abstract>
        <gco:CharacterString>Parcel polygons.</gco:CharacterString>
      </gmd:abstract>
      <gmd:descriptiveKeywords><gmd:MD_Keywords>
        <gmd:keyword><gco:CharacterString>cadastre</gco:CharacterString></gmd:keyword>
        <gmd:type>
          <gmd:MD_KeywordTypeCode codeListValue="theme">theme</gmd:MD_KeywordTypeCode>
        </gmd:type>
      </gmd:MD_Keywords></gmd:descriptiveKeywords>
      <gmd:extent><gmd:EX_Extent><gmd:geographicElement>
        <gmd:EX_GeographicBoundingBox>
          <gmd:westBoundLongitude><gco:Decimal>-94</gco:Decimal></gmd:westBoundLongitude>
          <gmd:eastBoundLongitude><gco:Decimal>-90</gco:Decimal></gmd:eastBoundLongitude>
          <gmd:northBoundLatitude><gco:Decimal>44</gco:Decimal></gmd:northBoundLatitude>
          <gmd:southBoundLatitude><gco:Decimal>40</gco:Decimal></gmd:southBoundLatitude>
        </gmd:EX_GeographicBoundingBox>
      </gmd:geographicElement></gmd:EX_Extent></gmd:extent>
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
  <gmd:spatialRepresentationInfo><gmd:MD_VectorSpatialRepresentation>
    <gmd:geometricObjects><gmd:MD_GeometricObjects>
      <gmd:geometricObjectType>
        <gmd:MD_GeometricObjectTypeCode codeListValue="surface">
          surface
        </gmd:MD_GeometricObjectTypeCode>
      </gmd:geometricObjectType>
    </gmd:MD_GeometricObjects></gmd:geometricObjects>
  </gmd:MD_VectorSpatialRepresentation></gmd:spatialRepresentationInfo>
</gmd:MD_Metadata>
""",
        encoding="utf-8",
    )

    result = invoke(
        runner,
        ["--no-analytics", "crosswalk", str(path), "--from", "iso", "--validate"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    record = payload["record"]
    assert payload["validation"]["valid"] is True
    assert record["dct_title_s"] == "County parcels"
    assert record["gbl_resourceType_sm"] == ["Polygon data"]
    assert record["dct_accessRights_s"] == "Public"


def test_crosswalks_lists_iso_and_fgdc_mappings(runner, mock_client):
    mock_client({})

    result = invoke(runner, ["--no-analytics", "aardvark", "crosswalks", "--output", "json"])

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert {
        "standard": "iso",
        "aardvark": "dct_title_s",
        "source": "gmd:CI_Citation/gmd:title",
    } in rows
