from typing import List, Tuple
from osm_public_space_mapper.utils.osm_element import OsmElement


def get_and_drop_buildings(elements: List[OsmElement]) -> Tuple[List[OsmElement], List[OsmElement]]:
    """Iterates over list of OsmElements, returns the buildings as list and the given list without buildings

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over

    Returns:
        Tuple[List[OsmElement], List[OsmElement]]: given list without buildings and buildings as separate list
    """
    buildings = [e for e in elements if e.is_building()]
    for building in buildings:
        building.space_type = 'building'
        building.access = 'undefined'
        building.access_derived_from = 'undefined'
    elements = [e for e in elements if not e.is_building()]
    return elements, buildings


def set_missing_space_types(elements: List[OsmElement]) -> None:
    """iterates over list of OsmElements and sets space_type based on tags if space_type is not set yet

    Args:
        elements (List[OsmElement]): list of OsmElements to iterate over
    """
    def set_space_type_for_construction(elements: List[OsmElement]) -> None:
        for e in elements:
            if e.is_construction():
                e.space_type = 'construction'

    def set_space_type_from_tags(elements: List[OsmElement]) -> None:
        tag_keys = ['leisure', 'amenity', 'natural', 'place', 'landuse', 'man_made']
        for e in elements:
            for key in tag_keys:
                if e.has_tag_key(key):
                    e.space_type = e.tags.get(key)
                    break

    set_space_type_for_construction(elements)
    set_space_type_from_tags(elements)
