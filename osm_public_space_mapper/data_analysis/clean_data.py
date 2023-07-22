import pyproj
import esy.osm.shape
import copy
from typing import List, TypeAlias

import shapely
from shapely.geometry import (
    LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString, GeometryCollection
)

from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.geometry_element import GeometryElement
from osm_public_space_mapper.utils.bounding_box import BoundingBox

ShapelyGeometry: TypeAlias = LinearRing | Polygon | MultiPolygon | Point | MultiPoint | LineString | MultiLineString


def drop_invalid_geometries(elements: List[OsmElement]) -> List[OsmElement]:
    """Returns only the elements of a list of OsmElements that have a valid Shapely geometry
    Args:
        elements (List[OsmElement]): list of OsmElements

    Returns:
        List[OsmElement]: filtered list

    Note:
        OSM relations can not be processed by esy.osm.shape and have an invalid geometry.
        These elements are excluded from further analysis, because they are not very relevant to the public space analysis.
    """
    return [e for e in elements if type(e.geom) != esy.osm.shape.shape.Invalid]


def drop_empty_geometries(elements: List[OsmElement]) -> List[OsmElement]:
    count = len([e for e in elements if e.geom.is_empty])
    if count > 0:
        print(count, 'elements were deleted because of empty geometry')
    return [e for e in elements if not e.geom.is_empty]


def drop_elements_without_tags(elements: List[OsmElement]) -> List[OsmElement]:
    """Returns only the elements of a list of OsmElements that have a tag

    Args:
        elements (List[OsmElement]): list of OsmElements

    Returns:
        List[OsmElement]: filtered list

    Note:
        OSM elements without tags are usually nodes that are required for the spatial definition of ways in OSM.
        They are not required for the public space analysis because they do not contain any additional information.
    """
    return [e for e in elements if len(e.tags) > 0]


def drop_points_apart_from_entrances(elements: List[OsmElement]) -> List[OsmElement]:
    """drops alls points apart from entrances because they are not relevant for analysis

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over

    Returns:
        List[OsmElement]: list of OsmElements without points apart from entrances

    Notes:
        Nodes in OSM also describe areas in some cases (e.g. bicycle parking, localities), however, these points cannot be converted into areas without exact specification of the size.
        In addition, these points are usually not directly relevant for public accessibility but describe the presence of certain amenities and thus often the quality of a space.
    """
    for e in elements:
        if e.is_point() and not e.is_entrance():
            e.ignore = True
    return [e for e in elements if not e.ignore]


def clean_geometries(elements: List[OsmElement]) -> None:
    """Iterates over a list of OsmElements and cleans the geometries by transforming simple multipolygons to polygons,
    transforming false polygons to linestrings and cropping overlapping polygons

    Args:
        elements (List[OsmElement]): list of OsmElements to be iterated over
    """
    def transform_simple_multipolygon_to_polygon(elements: List[OsmElement]) -> None:
        """Iterates over a list of OsmElements and transforms the geometry of an element to Polygon if it is a MultiPolygon with only one element

        Args:
            elements (List[OsmElement]): list of OsmElements to be iterated over

        Note:
            Not necessary but helpful because esy.osm.shape saves some OSM objects as MultiPolygon with only one element
        """
        for e in elements:
            if type(e.geom) == MultiPolygon and len(e.geom.geoms) == 1:
                e.geom = e.geom.geoms[0]

    def transform_false_polygons_to_linestrings(elements: List[OsmElement]) -> None:
        """Iterates over a list of OsmElements and transforms the geometry of an element to LineString if it is a Polygon but should be a LineString

        Args:
            elements (List[OsmElement]): list of OsmElements to be iterated over

        Note:
            Neccessary because current version of esy.osm.shape interprets some closed ways wrongly as Polygons insted of LineStrings
        """

        def transform_to_linestring(e: OsmElement) -> None:
            e.geom = LineString(e.geom.exterior)

        for e in elements:
            if e.is_highway_polygon() or e.is_barrier_polygon() or e.is_wall_polygon():
                if not e.is_area():
                    transform_to_linestring(e)

    transform_simple_multipolygon_to_polygon(elements)
    transform_false_polygons_to_linestrings(elements)


def project_geometries(elements: List[OsmElement], local_crs: pyproj.crs.crs.CRS = pyproj.CRS.from_epsg(3035)) -> None:
    """Iterates over list of OsmElements and projects their geometries into the given local_crs

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over
        local_crs (pyproj.crs.crs.CRS, optional): coordinate reference system to project to. Defaults to EPSG 3035
    """
    projector = pyproj.Transformer.from_crs(pyproj.CRS.from_epsg(4326), local_crs, always_xy=True)
    for e in elements:
        e.geom = shapely.ops.transform(projector.transform, e.geom)


def drop_irrelevant_elements_based_on_tags(elements: List[OsmElement]) -> List[OsmElement]:

    def drop_elements_non_groundlevel(elements: List[OsmElement]) -> List[OsmElement]:
        """Iterates over list of OsmElements and drops element not on ground level according to tags

        Args:
            elements (list): list of OsmElements to iterate over

        Returns:
            List[OsmElement]: filtered list
        """

        for e in elements:
            if e.is_non_groundlevel():
                e.ignore = True
        return [e for e in elements if not e.ignore]

    def drop_elements_without_relevant_tag(elements: List[OsmElement]) -> List[OsmElement]:
        """iterates over list of OsmElements and drops the elements without a relevant tag

        Args:
            elements (List[OsmElement]): list of OsmElements to iterate over

        Returns:
            List[OsmElement]: filtered list
        """
        relevant_keys = [
            'highway',
            'public_transport',
            'railway',
            'barrier',
            'amenity',
            'leisure',
            'natural',
            'water',
            'parking',
            'embankment',
            'landuse',
            'footway',
            'bridge',
            'place',
            'construction',
            'parking_space',
            'man_made'
            ]
        for e in elements:
            found = False
            for key in relevant_keys:
                if e.has_tag_key(key):
                    found = True
                    break
            if not found:
                e.ignore = True
        return [e for e in elements if not e.ignore]

    def drop_elements_with_irrelevant_tag(elements: List[OsmElement]) -> List[OsmElement]:
        """iterates over list of OsmElements and drops the elements with irrelevant tag

        Args:
            elements (List[OsmElement]): list of OsmElements to iterate over

        Returns:
            List[OsmElement]: filtered list
        """
        irrelevant_keys = ['boundary']
        for e in elements:
            for key in irrelevant_keys:
                if e.has_tag_key(key):
                    e.ignore = True
                    break
        return [e for e in elements if not e.ignore]

    def drop_elements_with_irrelevant_tag_value(elements: List[OsmElement]) -> List[OsmElement]:
        """iterates over list of OsmElements and drops the elements where specific tag keys have specific, irrelevant values

        Args:
            elements (List[OsmElement]): list of OsmElements to iterate over

        Returns:
            List[OsmElement]: filtered list
        """
        relevant_amenity_tag_values = ['fountain', 'shelter', 'parking', 'parking_space', 'bus_station', 'grave_yard', 'biergarten', 'motorcycle_parking', 'public_bath']
        irrelevant_tag_values = {'natural': {'tree_row'},
                                 'landuse': {'commercial', 'retail', 'residential', 'industrial', 'education'},
                                 'place': {'neighbourhood', 'city_block', 'locality', 'quarter'},
                                 'indoor': {'yes', 'room'},
                                 'highway': {'corridor', 'proposed'}
                                 }

        for e in elements:
            exclude = False
            for key, values in irrelevant_tag_values.items():
                if e.has_tag_key(key):
                    if e.tags.get(key) in values:
                        exclude = True
                        break
            if e.has_tag_key('amenity'):
                if e.tags.get('amenity') not in relevant_amenity_tag_values:
                    exclude = True
            if exclude:
                e.ignore = True
        return [e for e in elements if not e.ignore]

    elements = drop_elements_non_groundlevel(elements)
    elements = drop_elements_without_relevant_tag([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    elements = drop_elements_with_irrelevant_tag([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    elements = drop_elements_with_irrelevant_tag_value([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    return elements


def drop_road_rail_walking(elements: List[OsmElement]) -> List[OsmElement]:
    return [e for e in elements if e.space_type not in ['road', 'rail', 'walking area']]


def clip_building_passages_from_buildings(buildings: List[OsmElement], traffic_elements: List[OsmElement]) -> List[OsmElement]:
    building_passages = []
    for e in traffic_elements:
        if e.is_building_passage() and (e.access is None or e.access == 'yes'):
            building_passages.append(e.geom)
    building_passages_union = shapely.ops.unary_union(building_passages)
    for b in buildings:
        if b.geom.intersects(building_passages_union):
            b.geom = b.geom.difference(building_passages_union)
    return [b for b in buildings if not b.geom.is_empty]


def set_space_category(elements: List[OsmElement | GeometryElement]) -> List[OsmElement | GeometryElement]:
    categories = {'greenspace': ['dog_park', 'flowerbed', 'grass', 'park', 'sand', 'village_green', 'garden', 'planter',
                                 'grassland', 'scrub', 'meadow', 'wood', 'allotments', 'beach', 'recreation_ground',
                                 'islet', 'forest', 'heath', 'nature_reserve', 'greenfield', 'shrubbery'],
                  'play and sports': ['playground', 'pitch', 'fitness_station', 'track', 'miniature_golf', 'horse_riding'],
                  'water': ['fountain', 'water', 'wetland', 'swimming_pool'],
                  'road': ['road', 'parking'],
                  'rail': ['rail'],  # to be merged with road later
                  'open space': ['public transport stop', 'square', 'scree', 'bridge', 'pier', 'marina', 'outdoor_seating', 'biergarten'],
                  'building': ['building'],
                  'inaccessible enclosed area': ['inaccessible enclosed area'],
                  'walking area': ['walking area'],  # to be merged with open space later
                  'construction': ['construction']
                  }
    uncategorized_space_types = []
    for e in elements:
        for category, space_types in categories.items():
            if e.space_type in space_types:
                e.space_category = category
        if not e.space_category:
            e.space_category = e.space_type
            uncategorized_space_types.append(e.space_type)
    if len(uncategorized_space_types) > 0:
        print('No space category given for', set(uncategorized_space_types), 'You should consider adding it to the function clean_data.set_space_category()')
    return elements


def merge_elements_with_identical_attributes(elements: List[OsmElement | GeometryElement]) -> List[GeometryElement]:
    """merge elements with identical space category and access to reduce overlaps between elements

    Args:
        elements (List[OsmElement  |  GeometryElement]): list of elements defining all defined space

    Returns:
        List[GeometryElement]: list of merged elements
    """
    merged_elements = []
    space_categories = set([e.space_category for e in elements])
    access_categories = set([e.access for e in elements])
    for sc in space_categories:
        for ac in access_categories:
            geometries_to_merge = []
            for e in elements:
                if e.space_category == sc and e.access == ac:
                    geometries_to_merge.append(e.geom)
            merged_geometry = shapely.ops.unary_union(geometries_to_merge)
            if not merged_geometry.is_empty:
                merged_elements.append(GeometryElement(geometry=merged_geometry, space_category=sc, access=ac))
    return merged_elements


def crop_overlapping_polygons(elements: List[GeometryElement]) -> List[GeometryElement]:

    def clip_elements_within_category(elements: List[GeometryElement]) -> List[GeometryElement]:

        def clip_access_no(elements: List[GeometryElement], space_category: str) -> None:
            geometry_to_clip = shapely.ops.unary_union([e.geom for e in elements if e.space_category == space_category and e.access == 'no'])
            if not geometry_to_clip.is_empty:
                for e in elements:
                    if e.space_category == sc and e.access in ['yes', 'restricted']:
                        e.geom = e.geom.difference(geometry_to_clip)

        def clip_access_restricted(elements: List[GeometryElement], space_category: str) -> None:
            geometry_to_clip = shapely.ops.unary_union([e.geom for e in elements if e.space_category == space_category and e.access == 'restricted'])
            if not geometry_to_clip.is_empty:
                for e in elements:
                    if e.space_category == sc and e.access == 'yes':
                        e.geom = e.geom.difference(geometry_to_clip)

        space_categories = set([e.space_category for e in elements])
        for sc in space_categories:
            if len(set([e.access for e in elements if e.space_category == sc])) > 1:
                clip_access_no(elements, sc)
                clip_access_restricted(elements, sc)

    def clip_category_from_elements(elements: List[OsmElement | GeometryElement], category_to_clip: str, categories_to_crop: List[str] | None = None) -> None:
        geometry_to_clip = shapely.ops.unary_union([e.geom for e in elements if e.space_category == category_to_clip])
        for e in elements:
            if not categories_to_crop:  # if no category to crop is specified elements from all categories apart from category_to_clip are cropped
                if not e.space_category == category_to_clip:
                    e.geom = e.geom.difference(geometry_to_clip)
            else:
                if e.space_category in categories_to_crop:
                    e.geom = e.geom.difference(geometry_to_clip)
            if type(e.geom) == GeometryCollection:  # convert GeometryCollections to MultiPolygons, dropping Points and LineStrings, for further processing
                e.geom = MultiPolygon([g for g in list(e.geom.geoms) if (type(g) == Polygon or type(g) == MultiPolygon)])

    clip_elements_within_category(elements)
    clip_category_from_elements(elements, category_to_clip='building')
    clip_category_from_elements(elements, category_to_clip='construction')
    clip_category_from_elements(elements, category_to_clip='rail', categories_to_crop=['greenspace', 'open space', 'walking area'])
    clip_category_from_elements(elements, category_to_clip='water')
    clip_category_from_elements(elements, category_to_clip='inaccessible enclosed area', categories_to_crop=['road', 'rail'])
    clip_category_from_elements(elements, category_to_clip='walking area', categories_to_crop=['greenspace', 'play and sports'])
    clip_category_from_elements(elements, category_to_clip='play and sports')
    clip_category_from_elements(elements, category_to_clip='greenspace')
    clip_category_from_elements(elements, category_to_clip='road', categories_to_crop=['open space', 'walking area'])
    for e in elements:
        if e.space_category == 'walking area':
            e.space_category = 'open space'
        elif e.space_category == 'inaccessible enclosed area':
            e.space_category = 'undefined space'
        elif e.space_category in ['rail', 'road']:
            e.space_category = 'traffic area'
    elements = merge_elements_with_identical_attributes(elements)
    clip_elements_within_category(elements)
    return elements


def crop_defined_space_to_bounding_box(all_defined_space: List[OsmElement | GeometryElement], bbox: BoundingBox) -> List[OsmElement | GeometryElement]:

    def intersects_bounding_box(element: OsmElement | GeometryElement, bbox: BoundingBox = bbox) -> bool:
        if bbox.geom_projected.intersects(element.geom):
            return True
        else:
            return False

    def crop_element_to_bounding_box(element: OsmElement | GeometryElement, bbox: BoundingBox = bbox) -> OsmElement | GeometryElement:
        """Drops element if it is outside of bounding box or crops geometry if within and outside of the bounding box

        Args:
            element (OsmElement | GeometryElement): element to crop to bounding box
            bbox (BoundingBox): BoundingBox object with the geom_projected attribute

        Returns:
            OsmElement | GeometryElement]: list of OsmElements and/or shapely geometries with cropped geometries
         """
        if bbox.geom_projected.covers(element.geom):
            return element
        else:
            e_cropped = copy.deepcopy(element)
            e_cropped.geom = bbox.geom_projected.intersection(e_cropped.geom)
            if not e_cropped.geom.is_empty:
                return e_cropped
            else:
                return 'empty cropped geometry'

    all_defined_space_cropped = []
    for element in all_defined_space:
        if intersects_bounding_box(element):
            element_cropped = crop_element_to_bounding_box(element)
            if not element_cropped == 'empty cropped geometry':
                all_defined_space_cropped.append(element_cropped)
    return all_defined_space_cropped


def drop_all_linestrings(elements: List[OsmElement]) -> List[OsmElement]:
    """returns only the elements that are not LineStrings

    Args:
        elements (List[OsmElement]): list of OsmElements

    Returns:
        List[OsmElement]: filtered list of OsmElements

    Notes:
        Most linestrings apart from barriers and highways are not relevant for the analysis and have to be polygonized before they can be visualized
        For now, all linestrings are dropped (roads, rail and paths are saved as polygons separately)
    """
    return [e for e in elements if not e.is_linestring()]


def drop_linestring_barriers_and_entrance_points(elements: List[OsmElement]) -> List[OsmElement]:
    for e in elements:
        if e.has_tag_key('barrier') and e.is_linestring():
            e.ignore = True
        elif e.is_entrance() and e.is_point():
            e.ignore = True
    return [e for e in elements if not e.ignore]


def drop_elements_with_undefined_space_type(elements: List[OsmElement]) -> List[OsmElement]:
    """Returns only the elements were a space type was defined

    Args:
        elements (List[OsmElement]): list of OsmElements

    Returns:
        List[OsmElement]: filtered list of OsmElements

    Notes:
        the space type of an element is set in different steps mostly defined in analyse_space_type.
        If not space type was set until the end, it means that the element does not have any of the pre-defined tags like highway, amenity, leisure etc.
    """
    return [e for e in elements if e.space_type is not None]
