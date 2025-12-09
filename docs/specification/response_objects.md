# Response Objects

{% include-markdown "includes/wip.md" %}

## META block

The META block MAY contain these potential user interface component entries (see 8.5):

| Feature | Key(s) | Description | Example Value(s) |
| :---- | :---- | :---- | :---- |
| Citation | citation | Generic citation format. String. | {"citation": "\[Creator not found\], (1932). A food map of the United States. https://quod.lib.umich.edu/c/clark1ic/x-003289100/39015091916158 (pictorial map)."} |
| Data Dictionary | dictionary | CSV | `document_data_dictionary_id,friendlier_id,field_name,field_type,values,definition,definition_source,parent_field_name,position` |
| Downloads | downloads | Convenience presentation of dct\_references\_s’ downloads. Array of objects. | {"downloads": \[{"label": "Download Shapefile", "url": "https://stacks.stanford.edu/object/cf162mm8787"}\]} |
| Metadata | metadata | Convenience presentation of dct\_references\_s’ metadata entries. Array of objects. | {"metadata": \[{"label": "ISO 19139", "url": "https://web.s3.wisc.edu/rml-gisdata/metadata/Bayfield\_Trails\_2020.xml"}\]} |
| Relationships | relationships | Convenience presentation of OGM Aardvark relationship fields. Nested Objects. | {"relationships": { "member\_of": { "links": { "related":     ".../resource/b0153110-e455-4ced-9114-9b13250a7093" }, "data": \[{ "type": "resource", "id": "b0153110-e455-4ced-9114-9b13250a7093"}\]}} |
| Viewer | viewer: protocol endpoint geometry | The viewer key contains all the necessary values to display an npm \`@geoblacklight-frontend\` package-driven item viewer. Object. | {"viewer": {"protocol": "iiif\_manifest", "endpoint": "https://quod.lib.umich.edu/cgi/i/image/api/search/clark1ic:003289100","geometry": { "type":"Polygon", "coordinates": \[\[\[\-124.98,49.31\],\[\-67.18,49.31\],\[\-67.18,22.61\],\[\-124.98,22.61\],\[\-124.98,49.31\]\]\] }}} |
| Thumbnail | thumbnail: url alt\_text | Thumbnail object, including URL and Alt Text entries. Object. | {"thumbnail": { "url":  "https://quod.lib.umich.edu/cgi/i/image/api/image/clark1ic:003289100:39015091916158/full/400,/0/default.jpg", "alt-text": "A food map of the United States"}} |

## UI Component Support

A list of the frontend feature components this OGM API can support. 

See the BTAA proof of concept React UI for an example implementation:  
[https://github.com/geobtaa/rui](https://github.com/geobtaa/rui)

### Search

* Autocomplete  
* Search  
* Map Search  
* Results  
* Result Thumbnails  
* Facets  
* Pagination  
* Per Page  
* Sorting  
* Spelling Suggestions  
* Constraints

### Resource View

* Viewer  
* Context  
  * Breadcrumb  
  * Sidebar Map  
  * More Like This  
* Metadata Text  
* Metadata Links  
* Citation  
* Downloads  
* Relationships