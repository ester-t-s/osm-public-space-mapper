import copy
import shapely
from typing import List, Tuple

from osm_public_space_mapper.utils.helpers import buffer_list_of_elements
from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.geometry_element import GeometryElement


def set_traffic_space_type(elements: List[OsmElement]) -> None:
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
            e.access_derived_from = ('space category')
        elif e.is_rail():
            e.space_type = 'rail'
            e.access = ('no', 'overwrite_yes')
            e.access_derived_from = ('space category')
        elif e.has_tag('highway'):
            e.space_type = 'road'


def get_roads_as_polygons(elements: List[OsmElement],
                          highway_default_widths: dict[str, Tuple[float, float]] = {
                              'service': (4.5, 3),
                              'residential': (4.5, 3),
                              'tertiary': (5, 3.8),
                              'primary': (6, 3.8),
                              'cycleway': (2, 1),
                              'secondary': (6.5, 4),
                              'motorway_link': (6.5, 4),
                              'platform': (1, 1),
                              'motorway': (6.5, 3.8),
                              'unclassified': (5, 3),
                              'primary_link': (6.5, 3.8),
                              'secondary_link': (6.5, 3.8),
                              'construction': (5, 3),
                              'everything else': (5, 3)
                          },
                          cycleway_default_widths: dict[str, dict[str, float]] = {
                              'cycleway': {
                                  'lane': 1.5,
                                  'opposite': 0.5,
                                  'track': 1.5,
                                  'opposite_lane': 1,
                                  'opposite_track': 1.5
                              },
                              'cycleway:right': {
                                  'lane': 1.5,
                                  'track': 1.5
                              },
                              'cycleway:both': {
                                  'lane': 2*1.5,
                                  'track': 2*1.5
                              },
                              'cycleway:left': {
                                  'lane': 1.5,
                                  'track': 1.5
                              }
                          },
                          highway_types_for_default_streetside_parking: List[str] = [
                              'residential',
                              'tertiary',
                              'secondary',
                              'primary'
                              ],
                          default_parking_width: float = 6.5
                          ) -> List[OsmElement]:

    """iterates over list of OsmElements and buffers highways if LineString and thus transforms them to Polygons based on given or estimated width and returns them in a list

    Args:
        elements (List[OsmElement]): list of road OsmElements to iterate over and buffer
        highway_default_widths (dict[str, Tuple[float, float]]): dictionary with default highway widths of the roadway without parking, cycle lane etc. in a dictionary for each OSM highway type.
                                                                Each dict element has a tuple consisting of the value for bi-directional and uni-directional highways.
        cycleway_default_widths (dict[dict[str: float]]): default cyleway widths with separate values given for different tags and their values in a nested dictionary.
        highway_types_for_default_streetside_parking (List[str], optional): highway tag values where parking is assumed.
                                                                            Defaults to ['residential', 'tertiary', 'secondary', 'primary'].
        default_parking_width (float, optional): _description_. Defaults to 6.5, assuming one side horizontal (2m) and one side angle parking (4.5m),
                                                taken from OSM Verkehrswende project https://parkraum.osm-verkehrswende.org/project-prototype-neukoelln/report/#27-fl%C3%A4chenverbrauch


    Returns:
        List[OsmElement]: list of road OsmElements with buffered geometries
    """
    def set_road_width(element: OsmElement) -> None:
        """Sets road width of a highway element in width attribute, either taken from width tags or estimated based on default values and

        Args:
            element (OsmElement): the OsmElement to analyse
        """

        def estimate_road_width(element: OsmElement) -> float:
            """estimates road with of an OsmElement based on default values and tags and returns the width

            Args:
                element (OsmElement): the OsmElement to analyse

            Returns:
                float: estimated width
            """

            def set_base_highway_width(element: OsmElement,
                                       direction: str) -> float:
                i = 1 if direction == 'uni-directional' else 0 if direction == 'bi-directional' else None
                if element.tags.get('highway') in highway_default_widths:
                    width = highway_default_widths[element.tags.get('highway')][i]
                else:
                    width = highway_default_widths['everything else'][i]
                return width

            def adapt_to_lanes(element: OsmElement,
                               width: float,
                               direction: str) -> float:
                normal_lane_number = 1 if direction == 'uni-directional' else 2 if direction == 'bi-directional' else None
                if element.has_tag('lanes') and float(element.tags.get('lanes')) != normal_lane_number:
                    width = width * float(element.tags.get('lanes')) / normal_lane_number
                return width

            def add_cycleway(element: OsmElement,
                             width: float) -> float:
                if element.tags.get('highway') not in cycleway_default_widths:  # if it's not a cycleway by itself
                    for tag in cycleway_default_widths:
                        if element.has_tag(tag):
                            if element.tags.get(tag) in cycleway_default_widths[tag]:
                                width += cycleway_default_widths[tag][element.tags.get(tag)]
                return width

            def add_parking(element: OsmElement,
                            width: float) -> float:
                if element.tags.get('highway') in highway_types_for_default_streetside_parking:
                    width += default_parking_width
                return width

            def add_shoulder(element: OsmElement, width: float) -> float:
                """Note:
                function not defined because shoulder is insignificant in the Vienna OSM database. However, other similar projects take shoulder into account.
                """
                return width

            direction = 'uni-directional' if element.has_tag('oneway') else 'bi-directional'
            width = set_base_highway_width(element, direction)
            width = adapt_to_lanes(element, width, direction)
            width = add_cycleway(element, width)
            width = add_parking(element, width)
            return width

        if element.has_tag('width:carriageway'):
            element.width = float(e.tags.get('width:carriageway'))
        elif element.has_tag('width'):
            element.width = float(e.tags.get('width'))
        else:
            element.width = estimate_road_width(element)

    highways_polygons = []
    for e in [e for e in elements if e.space_type == 'road']:
        if e.is_linestring():
            set_road_width(e)
            e.geom = e.geom.buffer(distance=round(e.width/2, 1), cap_style='square')
            highways_polygons.append(e)
        elif e.is_polygon() or e.is_multipolygon():
            highways_polygons.append(e)
    return highways_polygons


def get_rail_as_polygons_and_smooth(elements: List[OsmElement],
                                    tram_gauge: float = 1.435,
                                    tram_additional_carriageway_width: float = 1,
                                    train_gauge: float = 1.435,
                                    train_additional_carriageway_width: float = 1.5) -> GeometryElement:
    """iterates over list of OsmElements and buffers railways and thus transforms the LineStrings to Polygons based on tram and train gauge and buffer size

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over and buffer if railway LineString
        tram_gauge (float): tram gauge. Defaults to 1.435
        tram_additional_carriageway_width (float): tram buffer size of what should be added to the tram gauge for total tram rail width
        train_gauge (float): train gauge. Defaults to 1.435
        train_additional_carriageway_width (float): train buffer size of what should be added to the train gauge for total train rail width

    Returns:
        List[OsmElement]: list of only railways as OsmElements with buffered geometries
    """

    def smooth_rail(rail_polygons: List[OsmElement]) -> GeometryElement:
        rail_union = shapely.ops.unary_union([e.geom for e in rail_polygons])
        rail_smoothed = GeometryElement(geometry=rail_union.buffer(1, join_style='mitre').buffer(-1, join_style='mitre'),
                                        space_type='rail',
                                        access='no',
                                        access_derived_from='space_type'
                                        )
        return rail_smoothed

    rails_polygons = []
    for e in [e for e in elements if e.space_type == 'rail']:
        if e.tags.get('railway') == 'tram':
            e.width = tram_gauge + tram_additional_carriageway_width
        elif e.tags.get('railway') == 'rail':  # ignore subway because assume it's underground
            e.width = train_gauge + train_additional_carriageway_width
        if e.is_linestring():
            e.geom = e.geom.buffer(distance=round(e.width/2, 1), cap_style='flat')
            rails_polygons.append(e)
        elif e.is_multipolygon() or e.is_polygon():
            rails_polygons.append(e)
    return smooth_rail(rails_polygons)


def get_pedestrian_ways_as_polygons(elements: List[OsmElement], pedestrian_way_default_width: float = 2) -> List[OsmElement]:
    """buffers LineString pedestrian ways and returns them together with pedestrian way polygons

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over and get process pedestrian ways
        pedestrian_way_default_width (float, optional): assumed default width of pedestrian ways as base for buffer. Defaults to 1.6.

    Returns:
        List[OsmElement]: list of pedestrian ways as OsmElements with Polygon geometries
    """
    for e in elements:
        if e.space_type == 'walking area' and e.is_linestring():
            if e.tags.get('highway') == 'living_street':
                e.geom = e.geom.buffer(distance=pedestrian_way_default_width, cap_style='square')  # living streets count as walking area but are significantly wider than sidewalks / paths
            else:
                e.geom = e.geom.buffer(distance=pedestrian_way_default_width/2, cap_style='square')
    pedestrian_linestrings = [e for e in elements if e.space_type == 'walking area' and e.is_linestring()]
    pedestrian_polygons = [e for e in elements if e.space_type == 'walking area' and (e.is_multipolygon() or e.is_polygon())]
    return pedestrian_linestrings + pedestrian_polygons


def clean_and_smooth_roads(road_polygons: List[OsmElement],
                           elements: List[OsmElement],
                           pedestrian_ways: List[OsmElement],
                           buildings: List[OsmElement],
                           pedestrian_way_default_width: float = 1.6) -> GeometryElement:
    """merges road and rail geometries, crops it if it intersects with one of the other given elements and smooths the resulting geometry

    Args:
        road_polygons (List[OsmElement]): list of road OsmElements with Polygon / MultiPolygon geometries
        elements (List[OsmElement]): list of OsmElements to get specific cropper geometries from to clip
        pedestrian_ways (List[OsmElement]): pedestrian ways with Polygon / MultiPolygon geometries to clip
        buildings (List[OsmElement]): buildings to clip
        pedestrian_way_default_width (float, optional): assumed default width of pedestrian ways as base for buffering buildings. Defaults to 1.6.

    Returns:
        GeometryElement: cleaned and smoothed road polygons

    Notes:
        buildings are buffered because it is assumed that every building is surrounded by a pedestrian way
    """

    def get_cropper_geometries(elements: List[OsmElement] = elements,
                               pedestrian_ways: List[OsmElement] = pedestrian_ways,
                               buildings: List[OsmElement] = buildings,
                               pedestrian_way_default_width: float = pedestrian_way_default_width) -> Tuple[List[GeometryElement], List[GeometryElement]]:

        """combines and returns all geometries that should be used to crop the traffic areas in case they were assumed to wide

        Args:
            elements (List[OsmElement): list of OsmElements with platform elements
            pedestrian_ways (List[OsmElement]): pedestrian ways with Polygon / MultiPolygon geometry
            buildings (List[OsmElement): buildings
            pedestrian_way_default_width (float): assumed default width of pedestrian ways as base for buffering buildings

        Returns:
            Tuple[List[GeometryElement], List[GeometryElement]]: list of cropper geomtries, list of polygonized pedestrian ways
        """
        buildings_buffered = buffer_list_of_elements(buildings, buffer_size=pedestrian_way_default_width, join_style='mitre')
        platform_polygons = [e for e in elements if e.space_type == 'public transport stop' and (e.is_polygon() or e.is_multipolygon())]
        cropper_geometries = pedestrian_ways + buildings_buffered + platform_polygons
        return cropper_geometries

    def smooth_road(road_polygons_cropped: GeometryElement) -> GeometryElement:
        first_buffer_size = pedestrian_way_default_width/2+0.2  # buffer with half width of buffered pedestrian way plus a little more to close crossings that were cut out during cropping
        road_smoothed = copy.deepcopy(road_polygons_cropped)
        road_smoothed.geom = road_smoothed.geom.buffer(first_buffer_size, join_style='mitre').buffer(-first_buffer_size, join_style='mitre').buffer(0.3, join_style='round').buffer(-0.3, join_style='round')
        return road_smoothed

    cropper_geometries = get_cropper_geometries()
    cropper_geometries_union_smooth = shapely.ops.unary_union([e.geom for e in cropper_geometries]).buffer(0.3).buffer(-0.3)
    road_polygons_union = shapely.ops.unary_union([e.geom for e in road_polygons])
    road_polygons_cropped = GeometryElement(geometry=road_polygons_union.difference(cropper_geometries_union_smooth),
                                            space_type='road',
                                            access='no',
                                            access_derived_from='space type'
                                            )
    return smooth_road(road_polygons_cropped)
