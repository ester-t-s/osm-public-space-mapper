import pyproj
import esy.osm.shape
import copy

import shapely
from shapely.geometry import LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString, GeometryCollection

from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.geometry_element import GeometryElement
from osm_public_space_mapper.utils.bounding_box import BoundingBox

ShapelyGeometry = LinearRing | Polygon | MultiPolygon | Point | MultiPoint | LineString | MultiLineString


def drop_invalid_geometries(elements: list[OsmElement]) -> list[OsmElement]:
    """Returns only the elements of a list of OsmElements that have a valid Shapely geometry
    Args:
        elements (list[OsmElement]): list of OsmElements

    Returns:
        list[OsmElement]: filtered list

    Note:
        OSM relations can not be processed by esy.osm.shape and have an invalid geometry.
        These elements are excluded from further analysis, because they are not very relevant to the public space analysis.
    """
    return [e for e in elements if type(e.geom) != esy.osm.shape.shape.Invalid]


def drop_empty_geometries(elements: list[OsmElement]) -> list[OsmElement]:
    return [e for e in elements if not e.geom.is_empty]


def drop_elements_without_tags(elements: list[OsmElement]) -> list[OsmElement]:
    """Returns only the elements of a list of OsmElements that have a tag

    Args:
        elements (list[OsmElement]): list of OsmElements

    Returns:
        list[OsmElement]: filtered list

    Note:
        OSM elements without tags are usually nodes that are required for the spatial definition of ways in OSM.
        They are not required for the public space analysis because they do not contain any additional information.
    """
    return [e for e in elements if len(e.tags) > 0]


def drop_points_apart_from_entrances(elements: list[OsmElement]) -> list[OsmElement]:
    """drops alls points apart from entrances because they are not relevant for analysis

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over

    Returns:
        list[OsmElement]: list of OsmElements without points apart from entrances

    Notes:
        Nodes in OSM also describe areas in some cases (e.g. bicycle parking, localities), however, these points cannot be converted into areas without exact specification of the size.
        In addition, these points are usually not directly relevant for public accessibility but describe the presence of certain amenities and thus often the quality of a space.
    """
    for e in elements:
        if e.is_point() and not e.is_entrance():
            e.ignore = True
    return [e for e in elements if not e.ignore]


def clean_geometries(elements: list[OsmElement]) -> None:
    """Iterates over a list of OsmElements and cleans the geometries by transforming simple multipolygons to polygons,
    transforming false polygons to linestrings and cropping overlapping polygons

    Args:
        elements (list[OsmElement]): list of OsmElements to be iterated over
    """
    def transform_simple_multipolygon_to_polygon(elements: list[OsmElement]) -> None:
        """Iterates over a list of OsmElements and transforms the geometry of an element to Polygon if it is a MultiPolygon with only one element

        Args:
            elements (list[OsmElement]): list of OsmElements to be iterated over

        Note:
            Not neccessary but helpful because esy.osm.shape saves some OSM objects as MultiPolygon with only one element
        """
        for e in elements:
            if type(e.geom) == MultiPolygon and len(e.geom.geoms) == 1:
                e.geom = e.geom.geoms[0]

    def transform_false_polygons_to_linestrings(elements: list[OsmElement]) -> None:
        """Iterates over a list of OsmElements and transforms the geometry of an element to LineString if it is a Polygon but should be a LineString

        Args:
            elements (list[OsmElement]): list of OsmElements to be iterated over

        Note:
            Neccessary because current version of esy.osm.shape interpretes some closed ways wrongly as Polygons insted of LineStrings
        """
        def is_highway_polygon(e: OsmElement) -> bool:
            if e.has_tag('highway'):
                return e.is_polygon()

        def is_fence(e: OsmElement) -> bool:
            if e.tags.get('barrier') == 'fence':
                return e.is_polygon()

        def should_be_linestring(e: OsmElement) -> bool:
            return e.tags.get('area', 'no') == 'no'

        def transform_to_linestring(e: OsmElement) -> None:
            e.geom = LineString(e.geom.exterior)

        for e in elements:
            if is_highway_polygon(e) or is_fence(e):
                if should_be_linestring(e):
                    transform_to_linestring(e)

    transform_simple_multipolygon_to_polygon(elements)
    transform_false_polygons_to_linestrings(elements)


def project_geometries(elements: list[OsmElement], local_crs: pyproj.crs.crs.CRS) -> None:
    """Iterates over list of OsmElements and projects their geometries into the given local_crs

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over
        local_crs (pyproj.crs.crs.CRS, optional): coordinate reference system to project to
    """
    projector = pyproj.Transformer.from_crs(pyproj.CRS.from_epsg(4326), local_crs, always_xy=True)
    for e in elements:
        e.geom = shapely.ops.transform(projector.transform, e.geom)


def drop_irrelevant_elements_based_on_tags(elements: list[OsmElement]) -> list[OsmElement]:

    def drop_elements_non_groundlevel(elements: list[OsmElement]) -> list[OsmElement]:
        """Iterates over list of OsmElements and drops element not on ground level according to tags

        Args:
            elements (list): list of OsmElements to iterate over

        Returns:
            list[OsmElement]: filtered list
        """
        def is_non_groundlevel(e: OsmElement) -> bool:
            non_groundlevel = False
            if e.has_tag('level'):
                try:
                    list(map(float, str(e.tags.get('level')).split(';')))
                except ValueError:
                    pass
                else:
                    if 0 not in list(map(float, str(e.tags.get('level')).split(';'))):
                        non_groundlevel = True
            elif e.tags.get('tunnel') == 'yes':
                non_groundlevel = True
            elif e.tags.get('parking') == 'underground':
                non_groundlevel = True
            elif e.tags.get('location') == 'underground':
                non_groundlevel = True
            return non_groundlevel

        for e in elements:
            if is_non_groundlevel(e):
                e.ignore = True
        return [e for e in elements if not e.ignore]

    def drop_elements_without_relevant_tag(elements: list[OsmElement]) -> list[OsmElement]:
        """iterates over list of OsmElements and drops the elements without a relevant tag

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over

        Returns:
            list[OsmElement]: filtered list
        """
        relevant_tags = ['highway', 'public_transport', 'railway', 'barrier', 'amenity', 'leisure', 'natural', 'water',
                         'parking', 'embankment', 'landuse', 'footway', 'bridge', 'place', 'construction', 'parking_space', 'man_made'
                         ]
        for e in elements:
            found = False
            for tag in relevant_tags:
                if e.has_tag(tag):
                    found = True
                    break
            if not found:
                e.ignore = True
        return [e for e in elements if not e.ignore]

    def drop_elements_with_irrelevant_tag(elements: list[OsmElement]) -> list[OsmElement]:
        """iterates over list of OsmElements and drops the elements with irrelevant tag

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over

        Returns:
            list[OsmElement]: filtered list
        """
        irrelevant_tags = ['boundary']
        for e in elements:
            for tag in irrelevant_tags:
                if e.has_tag(tag):
                    e.ignore = True
                    break
        return [e for e in elements if not e.ignore]

    def drop_elements_with_irrelevant_tag_value(elements: list[OsmElement]) -> list[OsmElement]:
        """iterates over list of OsmElements and drops the elements where specific tags have specific, irrelevant values

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over

        Returns:
            list[OsmElement]: filtered list
        """
        relevant_amenity_tag_values = ['fountain', 'shelter', 'parking', 'parking_space', 'bus_station', 'grave_yard', 'biergarten', 'motorcycle_parking', 'public_bath']
        irrelevant_tag_values = {'natural': {'tree_row'},
                                 'parking': {'underground'},
                                 'landuse': set(('commercial', 'retail', 'residential', 'industrial', 'education')),
                                 'place': set(['neighbourhood', 'city_block', 'locality', 'quarter']),
                                 'indoor': set(('yes', 'room')),
                                 'highway': set(('corridor', 'proposed'))
                                 }

        for e in elements:
            exclude = False
            for tag, values in irrelevant_tag_values.items():
                if e.has_tag(tag):
                    if e.tags.get(tag) in values:
                        exclude = True
                        break
            if e.has_tag('amenity'):
                if e.tags.get('amenity') not in relevant_amenity_tag_values:
                    exclude = True
            if exclude:
                e.ignore = True
        return [e for e in elements if not e.ignore]

    elements = drop_elements_non_groundlevel([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    elements = drop_elements_without_relevant_tag([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    elements = drop_elements_with_irrelevant_tag([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    elements = drop_elements_with_irrelevant_tag_value([e for e in elements if not e.is_building()]) + [e for e in elements if e.is_building()]
    return elements


def drop_road_rail_walking(elements: list[OsmElement]) -> list[OsmElement]:
    return [e for e in elements if e.space_type not in ['road', 'rail', 'walking area']]


def set_space_category(elements: list[OsmElement | GeometryElement]) -> list[OsmElement | GeometryElement]:
    categories = {'greenspace': ['dog_park', 'flowerbed', 'grass', 'park', 'sand', 'village_green', 'garden',
                                 'grassland', 'scrub', 'meadow', 'wood', 'allotments', 'beach', 'recreation_ground',
                                 'islet', 'forest', 'heath', 'nature_reserve', 'greenfield'],
                  'play and sports': ['playground', 'pitch', 'fitness_station', 'track', 'miniature_golf', 'horse_riding'],
                  'water': ['fountain', 'water', 'wetland', 'swimming_pool'],
                  'traffic area': ['parking', 'traffic area'],
                  'open space': ['public transport stop', 'square', 'scree', 'bridge', 'pier', 'marina', 'outdoor_seating', 'biergarten'],
                  'building': ['building'],
                  'undefined space': ['undefined space'],
                  'walking area': ['walking area'],
                  'construction': ['construction']
                  }
    for e in elements:
        for category, space_types in categories.items():
            if e.space_type in space_types:
                e.space_category = category
        if not e.space_category:
            print('uncategorized space type:', e.space_type)
            e.space_category = e.space_type
    return elements


def merge_elements_with_identical_attributes(elements: list[OsmElement | GeometryElement]) -> list[GeometryElement]:
    """merge elements with identical space category and access to reduce overlaps between elements

    Args:
        elements (list[OsmElement  |  GeometryElement]): list of elements defining all defined space

    Returns:
        list[GeometryElement]: list of merged elements
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


def crop_overlapping_polygons(elements: list[OsmElement | GeometryElement]) -> list[OsmElement | GeometryElement]:

    def clip_elements_within_category(elements: list[OsmElement | GeometryElement]) -> list[OsmElement | GeometryElement]:

        def clip_access_no(elements: list[OsmElement | GeometryElement], space_category: str) -> None:
            geometry_to_clip = shapely.ops.unary_union([e.geom for e in elements if e.space_category == space_category and e.access == 'no'])
            if not geometry_to_clip.is_empty:
                for e in elements:
                    if e.space_category == sc and e.access in ['yes', 'restricted']:
                        e.geom = e.geom.difference(geometry_to_clip)

        def clip_access_restricted(elements: list[OsmElement | GeometryElement], space_category: str) -> None:
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

    def clip_category_from_elements(elements: list[OsmElement | GeometryElement], category_to_clip: str, categories_to_crop: list[str] | None = None) -> None:
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
    clip_category_from_elements(elements, category_to_clip='water')
    clip_category_from_elements(elements, category_to_clip='undefined space', categories_to_crop=['traffic area', 'open space', 'walking area'])  # undefined space at this point are only the inaccessible enclosed areas
    clip_category_from_elements(elements, category_to_clip='walking area', categories_to_crop=['greenspace', 'play and sports'])
    clip_category_from_elements(elements, category_to_clip='play and sports')
    clip_category_from_elements(elements, category_to_clip='greenspace')
    clip_category_from_elements(elements, category_to_clip='traffic area', categories_to_crop=['open space', 'walking area'])
    for e in elements:
        if e.space_category == 'walking area':
            e.space_category = 'open space'
        elif e.space_category == 'inaccessible enclosed area':
            e.space_category = 'undefined space'
    elements = merge_elements_with_identical_attributes(elements)
    return elements


def crop_defined_space_to_bounding_box(all_defined_space: list[OsmElement | GeometryElement], bbox: BoundingBox) -> list[OsmElement | GeometryElement]:

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
            return e_cropped

    all_defined_space_cropped = []
    for element in all_defined_space:
        if intersects_bounding_box(element):
            all_defined_space_cropped.append(crop_element_to_bounding_box(element))
    return all_defined_space_cropped


def drop_linestrings(elements: list[OsmElement]) -> list[OsmElement]:
    """returns only the elements that are not LineStrings

    Args:
        elements (list[OsmElement]): list of OsmElements

    Returns:
        list[OsmElement]: filtered list of OsmElements

    Notes:
        Most linestrings apart from barriers and highways are not relevant for the analysis and have to be polygonized before they can be visualized
        For now, all linestrings are dropped (roads, rail and paths are saved as polygons separately)
    """
    return [e for e in elements if not e.is_linestring()]


def drop_elements_with_undefined_space_type(elements: list[OsmElement]) -> list[OsmElement]:
    """Returns only the elements were a space type was defined

    Args:
        elements (list[OsmElement]): list of OsmElements

    Returns:
        list[OsmElement]: filtered list of OsmElements

    Notes:
        the space type of an element is set in different steps mostly defined in analyse_space_type.
        If not space type was set until the end, it means that the element does not have any of the pre-defined tags like highway, amenity, leisure etc.
    """
    return [e for e in elements if e.space_type is not None]
