# traffic area #

# highway_default_widths are based on minimum width from the Austrian 'Richtlinien und Vorschriften für das Straßenwesen'
# https://www.e-genius.at/mooc/smart-cities-teil-3/woche-10-mobilitaet-und-stadt-ii/108-automobilitaet/strassenbreiten
# dict with default highway widths of the roadway without parking/cycle lane etc. for each OSM highway type. Tuple consists of value for bi-directional and uni-directional highways in metres.
highway_default_widths = {'footway': (1.8, 1), 'service': (4.5, 3), 'residential': (4.5, 3), 'steps': (2, 1.5),
                          'tertiary': (4.8, 3.1), 'primary': (5.5, 3.1), 'cycleway': (2, 1.5), 'secondary': (4.8, 3.1),
                          'path': (1.5, 1), 'motorway_link': (6.5, 3.23), 'platform': (2, 1.5), 'pedestrian': (2, 2),
                          'motorway': (6.5, 3.25), 'living_street': (4.5, 3), 'unclassified': (4.5, 3), 'primary_link': (5.5, 3.1),
                          'track': (3, 2.5), 'corridor': (2, 1), 'proposed': (4.8, 3.1), 'secondary_link': (4.8, 3.1),
                          'construction': (5.5, 3.1), 'everything else': (4.8, 3.1)
                          }
cycletrack_width, cyclelane_width = 1.6, 1.6
cycleway_default_widths = {'cycleway': {'lane': cyclelane_width, 'opposite': 1, 'track': cycletrack_width, 'opposite_lane': cyclelane_width, 'opposite_track': cycletrack_width},
                           'cycleway:right': {'lane': cyclelane_width, 'track': cycletrack_width},
                           'cycleway:both': {'lane': 2*cyclelane_width, 'track': 2*cycletrack_width},
                           'cycleway:left': {'lane': cyclelane_width, 'track': cycletrack_width}}
highway_types_for_default_streetside_parking = ['residential', 'tertiary', 'living_street', 'secondary', 'primary']
default_parking_width = 6.5
# for parking assuming one side horizontal (2m) and one side angle parking (4.5m)
# width taken from OSM Verkehrswende project https://parkraum.osm-verkehrswende.org/project-prototype-neukoelln/report/#27-fl%C3%A4chenverbrauch

tram_gauge = 1.435
tram_buffer = 0.5
train_gauge = 1.435
train_buffer = 1.5
