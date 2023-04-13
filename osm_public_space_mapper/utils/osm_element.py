import shapely
from shapely.geometry import LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
import esy.osm.shape


class OsmElement:

    ShapelyGeometry = LinearRing | Polygon | MultiPolygon | Point | MultiPoint | LineString | MultiLineString

    def __init__(self, attr: tuple[ShapelyGeometry | esy.osm.shape.shape.Invalid, int, dict]) -> None:
        """Creates an object of the class OsmElement with private attributes geom, id, tags, space_type, access and ignore

        Args:
            attr (tuple[ShapelyGeometry  |  esy.osm.shape.shape.Invalid, int, dict]): Attributes of the OsmElement as a tuple with geometry, id and tags as returned by esy.osm.shape

        Raises:
            TypeError: raised if attr are not given as tuple with three elements
        """
        if type(attr) != tuple and len(attr) != 3:
            raise TypeError('Attributes can not be processed because of wrong type or length')
        self.__set_geom(attr[0])
        self.__set_id(attr[1])
        self.__set_tags(attr[2])
        self.__space_type = None
        self.__access = None
        self.__ignore = False
        self.__access_derived_from = None

    def __get_geom(self) -> ShapelyGeometry | esy.osm.shape.shape.Invalid:
        return self.__geom

    def __set_geom(self, g: ShapelyGeometry | esy.osm.shape.shape.Invalid):
        if isinstance(g, shapely.geometry.base.BaseGeometry):
            self.__geom = g
        elif type(g) == esy.osm.shape.shape.Invalid:
            self.__geom = g
        else:
            raise TypeError('Geometry is not a shapely geometry or esy.osm.shape.shape.Invalid')
    geom = property(__get_geom, __set_geom)

    def __get_id(self) -> int:
        return self.__id

    def __set_id(self, i: int):
        if type(i) == int:
            self.__id = i
        else:
            raise TypeError('Second tuple element is no integer ID')
    id = property(__get_id, __set_id)

    def __get_tags(self) -> dict:
        return self.__tags

    def __set_tags(self, t: dict[str, str]):
        if type(t) == dict:
            self.__tags = t
        else:
            raise TypeError('Third tuple element is no dict')
    tags = property(__get_tags, __set_tags)

    def __get_space_type(self) -> str:
        return self.__space_type

    def __set_space_type(self, space_type: str):
        if self.__space_type is None:
            self.__space_type = space_type
    space_type = property(__get_space_type, __set_space_type)

    def __get_access(self) -> None | str:
        return self.__access

    def __set_access(self, attr: str | tuple[str]) -> None:
        if type(attr) == str:
            access_type = attr
            if self.__access is None:
                self.__access = access_type
        elif type(attr) == tuple:
            access_type, overwrite = attr
            if overwrite == 'overwrite_yes':
                self.__access = access_type
    access = property(__get_access, __set_access)

    def __get_access_derived_from(self) -> str:
        return self.__access_derived_from

    def __set_access_derived_from(self, source: str):
        if self.__access_derived_from is None:
            self.__access_derived_from = source
    access_derived_from = property(__get_access_derived_from, __set_access_derived_from)

    def __get_ignore(self) -> bool:
        return self.__ignore

    def __set_ignore(self, value: bool):
        self.__ignore = value
    ignore = property(__get_ignore, __set_ignore)

    def __str__(self):
        return f'{self.__dict__}'

    def has_tag(self, tag: str) -> bool:
        """Returns if the element has a specific tag

        Args:
            tag (str): tag that should be checked for occurence

        Returns:
            bool: True if the element has that tag
        """
        return self.tags.get(tag) is not None

    def is_certain_geometry(self, geometry: ShapelyGeometry) -> bool:
        return type(self.geom) == geometry

    def is_linestring(self) -> bool:
        return self.is_certain_geometry(LineString)

    def is_polygon(self) -> bool:
        return self.is_certain_geometry(Polygon)

    def is_multipolygon(self) -> bool:
        return self.is_certain_geometry(MultiPolygon)

    def is_point(self) -> bool:
        return self.is_certain_geometry(Point)

    def is_building(self) -> bool:
        """identifies an element as building depending on tags and geometry

        Returns:
            bool: boolean value if element is identified as building
        """
        building = False
        building_tags = ['building', 'building:part', 'building:levels']
        if self.is_polygon() or self.is_multipolygon():
            for tag in building_tags:
                if self.has_tag(tag):
                    if self.tags.get('building') != 'roof' and self.tags.get('building') != 'no':
                        building = True
        return building

    def is_crossing(self) -> bool:
        """identifies an element as crossing depending on tags

        Returns:
            bool: boolean value if element is identified as crossing
        """
        crossing_tags = set(['highway', 'footway', 'railway'])
        crossing = False
        if self.tags.get('crossing', 'no') != 'no':
            crossing = True
        else:
            for tag in crossing_tags:
                if self.tags.get(tag) == 'crossing':
                    crossing = True
                    break
        return crossing

    def is_entrance(self) -> bool:
        """identifies an element as entrance depending on tags and geometry type

        Returns:
            bool: boolean value if element is identified as entrance
        """
        entrance = False
        if self.has_tag('highway') and self.tags.get('highway') != 'motorway' and self.is_linestring():
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
            If the element has a layer tag, it is not counted as barrier, because it is assumed that there is something below/above granting access through this barrier

        """
        barrier = False
        if self.has_tag('barrier') and self.is_linestring():
            barrier = True
        elif self.tags.get('highway') == 'motorway' and self.tags.get('layer') is None and self.is_linestring():
            barrier = True
        elif self.tags.get('railway') == 'rail' and self.tags.get('layer') is None and self.is_linestring() and self.tags.get('embedded') != 'yes':
            barrier = True
        elif self.tags.get('landuse') == 'railway' and (self.is_polygon() or self.is_multipolygon()):
            barrier = True
        return barrier

    def is_pedestrian_way(self) -> bool:
        """identifies an element as a pedestrian way based on values of highway tag and if it is not a crossing

        Returns:
            bool: returns True if element is identified as pedestrian way
        """
        highway_for_pedestrians = set(('footway', 'steps', 'path', 'pedestrian', 'living_street', 'track'))
        return self.tags.get('highway') in highway_for_pedestrians and not self.is_crossing()

    def is_platform_polygon(self) -> bool:
        """identifies an element as a public transport platform polygon based on tags and values and geometry type

        Returns:
            bool: returns true if element is identified as platform polygon
        """
        tags_and_values_for_platforms = {'public_transport': 'platform', 'railway': 'platform', 'highway': 'platform', 'shelter_type': 'public_transport'}
        is_platform_polygon = False
        if self.is_polygon() or self.is_multipolygon():
            for tag in tags_and_values_for_platforms:
                if self.tags.get(tag) == tags_and_values_for_platforms[tag]:
                    is_platform_polygon = True
                    break
        return is_platform_polygon

    def is_parking_polygon(self) -> bool:
        """identifies an element as parking polygon based on tags and values and geometry type

        Returns:
            bool: returns true if element is identified as parking polygon
        """
        if self.is_polygon() or self.is_multipolygon():
            return any([self.tags.get('amenity') in ['parking', 'parking_space'], self.has_tag('parking'), self.has_tag('motorcycle_parking'), self.has_tag('parking_space')])
        else:
            return False

    def is_rail(self) -> bool:
        """identifies an element as rail based on railway and landuse tag values, any geometry

        Returns:
            bool: returns true if element is identified as rail
        """
        return any([self.tags.get('railway') in ['tram', 'rail'], self.tags.get('landuse') == 'railway'])
