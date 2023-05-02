import shapely
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
    for b in buildings:
        b.space_type = 'building'
        b.access = 'no'
    elements = [e for e in elements if not e.is_building()]
    return elements, buildings


def clip_building_passages_from_buildings(buildings: List[OsmElement], elements: List[OsmElement]) -> List[OsmElement]:
    building_passages = []
    for e in elements:
        if e.is_building_passage() and (e.access is None or e.access == 'yes'):
            building_passages.append(e.geom)
    building_passages_union = shapely.ops.unary_union(building_passages)
    for b in buildings:
        if b.geom.intersects(building_passages_union):
            b.geom = b.geom.difference(building_passages_union)
    return [b for b in buildings if not b.geom.is_empty]


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
        tags = ['leisure', 'amenity', 'natural', 'place', 'landuse']
        for e in elements:
            for tag in tags:
                if e.has_tag(tag):
                    e.space_type = e.tags.get(tag)
                    break

    set_space_type_for_construction(elements)
    set_space_type_from_tags(elements)
