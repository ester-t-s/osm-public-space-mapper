import copy
import shapely
from shapely.geometry import Polygon, MultiPolygon

from example_application import local_variables as local_var
from osm_public_space_mapper.utils.helpers import buffer_list_of_elements
from osm_public_space_mapper.utils.osm_element import OsmElement


def set_traffic_space_type(elements: list[OsmElement]):

    def is_pedestrian_way(element: OsmElement):

        def is_crossing(element: OsmElement):
            tags_with_crossing_values = set(('footway', 'highway'))
            if element.has_tag('crossing'):
                return True
            for tag in tags_with_crossing_values:
                if element.tags.get(tag) == 'crossing':
                    return True
            return False

        highway_for_pedestrians = set(('footway', 'steps', 'path', 'pedestrian', 'living_street', 'track'))
        return element.tags.get('highway') in highway_for_pedestrians and not is_crossing(element)

    def is_platform_polygon(element: OsmElement):
        tags_and_values_for_platforms = {'public_transport': 'platform', 'railway': 'platform', 'highway': 'platform', 'shelter_type': 'public_transport'}
        is_platform_polygon = False
        if element.is_polygon() or element.is_multipolygon():
            for tag in tags_and_values_for_platforms:
                if element.tags.get(tag) == tags_and_values_for_platforms[tag]:
                    is_platform_polygon = True
                    break
        return is_platform_polygon

    def is_parking_polygon(element: OsmElement):
        if element.is_polygon() or element.is_multipolygon():
            return any([e.tags.get('amenity') in ['parking', 'parking_space'], e.has_tag('parking'), e.has_tag('motorcycle_parking')])
        else:
            return False

    def is_rail(element: OsmElement):
        return element.tags.get('railway') in ['tram', 'rail']

    for e in elements:
        if is_pedestrian_way(e):
            e.space_type = 'walking area'
        elif is_platform_polygon(e):
            e.space_type = 'public transport stop'
        elif is_parking_polygon(e):
            e.space_type = 'parking'
        elif is_rail(e):
            e.space_type = 'rail'
        elif e.has_tag('highway'):
            e.space_type = 'road'


def get_traffic_areas_as_polygons(elements: list[OsmElement],
                                  inaccessible_enclosed_areas: list[Polygon | MultiPolygon],
                                  buildings: list[OsmElement],
                                  highway_default_widths: dict[str, tuple[float, float]] = None,
                                  cycleway_default_widths: dict[dict[str: float]] = None,
                                  tram_gauge: float = 1.435, tram_buffer: float = 0.5,
                                  train_gauge: float = 1.435, train_buffer: float = 1.5,
                                  pedestrian_way_default_width: float = 1.6,
                                  non_traffic_space_around_buildings_default_width: float = 1.3
                                  ) -> list[Polygon | MultiPolygon]:

    def buffer_osm_element(element: OsmElement) -> OsmElement:
        buffer_size = round(element.width/2, 1)
        element_buffered = copy.deepcopy(element)
        element_buffered.geom = element.geom.buffer(buffer_size, cap_style='flat')
        return element_buffered

    def polygonize_highways(elements: list[OsmElement], highway_default_widths: dict[str, tuple[float, float]], cycleway_default_widths: dict[dict[str: float]]) -> list[OsmElement]:
        """iterates over list of OsmElements and buffers highways and thus transforms the LineStrings to Polygons based on given or estimated width and sets processed elements in given list to ignore

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over

        Returns:
            list[OsmElement]: list of only highways as OsmElements with buffered geom attribute
        """
        def set_road_width(element: OsmElement, highway_default_widths: dict[str, tuple[float, float]], cycleway_default_widths: dict[dict[str: float]]) -> None:
            """Sets road width of a highway element in width attribute, either taken from width tags or estimated based on default values and

            Args:
                element (OsmElement): the OsmElement to analyse
                highway_default_widths (dict[str, tuple[float, float]]): dictionary with default highway widths of the roadway without parking, cycle lane etc. in a dictionary for each OSM highway type.
                                                                        Each dict element has a tuple consisting of the value for bi-directional and uni-directional highways. Defaults set within function.
                cycleway_default_widths (dict[dict[str: float]]): default cyleway widths with separate values given for different tags and their values in a nested dictionary. Defaults set within function.
            """
            def set_defaults(highway_default_widths: dict[str, tuple[float, float]], cycleway_default_widths: dict[dict[str: float]]) -> set[dict, dict]:
                if highway_default_widths is None:
                    highway_default_widths = {'footway': (1.8, 1), 'service': (4.5, 3), 'residential': (4.5, 3), 'steps': (2, 1.5), 'tertiary': (4.8, 3.1), 'primary': (5.5, 3.1),
                                              'cycleway': (2, 1.5), 'secondary': (4.8, 3.1), 'path': (1.5, 1), 'motorway_link': (6.5, 3.23), 'platform': (2, 1.5), 'pedestrian': (2, 2),
                                              'motorway': (6.5, 3.25), 'living_street': (4.5, 3), 'unclassified': (4.5, 3), 'primary_link': (5.5, 3.1), 'track': (3, 2.5),
                                              'corridor': (2, 1), 'proposed': (4.8, 3.1), 'secondary_link': (4.8, 3.1), 'construction': (5.5, 3.1), 'everything else': (4.8, 3.1)
                                              }
                if cycleway_default_widths is None:
                    cycletrack_width, cyclelane_width = 1.6, 1.6
                    cycleway_default_widths = {'cycleway': {'lane': cyclelane_width, 'opposite': 1, 'track': cycletrack_width, 'opposite_lane': cyclelane_width, 'opposite_track': cycletrack_width},
                                               'cycleway:right': {'lane': cyclelane_width, 'track': cycletrack_width},
                                               'cycleway:both': {'lane': 2*cyclelane_width, 'track': 2*cycletrack_width},
                                               'cycleway:left': {'lane': cyclelane_width, 'track': cycletrack_width}
                                               }
                return highway_default_widths, cycleway_default_widths

            highway_default_widths, cycleway_default_widths = set_defaults(highway_default_widths, cycleway_default_widths)

            def estimate_road_width(element: OsmElement, highway_default_widths: dict[str, tuple[float, float]], cycleway_default_widths: dict[dict[str: float]]) -> float:
                """estimates road with of an OsmElement based on default values and tags and returns the width

                Args:
                    element (OsmElement): the OsmElement to analyse
                    highway_default_widths (dict[str, tuple[float, float]]): dictionary with default highway widths of the roadway without parking, cycle lane etc. in a dictionary for each OSM highway type.
                                                                            Each dict element has a tuple consisting of the value for bi-directional and uni-directional highways.
                    cycleway_default_widths (dict[dict[str: float]]): default cyleway widths with separate values given for different tags and their values in a nested dictionary

                Returns:
                    float: estimated width
                """

                def set_default_highway_width(element: OsmElement, direction: str, highway_default_widths: dict[str, tuple[float, float]]) -> float:
                    i = 1 if direction == 'uni-directional' else 0 if direction == 'bi-directional' else None
                    if element.tags.get('highway') in highway_default_widths:
                        width = highway_default_widths[element.tags.get('highway')][i]
                    else:
                        width = highway_default_widths['everything else'][i]
                    return width

                def adapt_to_lanes(element: OsmElement, width: float, direction: str) -> float:
                    normal_lane_number = 1 if direction == 'uni-directional' else 2 if direction == 'bi-directional' else None
                    if element.has_tag('lanes') and float(element.tags.get('lanes')) != normal_lane_number:
                        width = width * float(element.tags.get('lanes'))/normal_lane_number
                    return width

                def add_cycleway(element: OsmElement, width: float, cycleway_default_widths: dict[dict[str: float]]) -> float:
                    if element.tags.get('highway') not in cycleway_default_widths:  # if it's not a cycleway by itself
                        for tag in cycleway_default_widths:
                            if element.has_tag(tag):
                                if element.tags.get(tag) in cycleway_default_widths[tag]:
                                    width += cycleway_default_widths[tag][element.tags.get(tag)]
                    return width

                def add_parking(element: OsmElement,
                                width: float,
                                highway_types_for_default_streetside_parking: list[str] = ['residential', 'tertiary', 'living_street', 'secondary', 'primary'],
                                default_parking_width: float = 6.5) -> float:
                    """adds a default value to the given width if highway is of specific type

                    Args:
                        element (OsmElement): highway OsmElement
                        width (float): current width of the element
                        highway_types_for_default_streetside_parking (list[str], optional): highway tag values where parking is assumed.
                                                                                            Defaults to ['residential', 'tertiary', 'living_street', 'secondary', 'primary'].
                        default_parking_width (float, optional): _description_. Defaults to 6.5, assuming one side horizontal (2m) and one side angle parking (4.5m),
                                                                taken from OSM Verkehrswende project https://parkraum.osm-verkehrswende.org/project-prototype-neukoelln/report/#27-fl%C3%A4chenverbrauch

                    Returns:
                        float: width with added parking
                    """
                    if element.tags.get('highway') in highway_types_for_default_streetside_parking:
                        width += default_parking_width
                    return width

                def add_shoulder(element: OsmElement, width: float) -> float:
                    """Note:
                    function not defined because shoulder is insignificant in the Vienna OSM database. However, other similar projects take shoulder into account.
                    """
                    return width

                direction = 'uni-directional' if e.has_tag('oneway') else 'bi-directional'
                width = set_default_highway_width(e, direction, highway_default_widths)
                width = adapt_to_lanes(e, width, direction)
                width = add_cycleway(e, width, cycleway_default_widths)
                width = add_parking(e, width, local_var.highway_types_for_default_streetside_parking, local_var.default_parking_width)
                return width
            if element.has_tag('width:carriageway'):
                element.width = float(e.tags.get('width:carriageway'))
            elif element.has_tag('width'):
                element.width = float(e.tags.get('width'))
            else:
                element.width = estimate_road_width(element, highway_default_widths, cycleway_default_widths)

        def is_irrelevant_highway(element: OsmElement) -> bool:
            irrelevant_highway_tag_values = ['corridor', 'proposed']
            return element.tags.get('highway') in irrelevant_highway_tag_values

        highways_polygons = []
        for e in [e for e in elements if e.has_tag('highway')]:
            if not is_irrelevant_highway(e) and e.is_linestring():
                set_road_width(e, highway_default_widths, cycleway_default_widths)
                highways_polygons.append(buffer_osm_element(e))
        return highways_polygons

    def polygonize_railways(elements: list[OsmElement], tram_gauge: float, tram_buffer: float, train_gauge: float, train_buffer: float) -> list[OsmElement]:
        """iterates over list of OsmElements and buffers railways and thus transforms the LineStrings to Polygons based on tram and train gauge and buffer size

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over
            tram_gauge (float): tram gauge. Defaults to 1.435
            tram_buffer (float): tram buffer size of what should be added to the tram gauge for total tram rail width
            train_gauge (float): train gauge. Defaults to 1.435
            train_buffer (float): train buffer size of what should be added to the train gauge for total train rail width

        Returns:
            list[OsmElement]: list of only railways as OsmElements with buffered geom attribute
        """
        rails_polygons = []
        for e in [e for e in elements if e.space_type == 'rail']:
            if e.tags.get('railway') == 'tram':
                e.width = tram_gauge + tram_buffer
            elif e.tags.get('railway') == 'rail':  # ignore subway because assume it's underground
                e.width = train_gauge + train_buffer
            if e.is_linestring():
                rails_polygons.append(buffer_osm_element(e))
            elif e.is_multipolygon() or e.is_polygon():
                rails_polygons.append(e)
        return rails_polygons

    def get_road_and_rail(elements: list[OsmElement]) -> list[OsmElement]:
        return polygonize_highways(elements, highway_default_widths, cycleway_default_widths) + polygonize_railways(elements, tram_gauge, tram_buffer, train_gauge, train_buffer)

    def get_cropper_geometries(elements: list[OsmElement], inaccessible_enclosed_areas: list[Polygon | MultiPolygon], buildings: list[OsmElement]) -> list[Polygon | MultiPolygon]:
        """combines and returns all geometries that should be used to crop the traffic areas again

        Args:
            elements (list[OsmElement): list of OsmElements with platform and pedestrian way elements
            inaccessible_enclosed_areas (list[Polygon | MultiPolygon]): list of earlier defined inaccessible_enclosed_areas, because traffic areas will not be accessible there
            buildings (list[OsmElement): list of OsmElements iwth buildings

        Returns:
            list[Polygon|MultiPolygon]: list of polygon or multipolygon geomtries instead of OsmElements
        """
        pedestrian_linestrings_buffered = buffer_list_of_elements([e for e in elements if e.space_type == 'walking area' and e.is_linestring()], buffer_size=pedestrian_way_default_width/2, cap_style='flat')
        pedestrian_polygons = pedestrian_linestrings_buffered + [e for e in elements if e.space_type == 'walking area' and (e.is_multipolygon() or e.is_polygon())]
        buildings_buffered = buffer_list_of_elements(buildings, buffer_size=non_traffic_space_around_buildings_default_width, join_style='mitre')
        platform_polygons = [e for e in elements if e.space_type == 'public transport stop']
        cropper_geometries = [e.geom for e in pedestrian_polygons] + [e.geom for e in buildings_buffered] + [e.geom for e in platform_polygons] + inaccessible_enclosed_areas
        return cropper_geometries, pedestrian_polygons

    def smooth_road_and_rail(road_and_rail_cropped):
        first_buffer_size = pedestrian_way_default_width/2+0.01  # buffer with half width of buffered pedestrian way plus a little more to close crossings that were cut out during cropping
        smooth_road_and_rail = road_and_rail_cropped.buffer(first_buffer_size, join_style='mitre').buffer(-first_buffer_size, join_style='mitre').buffer(0.5, join_style='round').buffer(-0.5, join_style='round')
        return smooth_road_and_rail

    road_and_rail = get_road_and_rail(elements)
    cropper_geometries, pedestrian_polygons = get_cropper_geometries(elements, inaccessible_enclosed_areas, buildings)
    cropper_geometries_union = shapely.ops.unary_union(cropper_geometries).buffer(0.3).buffer(-0.3)
    road_and_rail_union = shapely.ops.unary_union([e.geom for e in road_and_rail])
    road_and_rail_cropped = road_and_rail_union.difference(cropper_geometries_union)
    return smooth_road_and_rail(road_and_rail_cropped), pedestrian_polygons
