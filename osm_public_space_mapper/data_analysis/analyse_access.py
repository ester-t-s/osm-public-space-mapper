import shapely
import copy
from typing import List, Set, Tuple
from shapely.geometry import Polygon, MultiPolygon
from osm_public_space_mapper.utils.helpers import buffer_list_of_elements
from osm_public_space_mapper.utils.osm_element import OsmElement
from osm_public_space_mapper.utils.geometry_element import GeometryElement


def interpret_tags(elements: List[OsmElement]) -> None:
    """Iterates over list of OsmElements and updates access attribute to yes, no or restricted based on used tags

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over
    """
    access_tag_values_yes = ['yes', 'public', 'permissive']
    access_tag_values_no = ['private', 'no', 'permit', 'key', 'military', 'residents']
    access_tag_values_restricted = ['children', 'customers']
    restricted_access_tags = ['fee', 'opening_hours', 'max_age', 'min_age', 'female', 'male', 'charge', 'seasonal']

    for e in elements:
        if any([e.has_tag('access'), e.has_tag('foot')]):
            if e.tags.get('access') in access_tag_values_no or e.tags.get('foot') in access_tag_values_no:
                e.access = 'no'
                e.access_derived_from = 'tags'
            elif e.tags.get('access') in access_tag_values_yes or e.tags.get('foot') in access_tag_values_yes:
                for tag in restricted_access_tags:
                    if e.has_tag(tag) and e.tags.get(tag) != 'no':
                        if (tag == 'opening_hours' and e.tags.get(tag) != '24/7') or tag != 'opening_hours':
                            e.access = 'restricted'
                            e.access_derived_from = 'tags'
                if e.access is None:  # if no restricted access tag was found but access / foot tag value is in tag_values_yes list
                    e.access = 'yes'
                    e.access_derived_from = 'tags'
            elif e.tags.get('access') in access_tag_values_restricted or e.tags.get('foot') in access_tag_values_restricted:
                e.access = 'restricted'
                e.access_derived_from = 'tags'
            else:
                for tag in restricted_access_tags:
                    if e.has_tag(tag) and e.tags.get(tag) != 'no':
                        if (tag == 'opening_hours' and e.tags.get(tag) != '24/7') or tag != 'opening_hours':
                            e.access = 'restricted'
                            e.access_derived_from = 'tags'
        else:
            for tag in restricted_access_tags:
                if e.has_tag(tag) and e.tags.get(tag) != 'no':
                    if (tag == 'opening_hours' and e.tags.get(tag) != '24/7') or tag != 'opening_hours':
                        e.access = 'restricted'
                        e.access_derived_from = 'tags'


def interpret_barriers(elements: List[OsmElement]) -> None:
    """iterates over list of OsmElements and sets access attribute for barriers

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over
    """
    def set_access_attribute_on_barrier(barrier: OsmElement, intersecting_entrances: List[OsmElement]) -> None:
        """sets the access attribute of a barrier based on its intersections with entrances

        Args:
            barrier (OsmElement): barrier that is analysed
            intersecting_entrances (List[OsmElement]): list of entrances that intersect with the barrier

        Notes:
            the access attribute can not be overwritten, so if it was set earlier and with a more reliable source, e.g. based on an access tag, this step will not influence the value of the access attribute
        """

        def set_access_attribute_of_entrances(intersecting_entrances: List[OsmElement]) -> None:
            """sets access attribute of the intersecting entrances if it was not set beforehand

            Args:
                intersecting_entrances (List[OsmElement]): list of intersecting entrances

            Notes:
                For gates, default access 'no' is assumed, if no tag indicates something else (which was analysed earlier), because gate counts as a barrier
                For all other entrances (highways and crossings), default access 'yes' is assumed
            """
            for entrance in intersecting_entrances:
                if entrance.tags.get('barrier') == 'gate':
                    entrance.access = 'no'
                else:
                    entrance.access = 'yes'

        def set_barrier_access_attribute_with_single_entrance(barrier: OsmElement, intersecting_entrance: OsmElement) -> None:
            """sets the access attribute of a barrier based on a single intersecting entrance

            Args:
                barrier (OsmElement): barrier that is analysed
                intersecting_entrance (OsmElement): entrance that intersect with the barrier
            """
            barrier.access = intersecting_entrance.access

        def set_barrier_access_attribute_with_multiple_entrances(barrier: OsmElement, intersecting_entrances: List[OsmElement]) -> None:
            """sets the access attribute of a barrier based on multiple intersecting entrances

            Args:
                barrier (OsmElement): barrier that is analysed
                intersecting_entrances (List[OsmElement]): list of entrances that intersect with the barrier
            """

            def clean_intersecting_entrances(intersecting_entrances: List[OsmElement]) -> List[OsmElement]:
                """ identifies and drops intersecting entrances that intersect with another intersecting entrance with access = no

                Args:
                    intersecting_entrances (List[OsmElement]): entrance elements that intersect with the barrier and should be checked

                Returns:
                    List[int]: filtered list of intersecting entrances with access

                Notes:
                    e.g. a path might not be tagged with access = private and thus might be interpreted as giving access to a fenced area, but path and fence cross gate with access = private tag
                """
                def get_intersection_ids_to_drop(intersecting_entrances: List[OsmElement]) -> Set[int]:
                    osmids_to_drop = set()
                    for idx, i1 in enumerate(list(intersecting_entrances)):
                        if i1 != intersecting_entrances[-1]:
                            for i2 in intersecting_entrances[idx+1:]:
                                if i1.geom.intersects(i2.geom):
                                    if i1.access == 'no' or i2.access == 'no':
                                        osmids_to_drop.add(i1.id)
                                        osmids_to_drop.add(i2.id)
                    return osmids_to_drop

                def drop_inaccessible_intersecting_entrances(intersecting_entrances: List[OsmElement], osmids_to_drop: Set[int]) -> List[OsmElement]:
                    return [i for i in intersecting_entrances if i.id not in osmids_to_drop]

                intersection_ids_to_drop = get_intersection_ids_to_drop(intersecting_entrances)
                intersecting_entrances_cleaned = drop_inaccessible_intersecting_entrances(intersecting_entrances, intersection_ids_to_drop)
                return intersecting_entrances_cleaned

            intersecting_entrances_cleaned = clean_intersecting_entrances(intersecting_entrances)
            has_access_point = False
            for i in intersecting_entrances_cleaned:
                if i.access == 'yes' or i.access is None:
                    has_access_point = True
                    break
                elif i.access == 'restricted':
                    has_access_point = 'restricted'
            if has_access_point is True:
                barrier.access = 'yes'
            elif has_access_point == 'restricted':
                barrier.access = 'restricted'
            else:
                barrier.access = 'no'

        set_access_attribute_of_entrances(intersecting_entrances)
        if len(intersecting_entrances) == 0:
            barrier.access = 'no'
        elif len(intersecting_entrances) == 1:
            set_barrier_access_attribute_with_single_entrance(barrier, intersecting_entrances[0])
        elif len(intersecting_entrances) > 1:
            set_barrier_access_attribute_with_multiple_entrances(barrier, intersecting_entrances)

    for barrier in [e for e in elements if e.is_barrier()]:
        barrier_geom_prep = shapely.prepared.prep(barrier.geom)
        intersecting_entrances = []
        for entrance in [e for e in elements if e.is_entrance()]:
            if barrier_geom_prep.intersects(entrance.geom):
                intersecting_entrances.append(entrance)
        set_access_attribute_on_barrier(barrier, intersecting_entrances)


def get_inaccessible_barriers(elements: List[OsmElement]) -> List[OsmElement]:
    """returns the elements in list of OsmElements that have access = no and is_barrier() = True

    Args:
        elements (List[OsmElement]): list of OsmElements

    Returns:
        List[OsmElement]: filtered list
    """
    return [e for e in elements if e.access == 'no' and e.is_barrier()]


def get_inaccessible_enclosed_areas(inaccessible_barriers: List[OsmElement], buildings: List[OsmElement]) -> List[GeometryElement]:
    """returns the polygons / multipolygons that are enclosed by inaccessible barriers and buildings

    Args:
        inaccessible_barriers (List[OsmElement]): list of inaccessible barriers as OsmElements
        buildings (List[OsmElement]): list of buildings as OsmElements

    Returns:
        List[GeometryElement]: list of GeometryElements that are enclosed by inaccessible barriers and buildings
    """
    buffer_size = 0.001
    barriers_buffered = buffer_list_of_elements(inaccessible_barriers, buffer_size, cap_style='square')
    barriers_buildings_union = shapely.ops.unary_union([e.geom for e in (barriers_buffered + buildings)])
    inaccessible_enclosed_areas = list()
    for polygon in barriers_buildings_union.geoms:
        if len(polygon.interiors) > 0:
            for i in range(len(polygon.interiors)):
                inaccessible_enclosed_areas.append(GeometryElement(geometry=Polygon(polygon.interiors[i]).buffer(buffer_size*2, cap_style='square'),  # doubled buffer size for improved visualization
                                                                   access='no',
                                                                   access_derived_from='inaccessible enclosed areas',
                                                                   space_type='undefined space'
                                                                   ))
    return inaccessible_enclosed_areas


def compare_and_crop_osm_elements_and_inaccessible_enclosed_areas_and_assign_access(elements: List[OsmElement],
                                                                                    road_and_rail: List[OsmElement],
                                                                                    pedestrian_ways: List[OsmElement],
                                                                                    enclosed_areas: List[GeometryElement]) -> Tuple[List[OsmElement], List[GeometryElement]]:

    def crop_road_rail_pedestrian_ways(road_and_rail: List[OsmElement], pedestrian_ways: List[OsmElement], enclosed_areas: List[GeometryElement]) -> Tuple[List[OsmElement], List[OsmElement]]:
        """crops the geometries of road and rail and pedestrian ways to the parts not intersecting with inaccessible enclosed areas

        Args:
            road_and_rail (List[OsmElement]): list of road and rail elements
            pedestrian_ways (List[OsmElement]): list of pedestrian way elements
            enclosed_areas (List[GeometryElement]): list of inaccessible enclosed areas

        Returns:
            Tuple[List[OsmElement], List[OsmElement]]: list of cropped road and rail and list of cropped pedestrian ways
        """
        road_and_rail_cropped, pedestrian_ways_cropped = [], []
        enclosed_areas_union = shapely.ops.unary_union([e.geom for e in enclosed_areas])
        for e in road_and_rail:
            e_cropped = copy.deepcopy(e)
            if e.geom.intersects(enclosed_areas_union):
                e_cropped.geom = e.geom.difference(enclosed_areas_union)
            road_and_rail_cropped.append(e_cropped)
        for e in pedestrian_ways:
            e_cropped = copy.deepcopy(e)
            if e.geom.intersects(enclosed_areas_union):
                e_cropped.geom = e.geom.difference(enclosed_areas_union)
            pedestrian_ways_cropped.append(e_cropped)
        return road_and_rail_cropped, pedestrian_ways_cropped

    def assign_access_for_elements_in_enclosed_areas(elements: List[OsmElement], enclosed_areas: List[GeometryElement]) -> None:
        """iterates over list of OsmElements and sets access = no if it is within enclosed areas

        Args:
            elements (List[OsmElement]): list of OsmElement
            enclosed_areas (List[GeometryElement]): list of enclosed areas
        """
        enclosed_areas_union = shapely.ops.unary_union([e.geom for e in enclosed_areas])
        for element in elements:
            if enclosed_areas_union.contains(element.geom):
                element.access = 'no'
                element.access_derived_from = 'inaccessible enclosed area'

    def drop_inaccessible_enclosed_areas_with_significant_overlap_and_assign_access_attribute(elements: List[OsmElement], enclosed_areas: List[GeometryElement]) -> List[GeometryElement]:
        """iterates over list of inaccessible enclosed areas and list of OsmElements and sets access = no on OsmElements with significant overlap with inaccessible enclosed area

        Args:
            elements (List[OsmElement]): list of OsmElements
            enclosed_areas (List[GeometryElement]): list of inaccessible enclosed areas

        Returns:
            List[GeometryElement]: list of inaccessible enclosed areas without the ones with significant overlap with an OsmElement
        """
        def significant_overlap(enclosed_area: GeometryElement, element: OsmElement) -> bool:
            overlap_threshold = 0.95
            if enclosed_area.geom.intersects(element.geom):
                intersection_area = enclosed_area.geom.intersection(element.geom).area
                if (intersection_area / enclosed_area.geom.area) >= overlap_threshold and (intersection_area / element.geom.area) >= overlap_threshold:
                    return True
            return False

        def drop_enclosed_areas_to_ignore(enclosed_areas: List[GeometryElement], enclosed_area_indices_to_ignore: List[int]) -> List[GeometryElement]:
            enclosed_areas_cleaned = []
            for idx, area in enumerate(enclosed_areas):
                if idx not in enclosed_area_indices_to_ignore:
                    enclosed_areas_cleaned.append(area)
            return enclosed_areas_cleaned

        enclosed_area_indices_to_ignore = []
        for idx, enclosed_area in enumerate(enclosed_areas):
            for element in [e for e in elements if e.is_polygon() or e.is_multipolygon()]:
                if significant_overlap(enclosed_area, element):
                    element.access = 'no'
                    element.access_derived_from = 'inaccessible enclosed area'
                    enclosed_area_indices_to_ignore.append(idx)

        enclosed_areas_cleaned = drop_enclosed_areas_to_ignore(enclosed_areas, enclosed_area_indices_to_ignore)
        return enclosed_areas_cleaned

    def split_osm_elements_with_intersection_with_inaccessible_enclosed_area(elements: List[OsmElement],
                                                                             enclosed_areas: List[GeometryElement]) -> List[OsmElement]:
        """iterates over list of OsmElements and splits them if they intersect with inaccessible enclosed area into the accessible and the inaccessible part

        Args:
            elements (List[OsmElement]): list of OsmElements to check and split
            enclosed_areas (List[GeometryElement]): list of inaccessible enclosed areas

        Returns:
            List[OsmElement]: list of split up OsmElements

        Notes:
            intersection geometry is only returned if it is a Polygon or a MultiPolygon and not a LineString, Point or GeometryCollection
            because they can not be processed later and they indicate a very small intersection that can be ignored
        """
        elements_split = []
        enclosed_areas_union = shapely.ops.unary_union([e.geom for e in enclosed_areas])
        for element in elements:
            element_intersects = False
            if element.is_polygon() or element.is_multipolygon():
                if element.geom.intersects(enclosed_areas_union):
                    if type(element.geom.intersection(enclosed_areas_union)) in [MultiPolygon, Polygon]:
                        element_intersection = copy.deepcopy(element)
                        element_intersection.geom = element.geom.intersection(enclosed_areas_union)
                        element_intersection.access = 'no'
                        element_intersection.access_derived_from = 'inaccessible enclosed area'
                        element_difference = copy.deepcopy(element)
                        element_difference.geom = element.geom.difference(enclosed_areas_union)
                        element_intersects = True
            if element_intersects:
                if not element_intersection.geom.is_empty:
                    elements_split.append(element_intersection)
                if not element_difference.geom.is_empty:
                    elements_split.append(element_difference)
            else:
                elements_split.append(element)
        return elements_split

    def crop_inaccessible_enclosed_areas_with_intersection_with_osm_element(elements: List[OsmElement],
                                                                            enclosed_areas: List[GeometryElement]) -> List[GeometryElement]:
        """iterates over list of inaccessible enclosed areas and returns the cropped geometry if it intersects with an OsmElement

        Args:
            elements (List[OsmElement]): list of OsmElements
            enclosed_areas (List[GeometryElement]): list of inaccessible enclosed areas

        Returns:
            List[GeometryElement]: list of cropped or original inaccessible enclosed areas

        Notes:
            only returns the cropped inaccessible enclosed area if it is not an empty geometry and is of significant size (2 square metre)
        """
        enclosed_areas_cropped = []
        elements_polygons_union = shapely.ops.unary_union([e.geom for e in elements if e.is_polygon() or e.is_multipolygon()])
        for area in enclosed_areas:
            area_intersects = False
            if area.geom.intersects(elements_polygons_union):
                area_cropped = copy.deepcopy(area)
                area_cropped.geom = area.geom.difference(elements_polygons_union)
                area_intersects = True
            if area_intersects:
                if not area_cropped.geom.is_empty and area_cropped.geom.area > 2:
                    enclosed_areas_cropped.append(area_cropped)
            else:
                enclosed_areas_cropped.append(area)
        return enclosed_areas_cropped

    road_and_rail_cropped, pedestrian_ways_cropped = crop_road_rail_pedestrian_ways(road_and_rail, pedestrian_ways, enclosed_areas)
    enclosed_areas_cleaned = drop_inaccessible_enclosed_areas_with_significant_overlap_and_assign_access_attribute(elements, enclosed_areas)
    elements_split = split_osm_elements_with_intersection_with_inaccessible_enclosed_area(elements, enclosed_areas_cleaned)
    enclosed_areas_cropped = crop_inaccessible_enclosed_areas_with_intersection_with_osm_element(elements, enclosed_areas_cleaned)

    return elements_split, road_and_rail_cropped, pedestrian_ways_cropped, enclosed_areas_cropped


def drop_linestring_barriers_and_entrance_points(elements: List[OsmElement]) -> List[OsmElement]:
    for e in elements:
        if e.has_tag('barrier') and e.is_linestring():
            e.ignore = True
        elif e.is_entrance() and e.is_point():
            e.ignore = True
    return [e for e in elements if not e.ignore]


def assume_access_based_on_space_type(elements: List[OsmElement]) -> None:
    """sets the access of OsmElements based on a give space_type if access is not set yet and space_type is given.
        also sets access to no for all elements with space_type parking, even if it is set differently already

    Args:
        elements (List[OsmElement]): list of OsmElements
    """
    space_types_with_access = ['public transport stop', 'park', 'playground', 'dog_park', 'fitness_station',
                               'square', 'track', 'brownfield', 'bus_station', 'forest', 'sand', 'garden', 'heath',
                               'recreation_ground', 'scree', 'greenfield', 'walking area', 'grassland',
                               'village_green', 'wood', 'cemetery', 'grass', 'pitch', 'beach', 'bridge',
                               'common',  'island', 'marina', 'pier', 'water_park', 'religious', 'shelter'
                               ]
    space_types_with_restricted_access = ['outdoor_seating', 'sports_centre', 'swimming_pool', 'biergarten',
                                          'miniature_golf', 'stadium', 'horse_riding'
                                          ]  # because usually linked to comsumption / fees / hours which might not be recorded in OSM
    space_types_without_access = ['allotments', 'construction', 'landfill', 'military', 'flowerbed', 'fountain',
                                  'water', 'wetland', 'parking', 'storage', 'farmland', 'orchard', 'plant_nursery', 'planter'
                                  'vineyard', 'harbour', 'resort', 'garages', 'stage', 'reservoir', 'scrub', 'shrubbery',
                                  'greenhouse_horticulture', 'meadow', 'nature_reserve'
                                  ]
    uncategorized_space_types = []
    for element in [e for e in elements if e.access is None and e.space_type is not None]:
        if element.space_type in space_types_with_access:
            element.access = 'yes'
            element.access_derived_from = 'space type'
        elif element.space_type in space_types_with_restricted_access:
            element.access = 'restricted'
            element.access_derived_from = 'space type'
        elif element.space_type in space_types_without_access:
            element.access = 'no'
            element.access_derived_from = 'space type'
        if not element.access:
            uncategorized_space_types.append(element.space_type)
            element.access = 'undefined'
    if len(uncategorized_space_types) > 0:
        print('No access categorized for', set(uncategorized_space_types), 'You should consider adding it to the function analyse_access.assume_access_based_on_space_type()')
