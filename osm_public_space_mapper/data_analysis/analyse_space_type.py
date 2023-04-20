from osm_public_space_mapper.utils.osm_element import OsmElement


def get_and_drop_buildings(elements: list[OsmElement]) -> tuple[list[OsmElement], list[OsmElement]]:
    """Iterates over list of OsmElements, returns the buildings as list and the given list without buildings

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over

    Returns:
        tuple[list[OsmElement], list[OsmElement]]: given list without buildings and buildings as separate list
    """
    buildings = [e for e in elements if e.is_building()]
    for b in buildings:
        b.space_type = 'building'
        b.access = 'no'
    elements = [e for e in elements if not e.is_building()]
    return elements, buildings


def set_missing_space_types(elements: list[OsmElement]) -> None:
    """iterates over list of OsmElements and sets space_type based on tags if space_type is not set yet

    Args:
        elements (list[OsmElement]): list of OsmElements to iterate over
    """
    def set_space_type_for_construction(elements: list[OsmElement]) -> None:
        for e in elements:
            if any([e.has_tag('construction'), e.has_tag('construction:highway'),
                    e.tags.get('landuse') == 'construction', e.tags.get('highway') == 'construction', e.tags.get('railway') == 'construction']):
                e.space_type = 'construction'

    def set_space_type_for_parking(elements: list[OsmElement]) -> None:
        for e in [e for e in elements if e.is_polygon() or e.is_multipolygon()]:
            if any([e.tags.get('amenity') in ['parking', 'parking_space'], e.has_tag('parking'), e.has_tag('motorcycle_parking')]):
                e.space_type = 'parking'

    def set_space_type_for_platforms(elements: list[OsmElement]) -> None:
        tags_and_values_for_platforms = {'railway': 'platform', 'shelter_type': 'public_transport', 'public_transport': 'platform'}
        for e in elements:
            for tag in tags_and_values_for_platforms:
                if e.tags.get(tag) == tags_and_values_for_platforms[tag]:
                    e.space_type = 'public transport stop'
                    break

    def set_space_type_from_tags(elements: list[OsmElement]) -> None:
        tags = ['leisure', 'amenity', 'natural', 'place', 'landuse']
        for e in elements:
            for tag in tags:
                if e.has_tag(tag):
                    e.space_type = e.tags.get(tag)

    set_space_type_for_construction(elements)
    set_space_type_for_parking(elements)
    set_space_type_for_platforms(elements)
    set_space_type_from_tags(elements)
