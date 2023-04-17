import pyproj
import esy.osm.shape
import copy

import shapely
from shapely.geometry import LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString

from osm_public_space_mapper.utils.osm_element import OsmElement
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
        relevant_tags = ['highway', 'public_transport', 'railway', 'barrier', 'amenity', 'leisure', 'natural',
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
        irrelevant_tag_values = {'natural': set(('tree_row')),
                                 'parking': set(('underground')),
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


def clip_overlapping_polygons(elements: list[OsmElement],
                              buildings: list[OsmElement],
                              inaccessible_enclosed_areas: list[Polygon | MultiPolygon],
                              road_and_rail: MultiPolygon,
                              pedestrian_ways: list[Polygon | MultiPolygon]) -> None:

    def get_intersecting_elements(base_element: Polygon | MultiPolygon, check_elements: list[OsmElement]) -> list[OsmElement]:
        intersecting_elements = []
        base_element_prep = shapely.prepared.prep(base_element.buffer(-0.2))
        for e in check_elements:
            if base_element_prep.intersects(e.geom):
                intersecting_elements.append(e)
        return intersecting_elements

    def clip_enclosed_areas_intersecting_with_elements(elements: list[OsmElement] = elements,
                                                       buildings: list[OsmElement] = buildings,
                                                       inaccessible_enclosed_areas: list[Polygon | MultiPolygon] = inaccessible_enclosed_areas,
                                                       road_and_rail: MultiPolygon = road_and_rail,
                                                       pedestrian_ways: list[OsmElement] = pedestrian_ways) -> list[Polygon | MultiPolygon]:

        enclosed_areas_clipped = []
        for enclosed_area in inaccessible_enclosed_areas:
            intersecting_osm_elements = get_intersecting_elements(enclosed_area, elements)
            intersecting_buildings = get_intersecting_elements(enclosed_area, buildings)
            intersecting_pedestrian_ways = get_intersecting_elements(enclosed_area, pedestrian_ways)
            intersecting_geometries = [e.geom for e in intersecting_osm_elements] + [e.geom for e in intersecting_buildings] + [e.geom for e in intersecting_pedestrian_ways] + list(road_and_rail.geoms)
            intersecting_geometries_union = shapely.ops.unary_union(intersecting_geometries)
            enclosed_areas_clipped.append(enclosed_area.difference(intersecting_geometries_union))
        return [e for e in enclosed_areas_clipped if not e.is_empty]

    def clip_osm_elements_within_osm_elements(elements: list[OsmElement] = elements) -> list[OsmElement]:
        for p1 in elements:
            for p2 in elements + [e for e in pedestrian_ways if e.access != 'no'] + buildings:
                if p1 == p2:
                    pass
                elif p1.geom.buffer(0.2).contains(p2.geom):
                    p1.geom = p1.geom.difference(p2.geom)
        return [e for e in elements if not e.geom.is_empty]

    def clip_osm_elements_intersecting_with_ways_and_buildings(elements: list[OsmElement] = elements,
                                                               buildings: list[OsmElement] = buildings,
                                                               pedestrian_ways: list[OsmElement] = pedestrian_ways) -> list[OsmElement]:
        for element in elements:
            intersecting_buildings = get_intersecting_elements(element.geom, buildings)
            intersecting_pedestrian_ways = get_intersecting_elements(element.geom, pedestrian_ways)
            intersecting_geometries = [e.geom for e in intersecting_buildings] + [e.geom for e in intersecting_pedestrian_ways]
            intersecting_geometries_union = shapely.ops.unary_union(intersecting_geometries)
            element.geom = element.geom.difference(intersecting_geometries_union)
        return [e for e in elements if not e.geom.is_empty]

    enclosed_areas_clipped = clip_enclosed_areas_intersecting_with_elements()
    elements = clip_osm_elements_within_osm_elements()
    elements = clip_osm_elements_intersecting_with_ways_and_buildings()
    return elements, enclosed_areas_clipped


def crop_defined_space_to_bounding_box(all_defined_space_lists: dict[str, list[OsmElement | ShapelyGeometry]], bbox: BoundingBox) -> dict:

    def crop_elements_list_to_bounding_box(elements: list[OsmElement | ShapelyGeometry], bbox: BoundingBox) -> list[OsmElement | ShapelyGeometry]:
        """Iterates over list of OsmElements or shapely geometries and drops elements that are outside of bounding box
        and crops the geometries of those elements that are within and outside of the bounding box

        Args:
            elements (list[OsmElement | ShapelyGeometry]): list of OsmElements and/or shapely geometries to iterate over
            bbox (BoundingBox): BoundingBox object with the geom_projected attribute

        Returns:
            list[OsmElement|ShapelyGeometry]: list of OsmElements and/or shapely geometries with cropped geometries
        """
        elements_cropped = []
        for e in elements:
            if type(e) == OsmElement:
                geometry = e.geom
            else:
                geometry = e
            if not bbox.geom_projected.intersects(geometry):
                pass
            elif shapely.ops.prep(bbox.geom_projected).covers(geometry):
                elements_cropped.append(e)
            else:
                geometry_cropped = bbox.geom_projected.intersection(geometry)
                e_cropped = copy.deepcopy(e)
                if type(e) == OsmElement:
                    e_cropped.geom = geometry_cropped
                else:
                    e_cropped = geometry_cropped
                elements_cropped.append(e_cropped)
        return elements_cropped
    all_defined_space_lists_cropped = dict()
    for list_name, elements in all_defined_space_lists.items():
        elements_cropped = crop_elements_list_to_bounding_box(elements, bbox)
        all_defined_space_lists_cropped[list_name] = elements_cropped
    return all_defined_space_lists_cropped


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
