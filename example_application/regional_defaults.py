# traffic area #

# highway_default_widths are based on minimum width from the Austrian 'Richtlinien und Vorschriften für das Straßenwesen, RSV 04.03.12'
# dict with default highway widths of the roadway without parking/cycle lane etc. for each OSM highway type.
# Tuple consists of value for bi-directional and uni-directional highways in metres.
highway_default_widths = {
    'service': (4.5, 3.6),
    'residential': (4.5, 3.6),
    'tertiary': (5.25, 3.8),
    'primary': (6.5, 3.8),
    'cycleway': (2, 1),
    'secondary': (6.5, 3.8),
    'motorway_link': (6.5, 3.8),
    'platform': (1.5, 1),
    'motorway': (6.5, 3.8),
    'unclassified': (5.25, 3.8),
    'primary_link': (6.5, 3.8),
    'secondary_link': (6.5, 3.8),
    'construction': (5.25, 3.8),
    'everything else': (5.25, 3.6)
}
# cycleway_default_widths are based on minimum width from the Austrian 'Richtlinien und Vorschriften für das Straßenwesen, RSV 03.02.13'
cycleway_track_width, cycleway_lane_width = 1.5, 1.5
cycleway_default_widths = {
    'cycleway': {
        'lane': cycleway_lane_width,
        'opposite': 0.5,
        'track': cycleway_track_width,
        'opposite_lane': 1,
        'opposite_track': cycleway_track_width
    },
    'cycleway:right': {
        'lane': cycleway_lane_width,
        'track': cycleway_track_width
    },
    'cycleway:both': {
        'lane': cycleway_lane_width*2,
        'track': cycleway_track_width*2
    },
    'cycleway:left': {
        'lane': cycleway_lane_width,
        'track': cycleway_track_width
    }
}
highway_types_for_default_streetside_parking = ['residential', 'tertiary', 'secondary', 'primary']  # parking should also be assumed for living_street but living_street is categorized as walking area
default_parking_width = 6.5
# for parking assuming one side horizontal (2m) and one side angle parking (4.5m)
# width taken from OSM Verkehrswende project https://parkraum.osm-verkehrswende.org/project-prototype-neukoelln/report/#27-fl%C3%A4chenverbrauch

tram_gauge = 1.435
tram_additional_carriageway_width = 1
train_gauge = 1.435
train_additional_carriageway_width = 1.5

pedestrian_way_default_width = 1.8
