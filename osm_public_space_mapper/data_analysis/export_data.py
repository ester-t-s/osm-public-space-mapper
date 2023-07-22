import geopandas as gpd
import pyproj
import shapely
from typing import List, Dict
from osm_public_space_mapper.utils.geometry_element import GeometryElement
from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.bounding_box import BoundingBox


def check_completeness(all_defined_space: List[OsmElement | GeometryElement],
                       undefined_space_within_bbox: GeometryElement,
                       bbox: BoundingBox) -> None:
    all_space = [e.geom for e in all_defined_space + [undefined_space_within_bbox]]
    assert bbox.geom_projected.difference(shapely.ops.unary_union(all_space)).area < 0.01
    for element in all_defined_space + [undefined_space_within_bbox]:
        assert element.space_category is not None
        assert element.access is not None


def save2geojson(all_defined_space: List[OsmElement | GeometryElement],
                 undefined_space_within_bbox: GeometryElement,
                 fname: str,
                 local_crs: pyproj.crs.crs.CRS = pyproj.CRS.from_epsg(3035)
                 ) -> None:
    """
    Args:
        all_defined_space_lists (dict): dictionary of all lists of defined spaces
        undefined_space_within_bbox (GeometryElement): MultiPolygon of undefined space within bounding box
        fname (str): filename / path to save the GeoJSoN to
        local_crs (pyproj.crs.crs.CRS, optional): local CRS that was used for preceding analsis, required for transformation back to EPSG 4326. Defaults to EPSG 3035
    """
    def write_info_to_dict(all_defined_space: List[OsmElement | GeometryElement], undefined_space_within_bbox: GeometryElement) -> Dict:
        projector = pyproj.Transformer.from_crs(local_crs, pyproj.CRS.from_epsg(4326), always_xy=True)
        geometries, access, space_category = [], [], []
        for element in all_defined_space:
            geometries.append(shapely.ops.transform(projector.transform, element.geom))
            access.append(element.access)
            space_category.append(element.space_category)
        geometries.append(shapely.ops.transform(projector.transform, undefined_space_within_bbox.geom))
        access.append(undefined_space_within_bbox.access)
        space_category.append(undefined_space_within_bbox.space_category)
        data = {'geometry': geometries, 'access': access, 'space_category': space_category}
        return data
    data = write_info_to_dict(all_defined_space, undefined_space_within_bbox)
    gdf = gpd.GeoDataFrame(data)
    gdf.to_file(fname, driver='GeoJSON')
