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
