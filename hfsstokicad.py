import re
import json
import sys
from os import remove
from dataclasses import dataclass
from typing import List, Any, Dict, Tuple
import math

# doubled hssf elements (should be replaced with Element0..EleemntN to validate json file)
doubled = {"MoveBackwards", "VariableProp", "AnsoftRangedIDServer", "Operation", "TolVt", "GeometryPart",
           "PLSegment", 'Edge', "DependencyObject", "PLPoint", "DependencyInformation", "GeometryPosition", "Range",
           "Sweep", "Solution", "SimValue", "Soln", "TraceComponentDefinition", "TraceDef", "MainMapItem", "SubMapItem",
           "ListItem", "IDMapItem", "Graph2D"}

# PCB elements excluded for result
exclude_names = {"Port", "Top", "Bottom"}

deg_delta = 0.1


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Arc:
    number_of_point: int
    startindex: int
    type: str
    angle: float = 0
    center_x: float = 0
    center_y: float = 0
    numberofsegments: int = 0


def prepare_json(text: str) -> str:
    """
    function makes first changes in whole source file:
    begin -> {, end -> }, ' -> ", removes quotes,  screens #
    function removes tabulations and deletes project preview block
    :param text: whole text
    :return: text corrected
    """

    # rule0: remove files part
    i = text.find(r"$end 'AnsoftProject'")
    text = text[: i + len(r"$end 'AnsoftProject'")]
    text += '\n'

    # rule1: remove tabulations
    text = re.sub(r"\t", "", text)

    # rule2: remove doubled quotes
    text = re.sub('\'\"|\"\'', r'"', text)

    # rule3 change quotes ' -> "
    text = re.sub(r"'", r'"', text)

    # rule4: $begin "Attribute" -> "Attribute":{
    templ = re.compile(r'\$begin "([\w| ]*)"\n')
    text = templ.sub(r'"\1":{\n', text)

    # rule5: $end "Attribute" -> }
    text = re.sub(r'\$end \"?[\w\s]*\"\n', "},\n", text)

    # rule6 screens # symbol
    templ = re.compile(r'#([\w]+)')
    text = templ.sub(r'"\1"', text)

    # rule7 function()) -> 'function<text>)' (if no spaces)
    templ = re.compile(r'(\w*)\(( *)\)\)')
    text = templ.sub(r'"\1<\2>")', text)

    return text


def data_correct(text: str) -> str:
    """
    some text corrections for hssf
    :param text:
    :return:
    """

    # rule8 '. ' -> "" (remove dor with space)
    text = text.replace(". ", "")

    # rule9 '[value: value]' -> 'value-value for Level strings'
    if 'Level' in text:
        templ = re.compile(r'\[(-?\d+\.?\d*): (-?\d+)]')
        text = templ.sub(r'\1-\2', text)

    # rule10 ": " -> ", "
    text = re.sub("[^ ]: ", ", ", text)

    # rule11 '(R=R1, G=G1, B=B1) - > ({R=R1}, {G=G1}, {B=B1})'
    if 'Color' in text:
        templ = re.compile(r'\(R=(\d+), G=(\d+), B=(\d+)\)')
        text = templ.sub(r'({"R": \1}, {"G": \2}, {"B": \3})', text)

    # rule12 '[, ' -> [
    text = text.replace(r'[, ', '[')

    # rule13: special rule for strings like Name='max(dB(S(1,1)))'
    templ = re.compile(r'\(?(d?B?)\(?[SZ]\(1[,;]1\)\)?\)?')
    text = templ.sub(r'<\1<S<1.1>>>', text)

    # rule14: special rule for db(S(1, 1))
    templ = re.compile(r'dB\(([^\)]*)\)')
    text = templ.sub(r'db<\1>', text)

    # rule15: special rule for theta-rho-phi(0)
    if "theta-rho-phi(0)" in text:
        text = text.replace("(0)", "<0>")

    # rule16: fix SimVAlueID parameter
    if "SimValueID" in text:
        text = text.replace("SimValueID=", "\"SimValueID\", ")

    # rule17 handle special words $begin_data and $end_data
    templ = re.compile(r"\$begin_cdata\$(.)*?\$end_cdata\$")
    text = templ.sub(r'"start_data \1end_data"', text)

    # rule18 for Height()
    if 'Height' in text and 'if' in text:
        text = text.replace('(', '<')
        text = text.replace(')', '>')
        text = text.replace(',', ';')

    return text


def special_rules(text: str) -> str:
    """
    some special rules for unhandable hssf strings
    :param text: string to correct
    :return: corrected string
    """
    if "3D Modeler" in text:
        templ = re.compile(r'("3D Modeler")(.*)')
        temp = templ.sub(r'\2', text)
        temp = temp.replace(r'"', r'\"')
        return r'"3D Modeler":"' + temp + r'",'

    if "R3DWindowPos(Editor3d())" in text:
        text = text.replace(r'R3DWindowPos(Editor3d())', r'"R3DWindowPos":"Editor3d()",')
        return text

    if 'Circuit(Editor3d(View(WindowPos' in text:
        text = "\n"
        return text

    if "cam(XYCam" in text or "cam(PolCam" in text:
        text = "\"" + text[:4] + "\":\"" + text[4:] + "\","
        return text

    if "R3DWindowPos(" in text:
        text = text.replace(r'"', r'\"')
        text = "\"" + text[:12] + "\":\"" + text[12:] + "\","
        return text

    if "WindowPos(" in text and text.index("WindowPos") == 0:
        text = "\"" + text[:9] + "\":\"" + text[9:] + "\","
        return text

    return ""


def string_handler(text: str) -> str:
    """
    functions applies regexp rules to string to make it part of valid json
    :param text: string
    :return: corrected string
    """

    temp = special_rules(text)
    if temp:
        return temp

    text = data_correct(text)

    # rule19: comma in the middle of text (without space) becomes ;
    templ = re.compile(r',([^ ])')
    text = templ.sub(r';\1', text)

    # rule20: attribute=value(data) -> 'attribute':'value(data)'
    templ = re.compile(r'"?(\w+)"?="?(\w+)\((\w+)\)"?')
    temp = templ.sub(r'"\1":"\2(\3)",', text)
    if temp != text:
        return temp

    # rule21: (id=value, id1 = value1) -> ("id"->"value", "id1"->"value1")
    templ = re.compile(r'([\w ]+)\(([^\)]*)\)')
    res = templ.findall(text)
    for r in res:
        templ2 = re.compile(r'"?([\w-]+)"?="?([^,\)"])*"?')
        for data in r:
            text = templ2.sub(r'"\1":"\2"', text)

    # rule22 blabala attribute(text)  -> blabbla {"attribute":{"text"}}
    #      attribute(text)  -> "attribute":{"text"}
    templ = re.compile(r'"?([\w]+)"?\(([\w "-]+):([^\)]+)\)')
    res = templ.search(text)
    if res is not None:
        if res.start() == 0:
            text = templ.sub(r'"\1":{\2:\3},', text)
        else:
            text = templ.sub(r'{"\1":{\2:\3}}', text)

    # rule 23: Attribute="value" -> "Attribute":"value",
    #          Attribute=value -> "Attribute":value,
    #          "Attribute"=value -> "Attribute":value,
    #          Attribute = value, -> "Attribute":value
    templ = re.compile(r'"?([\w +-]*)"? ?= ?("?[^,]*"?),? ?')
    text = templ.sub(r'"\1":\2,', text)

    # rule 24: Attribute[value] -> "Attribute":"[value]" (without " in [])
    templ = re.compile(r'"?([\w ]+)"?(\[[^\]\"]*\])')
    text = templ.sub(r'"\1":"\2",', text)

    # rule 25: Attribute[...] -> "Attribute":[...],
    templ = re.compile(r'"?([\w ]+)"?\[([^\]]*)\]')
    text = templ.sub(r'"\1":[\2],', text)

    # rule 26: Attribute(values) -> "Attribute":[values],
    #        "Attribute"(values) -> "Attribute":[values],
    templ = re.compile(r'"?([\w ]+)"?\((.*)\)')
    text = templ.sub(r'"\1":[\2],', text)

    # rule27: remove extra commas
    text = re.sub(",,", ",", text)

    return text


def create_first_json(filename: str):
    f = open(filename, encoding='utf-8', errors='ignore')
    text = f.read()
    f.close()
    text = prepare_json(text)
    g = open(filename.split('.')[0] + '.json', "w", encoding='utf-8', errors='ignore')
    g.write('{')
    text = text.split('\n')
    for s in text:
        s = string_handler(s)
        g.write(s + '\n')
    g.write('}')
    g.close()
    return


def replace_with_count(text: str) -> str:
    """
    adds numeric counter to attributes from "doubled" list
    :param text: file content
    :return: corrected fole content
    """

    for word in doubled:
        i = 0
        templ = '\"' + word + '\"'
        while templ in text:
            text = text.replace(word + '\"', word + str(i) + '\"', 1)
            i += 1
    return text


def create_second_json(filename: str):
    """
    this function adds numeric endings to attributes name from "doubled" list and
    changes },} to }} in pre-json file created with create_first_json function
    :param filename: name of json file
    :return:
    """
    g = open(filename + '.json', encoding='utf-8', errors='ignore')
    text = g.read()
    text = replace_with_count(text)
    text = re.sub(',\n*}', '}', text)
    g.close()
    g = open(filename + '.json', "w", encoding='utf-8')
    g.write(text)
    g.close()


def get_variables(data: Dict[str, Any]):
    """
    gets variables list for data given
    :param data: data
    :return: dict with variables
    """
    res: Dict[str, Any] = dict()
    for key in data:
        res[data[key][0]] = data[key][3].replace("mm", "")
        try:
            res[data[key][0]] = float(res[data[key][0]])
        except ValueError:
            pass
    return res


def create_coord_dict(data: Dict[str, Any], res: Dict[int, List[str]]) -> Dict[int, List[str]]:
    """
    function gets list of rectangle coordinates from dict sctucture with data
    :param data: dict with file data
    :param res: dict to add data
    :return: new dict with data
    """
    for key in data.keys():
        name = data[key]['Attributes']['Name']
        if name not in exclude_names:
            operations = data[key]['Operations']
            for operation in operations.keys():
                if operations[operation]['OperationType'] == 'CoverLines':
                    faces = operations[operation]['OperationIdentity']['GeomTopolBasedOperationIdentityHelper'][
                        'NewFaces']
                    points = faces['Face']['FaceGeomTopol']['FaceGeometry']['FcTolVts']
                    point_array = []
                    for point in points.keys():
                        point_array.append(points[point])
                    res[int(key[12:])] = point_array
    return res


def add_parameters_value(parameters: Dict[str, Any], points: List[Point]):
    """
    custom function for parametrical parameters, change it for every antenna
    :param parameters: list of variables
    :param points: list of points
    :return:
    """
    angle_rad = float(parameters['Angle'].replace("deg", "")) / 180 * math.pi
    points[0].x = float(parameters['X02'][:4]) + parameters['W2']
    points[0].y = parameters['Y02'] - 0.2
    points[8].x = parameters['Y20'] - (parameters['Y22'] * math.cos(angle_rad) -
                                       parameters['X22'] * math.sin(angle_rad))
    points[8].y = parameters['X20'] - parameters['X22'] * math.cos(angle_rad) - parameters['Y22'] * math.sin(angle_rad)
    points[15].x = float(parameters['X02'][:4]) + parameters['W2']
    points[15].y = parameters['Y02'] - 0.2


def get_arc_data(data: Dict[str, Any], parameters: Dict[str, Any]) -> Tuple[List[Arc], List[Point]]:
    """
    create list with angle data
    :param parameters: list of variables
    :param data: dict with data
    :return:list of arc data
    """
    res_arcs: List[Arc] = list()
    res_points: List[Point] = list()
    try:
        for geometry_part in data.keys():
            operations = data[geometry_part]['Operations']
            for key in operations:
                if operations[key]['OperationType'] == 'Polyline':
                    arcs = operations[key]['PolylineParameters']['PolylineSegments']
                    for segment in arcs.keys():
                        if arcs[segment]['SegmentType'] == 'AngularArc':
                            try:
                                res_arcs.append(Arc(startindex=arcs[segment]['StartIndex'],
                                                    number_of_point=arcs[segment]['NoOfPoints'],
                                                    numberofsegments=int(arcs[segment]['NoOfSegments']),
                                                    angle=float(arcs[segment]['ArcAngle'].replace("deg", "")),
                                                    center_x=float(arcs[segment]['ArcCenterX'].replace('mm', "")),
                                                    center_y=float(arcs[segment]['ArcCenterY'].replace('mm', "")),
                                                    type="arc"))
                            except ValueError:
                                angle = -float(parameters['Angle'].replace("deg", "")) if "-" in arcs[segment][
                                    'ArcAngle'] \
                                    else float(parameters['Angle'].replace("deg", ""))
                                res_arcs.append(Arc(startindex=arcs[segment]['StartIndex'],
                                                    number_of_point=arcs[segment]['NoOfPoints'],
                                                    numberofsegments=int(arcs[segment]['NoOfSegments']),
                                                    angle=angle,
                                                    center_x=float(arcs[segment]['ArcCenterX'].replace('mm', "")),
                                                    center_y=float(arcs[segment]['ArcCenterY'].replace('mm', "")),
                                                    type="arc"))
                        if arcs[segment]['SegmentType'] == 'Line':
                            res_arcs.append(Arc(type="line",
                                                startindex=arcs[segment]['StartIndex'],
                                                number_of_point=arcs[segment]['NoOfPoints']))
                    points = operations[key]['PolylineParameters']['PolylinePoints']
                    for point in points.keys():
                        try:
                            res_points.append(Point(x=float(points[point]['X'].replace("mm", "")),
                                                    y=float(points[point]['Y'].replace("mm", ""))))
                        except ValueError:
                            res_points.append(Point(x=0, y=0))
        add_parameters_value(parameters, res_points)
    except KeyError:
        pass
    return res_arcs, res_points


def get_coordinates(filename: str):
    """
    function opens json file, converts to dict and gets coordinates of rectangles using special dictionary path
    :param filename: name of json file
    :return:
    """
    g = open(filename + '.json', encoding='utf-8', errors='ignore')
    data = json.loads(g.read())
    g.close()
    geometry_data = data['AnsoftProject']['HFSSModel']['ModelSetup']['GeometryCore']['GeometryOperations']
    res = dict()
    res = create_coord_dict(geometry_data['ToplevelParts'], res)
    res = create_coord_dict(geometry_data['OperandParts'], res)
    variables = get_variables(data['AnsoftProject']['HFSSModel']['ModelSetup']['Properties'])
    res_arcs, res_points = get_arc_data(geometry_data['ToplevelParts'], variables)
    return res, res_arcs, res_points


def get_indexes(coords: list) -> (int, int):
    """
    get indexes of coords elements
    :param coords: list with coords for example
    [[3, 15.12, 14.56, 0], [3, 13.32, 14.56, 0], [3, 13.32, 15.56, 0], [3, 15.12, 15.56, 0]]
    :return: indexes of coord elements (1, 2) here
    """
    indexes = []
    arr = [len(set(x)) for x in [[coords[i][j] for i in range(0, 4)] for j in range(0, 4)]]
    for i in range(0, 4):
        if arr[i] > 1:
            indexes.append(i)
    return indexes


def get_points_for_arc(arcs: List[Arc], res_points: List[Point], delta: float) -> List[Point]:
    """
    gets points for polilyne instead of arcs
    :param res_points: start points for arcs data
    :param delta: accuracy in degrees
    :param arcs: arcs with data
    :return: list of points with selected delta in degrees
    """
    poly_points: List[Point] = []
    for arc in arcs:
        if arc.type == "arc":
            start_point = res_points[arc.startindex]
            x: float = start_point.x
            y: float = start_point.y
            ang: float = arc.angle
            x_c: float = arc.center_x
            y_c: float = arc.center_y
            r: float = math.sqrt((x - x_c) * (x - x_c) + (y - y_c) * (y - y_c))
            start_angle: float = math.atan2(y - y_c, x - x_c) / math.pi * 180
            stop_angle: float = start_angle + ang
            if ang > 0:
                da: float = delta
                cond = lambda a: a < stop_angle
            else:
                da = -delta
                cond = lambda a: a > stop_angle
            a = start_angle
            while cond(a):
                x = x_c + r * math.cos(a / 180 * math.pi)
                y = y_c + r * math.sin(a / 180 * math.pi)
                poly_points.append(Point(x=x, y=y))
                a += da
        if arc.type == "line":
            start_point = res_points[arc.startindex]
            end_point = res_points[arc.startindex + 1]
            poly_points.append(Point(x=start_point.x, y=start_point.y))
            poly_points.append(Point(x=end_point.x, y=end_point.y))
    return poly_points


def get_kicad_line_for_polyline(poly_points: List[Point]) -> Tuple[str, str]:
    """
    gets list of points and returnes str with KiCad poly
    :param poly_points: points with lie data
    :return: string for KiCadPoly with this data
    """
    line1_res = '(fp_poly (pts '
    line2_res = '(fp_poly (pts '
    for p in poly_points:
        line1_res += '( xy %f %f)\n' % (p.x, p.y)
        line2_res += '( xy %f %f)\n' % (-p.x, p.y)
    line1_res += ") (layer F.Cu) (width 0.001)) \n"
    line2_res += ") (layer F.Cu) (width 0.001)) \n"
    return line1_res, line2_res


def write_to_files(filename: str, res: dict, arcs: List[Arc], res_points: List[Point]):
    """
    function creates kicad_mod files (direct and inverted)
    :param res_points: list of start points data
    :param arcs: list of arcs data
    :param filename: name of file
    :param res: dict with coordinates
    :return:
    """
    f1 = open(filename + ".kicad_mod", "w")
    f1.write("(module %s\n" % filename)
    f2 = open(filename + "_inverted.kicad_mod", "w")
    f2.write("(module %s\n" % filename)
    [i, j] = get_indexes(res[list(res.keys())[0]])

    for rect in res.keys():
        points = res[rect]
        if len(points) == 4 and abs((points[1][0] - points[0][0]) * (points[0][1] - points[1][1])) < 200:
            s1 = "  (fp_poly (pts "
            s2 = "  (fp_poly (pts "
            for point in points:
                s1 += ("(xy %.6f %.6f) " % (point[i], point[j]))
                s2 += ("(xy %.6f %.6f) " % (0 - point[i], point[j]))
            f1.write(s1[:-1] + ") (layer F.Cu) (width 0.001) )\n" + "   ")
            f2.write(s2[:-1] + ") (layer F.Cu) (width 0.001) )\n" + "   ")

    poly_points: List[Point] = get_points_for_arc(arcs, res_points, deg_delta)
    if poly_points:
        line1_res, line2_res = get_kicad_line_for_polyline(poly_points)
        f1.write(line1_res)
        f2.write(line2_res)
    f1.write(")")
    f1.close()
    f2.write(")")
    f2.close()


def main(filename: str) -> bool:
    try:
        create_first_json(filename)
    except FileNotFoundError:
        print("File %s not found" % filename)
        return False
    filename = filename.split('.')[0]
    create_second_json(filename)

    try:
        res, arc, points = get_coordinates(filename)
    except json.decoder.JSONDecodeError:
        print("Json failed")
        return False

    remove(filename + '.json')

    new_keys = sorted(res.keys())
    new_res = {}
    for key in new_keys:
        new_res[key] = res[key]
    write_to_files(filename, new_res, arc, points)
    print("%s.kicad_mod created, %s_inverted.kicad_mod created" % (filename, filename))
    return True


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("File name required")
