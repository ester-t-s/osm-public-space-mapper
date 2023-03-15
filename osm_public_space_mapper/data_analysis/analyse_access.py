import numpy as np

import shapely
from shapely.geometry import Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString

from osm_public_space_mapper.utils.helpers import buffer_list_of_elements
from osm_public_space_mapper.utils.osm_element import OsmElement


def interprete_tags(elements:list[OsmElement]) -> None:
    """Iterates over list of OsmElements and updates access attribute to yes, no or restricted based on used tags

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over
    """    
    access_tag_values_yes = ['yes', 'public', 'permissive', 'bus', 'destination']
    access_tag_values_no = ['private', 'no', 'permit', 'children', 'customers', 'key', 'military', 'permit']
    restricted_access_tags = ['fee', 'opening_hours', 'max_age', 'min_age', 'female', 'male','charge', 'seasonal']

    for e in elements:
        if any([e.has_tag('access'), e.has_tag('foot'), e.has_tag('parking_space')]):
            if e.tags.get('access') in access_tag_values_no or e.tags.get('foot') in access_tag_values_no or e.tags.get('parking_space') in access_tag_values_no:
                e.access = 'no'
            elif e.tags.get('access') in access_tag_values_yes or e.tags.get('foot') in access_tag_values_yes:
                for tag in restricted_access_tags:
                    if e.has_tag(tag):
                        if e.tags.get(tag) != 'no':
                            if e.tags.get('opening_hours') != '24/7':
                                e.access = 'restricted'
                if e.access == None:
                    e.access = 'yes'
        else:
            for tag in restricted_access_tags:
                if e.has_tag(tag):
                    if e.tags.get(tag) != 'no':
                        if e.tags.get('opening_hours') != '24/7':
                            e.access = 'restricted'

def interprete_barriers(elements:list[OsmElement]) -> None:
    """iterates over list of OsmElements and sets access attribute for barriers

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over
    """    

    def set_barrier_attribute(elements:list[OsmElement]) -> None:
        """Iterates over list of OsmElements and adds temporary attribute is_barrier with boolean value depending on tags.

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over

        Notes:
            Barriers, motorways and railways (not trams) are marked as barriers.
            For all apart from landuse == railway, only LineStrings are counted because they should be set up as LineStrings.
            If the element has a layer tag, it is not counted as barrier, because it is assumed that there is something below/above granting access through this barrier
        """        
        for e in elements:
            if e.has_tag('barrier') and e.is_linestring():
                e.is_barrier = True
            elif e.tags.get('highway')=='motorway' and e.tags.get('layer') is None and e.is_linestring():
                # based on assumption that there is something below / above that probably grants access if layer tag is given
                e.is_barrier = True
            elif e.tags.get('railway')=='rail' and e.tags.get('layer') is None and e.is_linestring() and e.tags.get('embedded')!='yes':
                e.is_barrier = True
            elif e.tags.get('landuse')=='railway' and e.is_polygon() or e.is_multipolygon():
                e.is_barrier = True
            else:
                e.is_barrier = False

    def set_entrance_attribute(elements:list[OsmElement]) -> None:
        """Iterates over list of OsmElements and adds temporary attribute is_entrance with boolean value depending on tags.

        Args:
            elements (list[OsmElement]): list of OsmElements to iterate over

        Notes:
            Elements that might grant access through a barrier count as entrances. 
            These are highways and other elements with a specific, predefined tag value like barrier=gate
        """        
        entrance_tags_values = {'railway':['railway_crossing'], 'crossing':'any value apart from no', 'highway':['crossing'], 'barrier':['gate']}
        for e in elements:
            is_entrance = False
            if e.has_tag('highway') and e.tags.get('highway')!='motorway' and e.is_linestring():
                is_entrance = True
            else:
                for tag in entrance_tags_values:
                    if e.tags.get(tag) is not None:
                        if entrance_tags_values[tag]=='any value apart from no':
                            if e.tags.get(tag) != 'no':
                                is_entrance = True
                                break
                        else:              
                            for value in entrance_tags_values[tag]:
                                if e.tags.get(tag) == value:
                                    is_entrance = True
                                    break
            e.is_entrance = is_entrance

    def set_access_attribute_on_barriers(elements:list[OsmElement]) -> None:

        def set_access_attribute_on_barrier(barrier:OsmElement, intersecting_entrances:list[OsmElement]) -> None:
            """sets the access attribute of a barrier based on its intersections with entrances

            Args:
                barrier (OsmElement): barrier that is analysed
                intersecting_entrances (list[OsmElement]): list of entrances that intersect with the barrier

            Notes:
                the access attribute can not be overwritten, so if it was set earlier and with a more reliable source, e.g. based on an access tag, this step will not influence the value of the access attribute
            """            

            def set_barrier_access_attribute_with_single_entrance(barrier:OsmElement,intersecting_entrance:OsmElement) -> None:
                """sets the access attribute of a barrier based on a single intersecting entrance

                Args:
                    barrier (OsmElement): barrier that is analysed
                    intersecting_entrance (OsmElement): entrance that intersect with the barrier
                """                
                if intersecting_entrance.access is None:
                    barrier.access = 'yes'
                else:
                    barrier.access = intersecting_entrance.access

            def set_barrier_access_attribute_with_multiple_entrances(barrier:OsmElement, intersecting_entrances:list[OsmElement]) -> None:
                """sets the access attribute of a barrier based on multiple intersecting entrances

                Args:
                    barrier (OsmElement): barrier that is analysed
                    intersecting_entrances (list[OsmElement]): list of entrances that intersect with the barrier
                """                

                def clean_intersecting_entrances(intersecting_entrances:list[OsmElement]) -> list[OsmElement]:
                    """ identifies and drops intersecting entrances that intersect with another intersecting entrance with access = no

                    Args:
                        intersecting_entrances (list[OsmElement]): entrance elements that intersect with the barrier and should be checked

                    Returns:
                        list[int]: filtered list of intersecting entrances with access

                    Notes:
                        e.g. a path might not be tagged with access = private and thus might be interpreted as giving access to a fenced area, but path and fence cross gate with access = private tag
                    """    
                    def get_intersection_ids_to_drop(intersecting_entrances:list[OsmElement]) -> set[int]:    
                        osmids_to_drop = set()
                        for idx,i1 in enumerate(list(intersecting_entrances)):
                            if i1 != intersecting_entrances[-1]:
                                for i2 in intersecting_entrances[idx+1:]:
                                    if i1.geom.intersects(i2.geom):
                                        if i1.access == 'no' or i2.access == 'no':
                                            osmids_to_drop.add(i1.id)
                                            osmids_to_drop.add(i2.id)
                        return osmids_to_drop

                    def drop_inaccessible_intersecting_entrances(intersecting_entrances:list[OsmElement], osmids_to_drop:set[int]) -> list[OsmElement]:
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
                if has_access_point == True:
                    barrier.access = 'yes'
                elif has_access_point == 'restricted':
                    barrier.access = 'restricted'
                else:
                    barrier.access = 'no'  

            if len(intersecting_entrances) == 0:
                barrier.access = 'no'
            elif len(intersecting_entrances) == 1:
                set_barrier_access_attribute_with_single_entrance(barrier,intersecting_entrances[0])
            elif len(intersecting_entrances) > 1:
                set_barrier_access_attribute_with_multiple_entrances(barrier, intersecting_entrances)
        
        for barrier in [e for e in elements if e.is_barrier]:
            barrier_geom_prep = shapely.prepared.prep(barrier.geom)
            intersecting_entrances = []
            for entrance in [e for e in elements if e.is_entrance]:
                if barrier_geom_prep.intersects(entrance.geom):
                    intersecting_entrances.append(entrance)
            set_access_attribute_on_barrier(barrier, intersecting_entrances)

    set_barrier_attribute(elements)
    set_entrance_attribute(elements)
    set_access_attribute_on_barriers(elements)

def get_inaccessible_barriers(elements:list[OsmElement]) -> list[OsmElement]:
    """returns the elements in list of OsmElements that have access = no and is_barrier = True

    Args:
        elements (list[OsmElement]): list of OsmElements

    Returns:
        list[OsmElement]: filtered list
    """    
    return [e for e in elements if e.access == 'no' and e.is_barrier]

def get_inaccessible_enclosed_areas(inaccessible_barriers:list[OsmElement], buildings:list[OsmElement]) -> list[Polygon|MultiPolygon]:
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

def compare_osm_elements_to_inaccessible_enclosed_areas_and_drop_intersections(elements:list[OsmElement], enclosed_areas:list[Polygon|MultiPolygon]) -> list[Polygon|MultiPolygon]:
    """iterates over list of inaccessible enclosed areas and compares them to list of OsmElements based on intersecting area and drops the inaccessible enclosed area if it is an OsmElement with access

    Args:
        elements (list[OsmElement]): list of OsmElements
        enclosed_areas (list[Polygon | MultiPolygon]): list of geometries of inaccessible enclosed areas

    Returns:
        list[Polygon|MultiPolygon]: filtered list of geometries of inaccessible enclosed areas
    """    
    
    def drop_enclosed_areas_to_ignore(enclosed_areas:list[Polygon|MultiPolygon], enclosed_area_indices_to_ignore:list[int]) -> list[Polygon|MultiPolygon]:
        enclosed_areas_cleaned = []
        for idx, area in enumerate(enclosed_areas):
            if idx not in enclosed_area_indices_to_ignore:
                enclosed_areas_cleaned.append(area)
        return enclosed_areas_cleaned

    overlap_threshold = 0.95
    enclosed_area_indices_to_ignore = []
    for idx, enclosed_area in enumerate(enclosed_areas):
        enclosed_area_prep = shapely.prepared.prep(enclosed_area)
        for e in [e for e in elements if e.is_polygon() or e.is_multipolygon()]:
            if enclosed_area_prep.intersects(e.geom):
                intersection_area = enclosed_area.intersection(e.geom).area
                if (intersection_area / enclosed_area.area) >= overlap_threshold and (intersection_area / e.geom.area) >= overlap_threshold:
                    enclosed_area_indices_to_ignore.append(idx)
                    if e.access is None:
                        e.access = 'no'
                    break           
    enclosed_areas_cleaned = drop_enclosed_areas_to_ignore(enclosed_areas, enclosed_area_indices_to_ignore)
    return enclosed_areas_cleaned

def clear_temporary_attributes_and_drop_linestring_barriers(elements:list[OsmElement]) -> list[OsmElement]:
    for e in elements:
        del e.is_entrance
        if e.is_barrier and e.is_linestring():
            e.ignore = True
        del e.is_barrier
    return [e for e in elements if not e.ignore]

def assume_and_clean_access_based_on_space_type(elements:list[OsmElement]) -> None:
    """sets the access of OsmElements based on a give space_type if access is not set yet and space_type is given.
        also sets access to no for all elements with space_type parking, even if it is set differently already

    Args:
        elements (list[OsmElement]): list of OsmElements
    """    
    def assume_access_based_on_space_type(element:OsmElement) -> None:
        space_types_with_access = ['public transport stop', 'park', 'playground', 'dog_park', 'place', 'fitness_station', 
                                    'square', 'track', 'brownfield', 'bus_station', 'forest', 'sand', 'garden', 'heath', 
                                    'greenhouse_horticulture', 'meadow', 'nature_reserve', 'recreation_ground', 'scree',
                                    'scrub', 'village_green', 'wood', 'cemetery', 'grass', 'pitch', 'beach', 'bridge',
                                    'common',  'island', 'marina', 'pier', 'water_park', 'religious', 'shelter', 'grassland',
                                    'greenfield']
        space_types_with_restricted_access = ['outdoor_seating', 'sports_centre', 'swimming_pool', 'biergarten', 'miniature_golf',
                                            'stadium', 'horse_riding'] #because usually linked to comsumption / fees / hours which might not be recorded in OSM
        space_types_without_access = ['allotments', 'construction', 'landfill', 'military','railway', 'flowerbed','fountain', 
                                    'water', 'wetland', 'parking', 'storage', 'farmland', 'orchard', 'plant_nursery',
                                    'vineyard', 'harbour', 'resort', 'garages', 'stage', 'reservoir']
        if element.space_type in space_types_with_access:
            element.access = 'yes'
        elif element.space_type in space_types_with_restricted_access:
            element.access = 'restricted'
        elif element.space_type in space_types_without_access:
            element.access = 'no'
    def set_all_parking_to_no_access(elements:list[OsmElement]) -> None:
        for e in [e for e in elements if e.space_type == 'parking']:
            e.access = ('no', 'overwrite_yes')

    for element in [e for e in elements if e.access is None and e.space_type is not None]:
        assume_access_based_on_space_type(element)
    set_all_parking_to_no_access(elements)
