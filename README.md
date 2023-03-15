# OSM Public Space Mapper
*This project is a work in progress.*

## Project description
This repository includes a python script to identify and map publicly accessible space based on OpenStreetMap Data. I developed it as part of Master thesis. The underlying understanding of public space is publicly accessible and usable areas that are outdoor and urban.

## Usage
The script works with an extract of OSM data, for example downloaded from Geofabrik and cropped with a command line tool like Osmosis. Results are improved if complete ways are added, e.g. with Osmosis:
```
osmosis --read-pbf file=orig-data/austria-latest.osm.pbf --bb top=48.1999 left=16.3843 bottom=48.1931 right=16.3977 completeWays=yes --wb data/sample-data-rennweg-to-arenbergpark.osm.pbf
```
Apart from the dataset in osm.pbf format, the coordinates of the bounding box and the target filename have to be passed to the script. The target CRS is set to EPSG 3035 for European Lambert Azimuthal Equal Area but can be switched to a more precise, local CRS. Other local variables can be set in example_application/local_variables.py.
The data analysis is brought together in osm_public_space_mapper.data_analysis.full_data_analysis and uses multiple other modules from the package and the custom classes BoundingBox and OsmElement defined in osm_public_space_mapper.utils.
The result will be a GeoJSON file with Polygon objects (EPSG 4326) and the attributes space_type and access. If elements are left with undefined access, the space_type should be checked and access should be derived from that.
An OSM extract for a part of Vienna's third district, downloaded on March 8, 2023, is provided as sample data under OSM Licence: [OpenStreetMap](https://wiki.osmfoundation.org/wiki/Licence/Attribution_Guidelines)

## Limitations
The script is not optimized for performance. An analysis for an area of around 1 km2 should be processed in around five minutes. Bigger areas take significantly longer.
The analysis only looks at outdoor elements. Buidlings and everything located in buildings is ignored.
The analysis was developed with Western European cities in mind and is applied to a part of Vienna. The assumptions about public space lying behind the analysis might not be equally applicable to very different cultural and spatial contexts.

## Contributing

Contributions are welcome! If you can see a way to improve this project:

- Do click the fork button
- Make your changes and make a pull request.

Or to report a bug or request something new, make an issue.

## Note of thanks
Many thanks for the support to my supervisors Dr. Florian Ledermann, Andrea Binn and Prof. Dr. Marian Dörk

## Contact
Ester Scheck, [ester.scheck@fh-potsdam.de](mailto:ester.scheck@fh-potsdam.de)
