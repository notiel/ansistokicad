import re
import json

extras = {"\"Soln", "\"Range", "\"SourceEntry", "\"StockNameIDMap", "\"CursorBoxBg", "\"Color", "\"LineColor",
          "\"SymbolColor", "\"AxisColor"}

doubled = {"MoveBackwards", "VariableProp", "AnsoftRangedIDServer", "Operation", "TolVt", "GeometryPart", 'Edge', "DependencyObject",
          "DependencyInformation", "GeometryPosition", "Range", "Sweep", "Solution", "SimValue", "Soln", "TraceComponentDefinition",
           "TraceDef", "MainMapItem", "SubMapItem", "ListItem", "IDMapItem", "Graph2D"}

def prepare_json(text: str)->str:
    """
    function makes first changes in source file: begin -> {, end -> }, <> -> less/more, ' -> "
    function deletes project preview block
    :param text: whole text
    :return: text corrected
    """
    text = re.sub('\$begin ', '{', text)
    text = re.sub('\$end \'[\w\s]*\'\n', '},\n', text)
    text = re.sub('\'\"', '\"', text)
    text = re.sub('\"\'', '\"', text)
    text = re.sub("'", "\"", text)
    text = re.sub("\"\"", "\" \"", text)
    text = re.sub(">=", "moreequal", text)
    text = re.sub("<=", "lessequal", text)
    text = re.sub(">", "more", text)
    text = re.sub("<=", "less", text)
    i = text.index("{\"ProjectPreview\"")
    text = text[:i]
    return text

def special_changes(s:str) -> str:
    """
    changes based on file structure
    :param s: string to change
    :return: result
    """
    if "GroupByMaterial" in s:
        s = s.replace("(", "\":{")
        s = s.replace(')', "},")
        s = s.replace("=", ':')
        s = '\"' + s + '\n'
        return s
    if "3D Modeler" in s:
        temp = s[12:]
        temp = temp.replace(r'"', r'\"')
        temp = "\"" + temp + "\""
        s = "\"3D Modeler\":" + temp
        return s
    if "bG(" in s:
        s = s.replace(r'"', r'\"')
        s = s.replace("(", "\":\"(")
        s = '\"' + s + '\",\n'
        return s
    if "view(" in s or "WindowPos(" in s or "R3DWindowPos(" in s:
        s = s.replace(': \"dB(GainTotal)\"', ": dB(GainTotal)")
        s = s.replace("(", "\":\"(", 1)
        s = '\"' + s + '\"'
        return s
    if r'="S(' in s or '\"re(' in s or '\"im(' in s:
        s = s.replace("=", "\":")
        s = '\"' + s + ',\n'
        return s
    return ""

def correct_data(s: str)->str:
    """
    some source-file-specific changes
    :param s: source string
    :return: result
    """
    if "SweptValues" in s:
        s = s.replace(r'"', r'\"')
        return s
    if "SimValueID" in s:
        s = s.replace("SimValueID=", "\"SimValueID\", ")
        return s
    if "dB(" in s:
        s = s.replace('(', "!")
        s = s.replace(')', "!")
        return s
    return s

def bracket_string_rool(s:str)->str:
    """

    :param s:
    :return:
    """
    temp = s.replace('(', '\": [', 1)
    temp = temp[::-1]
    temp = temp.replace(')', ',]', 1)
    temp = temp[::-1]
    temp = '\"' + temp
    if 'oa' in temp:
        new_temp = (temp.split('oa')[-1])
        new_temp = new_temp[1:-3]
        data = new_temp.split(', ')
        new_data = []
        for d in data:
            d = d.replace('=', '\": ')
            d = '\"' + d
            new_data.append(d)
            data = ', '.join(new_data)
        temp = temp.split('oa')[0] + '{\"oa\": {' + data + '}} ],'
    for word in extras:
        if word in temp:
            i = temp.index("[")
            j = temp.index(']')
            new_temp = temp[i + 1:j]
            data = new_temp.split(", ")
            new_data = []
            for d in data:
                d = d.replace('=', "\": ")
                d = '\"' + d
                new_data.append(d)
            data = ', '.join(new_data)
            temp = word + "\": {" + data + "},"
    return temp

def equals_string_rool(s: str)->str:
    temp = s.split('=')
    if (temp[1][0] != '$') and (temp[1][0] != '#'):
        new = '\"%s\": %s,\n' % (temp[0], temp[1])
        return new
    else:
        return '\"%s\": \"%s\",\n' % (temp[0], temp[1])

def string_handler(s):
    s = re.sub("\t", "", s)
    temp = special_changes(s)
    if temp != "":
        return temp
    s = correct_data(s)
    if s[0] == '{':
        return s[1:] + ':{\n'
    if '(' in s and '=\"(' not in s:
        return bracket_string_rool(s) + '\n'
    if '=' in s:
        return equals_string_rool(s)
    if '[' in s:
        temp = s.split('[')
        return '\"%s\": \"[%s\",\n' % (temp[0], temp[1])
    return s + '\n'

def create_first_json(filename: str):

    f = open(filename + '.hfss')
    g = open(filename + '.json', "w")
    text = f.read()
    text = prepare_json(text)
    g.write('{')
    text = text.split('\n\t')
    for s in text:
        g.write(string_handler(s))
    g.write('}')
    g.close()
    return

def replace_with_count(text: str)->str:
    """

    :param text:
    :return:
    """

    for word in doubled:
        i = 0
        templ = '\"'+word+'\"'
        while templ in text:
            text = text.replace(word+'\"', word+str(i)+'\"', 1)
            i+=1
    return text



def create_second_json(filename:str):
    g = open(filename + '.json')
    text = g.read()
    text = replace_with_count(text)
    text = re.sub(',\n*}', '}', text)
    text = re.sub('\""', "\"", text)
    # text = re.sub('\"\"\n', '', text)
    g.close()
    g = open(filename + '.json', "w")
    g.write(text)


def get_coordinates(filename):
    g = open(filename + '.json')
    data = json.loads(g.read())
    data = data['AnsoftProject']['HFSSModel']['ModelSetup']['GeometryCore']['GeometryOperations']['ToplevelParts']
    res = ""
    for key in data.keys():
        operations = data[key]['Operations']
        for operation in operations.keys():
            if operations[operation]['OperationType'] == 'CoverLines':
                faces = operations[operation]['OperationIdentity']['GeomTopolBasedOperationIdentityHelper']['NewFaces']
                points = faces['Face']['FaceGeomTopol']['FaceGeometry']['FcTolVts']
                s = ""
                for point in points.keys():
                    s += ("(xy %.6f %.6f) " % (points[point][0], points[point][1]))
                s = s[:-2]
                s += ')\n    '
                res+=s
    res = res[:-5]
    return res

def write_to_file(filename:str, res: str):
    """
    :param filename:
    :return:
    """
    f = open(filename+".kicad_mod", "w")
    f.write("(module %s\n" % filename)
    f.write("  (fp_poly (pts " + res)
    f.write("))\n)")
    f.close()

def main ():
    filename = 'IFA_Mushrooms_Exploded'
    create_first_json(filename)
    create_second_json(filename)
    res = get_coordinates(filename)
    write_to_file(filename, res)

if __name__ == '__main__':
    main()

