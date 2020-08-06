from pycromanager import Bridge, Acquisition

bridge = Bridge()
#get object representing micro-magellan API
magellan = bridge.get_magellan()


test_surface = magellan.create_surface('Test surface')


#get the positions of the interpolation points that were manually clicked
interp_points = test_surface.get_points()
first_point = interp_points.get(0)
print(first_point.x, first_point.y, first_point.z)

test_surface.get_extrapolated_value(5., 200.)


#get
xy_positions = test_surface.get_xy_positions()
for i in range(xy_positions.size()):
    pos = xy_positions.get(i)
    x, y = pos.get_center().x, pos.get_center().y
    z = test_surface.get_extrapolated_value(x, y)

