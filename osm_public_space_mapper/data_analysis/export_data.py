import geopandas as gpd
import pickle
from shapely import MultiPolygon

def save2geojson(all_defined_space_lists:dict, undefined_space_within_bbox:MultiPolygon, fname:str):
    def write_info_to_dict(all_defined_space_lists:dict, undefined_space_within_bbox:MultiPolygon) -> dict:
        geometries, access_types, space_types, osmids, osmtags = [],[],[],[],[]
        for list_name, elements in all_defined_space_lists.items():
            if list_name == 'dataset':
                for e in elements:
                    if e.is_polygon() or e.is_multipolygon():
                        geometries.append(e.geom)
                        if e.access is None:
                            access_types.append('undefined')
                        else:
                            access_types.append(e.access)
                        space_types.append(e.space_type)
                        osmids.append(e.id)
                        osmtags.append(e.tags)
            elif list_name == 'buildings':
                for e in elements:
                    geometries.append(e.geom)
                    access_types.append('no')
                    space_types.append('building')
                    osmids.append(e.id)
                    osmtags.append(e.tags)
            elif list_name == 'inaccessible_enclosed_areas':
                for e in elements:
                    geometries.append(e)
                    access_types.append('no')
                    space_types.append('inaccessible enclosed area')
                    osmids.append(None)
                    osmtags.append(None)
            elif list_name == 'traffic_areas':
                for e in elements:
                    geometries.append(e)
                    access_types.append('no')
                    space_types.append('traffic area')
                    osmids.append(None)
                    osmtags.append(None)
        geometries.append(undefined_space_within_bbox)
        access_types.append('yes')
        space_types.append('undefined space')
        osmids.append(None)
        osmtags.append(None)
        data = {'geometry': geometries, 'access': access_types, 'space_type':space_types, 'osmid':osmids, 'tags': osmtags}
        return data
    data = write_info_to_dict(all_defined_space_lists, undefined_space_within_bbox)
    gdf = gpd.GeoDataFrame(data)
    gdf.to_file(fname, driver = 'GeoJSON')