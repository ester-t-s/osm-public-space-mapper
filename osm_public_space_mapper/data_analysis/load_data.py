import esy.osm.shape

from osm_public_space_mapper.utils.osm_element import OsmElement


def load_elements(filepath: str) -> list[OsmElement]:
    """Loads OSM elements from .osm.pbf file and returns them in a list of OsmElements

    Args:
        filepath (str): filepath of the .osm.pbf file

    Returns:
        list[OsmElement]: list of OsmElements containing all objects from the OSM file
    """
    shape = esy.osm.shape.Shape(filepath)
    osm_elements = [OsmElement(obj) for obj in shape(lambda e:e)]
    return osm_elements
