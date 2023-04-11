import shapely
from shapely.geometry import Polygon, MultiPolygon
from osm_public_space_mapper.utils.helpers import buffer_list_of_elements
from osm_public_space_mapper.utils.osm_element import OsmElement


def interprete_tags(elements: list[OsmElement]) -> None:
    """Iterates over list of OsmElements and updates access attribute to yes, no or restricted based on used tags

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over
    """
    access_tag_values_yes = ['yes', 'public', 'permissive', 'bus', 'destination']
    access_tag_values_no = ['private', 'no', 'permit', 'children', 'customers', 'key', 'military', 'permit']
    restricted_access_tags = ['fee', 'opening_hours', 'max_age', 'min_age', 'female', 'male', 'charge', 'seasonal']

    for e in elements:
        if any([e.has_tag('access'), e.has_tag('foot'), e.has_tag('parking_space')]):
            if e.tags.get('access') in access_tag_values_no or e.tags.get('foot') in access_tag_values_no or e.tags.get('parking_space') in access_tag_values_no:
                e.access = 'no'
                e.access_derived_from = 'tags'
            elif e.tags.get('access') in access_tag_values_yes or e.tags.get('foot') in access_tag_values_yes:
                for tag in restricted_access_tags:
                    if e.has_tag(tag):
                        if e.tags.get(tag) != 'no':
                            if e.tags.get('opening_hours') != '24/7':
                                e.access = 'restricted'
                                e.access_derived_from = 'tags'
                if e.access is None:
                    e.access = 'yes'
                    e.access_derived_from = 'tags'
        else:
            for tag in restricted_access_tags:
                if e.has_tag(tag):
                    if e.tags.get(tag) != 'no':
                        if e.tags.get('opening_hours') != '24/7':
                            e.access = 'restricted'
                            e.access_derived_from = 'tags'


def interprete_barriers(elements: list[OsmElement]) -> None:
    """iterates over list of OsmElements and sets access attribute for barriers

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over
    """

    def set_access_attribute_on_barriers(elements: list[OsmElement]) -> None:

        def set_access_attribute_on_barrier(barrier: OsmElement, intersecting_entrances: list[OsmElement]) -> None:
            """sets the access attribute of a barrier based on its intersections with entrances

            Args:
                barrier (OsmElement): barrier that is analysed
                intersecting_entrances (list[OsmElement]): list of entrances that intersect with the barrier

            Notes:
                the access attribute can not be overwritten, so if it was set earlier and with a more reliable source, e.g. based on an access tag, this step will not influence the value of the access attribute
            """

            def set_barrier_access_attribute_with_single_entrance(barrier: OsmElement, intersecting_entrance: OsmElement) -> None:
                """sets the access attribute of a barrier based on a single intersecting entrance

                Args:
                    barrier (OsmElement): barrier that is analysed
                    intersecting_entrance (OsmElement): entrance that intersect with the barrier
                """
                if intersecting_entrance.access is None:
                    barrier.access = 'yes'
                else:
                    barrier.access = intersecting_entrance.access

            def set_barrier_access_attribute_with_multiple_entrances(barrier: OsmElement, intersecting_entrances: list[OsmElement]) -> None:
                """sets the access attribute of a barrier based on multiple intersecting entrances

                Args:
                    barrier (OsmElement): barrier that is analysed
                    intersecting_entrances (list[OsmElement]): list of entrances that intersect with the barrier
                """

                def clean_intersecting_entrances(intersecting_entrances: list[OsmElement]) -> list[OsmElement]:
                    """ identifies and drops intersecting entrances that intersect with another intersecting entrance with access = no

                    Args:
                        intersecting_entrances (list[OsmElement]): entrance elements that intersect with the barrier and should be checked

                    Returns:
                        list[int]: filtered list of intersecting entrances with access

                    Notes:
                        e.g. a path might not be tagged with access = private and thus might be interpreted as giving access to a fenced area, but path and fence cross gate with access = private tag
                    """
                    def get_intersection_ids_to_drop(intersecting_entrances: list[OsmElement]) -> set[int]:
                        osmids_to_drop = set()
                        for idx, i1 in enumerate(list(intersecting_entrances)):
                            if i1 != intersecting_entrances[-1]:
                                for i2 in intersecting_entrances[idx+1:]:
                                    if i1.geom.intersects(i2.geom):
                                        if i1.access == 'no' or i2.access == 'no':
                                            osmids_to_drop.add(i1.id)
                                            osmids_to_drop.add(i2.id)
                        return osmids_to_drop

                    def drop_inaccessible_intersecting_entrances(intersecting_entrances: list[OsmElement], osmids_to_drop: set[int]) -> list[OsmElement]:
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

    set_access_attribute_on_barriers(elements)


def get_inaccessible_barriers(elements: list[OsmElement]) -> list[OsmElement]:
    """returns the elements in list of OsmElements that have access = no and is_barrier() = True

    Args:
        elements (list[OsmElement]): list of OsmElements

    Returns:
        list[OsmElement]: filtered list
    """
    return [e for e in elements if e.access == 'no' and e.is_barrier()]


def get_inaccessible_enclosed_areas(inaccessible_barriers: list[OsmElement], buildings: list[OsmElement]) -> list[Polygon | MultiPolygon]:
    """returns the polygons / multipolygons that are enclosed by inaccessible barriers and buildings

    Args:
        inaccessible_barriers (list[OsmElement]): list of inaccessible barriers as OsmElements
        buildings (list[OsmElement]): list of buildings as OsmElements

    Returns:
        list[Polygon|MultiPolygon]: list of shapely Polygons or MultiPolygons that are enclosed by inaccessible barriers and buildings
    """

    buffer_size = 0.001
    barriers_buffered = buffer_list_of_elements(inaccessible_barriers, buffer_size, cap_style='square')
    buildings_buffered = buffer_list_of_elements(buildings, buffer_size, cap_style='square')
    barriers_buildings_union = shapely.ops.unary_union([e.geom for e in (barriers_buffered + buildings_buffered)])
    inaccessible_enclosed_areas = list()
    for polygon in barriers_buildings_union.geoms:
        if len(polygon.interiors) > 0:
            for i in range(len(polygon.interiors)):
                inaccessible_enclosed_areas.append(Polygon(polygon.interiors[i]).buffer(buffer_size, cap_style='square'))
    # Because of the buffering, this function leads to some weird, thin shapes. A cleaner way of processing should be implemented
    return inaccessible_enclosed_areas


def set_access_of_osm_elements_in_inaccessible_enclosed_areas(elements: list[OsmElement], enclosed_areas: list[Polygon | MultiPolygon]) -> None:
    """iterates over list of inaccessible enclosed areas and list of OsmElements and sets access = no on OsmElements intersecting with inaccessible enclosed area

    Args:
        elements (list[OsmElement]): list of OsmElements
        enclosed_areas (list[Polygon | MultiPolygon]): list of geometries of inaccessible enclosed areas
    """

    for enclosed_area in enclosed_areas:
        enclosed_area_prep = shapely.prepared.prep(enclosed_area.buffer(-0.2))
        for e in elements:
            if enclosed_area_prep.intersects(e.geom):
                e.access = 'no'
                e.access_derived_from = 'inaccessible enclosed area'


def drop_linestring_barriers(elements: list[OsmElement]) -> list[OsmElement]:
    for e in elements:
        if e.has_tag('barrier') and e.is_linestring():
            e.ignore = True
    return [e for e in elements if not e.ignore]


def assume_access_based_on_space_type(elements: list[OsmElement]) -> None:
    """sets the access of OsmElements based on a give space_type if access is not set yet and space_type is given.
        also sets access to no for all elements with space_type parking, even if it is set differently already

    Args:
        elements (list[OsmElement]): list of OsmElements
    """
    space_types_with_access = ['public transport stop', 'park', 'playground', 'dog_park', 'place', 'fitness_station',
                               'square', 'track', 'brownfield', 'bus_station', 'forest', 'sand', 'garden', 'heath',
                               'greenhouse_horticulture', 'meadow', 'nature_reserve', 'recreation_ground', 'scree',
                               'scrub', 'village_green', 'wood', 'cemetery', 'grass', 'pitch', 'beach', 'bridge',
                               'common',  'island', 'marina', 'pier', 'water_park', 'religious', 'shelter', 'grassland',
                               'greenfield'
                               ]
    space_types_with_restricted_access = ['outdoor_seating', 'sports_centre', 'swimming_pool', 'biergarten',
                                          'miniature_golf', 'stadium', 'horse_riding'
                                          ]  # because usually linked to comsumption / fees / hours which might not be recorded in OSM
    space_types_without_access = ['allotments', 'construction', 'landfill', 'military', 'railway', 'flowerbed', 'fountain',
                                  'water', 'wetland', 'parking', 'storage', 'farmland', 'orchard', 'plant_nursery',
                                  'vineyard', 'harbour', 'resort', 'garages', 'stage', 'reservoir'
                                  ]
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
