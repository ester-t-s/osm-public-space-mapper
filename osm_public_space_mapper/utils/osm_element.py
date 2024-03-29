from shapely.geometry import (
    LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
)
import esy.osm.shape
from osm_public_space_mapper.utils.geometry_element import GeometryElement
from typing import Dict, Tuple, TypeAlias

ShapelyGeometry: TypeAlias = LinearRing | Polygon | MultiPolygon | Point | MultiPoint | LineString | MultiLineString


class OsmElement(GeometryElement):

    def __init__(self, attr: Tuple[ShapelyGeometry | esy.osm.shape.shape.Invalid, int, dict]) -> None:
        """Creates an object of the class OsmElement with private attributes geom, id, tags, space_type, access and ignore

        Args:
            attr (Tuple[ShapelyGeometry  |  esy.osm.shape.shape.Invalid, int, dict]): Attributes of the OsmElement as a tuple with geometry, id and tags as returned by esy.osm.shape

        Raises:
            TypeError: raised if attr are not given as tuple with three elements
        """
        GeometryElement.__init__(self, geometry=attr[0])
        self._set_id(attr[1])
        self._set_tags(attr[2])

    def _get_id(self) -> int:
        return self.__id

    def _set_id(self, i: int):
        if type(i) == int:
            self.__id = i
        else:
            raise TypeError('Second tuple element is no integer ID')
    id = property(_get_id, _set_id)

    def _get_tags(self) -> dict:
        return self.__tags

    def _set_tags(self, t: Dict[str, str]):
        if type(t) == dict:
            self.__tags = t
        else:
            raise TypeError('Third tuple element is no dict')
    tags = property(_get_tags, _set_tags)

    def has_tag_key(self, key: str) -> bool:
        """Returns if the element has a specific tag key

        Args:
            key (str): tag key that should be checked for occurrence

        Returns:
            bool: True if the element has that tag key
        """
        return self.tags.get(key) is not None

    # IDENTIFY PROPERTIES OF ELEMENT #

    # identify buildings
    def is_building(self) -> bool:
        """identifies an element as building depending on tags and geometry

        Returns:
            bool: boolean value if element is identified as building
        """
        building = False
        building_keys = ['building', 'building:part', 'building:levels']
        if self.is_polygon() or self.is_multipolygon():
            for key in building_keys:
                if self.has_tag_key(key):
                    if self.tags.get('building') != 'roof' and self.tags.get('building') != 'no':
                        building = True
        return building

    def is_building_passage(self) -> bool:
        if self.has_tag_key('highway') and self.tags.get('tunnel') == 'building_passage':
            return True
        else:
            return False

    # identify traffic area
    def is_crossing(self) -> bool:
        """identifies an element as crossing depending on tags

        Returns:
            bool: boolean value if element is identified as crossing
        """
        crossing_keys = set(['highway', 'footway', 'railway'])
        crossing = False
        if self.tags.get('crossing', 'no') != 'no':
            crossing = True
        else:
            for key in crossing_keys:
                if self.tags.get(key) == 'crossing':
                    crossing = True
                    break
        return crossing

    def is_pedestrian_way(self) -> bool:
        """identifies an element as a pedestrian way based on values of highway tag key and if it is not a crossing

        Returns:
            bool: returns True if element is identified as pedestrian way
        """
        highway_for_pedestrians = set(('footway', 'steps', 'path', 'pedestrian', 'living_street', 'track'))
        return self.tags.get('highway') in highway_for_pedestrians and not self.is_crossing()

    def is_shared_cycleway_footway(self) -> bool:
        if self.tags.get('highway') in ['cycleway', 'footway'] and self.tags.get('segregated') == 'no':
            return True
        else:
            return False

    def is_platform_polygon(self) -> bool:
        """identifies an element as a public transport platform polygon based on tag keys and values and geometry type

        Returns:
            bool: returns true if element is identified as platform polygon
        """
        keys_and_values_for_platforms = {'public_transport': 'platform', 'railway': 'platform', 'highway': 'platform', 'shelter_type': 'public_transport'}
        is_platform_polygon = False
        if self.is_polygon() or self.is_multipolygon():
            for key in keys_and_values_for_platforms:
                if self.tags.get(key) == keys_and_values_for_platforms[key]:
                    is_platform_polygon = True
                    break
        return is_platform_polygon

    def is_parking_polygon(self) -> bool:
        """identifies an element as parking polygon based on tag keys and values and geometry type

        Returns:
            bool: returns true if element is identified as parking polygon
        """
        if self.is_polygon() or self.is_multipolygon():
            return any([self.tags.get('amenity') in ['parking', 'parking_space'], self.has_tag_key('parking'), self.has_tag_key('motorcycle_parking'), self.has_tag_key('parking_space')])
        else:
            return False

    def is_rail(self) -> bool:
        """identifies an element as rail based on railway and landuse key values, any geometry

        Returns:
            bool: returns true if element is identified as rail
        """
        return any([self.tags.get('railway') in ['tram', 'rail'], self.tags.get('landuse') == 'railway'])

    def is_highway_polygon(self) -> bool:
        if self.has_tag_key('highway'):
            return self.is_polygon()

    # identify construction
    def is_construction(self) -> bool:
        if any([self.has_tag_key('construction'),
                self.has_tag_key('construction:highway'),
                self.tags.get('landuse') == 'construction',
                self.tags.get('highway') == 'construction',
                self.tags.get('railway') == 'construction']):
            return True
        else:
            return False

    # identify barriers and entrances
    def is_barrier_polygon(self) -> bool:
        if self.tags.get('barrier') in set(['fence', 'hedge']):
            return self.is_polygon()

    def is_wall_polygon(self) -> bool:
        if self.tags.get('barrier') == 'wall' and not self.has_tag_key('building'):
            return self.is_polygon()

    def is_entrance(self) -> bool:
        """identifies an element as entrance depending on tags and geometry type

        Returns:
            bool: boolean value if element is identified as entrance
        """
        entrance = False
        if self.has_tag_key('highway') and self.tags.get('highway') != 'motorway' and self.is_linestring():
            entrance = True
        elif self.is_crossing():
            entrance = True
        elif self.tags.get('barrier') == 'gate':
            entrance = True
        return entrance

    def is_barrier(self) -> bool:
        """identifies an element as barrier depending on tags and geometry type

        Returns:
            bool: boolean value if element is identified as barrier

        Notes:
            Barriers, motorways and railways (not trams) are identified as barriers.
            For all apart from landuse == railway, only LineStrings are counted because they should be set up as LineStrings.
            If the element has a layer key, it is not counted as barrier, because it is assumed that there is something below/above granting access through this barrier

        """
        barrier = False
        if self.has_tag_key('barrier') and self.is_linestring():
            barrier = True
        elif self.tags.get('highway') == 'motorway' and self.is_linestring():
            barrier = True
        elif self.tags.get('railway') == 'rail' and self.is_linestring() and self.tags.get('embedded') != 'yes':
            barrier = True
        elif self.tags.get('landuse') == 'railway' and (self.is_polygon() or self.is_multipolygon()):
            barrier = True
        return barrier

    # identify area
    def is_area(self) -> bool:
        return self.tags.get('area') == 'yes'

    # identify groundlevel
    def is_non_groundlevel(self) -> bool:
        non_groundlevel = False
        if self.has_tag_key('level'):
            try:
                list(map(float, str(self.tags.get('level')).split(';')))
            except ValueError:
                pass
            else:
                if 0 not in list(map(float, str(self.tags.get('level')).split(';'))):
                    non_groundlevel = True
        elif self.tags.get('tunnel') == 'yes':
            non_groundlevel = True
        elif self.tags.get('parking') == 'underground':
            non_groundlevel = True
        elif self.tags.get('location') == 'underground':
            non_groundlevel = True
        return non_groundlevel
