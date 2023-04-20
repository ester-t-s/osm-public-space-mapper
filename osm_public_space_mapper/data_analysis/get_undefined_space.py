from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.geometry_element import GeometryElement
from osm_public_space_mapper.utils.bounding_box import BoundingBox
import shapely
from shapely.geometry import LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
ShapelyGeometry = LinearRing | Polygon | MultiPolygon | Point | MultiPoint | LineString | MultiLineString


def load(all_defined_space: list[OsmElement | GeometryElement], bbox: BoundingBox) -> GeometryElement:
    """returns space that is not part of all defined space as a Polygon

    Args:
        all_defined_space (dict[str,list[OsmElement | GeometryElement]]): dictionary of all lists with defined space
        bbox (BoundingBox): BoundingBox in which the undefined space should be loaded

    Returns:
        MultiPolygon: undefined space within BoundingBox as Polyon
    """
    defined_space_union = shapely.ops.unary_union([e.geom for e in all_defined_space])
    undefined_space = GeometryElement(geometry=bbox.geom_projected.difference(defined_space_union),
                                      access='yes',
                                      space_category='undefined space')
    return undefined_space
