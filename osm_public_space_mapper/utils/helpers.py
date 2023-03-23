import copy
from osm_public_space_mapper.utils.osm_element import OsmElement


def buffer_list_of_elements(elements: list[OsmElement], buffer_size: float, cap_style: str = 'flat', join_style: str = 'mitre') -> list[OsmElement]:
    """Buffers the geometries of all elements in a list of OsmElements

    Args:
        elements (list[OsmElement]): list of OsmElements. geom attribute can be any Shapely geometry
        buffer_size (float): buffer size
        cap_style (str, optional): buffer cap style. Defaults to 'flat'.

    Returns:
        list[OsmElement]: list of OsmElements with the new, buffered geometry as geom attribute
    """
    elements_buffer = []
    for e in elements:
        e_buffered = copy.deepcopy(e)
        e_buffered.geom = e.geom.buffer(buffer_size, cap_style=cap_style, join_style=join_style)
        elements_buffer.append(e_buffered)
    return elements_buffer
