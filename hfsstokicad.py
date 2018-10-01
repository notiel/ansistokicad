import re
import json
import sys
from os import remove

# doubled hssf elements (should be replaced with Element0..EleemntN to validate json file)
doubled = {"MoveBackwards", "VariableProp", "AnsoftRangedIDServer", "Operation", "TolVt", "GeometryPart", 'Edge',
           "DependencyObject",
           "DependencyInformation", "GeometryPosition", "Range", "Sweep", "Solution", "SimValue", "Soln",
           "TraceComponentDefinition",
           "TraceDef", "MainMapItem", "SubMapItem", "ListItem", "IDMapItem", "Graph2D"}

# PCB elements excluded for result
exclude_names = {"Port", "Top", "Bottom"}


def prepare_json(text: str) -> str:
    """
    function makes first changes in whole source file:
    begin -> {, end -> }, ' -> ", removes quotes,  screens #
    function removes tabulations and deletes project preview block
    :param text: whole text
    :return: text corrected
    """

    # rule1: remove tabulations
    text = re.sub(r"\t", "", text)

    # rule2: remove doubled quotes
    text = re.sub('\'\"|\"\'', r'"', text)

    # rule3 ' -> "
    text = re.sub(r"'", r'"', text)

    # rule4: $begin "Attribute" -> "Attribute":{
    templ = re.compile(r'\$begin "([\w| ]*)"\n')
    text = templ.sub(r'"\1":{\n', text)

    # rule5: $end "Attribute" -> }
    text = re.sub('\$end \"?[\w\s]*\"\n', "},\n", text)

    # rule6 screens # symbol
    templ = re.compile(r'#([\w]+)')
    text = templ.sub(r'"\1"', text)

    # rule7 function()) -> 'function<text>)' (if no spaces)
    templ = re.compile(r'(\w*)\(( *)\)\)')
    text = templ.sub(r'"\1<\2>")', text)

    # rule 8 ": " -> ", "
    text = re.sub("[^ ]: ", ", ", text)

    # remove ProjectPreview part
    i = text.index(r'"ProjectPreview":{')
    text = text[:i]

    return text


def data_correct(text: str) -> str:
    """
    some text corrections for hssf
    :param text:
    :return:
    """

    # rule9: special rule for strings like Name='max(dB(S(1,1)))'
    templ = re.compile(r'\(?(d?B?)\(?[SZ]\(1[,;]1\)\)?\)?')
    text = templ.sub(r'<\1<S<1.1>>>', text)

    # rule10: special rule for db(S(1, 1))
    templ = re.compile(r'dB\(([^\)]*)\)')
    text = templ.sub(r'db<\1>', text)

    # rule11: special rule for theta-rho-phi(0)
    if "theta-rho-phi(0)" in text:
        text = text.replace("(0)", "<0>")

    # rule12: fix SimVAlueID parameter
    if "SimValueID" in text:
        text = text.replace("SimValueID=", "\"SimValueID\", ")

    # rule13 escape characters for quotes in strings with SweptVAlue parameter
    #if "SweptValues" in text:
    #    text = text.replace(r'"', r'\"')

    # rule14 handle special words $begin_data and $end_data
    templ = re.compile(r"\$begin_cdata\$(.)*?\$end_cdata\$")
    text = templ.sub(r'"start_data \1end_data"', text)

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

    if 'Height' in text:
        print(text)
    temp = special_rules(text)
    if temp:
        return temp

    text = data_correct(text)

    # rule15: comma in the middle of text (without space) becomes ;
    templ = re.compile(r',([^ ])')
    text = templ.sub(r';\1', text)

    # rule16: attribute=value(data) -> 'attribute':'value(data)'
    templ = re.compile(r'"?(\w+)"?="?(\w+)\((\w+)\)"?')
    temp = templ.sub(r'"\1":"\2(\3)",', text)
    if temp != text:
        return temp


    # rule17: (id=value, id1 = value1) -> ("id"->"value", "id1"->"value1")
    templ = re.compile(r'([\w ]+)\(([^\)]*)\)')
    res = templ.findall(text)
    for r in res:
        templ2 = re.compile(r'"?([\w-]+)"?="?([^,\)"])*"?')
        for data in r:
            text = templ2.sub(r'"\1":"\2"', text)

    # rule18 blabala attribute(text)  -> blabbla {"attribute":{"text"}}
    #      attribute(text)  -> "attribute":{"text"}
    templ = re.compile(r'"?([\w]+)"?\(([\w "-]+):([^\)]+)\)')
    res = templ.search(text)
    if res is not None:
        if res.start() == 0:
            text = templ.sub(r'"\1":{\2:\3},', text)
        else:
            text = templ.sub(r'{"\1":{\2:\3}}', text)

    # rule 19: Attribute="value" -> "Attribute":"value",
    #          Attribute=value -> "Attribute":value,
    #          "Attribute"=value -> "Attribute":value,
    #          Attribute = value, -> "Attribute":value
    templ = re.compile(r'"?([\w +-]*)"? ?= ?("?[^,]*"?),? ?')
    text = templ.sub(r'"\1":\2,', text)

    # rule 20: Attribute[value] -> "Attribute":"[value]" (without " in [])
    templ = re.compile(r'"?([\w ]+)"?(\[[^\]\"]*\])')
    text = templ.sub(r'"\1":"\2",', text)

    # rule 21: Attribute[...] -> "Attribute":[...],
    templ = re.compile(r'"?([\w ]+)"?\[([^\]]*)\]')
    text = templ.sub(r'"\1":[\2],', text)

    # rule 22: Attribute(values) -> "Attribute":[values],
    #        "Attribute"(values) -> "Attribute":[values],
    templ = re.compile(r'"?([\w ]+)"?\((.*)\)')
    text = templ.sub(r'"\1":[\2],', text)

    # rule23: remove extra commas
    text = re.sub(",,", ",", text)

    return text


def create_first_json(filename: str):
    f = open(filename)
    text = f.read()
    f.close()
    text = prepare_json(text)
    g = open(filename.split('.')[0] + '.json', "w")
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
    g = open(filename + '.json')
    text = g.read()
    text = replace_with_count(text)
    text = re.sub(',\n*}', '}', text)
    g.close()
    g = open(filename + '.json', "w")
    g.write(text)


def create_coord_dict(data: dict, res: dict) -> dict:
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


def get_coordinates(filename: str):
    """
    function opens json file, converts to dict and gets coordinates of rectangles using special dictionary path
    :param filename: name of json file
    :return:
    """
    g = open(filename + '.json')
    data = json.loads(g.read())
    g.close()
    data1 = data['AnsoftProject']['HFSSModel']['ModelSetup']['GeometryCore']['GeometryOperations']['ToplevelParts']
    data2 = data['AnsoftProject']['HFSSModel']['ModelSetup']['GeometryCore']['GeometryOperations']['OperandParts']
    res = dict({})
    res = create_coord_dict(data1, res)
    res = create_coord_dict(data2, res)
    return res

def get_indexes(coords: list) -> (int, int):
    """
    get indexes of coords elements
    :param coords: list with coords for example
    [[3, 15.12, 14.56, 0], [3, 13.32, 14.56, 0], [3, 13.32, 15.56, 0], [3, 15.12, 15.56, 0]]
    :return: indexes of coord elements (1, 2) here
    """
    indexes = []
    arr  = [len(set(x)) for x in [[coords[i][j] for i in range (0, 4)] for j in range (0, 4)]]
    for i in range(0,4):
        if arr[i] > 1:
            indexes.append(i)
    return indexes


def write_to_files(filename: str, res: dict):
    """
    function creates kicad_mod files (direct and inverted)
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
        if len(points) < 2 and abs(points[1][0] - points[0][0]) < 30:
            s1 = "  (fp_poly (pts "
            s2 = "  (fp_poly (pts "
            for point in points:
                s1 += ("(xy %.6f %.6f) " % (point[i], point[j]))
                s2 += ("(xy %.6f %.6f) " % (0-point[i], point[j]))
            f1.write(s1[:-1] + ") (layer F.Cu) (width 0.001) )\n" + "   ")
            f2.write(s2[:-1] + ") (layer F.Cu) (width 0.001) )\n" + "   ")
    f1.write(")")
    f1.close()
    f2.write(")")
    f2.close()


def main(filename):
    try:
        create_first_json(filename)
    except FileNotFoundError:
        print("File %s not found" % (filename))
        return
    filename = filename.split('.')[0]
    create_second_json(filename)

    try:
        res = get_coordinates(filename)
    except json.decoder.JSONDecodeError:
        print("Json failed")
        return

    # remove(filename + '.json')

    new_keys = sorted(res.keys())
    new_res = {}
    for key in new_keys:
        new_res[key] = res[key]
    write_to_files(filename, new_res)
    print("%s.kicad_mod created, %s_inverted.kicad_mod created" % (filename, filename))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("File name required")
