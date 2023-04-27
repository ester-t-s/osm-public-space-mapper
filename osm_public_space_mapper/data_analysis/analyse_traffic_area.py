import copy
import shapely
from typing import List, Tuple

from example_application import local_variables as local_var
from osm_public_space_mapper.utils.helpers import buffer_list_of_elements
from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.geometry_element import GeometryElement


def set_traffic_space_type(elements: List[OsmElement]):
    """iterates over list of OsmElements and sets space type attribute if element is traffic area (walking area, public transport stop, parking, rail, road)

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over
    """
    for e in elements:
        if e.is_pedestrian_way() or e.is_shared_cycleway_footway():
            e.space_type = 'walking area'
        elif e.is_platform_polygon():
            e.space_type = 'public transport stop'
        elif e.is_parking_polygon():
            e.space_type = 'parking'
            e.access = ('no', 'overwrite_yes')
        elif e.is_rail():
            e.space_type = 'rail'
        elif e.has_tag('highway'):
            e.space_type = 'road'


def get_traffic_areas_as_polygons(elements: List[OsmElement],
                                  highway_default_widths: dict[str, Tuple[float, float]] = None,
                                  cycleway_default_widths: dict[dict[str: float]] = None,
                                  tram_gauge: float = 1.435, tram_additional_carriageway_width: float = 0.5,
                                  train_gauge: float = 1.435, train_additional_carriageway_width: float = 1.5,
                                  ) -> List[GeometryElement]:

    def polygonize_highways(elements: List[OsmElement], highway_default_widths: dict[str, Tuple[float, float]], cycleway_default_widths: dict[dict[str: float]]) -> List[OsmElement]:
        """iterates over list of OsmElements and buffers highways if LineString and thus transforms them to Polygons based on given or estimated width and returns them in a list

        Args:
            elements (List[OsmElement]): list of OsmElements to iterate over and set geom_buffered attribute

        Returns:
            List[OsmElement]: list of only highways as OsmElements with geom_buffered attribute
        """
        def set_road_width(element: OsmElement,
                           highway_default_widths: dict[str, Tuple[float, float]] = {
                               'service': (4.5, 3),
                               'residential': (4.5, 3),
                               'tertiary': (4.5, 3),
                               'primary': (5.5, 3),
                               'cycleway': (2, 1.5),
                               'secondary': (4.5, 3),
                               'motorway_link': (6.5, 3),
                               'platform': (2, 1.5),
                               'motorway': (6.5, 3),
                               'unclassified': (4.5, 3),
                               'primary_link': (5.5, 3),
                               'secondary_link': (5, 3),
                               'construction': (5, 3),
                               'everything else': (5, 3)
                            },
                           cycleway_default_widths: dict[dict[str: float]] = {'cycleway': {'lane': 1.5, 'opposite': 1, 'track': 1.5, 'opposite_lane': 1.5, 'opposite_track': 1.5},
                                                                              'cycleway:right': {'lane': 1.5, 'track': 1.5},
                                                                              'cycleway:both': {'lane': 2*1.5, 'track': 2*1.5},
                                                                              'cycleway:left': {'lane': 1.5, 'track': 1.5}
                                                                              }) -> None:
            """Sets road width of a highway element in width attribute, either taken from width tags or estimated based on default values and

            Args:
                element (OsmElement): the OsmElement to analyse
                highway_default_widths (dict[str, Tuple[float, float]]): dictionary with default highway widths of the roadway without parking, cycle lane etc. in a dictionary for each OSM highway type.
                                                                        Each dict element has a tuple consisting of the value for bi-directional and uni-directional highways.
                cycleway_default_widths (dict[dict[str: float]]): default cyleway widths with separate values given for different tags and their values in a nested dictionary.
            """

            def estimate_road_width(element: OsmElement, highway_default_widths: dict[str, Tuple[float, float]], cycleway_default_widths: dict[dict[str: float]]) -> float:
                """estimates road with of an OsmElement based on default values and tags and returns the width

                Args:
                    element (OsmElement): the OsmElement to analyse
                    highway_default_widths (dict[str, Tuple[float, float]]): dictionary with default highway widths of the roadway without parking, cycle lane etc. in a dictionary for each OSM highway type.
                                                                            Each dict element has a tuple consisting of the value for bi-directional and uni-directional highways.
                    cycleway_default_widths (dict[dict[str: float]]): default cyleway widths with separate values given for different tags and their values in a nested dictionary

                Returns:
                    float: estimated width
                """

                def set_base_highway_width(element: OsmElement, direction: str, highway_default_widths: dict[str, Tuple[float, float]]) -> float:
                    i = 1 if direction == 'uni-directional' else 0 if direction == 'bi-directional' else None
                    if element.tags.get('highway') in highway_default_widths:
                        width = highway_default_widths[element.tags.get('highway')][i]
                    else:
                        width = highway_default_widths['everything else'][i]
                    return width

                def adapt_to_lanes(element: OsmElement, width: float, direction: str) -> float:
                    normal_lane_number = 1 if direction == 'uni-directional' else 2 if direction == 'bi-directional' else None
                    if element.has_tag('lanes') and float(element.tags.get('lanes')) != normal_lane_number:
                        width = width * float(element.tags.get('lanes')) / normal_lane_number
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
                                highway_types_for_default_streetside_parking: List[str] = ['residential', 'tertiary', 'living_street', 'secondary', 'primary'],
                                default_parking_width: float = 6.5) -> float:
                    """adds a default value to the given width if highway is of specific type

                    Args:
                        element (OsmElement): highway OsmElement
                        width (float): current width of the element
                        highway_types_for_default_streetside_parking (List[str], optional): highway tag values where parking is assumed.
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
                width = set_base_highway_width(e, direction, highway_default_widths)
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

        highways_polygons = []
        for e in [e for e in elements if e.space_type == 'road' and not e.access_derived_from == 'inaccessible enclosed area']:
            if e.is_linestring():
                set_road_width(e, highway_default_widths, cycleway_default_widths)
                cap_style = 'square' if e.is_building_passage() else 'flat'
                e.geom = e.geom.buffer(distance=round(e.width/2, 1), cap_style=cap_style)
                highways_polygons.append(e)
            elif e.is_polygon() or e.is_multipolygon():
                highways_polygons.append(e)
        return highways_polygons

    def polygonize_railways(elements: List[OsmElement], tram_gauge: float, tram_additional_carriageway_width: float, train_gauge: float, train_additional_carriageway_width: float) -> List[OsmElement]:
        """iterates over list of OsmElements and buffers railways and thus transforms the LineStrings to Polygons based on tram and train gauge and buffer size

        Args:
            elements (List[OsmElement]): list of OsmElements to iterate over and set geom_buffered attribute if applicable
            tram_gauge (float): tram gauge. Defaults to 1.435
            tram_additional_carriageway_width (float): tram buffer size of what should be added to the tram gauge for total tram rail width
            train_gauge (float): train gauge. Defaults to 1.435
            train_additional_carriageway_width (float): train buffer size of what should be added to the train gauge for total train rail width

        Returns:
            List[OsmElement]: list of only railways as OsmElements with geom_buffered attribute
        """
        rails_polygons = []
        for e in [e for e in elements if e.space_type == 'rail' and not e.access_derived_from == 'inaccessible enclosed area']:
            if e.tags.get('railway') == 'tram':
                e.width = tram_gauge + tram_additional_carriageway_width
            elif e.tags.get('railway') == 'rail':  # ignore subway because assume it's underground
                e.width = train_gauge + train_additional_carriageway_width
            if e.is_linestring():
                e.geom = e.geom.buffer(distance=round(e.width/2, 1), cap_style='flat')
                rails_polygons.append(e)
            elif e.is_multipolygon() or e.is_polygon():
                rails_polygons.append(e)
        return rails_polygons

    road_and_rail = (polygonize_highways(elements, highway_default_widths, cycleway_default_widths) +
                     polygonize_railways(elements, tram_gauge, tram_additional_carriageway_width, train_gauge, train_additional_carriageway_width))
    return road_and_rail


def get_pedestrian_ways_as_polygons(elements: List[OsmElement], pedestrian_way_default_width: float = 1.6) -> List[OsmElement]:
    """buffers LineString pedestrian ways and returns them together with pedestrian way polygons

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over and get process pedestrian ways
        pedestrian_way_default_width (float, optional): assumed default width of pedestrian ways as base for buffer. Defaults to 1.6.

    Returns:
        List[OsmElement]: list of pedestrian ways as OsmElements with geom_buffered attribute if the original LineString geometry was buffered
    """
    for e in elements:
        if e.space_type == 'walking area' and e.is_linestring():
            cap_style = 'square' if e.is_building_passage() else 'flat'  # differentiate for cleaner visualization
            e.geom = e.geom.buffer(distance=pedestrian_way_default_width/2, cap_style=cap_style)
    pedestrian_linestrings = [e for e in elements if e.space_type == 'walking area' and e.is_linestring()]
    pedestrian_polygons = [e for e in elements if e.space_type == 'walking area' and (e.is_multipolygon() or e.is_polygon())]
    """for p in pedestrian_polygons + pedestrian_linestrings:
        p.access = 'yes'  # if not set beforehand
        p.access_derived_from = 'space type'"""
    return pedestrian_linestrings + pedestrian_polygons


def clean_and_smooth_road_and_rail(road_and_rail: List[OsmElement],
                                   elements: List[OsmElement],
                                   pedestrian_ways: List[OsmElement],
                                   inaccessible_enclosed_areas: List[GeometryElement],
                                   buildings: List[OsmElement],
                                   pedestrian_way_default_width: float = 1.6) -> GeometryElement:
    """merges road and rail geometries, crops it if it intersects with one of the other given elements and smooths the resulting geometry

    Args:
        road_and_rail (List[OsmElement]): list of road and rail OsmElements with geom_buffered attribute or Polygon / MultiPolygon geom attribute
        elements (List[OsmElement]): list of OsmElements to get specific cropper geometries from
        pedestrian_ways (List[OsmElement]): pedestrian ways with geom_buffered attribute or Polygon / MultiPolygon geom attribute to clip
        inaccessible_enclosed_areas (List[GeometryElement]): inaccessible enclosed areas to clip
        buildings (List[OsmElement]): buildings to clip
        pedestrian_way_default_width (float, optional): assumed default width of pedestrian ways as base for buffering buildings. Defaults to 1.6.

    Returns:
        GeometryElement: cleaned and smoothed road and rail area

    Notes:
        buildings are buffered because it is assumed that every building is surrounded by a pedestrian way
    """

    def get_cropper_geometries(elements: List[OsmElement] = elements,
                               pedestrian_ways: List[OsmElement] = pedestrian_ways,
                               inaccessible_enclosed_areas: List[GeometryElement] = inaccessible_enclosed_areas,
                               buildings: List[OsmElement] = buildings,
                               pedestrian_way_default_width: float = pedestrian_way_default_width) -> Tuple[List[GeometryElement], List[GeometryElement]]:

        """combines and returns all geometries that should be used to crop the traffic areas in case they were assumed to wide

        Args:
            elements (List[OsmElement): list of OsmElements with platform elements
            pedestrian_ways (List[OsmElement]): pedestrian ways with geom_buffered attribute or Polygon / MultiPolygon geom attribute
            inaccessible_enclosed_areas (List[GeometryElement]): list of earlier defined inaccessible_enclosed_areas, because traffic areas will not be accessible there
            buildings (List[OsmElement): buildings
            pedestrian_way_default_width (float): assumed default width of pedestrian ways as base for buffering buildings

        Returns:
            Tuple[List[GeometryElement], List[GeometryElement]]: list of cropper geomtries, list of polygonized pedestrian ways
        """
        buildings_buffered = buffer_list_of_elements(buildings, buffer_size=pedestrian_way_default_width, join_style='mitre')
        platform_polygons = [e for e in elements if e.space_type == 'public transport stop' and (e.is_polygon() or e.is_multipolygon())]
        cropper_geometries = pedestrian_ways + buildings_buffered + platform_polygons + inaccessible_enclosed_areas
        return cropper_geometries

    def smooth_road_and_rail(road_and_rail_cropped: GeometryElement) -> GeometryElement:
        first_buffer_size = pedestrian_way_default_width/2+0.1  # buffer with half width of buffered pedestrian way plus a little more to close crossings that were cut out during cropping
        smooth_road_and_rail = copy.deepcopy(road_and_rail_cropped)
        smooth_road_and_rail.geom = smooth_road_and_rail.geom.buffer(first_buffer_size, join_style='mitre').buffer(-first_buffer_size, join_style='mitre').buffer(0.3, join_style='round').buffer(-0.3, join_style='round')
        return smooth_road_and_rail

    cropper_geometries = get_cropper_geometries()
    cropper_geometries_union_smooth = shapely.ops.unary_union([e.geom for e in cropper_geometries]).buffer(0.3).buffer(-0.3)
    road_and_rail_union = shapely.ops.unary_union([e.geom for e in road_and_rail])
    road_and_rail_cropped = GeometryElement(geometry=road_and_rail_union.difference(cropper_geometries_union_smooth),
                                            space_type='traffic area',
                                            access='no',
                                            access_derived_from='space type'
                                            )
    return smooth_road_and_rail(road_and_rail_cropped)
