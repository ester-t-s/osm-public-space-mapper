import pyproj
from osm_public_space_mapper.data_analysis import (
    load_data,
    clean_data,
    analyse_access,
    analyse_space_type,
    analyse_traffic_area,
    get_undefined_space,
    export_data
)
from example_application import local_variables as local_var
from osm_public_space_mapper.utils.bounding_box import BoundingBox


# PARAMETERS TO SET #
source_filepath = "example_application/vienna-rennweg-to-arenbergpark_20230308.osm.pbf"
bounding_box = BoundingBox(top=48.1999, left=16.3843, bottom=48.1931, right=16.3977)
local_crs = pyproj.CRS.from_epsg(3035)  # EPSG 3035 is recommended as default for European Lambert Azimuthal Equal Area, but can be adapted for a more suitable CRS
target_filepath = "example_application/public-space-vienna-rennweg-to-arenbergpark.geojson"
print_status = True  # Should the current analysis step be printed to the terminal?

# CLEANING AND PREPARING DATA #
if print_status:
    print('Loading elements from', source_filepath)
dataset = load_data.load_elements(source_filepath)
if print_status:
    print('Dropping invalid geometries')
dataset = clean_data.drop_invalid_geometries(dataset)
if print_status:
    print('Dropping empty geometries')
dataset = clean_data.drop_empty_geometries(dataset)
if print_status:
    print('Dropping elements without tags')
dataset = clean_data.drop_elements_without_tags(dataset)
if print_status:
    print('Dropping all points apart from entrances')
dataset = clean_data.drop_points_apart_from_entrances(dataset)
if print_status:
    print('Dropping irrelevant elements based on tags')
dataset = clean_data.drop_irrelevant_elements_based_on_tags(dataset)
if print_status:
    print('Cleaning geometries')
clean_data.clean_geometries(dataset)
if print_status:
    print('Projecting geometries')
clean_data.project_geometries(dataset, local_crs)

# IDENTIFY BUILDINGS #
if print_status:
    print('Returning buildings as separate list and delete from dataset')
dataset, buildings = analyse_space_type.get_and_drop_buildings(dataset)

# ANALYSING ACCESS #
if print_status:
    print('Interpreting tags for access')
analyse_access.interpret_tags(dataset)

# ANALYSING TRAFFIC AREA #
if print_status:
    print('Setting space type attribute traffic areas')
analyse_traffic_area.set_traffic_space_type(dataset)
if print_status:
    print('Getting car/bicycle/rail traffic areas as polygons')
road_and_rail = analyse_traffic_area.get_traffic_areas_as_polygons(dataset,
                                                                   local_var.highway_default_widths,
                                                                   local_var.cycleway_default_widths,
                                                                   local_var.tram_gauge,
                                                                   local_var.tram_additional_carriageway_width,
                                                                   local_var.train_gauge,
                                                                   local_var.train_additional_carriageway_width
                                                                   )
if print_status:
    print('Getting pedestrian ways as polygons')
pedestrian_ways = analyse_traffic_area.get_pedestrian_ways_as_polygons(dataset, local_var.pedestrian_way_default_width)
if print_status:
    print('Dropping all traffic areas from dataset')
dataset = clean_data.drop_road_rail_walking(dataset)

# CLEANING BUILDINGS #
if print_status:
    print('Clipping building passages from buildings')
buildings = analyse_space_type.clip_building_passages_from_buildings(buildings, road_and_rail+pedestrian_ways)

# ANALYSING ACCESS #
if print_status:
    print('Interpreting barriers - be patient, that may take a while.')
analyse_access.interpret_barriers(dataset)
if print_status:
    print('Getting inaccessible barriers')
inaccessible_barriers = analyse_access.get_inaccessible_barriers(dataset)
if print_status:
    print('Getting inaccessible enclosed areas')
inaccessible_enclosed_areas = analyse_access.get_inaccessible_enclosed_areas(inaccessible_barriers, buildings)
if print_status:
    print('Splitting elements if they overlap with inaccessible enclosed area and assign access - be patient, that may take a while.')
dataset, road_and_rail, pedestrian_ways, inaccessible_enclosed_areas = analyse_access.compare_and_crop_osm_elements_and_inaccessible_enclosed_areas_and_assign_access(dataset, road_and_rail, pedestrian_ways, inaccessible_enclosed_areas)

if print_status:
    print('Dropping LineString elements with barrier tag and entrance points from dataset')
dataset = analyse_access.drop_linestring_barriers_and_entrance_points(dataset)

# CLEANING TRAFFIC AREA #
road_and_rail = analyse_traffic_area.clean_and_smooth_road_and_rail(road_and_rail, dataset, pedestrian_ways, inaccessible_enclosed_areas, buildings, local_var.pedestrian_way_default_width)

# CLEANING DATA #
if print_status:
    print('Dropping linestrings from dataset')
dataset = clean_data.drop_linestrings(dataset)

# SETTING MISSING SPACE TYPE AND GUESSING MISSING ACCESS #
if print_status:
    print('Setting missing space types based on tags')
analyse_space_type.set_missing_space_types(dataset)
if print_status:
    print('Dropping elements with undefined space type')
dataset = clean_data.drop_elements_with_undefined_space_type(dataset)
if print_status:
    print('Setting missing access attribute based on space type')
analyse_access.assume_access_based_on_space_type((dataset + pedestrian_ways))

# CLEANING DATA #
if print_status:
    print('Combining all elements that define space in a list')
all_defined_space = dataset + buildings + inaccessible_enclosed_areas + pedestrian_ways + [road_and_rail]

if print_status:
    print('Generalizing space types in categories')
all_defined_space = clean_data.set_space_category(all_defined_space)

if print_status:
    print('Merging elements with same space category and access')
all_defined_space = clean_data.merge_elements_with_identical_attributes(all_defined_space)

if print_status:
    print('Clipping overlapping polygons - be patient, that may take a while.')
all_defined_space = clean_data.crop_overlapping_polygons(all_defined_space)

# PREPARING FOR EXPORT #
if print_status:
    print('Projecting bounding box')
bounding_box.project(local_crs)
if print_status:
    print('Cropping all element lists to projected bounding box')
all_defined_space_cropped = clean_data.crop_defined_space_to_bounding_box(all_defined_space, bounding_box)
if print_status:
    print('Getting undefined space within bounding box - be patient, that may take a while.')
undefined_space_within_bbox = get_undefined_space.load(all_defined_space_cropped, bounding_box)

# EXPORTING #
if print_status:
    print('Exporting all defined space and the undefined space to GeoJSON:', target_filepath)
export_data.save2geojson(all_defined_space_cropped,
                         undefined_space_within_bbox,
                         target_filepath, local_crs
                         )
