import csv
import query_parser as parse
import operator
import re


def is_number(s):
    try:
        float(s)  # for int, long and float
    except ValueError:
        try:
            complex(s)  # for complex
        except ValueError:
            return False

    return True


def get_truth(attr, value, op):
    ops = {'>': operator.gt,
           '<': operator.lt,
           '>=': operator.ge,
           '<=': operator.le,
           '=': operator.eq,
           '<>': operator.ne,
           'LIKE': like_op,
           'NOT LIKE': not_like_op
           }
    if is_number(attr) and is_number(value):
        return ops[op](float(attr), float(value))
    return ops[op](attr, value)


def like_op(before_se, query):
    """
    before_se is a list of list from previous stage, query is LIKE clause which is a pattern, string after LIKE
    :param before_se:
    :param query:
    :return:
    """
    keyword = re.compile(r'[a-z A-Z 0-9]+')
    keyword = keyword.findall(query)
    keyword = keyword[0] #now we have the STRING we are going to match

    pattern1 = re.compile(r'^%{}%$'.format(keyword))	#1 %str%
    pattern2 = re.compile(r'^%{}$'.format(keyword))   #2 %str
    pattern3 = re.compile(r'^{}%$'.format(keyword))   #3 str%
    pattern4 = re.compile(r'^{}$'.format(keyword))    #4 str
    pattern5 = re.compile(r'^_{}_$'.format(keyword))  #5 _str_
    pattern6 = re.compile(r'^_{}$'.format(keyword))   #6 _str
    pattern7 = re.compile(r'^{}_$'.format(keyword))   #7 str_
    pattern8 = re.compile(r'^%{}_$'.format(keyword))  #8 %str_
    pattern9 = re.compile(r'^_{}%$'.format(keyword))  #9 _str%

    q_pattern = None

    if re.match(pattern1, query) != None:
        q_pattern = re.compile(r'^.*{}.*$'.format(keyword))
    elif re.match(pattern2, query) != None:
        q_pattern = re.compile(r'^.*{}$'.format(keyword))
    elif re.match(pattern3, query) != None:
        q_pattern = re.compile(r'^{}.*$'.format(keyword))
    elif re.match(pattern4, query) != None:
        q_pattern = re.compile(r'^{}$'.format(keyword))
    elif re.match(pattern5, query) != None:
        q_pattern = re.compile(r'^.{}.$'.format(keyword))
    elif re.match(pattern6, query) != None:
        q_pattern = re.compile(r'^.{}$'.format(keyword))
    elif re.match(pattern7, query) != None:
        q_pattern = re.compile(r'^{}.$'.format(keyword))
    elif re.match(pattern8, query) != None:
        q_pattern = re.compile(r'^.*{}.$'.format(keyword))
    elif re.match(pattern9, query) != None:
        q_pattern = re.compile(r'^.{}.*$'.format(keyword))
    if re.match(q_pattern, before_se) != None:
        return 1
    return 0


def not_like_op(before_se, query):
    return not like_op(before_se, query)


def reorder_condition(file_map, conditions, keyword):
    if ('AND' in keyword and 'OR' not in keyword) or ('OR' in keyword and 'AND' not in keyword):
        priority = list()
        for cond in conditions:
            if len(cond[0]) == 2 and len(cond[1]) == 1:
                priority.append(0)
            elif len(cond[0]) == 2 and len(cond[1]) == 2 and cond[0][0] == cond[1][0]:
                priority.append(1)
            elif len(cond[0]) == 2 and len(cond[1]) == 2 and cond[2] == '=':
                priority.append(2)
            else:
                priority.append(3)
        new_conditions = list()
        for p in range(0, 4):
            for i in range(len(priority)):
                if priority[i] == p:
                    new_conditions.append(conditions[i])
                    priority[i] = -1
        return new_conditions
    elif 'OR' in keyword:
        for cond in conditions:
            if len(cond[0]) == 2 and len(cond[1]) == 2:
                if conditions.index(cond) == 0 or conditions.index(cond) == len(conditions) - 1:
                    pass
                elif keyword[conditions.index(cond)-1] != 'OR' and keyword[conditions.index(cond)] != 'OR':
                    tmp = cond
                    conditions.remove(cond)
                    conditions.append(tmp)
        return conditions
    else:
        return conditions


def decompose_condition(cond):
    """
    return decomposition of single condition
    :param cond:
    :return: target, value, op
    """
    if len(cond[0]) == 1:
        target = cond[0][0]
    else:
        target = cond[0][1].lower()
    if len(cond[1]) == 1:
        value = cond[1][0]
    else:
        value = cond[1][1].lower()
    op = cond[2]
    return target, value, op


def get_index(filename, attr):
    """
    find the index of one attribute
    :param filename:
    :param attr:
    :return: integer
    """
    try:
        my_file = open(filename, 'r', encoding='utf8')
        reader = csv.reader(my_file)
        attrs_set = [attr.lower() for attr in next(reader)]
        my_file.close()
        try:
            return attrs_set.index(attr.lower())
        except ValueError:
            print('No such attribute:', attr)
    except Exception:
        print('No such file:', filename)
    return -1


def checkrow(tf, op):
    if len(tf)==1:
        return(eval(tf[0]))
    n = 0
    ss = ''
    for st in range(len(tf)):
        while (n<len(op)):
            if op[n] in ['(', 'NOT']:
                ss = ss+op[n]+' '
                n += 1
            else:
                break
        ss = ss+tf[st]+' '
        if n<len(op):
            if op[n] in [')']:
                ss = ss+op[n]+' '
                n += 1
        if st<(len(tf)-1):
            ss = ss+op[n]+' '
            n+=1
    return(eval(ss.lower()))


def project(tuples, file_map, file_rename, attributes):
    if attributes[0][0] == '*':
        res = list()
        for i in range(len(tuples[0])):
            tmp = list()
            for file_idx in range(len(file_rename)):
                tmp.append(tuples[file_idx][i])
            res.append(tmp)
    else:
        res = list()
        file_idx = [file_rename.index(attribute[0]) for attribute in attributes]
        attr_idx = [get_index(file_map[attribute[0]], attribute[1].lower()) for attribute in attributes]
        for i in range(len(tuples[0])):
            tmp = list()
            for j in range(len(attr_idx)):
                tmp.append(tuples[file_idx[j]][i][attr_idx[j]])
            res.append(tmp)
    return res


def select(tuples, file_rename, file_map, keyword, cond):
    if len(cond[0]) == 2 and len(cond[1]) == 2:
        if keyword == '':
            if len(file_rename) == 2:
                if cond[0][0] == cond[1][0]:
                    return select_two(tuples, file_rename, file_map, keyword, cond)
                else:
                    return join_two(tuples, file_rename, file_map, keyword, cond)
        elif keyword == 'AND':
            if len(file_rename) == 2:
                if len(tuples[0]) == len(tuples[1]) or cond[0][0] == cond[1][0]:
                    return select_two(tuples, file_rename, file_map, keyword, cond)
                else:
                    return join_two(tuples, file_rename, file_map, keyword, cond)
            elif len(file_rename) == 3:
                if len(tuples[file_rename.index(cond[0][0])]) == len(tuples[file_rename.index(cond[1][0])]) or cond[0][0] == cond[1][0]:
                    return select_three(tuples, file_rename, file_map, keyword, cond)
                else:
                    return join_three(tuples, file_rename, file_map, keyword, cond)
        elif keyword == 'OR':
            if len(file_rename) == 2:
                if cond[0][0] == cond[1][0]:
                    pass
                else:
                    if len(tuples[0]) == len(tuples[1]) and len(tuples[0]) > 0:
                        tmp = [[], []]
                        tmp = join_two(tmp, file_rename, file_map, keyword, cond)
                        return merge(tuples, tmp, keyword)
                    else:
                        pass
        else:
            pass
    elif len(cond[0]) == 2 and len(cond[1]) == 1:
        file_index = file_rename.index(cond[0][0])
        filename = file_map[cond[0][0]]
        attr_index = get_index(filename, cond[0][1])
        return update_one(tuples, filename, file_index, attr_index, cond, keyword)
    else:
        pass
    print("Unexpected error in select(), some conditions might be missing")
    return tuples


def update_one(tuples, filename, file_index, attr_index, cond, keyword):
    left, right, op = decompose_condition(cond)
    if len(tuples[file_index]) == 0:
        new_tuples = list()
        my_file = open(filename, 'r', encoding='utf8')
        reader = csv.reader(my_file)
        for row in reader:
            if get_truth(row[attr_index], right, op):
                new_tuples.append(row)
        my_file.close()
    else:
        if keyword == 'AND':
            new_tuples = list()
            for row in tuples[file_index]:
                if get_truth(row[attr_index], right, op):
                    new_tuples.append(row)
        elif keyword == 'OR' or keyword == '':
            new_tuples = tuples[file_index]
            my_file = open(filename, 'r', encoding='utf8')
            reader = csv.reader(my_file)
            new_new_tuple = list()
            for row in reader:
                if get_truth(row[attr_index], right, op):
                    if row not in new_tuples:
                        new_new_tuple.append(row)
            my_file.close()
            for row in new_new_tuple:
                new_tuples.append(row)
    tuples[file_index] = new_tuples
    return tuples


def join_two(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    new_tuples = [[], []]
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    attr_idx0 = get_index(file_map[cond[0][0]], left)
    attr_idx1 = get_index(file_map[cond[1][0]], right)
    dict = {}
    if file_idx0 == file_idx1:
        print('JOIN TWO: There should be two different relation')
    if op == '=':
        if len(tuples[file_idx0]) != 0 and len(tuples[file_idx1]) != 0:
            if len(tuples[file_idx0]) < len(tuples[file_idx1]):
                for row in tuples[file_idx0]:
                    if row[attr_idx0] not in dict:
                        dict[row[attr_idx0]] = list()
                    dict[row[attr_idx0]].append(row)
                for row in tuples[file_idx1]:
                    if row[attr_idx1] in dict:
                        for row2 in dict[row[attr_idx1]]:
                            new_tuples[file_idx0].append(row2)
                            new_tuples[file_idx1].append(row)
            else:
                for row in tuples[file_idx1]:
                    if row[attr_idx1] not in dict:
                        dict[row[attr_idx1]] = list()
                    dict[row[attr_idx1]].append(row)
                for row in tuples[file_idx0]:
                    if row[attr_idx0] in dict:
                        for row2 in dict[row[attr_idx0]]:
                            new_tuples[file_idx0].append(row)
                            new_tuples[file_idx1].append(row2)
        elif len(tuples[file_idx0]) != 0 and len(tuples[file_idx1]) == 0:
            for row in tuples[file_idx0]:
                if row[attr_idx0] not in dict:
                    dict[row[attr_idx0]] = list()
                dict[row[attr_idx0]].append(row)
            filename = file_map[file_rename[file_idx1]]
            my_file = open(filename, 'r', encoding='utf8')
            reader = csv.reader(my_file)
            for row in reader:
                if row[attr_idx1] in dict:
                    for row2 in dict[row[attr_idx1]]:
                        new_tuples[file_idx0].append(row2)
                        new_tuples[file_idx1].append(row)
            my_file.close()
        elif len(tuples[file_idx0]) == 0 and len(tuples[file_idx1]) != 0:
            for row in tuples[file_idx1]:
                if row[attr_idx1] not in dict:
                    dict[row[attr_idx1]] = list()
                dict[row[attr_idx1]].append(row)
            filename = file_map[file_rename[file_idx0]]
            my_file = open(filename, 'r', encoding='utf8')
            reader = csv.reader(my_file)
            for row in reader:
                if row[attr_idx0] in dict:
                    for row2 in dict[row[attr_idx0]]:
                        new_tuples[file_idx0].append(row)
                        new_tuples[file_idx1].append(row2)
            my_file.close()
        elif len(tuples[0]) == 0 and len(tuples[1]) == 0:
            filename = file_map[file_rename[file_idx0]]
            my_file = open(filename, 'r', encoding='utf8')
            reader = csv.reader(my_file)
            for row in reader:
                if row[attr_idx0] not in dict:
                    dict[row[attr_idx0]] = list()
                dict[row[attr_idx0]].append(row)
            my_file.close()
            filename = file_map[file_rename[file_idx1]]
            my_file = open(filename, 'r', encoding='utf8')
            reader = csv.reader(my_file)
            for row in reader:
                if row[attr_idx1] in dict:
                    for row2 in dict[row[attr_idx1]]:
                        new_tuples[file_idx0].append(row2)
                        new_tuples[file_idx1].append(row)
            my_file.close()
    else:
        if len(tuples[file_idx0]) != 0 and len(tuples[file_idx1]) != 0:
            for row in tuples[file_idx0]:
                for row2 in tuples[file_idx1]:
                    if get_truth(row[attr_idx0], row2[attr_idx1], op):
                        new_tuples[file_idx0].append(row)
                        new_tuples[file_idx1].append(row2)
        elif len(tuples[file_idx0]) != 0 and len(tuples[file_idx1]) == 0:
            filename = file_map[file_rename[file_idx1]]
            for row in tuples[file_idx0]:
                my_file = open(filename, 'r', encoding='utf8')
                reader = csv.reader(my_file)
                for row2 in reader:
                    if get_truth(row[attr_idx0], row2[attr_idx1], op):
                        new_tuples[file_idx0].append(row)
                        new_tuples[file_idx1].append(row2)
                my_file.close()
        elif len(tuples[file_idx0]) == 0 and len(tuples[file_idx1]) != 0:
            filename = file_map[file_rename[file_idx0]]
            for row in tuples[file_idx1]:
                my_file = open(filename, 'r', encoding='utf8')
                reader = csv.reader(my_file)
                for row2 in reader:
                    if get_truth(row2[attr_idx0], row[attr_idx1], op):
                        new_tuples[file_idx0].append(row2)
                        new_tuples[file_idx1].append(row)
                my_file.close()
        elif len(tuples[0]) == 0 and len(tuples[1]) == 0:
            print('Could not handle join two full tables now! It may take long time to run.')
            return tuples
    return new_tuples


def join_three(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    new_tuples = [[], [], []]
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    attr_idx0 = get_index(file_map[cond[0][0]], left)
    attr_idx1 = get_index(file_map[cond[1][0]], right)
    dict = {}
    if file_idx0 == file_idx1:
        print('JOIN Three: There should be two different relation')
    for i in range(len(file_rename)):
        if i not in [file_idx0, file_idx1]:
            third_table_idx = i
    len3 = len(tuples[third_table_idx])
    if len3 != 0 and (len3 == len(tuples[file_idx0]) or len3 == len(tuples[file_idx1])):
        dict3 = {}
        if op == '=':
            if len3 == len(tuples[file_idx0]):
                for row, row3 in zip(tuples[file_idx0], tuples[third_table_idx]):
                    if row[attr_idx0] not in dict:
                        dict[row[attr_idx0]] = list()
                        dict3[row[attr_idx0]] = list()
                    dict[row[attr_idx0]].append(row)
                    dict3[row[attr_idx0]].append(row3)
                if len(tuples[file_idx1]) == 0:
                    filename = file_map[file_rename[file_idx1]]
                    my_file = open(filename, 'r', encoding='utf8')
                    reader = csv.reader(my_file)
                    for row in reader:
                        if row[attr_idx1] in dict:
                            for row2, row3 in zip(dict[row[attr_idx1]], dict3[row[attr_idx1]]):
                                new_tuples[file_idx0].append(row2)
                                new_tuples[file_idx1].append(row)
                                new_tuples[third_table_idx].append(row3)
                    my_file.close()
                elif len(tuples[file_idx1]) != 0:
                    for row in tuples[file_idx1]:
                        if row[attr_idx1] in dict:
                            for row2, row3 in zip(dict[row[attr_idx1]], dict3[row[attr_idx1]]):
                                new_tuples[file_idx0].append(row2)
                                new_tuples[file_idx1].append(row)
                                new_tuples[third_table_idx].append(row3)
            elif len3 == len(tuples[file_idx1]):
                for row, row3 in zip(tuples[file_idx1], tuples[third_table_idx]):
                    if row[attr_idx1] not in dict:
                        dict[row[attr_idx1]] = list()
                        dict3[row[attr_idx1]] = list()
                    dict[row[attr_idx1]].append(row)
                    dict3[row[attr_idx1]].append(row3)
                if len(tuples[file_idx0]) == 0:
                    filename = file_map[file_rename[file_idx0]]
                    my_file = open(filename, 'r', encoding='utf8')
                    reader = csv.reader(my_file)
                    for row in reader:
                        if row[attr_idx0] in dict:
                            for row2, row3 in zip(dict[row[attr_idx0]], dict3[row[attr_idx0]]):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
                    my_file.close()
                elif len(tuples[file_idx0]) != 0:
                    for row in tuples[file_idx0]:
                        if row[attr_idx0] in dict:
                            for row2, row3 in zip(dict[row[attr_idx0]], dict3[row[attr_idx0]]):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
        else:
            if len(tuples[file_idx0]) and len(tuples[file_idx1]):
                print('Could not handle join two full tables now! It may take long time to run.')
            elif len3 == len(tuples[file_idx0]):
                if len(tuples[file_idx1]) == 0:
                    filename = file_map[file_rename[file_idx1]]
                    for row, row3 in zip(tuples[file_idx0], tuples[third_table_idx]):
                        my_file = open(filename, 'r', encoding='utf8')
                        reader = csv.reader(my_file)
                        for row2 in reader:
                            if get_truth(row[attr_idx0], row2[attr_idx1], op):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
                        my_file.close()
                elif len(tuples[file_idx1]) != 0:
                    for row, row3 in zip(tuples[file_idx0], tuples[third_table_idx]):
                        for row2 in tuples[file_idx1]:
                            if get_truth(row[attr_idx0], row2[attr_idx1], op):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
            elif len3 == len(tuples[file_idx1]):
                if len(tuples[file_idx0]) == 0:
                    filename = file_map[file_rename[file_idx0]]
                    for row2, row3 in zip(tuples[file_idx1], tuples[third_table_idx]):
                        my_file = open(filename, 'r', encoding='utf8')
                        reader = csv.reader(my_file)
                        for row in reader:
                            if get_truth(row[attr_idx0], row2[attr_idx1], op):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
                        my_file.close()
                elif len(tuples[file_idx0]) != 0:
                    for row2, row3 in zip(tuples[file_idx1], tuples[third_table_idx]):
                        for row in tuples[file_idx0]:
                            if get_truth(row[attr_idx0], row2[attr_idx1], op):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
        return new_tuples
    elif len3 != len(tuples[file_idx0]) and len3 != len(tuples[file_idx1]):
        tmp_file_rename = list()
        tmp_file_rename.append(cond[0][0])
        tmp_file_rename.append(cond[1][0])
        tmp_tuples = list()
        tmp_tuples.append(tuples[file_idx0])
        tmp_tuples.append(tuples[file_idx1])
        tmp_tuples = join_two(tmp_tuples, tmp_file_rename, file_map, keyword, cond)
        new_tuples[file_idx0] = tmp_tuples[file_idx0]
        new_tuples[file_idx1] = tmp_tuples[file_idx1]
        new_tuples[third_table_idx] = tuples[third_table_idx]
        return new_tuples
    return tuples


def select_two(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    attr_idx0 = get_index(file_map[cond[0][0]], left)
    attr_idx1 = get_index(file_map[cond[1][0]], right)
    if len(tuples[0]) == 0 and len(tuples[1]) == 0 and keyword == 'AND':
        print("SELECT TWO: both tuples are empty")
        return tuples
    elif len(tuples[0]) == len(tuples[1]) and file_idx0 != file_idx1:
        new_tuple = [[], []]
        for i in range(len(tuples[0])):
            if get_truth(tuples[file_idx0][i][attr_idx0], tuples[file_idx1][i][attr_idx1], op):
                new_tuple[file_idx0].append(tuples[file_idx0][i])
                new_tuple[file_idx1].append(tuples[file_idx1][i])
        return new_tuple
    elif cond[0][0] == cond[1][0] and len(tuples[0]) != len(tuples[1]):
        new_tuple = []
        if len(tuples[file_idx0]) == 0:
            filename = file_map[file_rename[file_idx0]]
            my_file = open(filename, 'r', encoding='utf8')
            reader = csv.reader(my_file)
            for row in reader:
                if get_truth(row[attr_idx0], row[attr_idx1], op):
                    new_tuple.append(row)
        else:
            for row in tuples[file_idx0]:
                if get_truth(row[attr_idx0], row[attr_idx1], op):
                    new_tuple.append(row)
        tuples[file_idx0] = new_tuple
        return tuples
    elif cond[0][0] == cond[1][0] and len(tuples[0]) == len(tuples[1]):
        new_tuple = [[], []]
        for i in range(len(tuples[file_idx0])):
            if get_truth(tuples[file_idx0][i][attr_idx0], tuples[file_idx0][i][attr_idx1], op):
                new_tuple[file_idx0].append(tuples[file_idx0][i])
                new_tuple[1-file_idx0].append(tuples[1-file_idx0][i])
        return new_tuple
    else:
        pass
    print('Error in SELECT_TWO')
    return tuples


def select_three(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    attr_idx0 = get_index(file_map[cond[0][0]], left)
    attr_idx1 = get_index(file_map[cond[1][0]], right)
    if len(tuples[file_idx0]) == 0 and len(tuples[file_idx1]) == 0:
        print("SELECT THREE: both tuples are empty")
        return tuples
    if cond[0][0] == cond[1][0]:
        pass
    else:
        new_tuples = list()
        for i in range(len(file_rename)):
            new_tuples.append([])
        for i in range(len(file_rename)):
            if i not in [file_idx0, file_idx1]:
                third_table_idx = i
        if len(tuples[third_table_idx]) == len(tuples[file_idx0]):
            for i in range(len(tuples[file_idx0])):
                if get_truth(new_tuples[file_idx0][i][attr_idx0], new_tuples[file_idx1][i][attr_idx1], op):
                    new_tuples[file_idx0].append(tuples[file_idx0][i])
                    new_tuples[file_idx1].append(tuples[file_idx1][i])
                    new_tuples[third_table_idx].append(tuples[third_table_idx][i])
        else:
            for i in range(len(tuples[file_idx0])):
                if get_truth(new_tuples[file_idx0][i][attr_idx0], new_tuples[file_idx1][i][attr_idx1], op):
                    new_tuples[file_idx0].append(tuples[file_idx0][i])
                    new_tuples[file_idx1].append(tuples[file_idx1][i])
            new_tuples[third_table_idx] = tuples[third_table_idx]
        return new_tuples
    return tuples


def merge(tuple1, tuple2, keyword):
    file_num = len(tuple1)
    if file_num == len(tuple2):
        if keyword == 'OR':
            for i in range(len(tuple2[0])):
                if tuple2[0][i] not in tuple1[0]:
                    for j in range(file_num):
                        tuple1[j].append(tuple2[j][i])
        elif keyword == 'AND':
            pass
    else:
        print('Unexpected Error in Merge')
    return tuple1


def query_one_table(attribute, file, conditions, keyword):
    myFile = open(file[0][0], 'r', encoding = "utf8")
    reader = csv.reader(myFile)
    attrs_set = next(reader)
    tmp = []
    for row in reader:
        checkcon = [False]*len(conditions)
        for j in range(len(conditions)):
            cond = conditions[j]
            if len(cond)==3:
                if cond[0][0] in attrs_set:
                    valuel = row[attrs_set.index(cond[0][0])]
                else:
                    valuel = cond[0][0]
                #get value for right
                if cond[1][0] in attrs_set:
                    valuer = row[attrs_set.index(cond[1][0])]
                else:
                    valuer = cond[1][0]
                if cond[2]=='LIKE':
                    checkcon[j] = str(like_op(valuel, valuer))
                else:
                    checkcon[j] = str(int(get_truth(valuel, valuer, cond[2])))
            else:
                if cond[1][0] in attrs_set:
                    valuel = row[attrs_set.index(cond[1][0])]
                else:
                    valuel = cond[1][0]
                #get value for right
                if cond[2][0] in attrs_set:
                    valuer = row[attrs_set.index(cond[2][0])]
                else:
                    valuer = cond[2][0]
                #print(valuel, valuer)
                if cond[3]=='LIKE':
                    checkcon[j] = str(int(not like_op(valuel, valuer)))
                else:
                    checkcon[j] = str(int(not get_truth(valuel, valuer, cond[3])))
        thisrow = checkrow(checkcon, keyword)
        #print(checkcon)
        #print(keyword)
        if thisrow:
            tmp.append(row)
            #i += 1
            #if i==10:
            #    break

    if attribute[0][0]=='*':
        print(attrs_set)
    else:
        # print(attribute)
        ntmp = []
        for row in tmp:
            rowtmp = []
            for att in attribute:
                rowtmp.append(row[attrs_set.index(att[0])])
            ntmp.append(rowtmp)
        tmp = ntmp
    #for row in tmp:
    #    print(row)
    #print(len(tmp))
    return tmp


def query_two_table(attribute, file, conditions, keyword):
    tmp = [[], []]
    file_map = {}
    file_rename = []
    for filename in file:
        if len(filename) == 2:
            file_map[filename[1]] = filename[0]
            file_rename.append(filename[1])
    keyword_i = -1
    conditions = reorder_condition(file_map, conditions, keyword)
    for cond in conditions:
        if keyword_i == -1:
            tmp = select(tmp, file_rename, file_map, '', cond)
        else:
            if len(tmp[0]) == 0 and len(tmp[1]) == 0 and 'OR' not in keyword[keyword_i: len(keyword)]:
                return tmp
            else:
                tmp = select(tmp, file_rename, file_map, keyword[keyword_i], cond)
        keyword_i += 1
        while keyword_i < len(keyword) and (keyword[keyword_i] == '(' or keyword[keyword_i] == ')'):
            keyword_i += 1
    try:
        res = project(tmp, file_map, file_rename, attribute)
    except:
        print('Tuples rows does not match')
        res = list()
    return res


def query_three_table(attribute, file, conditions, keyword):
    tmp = [[], [], []]
    file_map = {}
    file_rename = []
    for filename in file:
        if len(filename) == 2:
            file_map[filename[1]] = filename[0]
            file_rename.append(filename[1])
    keyword_i = -1
    conditions = reorder_condition(file_map, conditions, keyword)
    for cond in conditions:
        if keyword_i == -1:
            tmp = select(tmp, file_rename, file_map, '', cond)
        else:
            tmp = select(tmp, file_rename, file_map, keyword[keyword_i], cond)
        keyword_i += 1
        while keyword_i < len(keyword) and (keyword[keyword_i] == '(' or keyword[keyword_i] == ')'):
            keyword_i += 1
    res = project(tmp, file_map, file_rename, attribute)
    return res


def execute_query(input_query):
    attribute, file, conditions, keyword = parse.sql_preprocess(input_query)
    # print('SELECT:', attribute)
    # print('FROM:', file)
    # print('WHERE conditions:', conditions)
    # print('WHERE KEY:', keyword)
    if len(file) == 1:
        return query_one_table(attribute, file, conditions, keyword)
    elif len(file) == 2:
        return query_two_table(attribute, file, conditions, keyword)
    elif len(file) == 3:
        return query_three_table(attribute, file, conditions, keyword)

