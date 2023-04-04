import geopandas as gpd
import pyproj
import shapely
from shapely import MultiPolygon


def save2geojson(all_defined_space_lists: dict,
                 undefined_space_within_bbox: MultiPolygon,
                 fname: str,
                 local_crs: pyproj.crs.crs.CRS
                 ) -> None:
    """saves given elements and geometries to a GeoJSON with EPSG 4326 because it is default for GeoJSON

    Args:
        all_defined_space_lists (dict): dictionary of all lists of defined spaces
        undefined_space_within_bbox (MultiPolygon): MultiPolygon of undefined space within bounding box
        fname (str): filename / path to save the GeoJSoN to
        local_crs (pyproj.crs.crs.CRS, optional): local CRS that was used for preceding analsis, required for transformation back to EPSG 4326.
    """
    def write_info_to_dict(all_defined_space_lists: dict, undefined_space_within_bbox: MultiPolygon) -> dict:
        projector = pyproj.Transformer.from_crs(local_crs, pyproj.CRS.from_epsg(4326), always_xy=True)
        geometries, access_types, space_types, access_source, osmids, osmtags = [], [], [], [], [], []
        for list_name, elements in all_defined_space_lists.items():
            if list_name == 'dataset':
                for e in elements:
                    if e.is_polygon() or e.is_multipolygon():
                        geometries.append(shapely.ops.transform(projector.transform, e.geom))
                        if e.access is None:
                            access_types.append('undefined')
                        else:
                            access_types.append(e.access)
                        space_types.append(e.space_type)
                        access_source.append(e.access_derived_from)
                        osmids.append(e.id)
                        osmtags.append(e.tags)
            elif list_name == 'buildings':
                for e in elements:
                    geometries.append(shapely.ops.transform(projector.transform, e.geom))
                    access_types.append('no')
                    space_types.append('building')
                    access_source.append('space type')
                    osmids.append(e.id)
                    osmtags.append(e.tags)
            elif list_name == 'inaccessible_enclosed_areas':
                for e in elements:
                    geometries.append(shapely.ops.transform(projector.transform, e))
                    access_types.append('no')
                    space_types.append('inaccessible enclosed area')
                    access_source.append('space type')
                    osmids.append(None)
                    osmtags.append(None)
            elif list_name == 'road_and_rail':
                for e in elements:
                    geometries.append(shapely.ops.transform(projector.transform, e))
                    access_types.append('no')
                    space_types.append('traffic area')
                    access_source.append('space type')
                    osmids.append(None)
                    osmtags.append(None)
        geometries.append(shapely.ops.transform(projector.transform, undefined_space_within_bbox))
        access_types.append('yes')
        space_types.append('undefined space')
        access_source.append('space type')
        osmids.append(None)
        osmtags.append(None)
        data = {'geometry': geometries,
                'access': access_types,
                'space_type': space_types,
                'access_source': access_source,
                'osmid': osmids,
                'tags': osmtags
                }
        return data
    data = write_info_to_dict(all_defined_space_lists, undefined_space_within_bbox)
    gdf = gpd.GeoDataFrame(data)
    gdf.to_file(fname, driver='GeoJSON')
