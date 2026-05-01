
from PyQt6 import QtCore, QtGui

from appObjects.ObjectCollection import GeometryObject, GerberObject, ExcellonObject
from appGUI.GUIElements import DialogBoxChoice

from copy import deepcopy
from shapely import MultiPolygon, Polygon, LinearRing, LineString, Point, unary_union

# App Translation
import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class appEditor(QtCore.QObject):
    def __init__(self, app):
        super(appEditor, self).__init__()

        self.app = app
        self.log = self.app.log
        self.inform = self.app.inform
        self.splash = self.app.splash
        self.worker_task = self.app.worker_task
        self.options = self.app.options
        self.app_units = self.app.app_units
        self.defaults = self.app.defaults
        self.collection = self.app.collection
        self.app_obj = self.app.app_obj
        self.decimals = self.app.decimals

    def convert_any2geo(self):
        """
        Will convert any object out of Gerber, Excellon, Geometry to Geometry object.
        :return:
        """
        self.defaults.report_usage("convert_any2geo()")

        # store here the default data for Geometry Data
        default_data = {}

        for opt_key, opt_val in self.options.items():
            if opt_key.find('geometry' + "_") == 0:
                o_name = opt_key[len('geometry') + 1:]
                default_data[o_name] = self.options[opt_key]
            else:
                default_data[opt_key] = self.options[opt_key]

        if isinstance(self.options["tools_mill_tooldia"], float):
            tools_diameters = [self.options["tools_mill_tooldia"]]
        else:
            try:
                dias = str(self.options["tools_mill_tooldia"]).strip('[').strip(']')
                tools_string = dias.split(",")
                tools_diameters = [eval(a) for a in tools_string if a != '']
            except Exception as e:
                self.log.error("appEditor.convert_any2geo() --> %s" % str(e))
                return 'fail'

        tools = {}
        t_id = 0
        for tooldia in tools_diameters:
            t_id += 1
            new_tool = {
                'tooldia': tooldia,
                'offset': 'Path',
                'offset_value': 0.0,
                'type': 'Rough',
                'tool_type': 'C1',
                'data': deepcopy(default_data),
                'solid_geometry': []
            }
            tools[t_id] = deepcopy(new_tool)

        def initialize_from_gerber(new_obj, app_obj):
            app_obj.log.debug("Gerber converted to Geometry: %s" % str(obj.obj_options["name"]))
            new_obj.solid_geometry = deepcopy(obj.solid_geometry)
            try:
                new_obj.follow_geometry = obj.follow_geometry
            except AttributeError:
                pass

            new_obj.obj_options.update(deepcopy(default_data))
            new_obj.obj_options["tools_mill_tooldia"] = tools_diameters[0] if tools_diameters else 0.0
            new_obj.tools = deepcopy(tools)
            for k in new_obj.tools:
                new_obj.tools[k]['solid_geometry'] = deepcopy(obj.solid_geometry)

        def initialize_from_excellon(new_obj, app_obj):
            app_obj.log.debug("Excellon converted to Geometry: %s" % str(obj.obj_options["name"]))
            solid_geo = []
            for tool in obj.tools:
                for geo in obj.tools[tool]['solid_geometry']:
                    solid_geo.append(geo)
            new_obj.solid_geometry = deepcopy(solid_geo)
            if not new_obj.solid_geometry:
                app_obj.log("convert_any2geo() failed")
                return 'fail'

            new_obj.obj_options.update(deepcopy(default_data))
            new_obj.obj_options["tools_mill_tooldia"] = tools_diameters[0] if tools_diameters else 0.0
            new_obj.tools = deepcopy(tools)
            for k in new_obj.tools:
                new_obj.tools[k]['solid_geometry'] = deepcopy(obj.solid_geometry)

        if not self.collection.get_selected():
            self.log.warning("appEditor.convert_any2geo --> No object selected")
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
            return

        for obj in self.collection.get_selected():
            out_name = '%s_conv' % obj.obj_options["name"]

            try:
                if obj.kind == 'excellon':
                    self.app_obj.new_object("geometry", out_name, initialize_from_excellon)

                if obj.kind == 'gerber':
                    self.app_obj.new_object("geometry", out_name, initialize_from_gerber)
            except Exception as e:
                self.log.error("Convert any2geo operation failed: %s" % str(e))

    def convert_any2gerber(self):
        """
        Will convert any object out of Gerber, Excellon, Geometry to Gerber object.

        :return:
        """

        def initialize_from_geometry(obj_init, app_obj):
            apertures = {
                0: {
                    'size': 0.0,
                    'type': 'REG',
                    'geometry': []
                }
            }

            for obj_orig in obj.solid_geometry:
                new_elem = {'solid': obj_orig}
                try:
                    new_elem['follow'] = obj_orig.exterior
                except AttributeError:
                    pass
                apertures[0]['geometry'].append(deepcopy(new_elem))

            obj_init.solid_geometry = deepcopy(obj.solid_geometry)
            obj_init.tools = deepcopy(apertures)

            if not obj_init.tools:
                app_obj.log("convert_any2gerber() failed")
                return 'fail'

        def initialize_from_excellon(obj_init, app_obj):
            apertures = {}

            aperture_id = 10
            for tool in obj.tools:
                apertures[aperture_id] = {
                    'size': float(obj.tools[tool]['tooldia']),
                    'type': 'C',
                    'geometry': []
                }

                for geo in obj.tools[tool]['solid_geometry']:
                    new_el = {
                        'solid': geo,
                        'follow': geo.exterior
                    }
                    apertures[aperture_id]['geometry'].append(deepcopy(new_el))

                aperture_id += 1

            # create solid_geometry
            solid_geometry = []
            for apid_val in apertures.values():
                for geo_el in apid_val['geometry']:
                    solid_geometry.append(geo_el['solid'])  # noqa

            solid_geometry = MultiPolygon(solid_geometry)
            solid_geometry = solid_geometry.buffer(0.0000001)

            obj_init.solid_geometry = deepcopy(solid_geometry)
            obj_init.tools = deepcopy(apertures)

            if not obj_init.tools:
                app_obj.log("convert_any2gerber() failed")
                return 'fail'

        if not self.collection.get_selected():
            self.log.warning("appEditor.convert_any2gerber --> No object selected")
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
            return

        for obj in self.collection.get_selected():

            outname = '%s_conv' % obj.obj_options["name"]

            try:
                if obj.kind == 'excellon':
                    self.app_obj.new_object("gerber", outname, initialize_from_excellon)
                elif obj.kind == 'geometry':
                    self.app_obj.new_object("gerber", outname, initialize_from_geometry)
                else:
                    self.log.warning("appEditor.convert_any2gerber --> This is no valid object for conversion.")

            except Exception as e:
                return "Operation failed: %s" % str(e)

    def convert_any2excellon(self, conv_obj_name=None):
        """
        Will convert any object out of Gerber, Excellon, Geometry to an Excellon object.

        :param conv_obj_name:    a FlatCAM object
        :return:
        """

        self.log.debug("Running conversion to Excellon object...")

        def initialize_from_geometry(obj_init, app_obj):
            tools = {}
            tool_uid = 1

            obj_init.solid_geometry = []

            for tool in obj.tools:
                print(obj.tools[tool])

            for geo in obj.solid_geometry:
                if not isinstance(geo, (Polygon, MultiPolygon, LinearRing)):
                    continue

                minx, miny, maxx, maxy = geo.bounds
                new_dia = min([maxx - minx, maxy - miny])

                new_drill = geo.centroid
                new_drill_geo = new_drill.buffer(new_dia / 2.0)

                current_tool_dias = []
                if tools:
                    for tool in tools:
                        if tools[tool] and 'tooldia' in tools[tool]:
                            current_tool_dias.append(tools[tool]['tooldia'])

                if new_dia in current_tool_dias:
                    digits = app_obj.decimals
                    for tool in tools:
                        if app_obj.dec_format(tools[tool]["tooldia"], digits) == app_obj.dec_format(new_dia, digits):
                            tools[tool]['drills'].append(new_drill)
                            tools[tool]['solid_geometry'].append(deepcopy(new_drill_geo))
                else:
                    tools[tool_uid] = {}
                    tools[tool_uid]['tooldia'] = new_dia
                    tools[tool_uid]['drills'] = [new_drill]
                    tools[tool_uid]['slots'] = []
                    tools[tool_uid]['solid_geometry'] = [new_drill_geo]
                    tool_uid += 1

                try:
                    obj_init.solid_geometry.append(new_drill_geo)
                except (TypeError, AttributeError):
                    obj_init.solid_geometry = [new_drill_geo]

            obj_init.tools = deepcopy(tools)
            obj_init.solid_geometry = unary_union(obj_init.solid_geometry)

            if not obj_init.solid_geometry:
                return 'fail'

        def initialize_from_gerber(obj_init, app_obj):
            tools = {}
            tool_uid = 1
            digits = app_obj.decimals

            obj_init.solid_geometry = []

            for aperture_id in obj.tools:
                if 'geometry' in obj.tools[aperture_id]:
                    for geo_dict in obj.tools[aperture_id]['geometry']:
                        if 'follow' in geo_dict:
                            if isinstance(geo_dict['follow'], Point):
                                geo = geo_dict['solid']
                                minx, miny, maxx, maxy = geo.bounds
                                new_dia = min([maxx - minx, maxy - miny])

                                new_drill = geo.centroid
                                new_drill_geo = new_drill.buffer(new_dia / 2.0)

                                current_tool_dias = []
                                if tools:
                                    for tool in tools:
                                        if tools[tool] and 'tooldia' in tools[tool]:
                                            current_tool_dias.append(
                                                app_obj.dec_format(tools[tool]['tooldia'], digits)
                                            )

                                formatted_new_dia = app_obj.dec_format(new_dia, digits)
                                if formatted_new_dia in current_tool_dias:
                                    for tool in tools:
                                        if app_obj.dec_format(tools[tool]["tooldia"], digits) == formatted_new_dia:
                                            if new_drill not in tools[tool]['drills']:
                                                tools[tool]['drills'].append(new_drill)
                                                tools[tool]['solid_geometry'].append(deepcopy(new_drill_geo))
                                else:
                                    tools[tool_uid] = {
                                        'tooldia': new_dia,
                                        'drills': [new_drill],
                                        'slots': [],
                                        'solid_geometry': [new_drill_geo]
                                    }
                                    tool_uid += 1

                                try:
                                    obj_init.solid_geometry.append(new_drill_geo)
                                except (TypeError, AttributeError):
                                    obj_init.solid_geometry = [new_drill_geo]
                            elif isinstance(geo_dict['follow'], LineString):
                                geo_coordinates = list(geo_dict['follow'].coords)

                                # slots can have only a start and stop point and no intermediate points
                                if len(geo_coordinates) != 2:
                                    continue

                                geo = geo_dict['solid']
                                try:
                                    new_dia = obj.tools[aperture_id]['size']
                                except Exception:
                                    continue

                                new_slot = (Point(geo_coordinates[0]), Point(geo_coordinates[1]))
                                new_slot_geo = geo

                                current_tool_dias = []
                                if tools:
                                    for tool in tools:
                                        if tools[tool] and 'tooldia' in tools[tool]:
                                            current_tool_dias.append(
                                                float('%.*f' % (self.decimals, tools[tool]['tooldia']))
                                            )

                                if float('%.*f' % (self.decimals, new_dia)) in current_tool_dias:
                                    for tool in tools:
                                        if float('%.*f' % (self.decimals, tools[tool]["tooldia"])) == float(
                                                '%.*f' % (self.decimals, new_dia)):
                                            if new_slot not in tools[tool]['slots']:
                                                tools[tool]['slots'].append(new_slot)
                                                tools[tool]['solid_geometry'].append(deepcopy(new_slot_geo))
                                else:
                                    tools[tool_uid] = {}
                                    tools[tool_uid]['tooldia'] = new_dia
                                    tools[tool_uid]['drills'] = []
                                    tools[tool_uid]['slots'] = [new_slot]
                                    tools[tool_uid]['solid_geometry'] = [new_slot_geo]
                                    tool_uid += 1

                                try:
                                    obj_init.solid_geometry.append(new_slot_geo)
                                except (TypeError, AttributeError):
                                    obj_init.solid_geometry = [new_slot_geo]

            obj_init.tools = deepcopy(tools)
            obj_init.solid_geometry = unary_union(obj_init.solid_geometry)

            if not obj_init.solid_geometry:
                return 'fail'
            obj_init.source_file = app_obj.f_handlers.export_excellon(obj_name=out_name, local_use=obj_init,
                                                                      filename=None, use_thread=False)

        if conv_obj_name is None:
            if not self.collection.get_selected():
                self.log.warning("appEditor.convert_any2excellon--> No object selected")
                self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
                return

            for obj in self.collection.get_selected():

                obj_name = obj.obj_options["name"]
                out_name = "%s_conv" % str(obj_name)
                try:
                    if obj.kind == 'gerber':
                        self.app_obj.new_object("excellon", out_name, initialize_from_gerber)
                    elif obj.kind == 'geometry':
                        self.app_obj.new_object("excellon", out_name, initialize_from_geometry)
                    else:
                        self.log.warning("appEditor.convert_any2excellon --> This is no valid object for conversion.")

                except Exception as e:
                    return "Operation failed: %s" % str(e)
        else:
            out_name = conv_obj_name
            obj = self.collection.get_by_name(out_name)

            try:
                if obj.kind == 'gerber':
                    self.app_obj.new_object("excellon", out_name, initialize_from_gerber)
                elif obj.kind == 'geometry':
                    self.app_obj.new_object("excellon", out_name, initialize_from_geometry)
                else:
                    self.log.warning("appEditor.convert_any2excellon --> This is no valid object for conversion.")

            except Exception as e:
                self.log.error("appEditor.convert_any2excellon() --> %s" % str(e))
                return "Operation failed: %s" % str(e)

    def on_convert_singlegeo_to_multigeo(self):
        """
        Called for converting a Geometry object from single-geo to multi-geo.
        Single-geo Geometry objects store their geometry data into self.solid_geometry.
        Multi-geo Geometry objects store their geometry data into the `self.tools` dictionary, each key
        (a tool actually) having as a value another dictionary. This value dictionary has
        one of its keys 'solid_geometry' which holds the solid-geometry of that tool.

        :return: None
        """
        self.defaults.report_usage("on_convert_singlegeo_to_multigeo()")

        obj = self.collection.get_active()

        if obj is None:
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed. Select a Geometry Object and try again."))
            return

        if not isinstance(obj, GeometryObject):
            self.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Expected a GeometryObject, got"), type(obj)))
            return

        obj.multigeo = True
        for tooluid, dict_value in obj.tools.items():
            dict_value['solid_geometry'] = deepcopy(obj.solid_geometry)

        if not isinstance(obj.solid_geometry, list):
            obj.solid_geometry = [obj.solid_geometry]

        # obj.solid_geometry[:] = []
        obj.plot()

        self.app.should_we_save = True

        self.inform.emit('[success] %s' % _("A Geometry object was converted to MultiGeo type."))

    def on_convert_multigeo_to_singlegeo(self):
        """
        Called for converting a Geometry object from multi-geo to single-geo.
        Single-geo Geometry objects store their geometry data into self.solid_geometry.
        Multi-geo Geometry objects store their geometry data into the self.tools dictionary, each key (a tool actually)
        having as a value another dictionary. This value dictionary has one of its keys 'solid_geometry' which holds
        the solid-geometry of that tool.

        :return: None
        """
        self.defaults.report_usage("on_convert_multigeo_to_singlegeo()")

        obj = self.collection.get_active()

        if obj is None:
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed. Select a Geometry Object and try again."))
            return

        if not isinstance(obj, GeometryObject):
            self.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Expected a GeometryObject, got"), type(obj)))
            return

        obj.multigeo = False
        total_solid_geometry = []
        for tool_uid, dict_value in obj.tools.items():
            total_solid_geometry += deepcopy(dict_value['solid_geometry'])
            # clear the original geometry
            if isinstance(dict_value['solid_geometry'], list):
                dict_value['solid_geometry'][:] = []
            else:
                dict_value['solid_geometry'] = []
        obj.solid_geometry = deepcopy(total_solid_geometry)
        obj.plot()

        self.app.should_we_save = True

        self.inform.emit('[success] %s' % _("A Geometry object was converted to SingleGeo type."))

    def on_edit_join(self, name=None):
        """
        Callback for Edit->Join. Joins the selected geometry objects into
        a new one.

        :return: None
        """
        self.defaults.report_usage("on_edit_join()")

        obj_name_single = str(name) if name else "Combo_SingleGeo"
        obj_name_multi = str(name) if name else "Combo_MultiGeo"

        geo_type_set = set()

        objs = self.collection.get_selected()

        if len(objs) < 2:
            self.inform.emit('[ERROR_NOTCL] %s: %d' %
                             (_("At least two objects are required for join. Objects currently selected"), len(objs)))
            return 'fail'

        for obj in objs:
            geo_type_set.add(obj.multigeo)

        # if len(geo_type_list) == 1 means that all list elements are the same
        if len(geo_type_set) != 1:
            self.inform.emit('[ERROR] %s' %
                             _("Failed join. The Geometry objects are of different types.\n"
                               "At least one is MultiGeo type and the other is SingleGeo type. A possibility is to "
                               "convert from one to another and retry joining \n"
                               "but in the case of converting from MultiGeo to SingleGeo, informations may be lost and "
                               "the result may not be what was expected. \n"
                               "Check the generated GCODE."))
            return

        fuse_tools = self.options["geometry_merge_fuse_tools"]

        # Determine parameters based on the check
        # Since len(geo_type_set) == 1, we just need to check which value is in the set
        is_multi_geo = True in geo_type_set  # True if all are multigeo, False if all are singlegeo
        obj_name = obj_name_multi if is_multi_geo else obj_name_single

        # Define initialize function once
        def initialize(geo_obj, app):
            GeometryObject.merge(
                geo_list=objs,
                geo_final=geo_obj,
                multi_geo=is_multi_geo,  # Use the determined flag
                fuse_tools=fuse_tools,
                log=app.log
            )
            app.inform.emit('[success] %s.' % _("Geometry merging finished"))

            # Update tool names using the determined name
            # Ensure tools and data exist before modification
            if hasattr(geo_obj, 'tools') and geo_obj.tools:
                for tool_data in geo_obj.tools.values():
                    if isinstance(tool_data, dict) and 'data' in tool_data and isinstance(tool_data['data'], dict):
                        tool_data['data']['name'] = obj_name
                    else:
                        # Log or handle unexpected tool structure if necessary
                        app.log.warning(f"Unexpected tool data structure found when setting name: {tool_data}")

        # Create the new object
        self.app_obj.new_object("geometry", obj_name, initialize)  # Use the determined name
        self.app.should_we_save = True

    def on_edit_join_exc(self):
        """
        Callback for Edit->Join Excellon. Joins the selected Excellon objects into
        a new Excellon.

        :return: None
        """
        self.defaults.report_usage("on_edit_join_exc()")

        objs = self.collection.get_selected()

        for obj in objs:
            if not isinstance(obj, ExcellonObject):
                self.inform.emit('[ERROR_NOTCL] %s' % _("Failed. Excellon joining works only on Excellon objects."))
                return

        if len(objs) < 2:
            self.inform.emit('[ERROR_NOTCL] %s: %d' %
                             (_("At least two objects are required for join. Objects currently selected"), len(objs)))
            return 'fail'

        fuse_tools = self.options["excellon_merge_fuse_tools"]

        def initialize(exc_obj, app):
            ExcellonObject.merge(exc_list=objs, exc_final=exc_obj, decimals=self.decimals, fuse_tools=fuse_tools,
                                 log=app.log)
            app.inform.emit('[success] %s.' % _("Excellon merging finished"))

        self.app_obj.new_object("excellon", 'Combo_Excellon', initialize)
        self.app.should_we_save = True

    def on_edit_join_grb(self):
        """
        Callback for Edit->Join Gerber. Joins the selected Gerber objects into
        a new Gerber object.

        :return: None
        """
        self.defaults.report_usage("on_edit_join_grb()")

        objs = self.collection.get_selected()

        for obj in objs:
            if not isinstance(obj, GerberObject):
                self.inform.emit('[ERROR_NOTCL] %s' % _("Failed. Gerber joining works only on Gerber objects."))
                return

        if len(objs) < 2:
            self.inform.emit('[ERROR_NOTCL] %s: %d' %
                             (_("At least two objects are required for join. Objects currently selected"), len(objs)))
            return 'fail'

        def initialize(grb_obj, app):
            GerberObject.merge(grb_list=objs, grb_final=grb_obj, app=self)
            app.inform.emit('[success] %s.' % _("Gerber merging finished"))

        self.app_obj.new_object("gerber", 'Combo_Gerber', initialize)
        self.app.should_we_save = True

    def on_custom_origin(self, use_thread=True):
        """
        Move selected objects to be centered in certain standard locations of the object (corners and center).
        :param use_thread: Control if to use threaded operation. Boolean.
        :return:
        """

        obj_list = self.collection.get_selected()

        if not obj_list:
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed. No object(s) selected..."))
            return

        choices = [
            {"label": _("Quadrant 2"), "value": "tl"},
            {"label": _("Quadrant 1"), "value": "tr"},
            {"label": _("Quadrant 3"), "value": "bl"},
            {"label": _("Quadrant 4"), "value": "br"},
            {"label": _("Center"), "value": "c"}
        ]
        dia_box = DialogBoxChoice(title='%s:' % _("Custom Origin"),
                                  icon=QtGui.QIcon(self.app.resource_location + '/origin3_32.png'),
                                  choices=choices,
                                  default_choice='c',
                                  parent=self.app.ui)
        if dia_box.ok is True:
            try:
                location_point = dia_box.location_point
            except Exception:
                return
        else:
            return

        def worker_task():
            with self.app.proc_container.new('%s ...' % _("Custom Origin")):

                xminlist = []
                yminlist = []
                xmaxlist = []
                ymaxlist = []

                # first get a bounding box to fit all
                for obj in obj_list:
                    xmin, ymin, xmax, ymax = obj.bounds()
                    xminlist.append(xmin)
                    yminlist.append(ymin)
                    xmaxlist.append(xmax)
                    ymaxlist.append(ymax)

                # get the minimum x,y for all objects selected
                x0 = min(xminlist)
                y0 = min(yminlist)
                x1 = max(xmaxlist)
                y1 = max(ymaxlist)

                if location_point == 'bl':
                    location = (x0, y0)
                elif location_point == 'tl':
                    location = (x0, y1)
                elif location_point == 'br':
                    location = (x1, y0)
                elif location_point == 'tr':
                    location = (x1, y1)
                else:
                    # center
                    cx = x0 + abs((x1 - x0) / 2)
                    cy = y0 + abs((y1 - y0) / 2)
                    location = (cx, cy)

                for obj in obj_list:
                    obj.offset((-location[0], -location[1]))
                    self.app_obj.object_changed.emit(obj)

                    # Update the object bounding box options
                    a, b, c, d = obj.bounds()
                    obj.obj_options['xmin'] = a
                    obj.obj_options['ymin'] = b
                    obj.obj_options['xmax'] = c
                    obj.obj_options['ymax'] = d

                    # make sure to update the Offset field in Properties Tab
                    try:
                        obj.set_offset_values()
                    except AttributeError:
                        # not all objects have this attribute
                        pass

                for obj in obj_list:
                    obj.plot()
                self.app.plotcanvas.fit_view()

                for obj in obj_list:
                    out_name = obj.obj_options["name"]

                    if obj.kind == 'gerber':
                        obj.source_file = self.app.f_handlers.export_gerber(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                    elif obj.kind == 'excellon':
                        obj.source_file = self.app.f_handlers.export_excellon(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                    elif obj.kind == 'geometry':
                        obj.source_file = self.app.f_handlers.export_dxf(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)

                self.inform.emit('[success] %s...' % _('Origin set'))

        if use_thread is True:
            self.worker_task.emit({'fcn': worker_task, 'params': []})
        else:
            worker_task()
        self.app.should_we_save = True
