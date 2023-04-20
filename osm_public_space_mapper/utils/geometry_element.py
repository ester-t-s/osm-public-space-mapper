import shapely
from shapely.geometry import LinearRing, Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
import esy.osm.shape


class GeometryElement:

    ShapelyGeometry = LinearRing | Polygon | MultiPolygon | Point | MultiPoint | LineString | MultiLineString

    def __init__(self, geometry: ShapelyGeometry,
                 space_type: None | str = None,
                 access: None | str = None,
                 access_derived_from: None | str = None,
                 space_category: None | str = None) -> None:
        """Creates an object of the class GeometryElement with geometry and additional attributes set to None in beginning

        Args:
            attr (tuple[ShapelyGeometry  |  esy.osm.shape.shape.Invalid, int, dict]): Attributes of the OsmElement as a tuple with geometry, id and tags as returned by esy.osm.shape

        Raises:
            TypeError: raised if attr are not given as tuple with three elements
        """
        self._set_geom(geometry)
        self.__space_type = space_type
        self.__access = access
        self.__ignore = False
        self.__access_derived_from = access_derived_from
        self.__space_category = space_category

    def _get_geom(self) -> ShapelyGeometry | esy.osm.shape.shape.Invalid:
        return self.__geom

    def _set_geom(self, g: ShapelyGeometry | esy.osm.shape.shape.Invalid):
        if isinstance(g, shapely.geometry.base.BaseGeometry):
            self.__geom = g
        elif type(g) == esy.osm.shape.shape.Invalid:
            self.__geom = g
        else:
            raise TypeError('Geometry is not a shapely geometry or esy.osm.shape.shape.Invalid')
    geom = property(_get_geom, _set_geom)

    def _get_space_type(self) -> str:
        return self.__space_type

    def _set_space_type(self, space_type: str):
        if self.__space_type is None:
            self.__space_type = space_type
    space_type = property(_get_space_type, _set_space_type)

    def _get_access(self) -> None | str:
        return self.__access

    def _set_access(self, attr: str | tuple[str]) -> None:
        if type(attr) == str:
            access_type = attr
            if self.__access is None:
                self.__access = access_type
        elif type(attr) == tuple:
            access_type, overwrite = attr
            if overwrite == 'overwrite_yes':
                self.__access = access_type
    access = property(_get_access, _set_access)

    def _get_access_derived_from(self) -> str:
        return self.__access_derived_from

    def _set_access_derived_from(self, source: str):
        if self.__access_derived_from is None:
            self.__access_derived_from = source
    access_derived_from = property(_get_access_derived_from, _set_access_derived_from)

    def _get_space_category(self) -> str:
        return self.__space_category

    def _set_space_category(self, category: str):
        self.__space_category = category
    space_category = property(_get_space_category, _set_space_category)

    def _get_ignore(self) -> bool:
        return self.__ignore

    def _set_ignore(self, value: bool):
        self.__ignore = value
    ignore = property(_get_ignore, _set_ignore)

    def __str__(self):
        return f'{self.__dict__}'

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
