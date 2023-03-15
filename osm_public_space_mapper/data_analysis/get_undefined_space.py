import shapely
from shapely.geometry import LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
ShapelyGeometry = LinearRing|Polygon|MultiPolygon|Point|MultiPoint|LineString|MultiLineString

from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.bounding_box import BoundingBox

def load(all_defined_space_lists:dict[str,list[OsmElement|ShapelyGeometry]], bbox:BoundingBox) -> MultiPolygon:
    """returns space that is not part of all defined space as a Polygon

    Args:
        all_defined_space_lists (dict[str,list[OsmElement | ShapelyGeometry]]): dictionary of all lists with defined space
        bbox (BoundingBox): BoundingBox in which the undefined space should be loaded

    Returns:
        MultiPolygon: undefined space within BoundingBox as Polyon
    """    
    defined_space_geometries = []
    for list_name, elements in all_defined_space_lists.items():
        for e in elements:
            if type(e) == OsmElement:
                defined_space_geometries.append(e.geom)
            else:
                defined_space_geometries.append(e)
    defined_space_union = shapely.ops.unary_union(defined_space_geometries)
    undefined_space = bbox.geom_projected.difference(defined_space_union)
    return undefined_space