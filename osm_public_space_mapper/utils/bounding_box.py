from shapely import Polygon
from shapely.ops import transform
import pyproj


class BoundingBox:
    def __init__(self, left: float, right: float, top: float, bottom: float) -> None:
        """Creates an object of the class BoundingBox with attributes left, right, top, bottom and geom with shapely Polygon

        Args:
            left (float): left bound in WSG84 coordinates / EPSG 4326
            right (float): right bound in WSG84 coordinates / EPSG 4326
            top (float): top bound in WSG84 coordinates / EPSG 4326
            bottom (float): bottom bound in WSG84 coordinates / EPSG 4326

        Raises:
            ValueError: raised if coordinates are not in range of -180 to 180
        """
        def make_polygon(self, left, right, top, bottom):
            return Polygon([(left, top), (right, top), (right, bottom), (left, bottom)])

        if any(coord < -180 or coord > 180 for coord in (left, right, top, bottom)):
            raise ValueError('Coordinates not in a possible range of EPSG 4326 / WGS 84')
        self.left_4326 = left
        self.right_4326 = right
        self.top_4326 = top
        self.bottom_4326 = bottom
        self.geom_4326 = make_polygon(self, self.left_4326, self.right_4326, self.top_4326, self.bottom_4326)

    def project(self, local_crs: pyproj.crs.crs.CRS) -> None:
        """Projects the shapely geometry of the BoundingBox into the given local_crs and saves it in the attribute geom_projected

        Args:
            local_crs (pyproj.crs.crs.CRS, optional): projected coordinate reference system that should be used for the projection, should be the same for projection of OsmElements.
        """
        projector = pyproj.Transformer.from_crs(pyproj.CRS.from_epsg(4326), local_crs, always_xy=True)
        self.geom_projected = transform(projector.transform, self.geom_4326)
