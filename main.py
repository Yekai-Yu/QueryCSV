import csv
import query_parser as parse
import operator
import re
import numpy as np
import time
from btree_search import get_rows
from os.path import exists

file_path = ''
idx_path = ''


def getrow(fname, num):
    # fname is a string. loclist is the list from getloc, num is the row number to locate
    f = open(fname, "r", encoding='utf8')
    f.seek(num)
    reader = csv.reader(f)
    res = next(reader)
    f.close()
    return res


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
    :param filename: example: reviewtag.npy
    :param attr: example: useful
    :return: integer
    """
    try:
        tag_name = np.load(filename)
        tag_name = [tag.lower() for tag in tag_name]
        try:
            return tag_name.index(attr.lower())
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


def intersect(a, b):
    return list(set(a) & set(b))


def union(a, b):
    """ return the union of two lists """
    return list(set(a) | set(b))


def project(tuples, file_map, file_rename, attributes):
    file_dict_attr_idx_lst = {}
    for attr in attributes:
        if attr[0] not in file_dict_attr_idx_lst:
            file_dict_attr_idx_lst[attr[0]] = list()
        file_dict_attr_idx_lst[attr[0]].append(get_index(idx_path + file_map[attr[0]].replace(".csv", "tag.npy"), attr[1]))
    location_list = {}
    for file_abbr in file_dict_attr_idx_lst:
        location_list[file_abbr] = np.load(idx_path + file_map[file_abbr].replace('.csv', 'loc.npy'))
    tmp_file_map = {}
    for file_abbr in file_dict_attr_idx_lst:
        tmp_file_map[file_abbr] = file_path + file_map[file_abbr]
    output_list = list()
    for i in range(len(tuples[0])):
        temp = list()
        for file_abbr in file_dict_attr_idx_lst:
            row_number = tuples[file_rename.index(file_abbr)][i]
            filename = tmp_file_map[file_abbr]
            row_location = location_list[file_abbr][row_number + 1]
            this_row = getrow(filename, row_location)
            idx_lst = file_dict_attr_idx_lst[file_abbr]
            for entry in idx_lst:
                temp.append(this_row[entry])
        output_list.append(temp)
    return output_list


def select(tuples, file_rename, file_map, keyword, cond):
    """
    distribute condition to corresponding function, available to two and three tables
    :param tuples:
    :param file_rename:
    :param file_map:
    :param keyword:
    :param cond:
    :return:
    """
    # Join
    if len(cond[0]) == 2 and len(cond[1]) == 2:
        # Join on two raw tables
        if keyword == '':
            if len(file_rename) == 2:
                if cond[0][0] == cond[1][0]:
                    return select_two(tuples, file_rename, file_map, keyword, cond)
                else:
                    return join_two(tuples, file_rename, file_map, keyword, cond)
        elif keyword == 'AND':
            if len(file_rename) == 2:
                # Join after join, or selection by comparing two attribute in one table
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
    # Selection on one table
    elif len(cond[0]) == 2 and len(cond[1]) == 1:
        file_index = file_rename.index(cond[0][0])
        filename = file_map[cond[0][0]]
        return update_one(tuples, filename, file_index, cond, keyword)
    else:
        print("Unexpected condition in SELECT")
    print("Unexpected error in select(), some conditions might be missing")
    return tuples


def update_one(tuples, filename, file_index, cond, keyword):
    """
    Perform selection on one table. DOES not support LIKE op yet
    :param tuples:
    :param filename:
    :param file_index:
    :param attr_index:
    :param cond:
    :param keyword:
    :return:
    """
    left, right, op = decompose_condition(cond)
    new_tuples = []
    if op == '=':
        index_file = idx_path + filename.replace(".csv", left + ".npy")
        if exists(index_file):
            dict = np.load(index_file).item()
            if right in dict:
                new_tuples = dict[right]
        else:
            index_file = idx_path + filename.replace(".csv", left + '.pkl')
            if exists(index_file):
                new_tuples = get_rows(index_file, right, op)
            else:
                print("Index is not found", index_file)
    else:
        index_file = idx_path + filename.replace(".csv", left + '.pkl')
        if exists(index_file):
            new_tuples = get_rows(index_file, right, op)
        else:
            print("Index is not found", index_file)
    if len(tuples[file_index]) == 0:
        tuples[file_index] = new_tuples
    elif keyword == 'AND':
        tuples[file_index] = intersect(tuples[file_index], new_tuples)
    elif keyword == 'OR':
        tuples[file_index] = union(tuples[file_index], new_tuples)
    return tuples


def join_two(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    new_tuples = [[], []]
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    filename1 = file_map[cond[0][0]]
    filename2 = file_map[cond[1][0]]
    if file_idx0 == file_idx1:
        print('JOIN TWO: There should be two different relation')
    # Join two tables with equality
    if op == '=':
        # Join after selection on two tables
        if len(tuples[file_idx0]) != 0 and len(tuples[file_idx1]) != 0:
            if len(tuples[file_idx0]) < 100 or len(tuples[file_idx1]) > 100:
                index_file1 = idx_path + filename1.replace(".csv", left + "idx.npy")
                index_file2 = idx_path + filename2.replace(".csv", right + "idx.npy")
                if exists(index_file1):
                    dict1 = np.load(index_file1).item()
                else:
                    print(index_file1, 'not exists')
                if exists(index_file2):
                    dict2 = np.load(index_file2).item()
                else:
                    print(index_file2, 'not exists')
                dict = {}
                # build hash map on the table with fewer records
                if len(tuples[file_idx0]) < len(tuples[file_idx1]):
                    for row_num in tuples[file_idx0]:
                        if dict1[row_num] not in dict:
                            dict[dict1[row_num]] = list()
                        dict[dict1[row_num]].append(row_num)

                    for row_num2 in tuples[file_idx1]:
                        if dict2[row_num2] in dict:
                            for row_num in dict[dict2[row_num2]]:
                                new_tuples[file_idx0].append(row_num)
                                new_tuples[file_idx1].append(row_num2)
                else:
                    for row_num in tuples[file_idx1]:
                        if dict2[row_num] not in dict:
                            dict[dict2[row_num]] = list()
                        dict[dict2[row_num]].append(row_num)

                    for row_num2 in tuples[file_idx0]:
                        if dict1[row_num2] in dict:
                            for row_num in dict[dict1[row_num2]]:
                                new_tuples[file_idx0].append(row_num2)
                                new_tuples[file_idx1].append(row_num)
            else:
                loc_file1 = idx_path + filename1.replace(".csv", "loc.npy")
                if exists(loc_file1):
                    location_list = np.load(loc_file1)
                else:
                    print(loc_file1, 'not exists')
                attr_pos = get_index(idx_path + filename1.replace(".csv", "tag.npy"), left)
                dict1 = {}
                for row_num in tuples[file_idx0]:
                    left_attr = getrow(file_path + filename1, location_list[row_num+1])[attr_pos]
                    if left_attr not in dict1:
                        dict1[left_attr] = list()
                    dict1[left_attr].append(row_num)
                loc_file2 = idx_path + filename2.replace('.csv', 'loc.npy')
                if exists(loc_file2):
                    location_list = np.load(loc_file2)
                else:
                    print(loc_file2, 'not exists')
                attr_pos = get_index(idx_path + filename2.replace('.csv', 'tag.npy'), right)
                for row_num2 in tuples[file_idx1]:
                    right_attr = getrow(file_path + filename2, location_list[row_num2+1])[attr_pos]
                    if right_attr in dict1:
                        for row_num in dict1[right_attr]:
                            new_tuples[file_idx0].append(row_num)
                            new_tuples[file_idx1].append(row_num2)
        # Join after selection on one table
        elif len(tuples[file_idx0]) != 0 and len(tuples[file_idx1]) == 0:
            if len(tuples[file_idx0]) > 100:
                index_file1 = idx_path + filename1.replace(".csv", left + "idx.npy")
                index_file2 = idx_path + filename2.replace(".csv", right + ".npy")
                if exists(index_file1):
                    dict1 = np.load(index_file1).item()
                else:
                    print(index_file1, 'not exists')
                if exists(index_file2):
                    dict2 = np.load(index_file2).item()
                else:
                    print(index_file2, 'not exists')
                for row_num in tuples[file_idx0]:
                    if dict1[row_num] in dict2:
                        for row_num2 in dict2[dict1[row_num]]:
                            new_tuples[file_idx0].append(row_num)
                            new_tuples[file_idx1].append(row_num2)
            else:
                loc_filename = idx_path + filename1.replace('.csv', 'loc.npy')
                index_file2 = idx_path + filename2.replace(".csv", right + ".npy")
                if exists(loc_filename):
                    location_list = np.load(loc_filename)
                else:
                    print(loc_filename, 'not exists')
                if exists(index_file2):
                    dict2 = np.load(index_file2).item()
                else:
                    print(index_file2, 'not exists')
                attr_pos = get_index(idx_path + filename1.replace(".csv", "tag.npy"), left)
                for row_num in tuples[file_idx0]:
                    left_attr = getrow(file_path + filename1, location_list[row_num + 1])[attr_pos]
                    if left_attr in dict2:
                        for row_num2 in dict2[left_attr]:
                            new_tuples[file_idx0].append(row_num)
                            new_tuples[file_idx1].append(row_num2)
        # Join after selection on one table
        elif len(tuples[file_idx0]) == 0 and len(tuples[file_idx1]) != 0:
            if len(tuples[file_idx1]) > 100:
                index_file1 = idx_path + filename1.replace(".csv", left + ".npy")
                index_file2 = idx_path + filename2.replace(".csv", right + "idx.npy")
                if exists(index_file1):
                    dict1 = np.load(index_file1).item()
                else:
                    print(index_file1, 'not exists')
                if exists(index_file2):
                    dict2 = np.load(index_file2).item()
                else:
                    print(index_file2, 'not exists')
                for row_num in tuples[file_idx1]:
                    if dict2[row_num] in dict1:
                        for row_num2 in dict1[dict2[row_num]]:
                            new_tuples[file_idx0].append(row_num2)
                            new_tuples[file_idx1].append(row_num)
            else:
                index_file1 = idx_path + filename1.replace(".csv", left + ".npy")
                loc_filename = idx_path + filename2.replace('.csv', 'loc.npy')
                if exists(index_file1):
                    dict1 = np.load(index_file1).item()
                else:
                    print(index_file1, 'not exists')
                if exists(loc_filename):
                    location_list = np.load(loc_filename)
                else:
                    print(loc_filename, 'not exists')
                attr_pos = get_index(idx_path + filename2.replace(".csv", "tag.npy"), right)
                for row_num in tuples[file_idx1]:
                    right_attr = getrow(file_path + filename2, location_list[row_num + 1])[attr_pos]
                    if right_attr in dict1:
                        for row_num2 in dict1[right_attr]:
                            new_tuples[file_idx0].append(row_num2)
                            new_tuples[file_idx1].append(row_num)
        # Join without selection
        elif len(tuples[0]) == 0 and len(tuples[1]) == 0:
            print("Join on two tables without selection is expensive!")
    else:
        print("Join on two tables with inequality")
    return new_tuples


def join_three(tuples, file_rename, file_map, keyword, cond):
    """
    Perform join on two out of three tables
    :param tuples:
    :param file_rename:
    :param file_map:
    :param keyword:
    :param cond:
    :return:
    """
    left, right, op = decompose_condition(cond)
    new_tuples = [[], [], []]
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    filename1 = file_map[cond[0][0]]
    filename2 = file_map[cond[1][0]]
    # dict (k, v) -> (attribute, list of row number)
    # dict1 (k, v) -> (row number, attribute)
    # dict2 (k, v) -> (attribute, list of row number) or (k, v) -> (row number, attribute) (if table 2 was selected)
    dict = {}
    if file_idx0 == file_idx1:
        print('JOIN Three: There should be two different relation')
    for i in range(len(file_rename)):
        if i not in [file_idx0, file_idx1]:
            third_table_idx = i
    len3 = len(tuples[third_table_idx])
    # one table and the third one were joined before
    if len3 != 0 and (len3 == len(tuples[file_idx0]) or len3 == len(tuples[file_idx1])):
        # dict3 (k, v) -> same as dict, the one table that not involved in join
        dict3 = {}
        # equality join
        if op == '=':
            # one table has been joined with the third table
            if len3 == len(tuples[file_idx0]):
                if len3 > 100 or len(tuples[file_idx1]) == 0:
                    index_file1 = idx_path + filename1.replace(".csv", left + "idx.npy")
                    if exists(index_file1):
                        dict1 = np.load(index_file1).item()
                    else:
                        print(index_file1, 'not exists')
                    for row, row3 in zip(tuples[file_idx0], tuples[third_table_idx]):
                        if dict1[row] not in dict:
                            dict[dict1[row]] = list()
                            dict3[dict1[row]] = list()
                        dict[dict1[row]].append(row)
                        dict3[dict1[row]].append(row3)
                    if len(tuples[file_idx1]) == 0:
                        index_file2 = idx_path + filename2.replace(".csv", right + ".npy")
                        if exists(index_file2):
                            dict2 = np.load(index_file2).item()
                        else:
                            print(index_file2, 'not exists')
                        for attr in dict:
                            for row2, row3 in zip(dict[attr], dict3[attr]):
                                if attr in dict2:
                                    for row in dict2[attr]:
                                        new_tuples[file_idx0].append(row2)
                                        new_tuples[file_idx1].append(row)
                                        new_tuples[third_table_idx].append(row3)
                    # Selection has been performed on the third table
                    elif len(tuples[file_idx1]) != 0:
                        index_file2 = idx_path + filename2.replace(".csv", right + "idx.npy")
                        if exists(index_file2):
                            dict2 = np.load(index_file2).item()
                        else:
                            print(index_file2, 'not exists')
                        for row in tuples[file_idx1]:
                            if dict2[row] in dict:
                                for row2, row3 in zip(dict[dict2[row]], dict3[dict2[row]]):
                                    new_tuples[file_idx0].append(row2)
                                    new_tuples[file_idx1].append(row)
                                    new_tuples[third_table_idx].append(row3)
                else:
                    loc_filename = idx_path + filename2.replace('.csv', 'loc.npy')
                    if exists(loc_filename):
                        location_list = np.load(loc_filename)
                    else:
                        print(loc_filename, 'not exists')
                    attr_pos = get_index(idx_path + filename2.replace(".csv", "tag.npy"), right)
                    dict2 = {}
                    for row_num in tuples[file_idx1]:
                        right_attr = getrow(file_path + filename2, location_list[row_num + 1])[attr_pos]
                        if right_attr not in dict2:
                            dict2[right_attr] = list()
                        dict2[right_attr].append(row_num)

                    loc_filename = idx_path + filename1.replace('.csv', 'loc.npy')
                    if exists(loc_filename):
                        location_list = np.load(loc_filename)
                    else:
                        print(loc_filename, 'not exists')
                    attr_pos = get_index(idx_path + filename1.replace(".csv", "tag.npy"), left)

                    for row, row3 in zip(tuples[file_idx0], tuples[third_table_idx]):
                        left_attr = getrow(file_path + filename1, location_list[row + 1])[attr_pos]
                        if left_attr in dict2:
                            for row2 in dict2[left_attr]:
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
            elif len3 == len(tuples[file_idx1]):
                index_file2 = idx_path + filename2.replace(".csv", right + "idx.npy")
                if exists(index_file2):
                    dict2 = np.load(index_file2).item()
                else:
                    print(index_file2, 'not exists')
                for row, row3 in zip(tuples[file_idx1], tuples[third_table_idx]):
                    if dict2[row] not in dict:
                        dict[dict2[row]] = list()
                        dict3[dict2[row]] = list()
                    dict[dict2[row]].append(row)
                    dict3[dict2[row]].append(row3)
                if len(tuples[file_idx0]) == 0:
                    index_file1 = idx_path + filename1.replace(".csv", left + ".npy")
                    if exists(index_file1):
                        dict1 = np.load(index_file1).item()
                    else:
                        print(index_file1, 'not exists')
                    for attr in dict:
                        for row2, row3 in zip(dict[attr], dict3[attr]):
                            if attr in dict1:
                                for row in dict1[attr]:
                                    new_tuples[file_idx0].append(row)
                                    new_tuples[file_idx1].append(row2)
                                    new_tuples[third_table_idx].append(row3)
                # Selection has been performed on the third table
                elif len(tuples[file_idx0]) != 0:
                    index_file1 = idx_path + filename1.replace(".csv", right + "idx.npy")
                    if exists(index_file1):
                        dict1 = np.load(index_file1).item()
                    else:
                        print(index_file1, 'not exists')
                    for row in tuples[file_idx0]:
                        if dict1[row] in dict:
                            for row2, row3 in zip(dict[dict1[row]], dict3[dict1[row]]):
                                new_tuples[file_idx0].append(row)
                                new_tuples[file_idx1].append(row2)
                                new_tuples[third_table_idx].append(row3)
        # inequality join
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
    # join two tables only
    elif len3 == 0 or (len3 != len(tuples[file_idx0]) and len3 != len(tuples[file_idx1])):
        tmp_file_rename = list()
        tmp_file_rename.append(cond[0][0])
        tmp_file_rename.append(cond[1][0])
        tmp_tuples = list()
        tmp_tuples.append(tuples[file_idx0])
        tmp_tuples.append(tuples[file_idx1])
        tuples[file_idx0], tuples[file_idx1] = join_two(tmp_tuples, tmp_file_rename, file_map, keyword, cond)
    else:
        print("Unexpected condition in JOIN THREE")
    return tuples


def select_two(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    filename1 = file_map[cond[0][0]]
    filename2 = file_map[cond[1][0]]
    if len(tuples[0]) == 0 and len(tuples[1]) == 0 and keyword == 'AND':
        print("SELECT TWO: both tuples are empty")
        return tuples
    elif cond[0][0] != cond[1][0] and len(tuples[0]) == len(tuples[1]):
        new_tuple = [[], []]
        for i in range(len(tuples[0])):
            if get_truth(tuples[file_idx0][i][attr_idx0], tuples[file_idx1][i][attr_idx1], op):
                new_tuple[file_idx0].append(tuples[file_idx0][i])
                new_tuple[file_idx1].append(tuples[file_idx1][i])
        return new_tuple
    elif cond[0][0] == cond[1][0]:
        index_file1 = idx_path + filename1.replace(".csv", left + "idx.npy")
        index_file2 = idx_path + filename2.replace(".csv", right + "idx.npy")
        if exists(index_file1):
            dict1 = np.load(index_file1).item()
        else:
            print(index_file1, 'not exists')
        if exists(index_file2):
            dict2 = np.load(index_file2).item()
        else:
            print(index_file2, 'not exists')
        if len(tuples[0]) != len(tuples[1]):
            new_tuple = []
            for row in tuples[file_idx0]:
                if get_truth(dict1[row], dict2[row], op):
                    new_tuple.append(row)
            tuples[file_idx0] = new_tuple
            return tuples
        elif len(tuples[0]) == len(tuples[1]):
            new_tuple = [[], []]
            for i, row in enumerate(tuples[file_idx0]):
                if get_truth(dict1[row], dict2[row], op):
                    new_tuple[file_idx0].append(tuples[file_idx0][i])
                    new_tuple[1 - file_idx0].append(tuples[1 - file_idx0][i])
            return new_tuple
    else:
        pass
    print('Error in SELECT_TWO')
    return tuples


def select_three(tuples, file_rename, file_map, keyword, cond):
    left, right, op = decompose_condition(cond)
    file_idx0 = file_rename.index(cond[0][0])
    file_idx1 = file_rename.index(cond[1][0])
    filename1 = file_map[cond[0][0]]
    filename2 = file_map[cond[1][0]]
    if len(tuples[file_idx0]) == 0 and len(tuples[file_idx1]) == 0:
        print("SELECT THREE: both tuples are empty")
        return tuples
    if cond[0][0] == cond[1][0]:
        pass
    else:
        index_file1 = idx_path + filename1.replace(".csv", left + "idx.npy")
        index_file2 = idx_path + filename2.replace(".csv", right + "idx.npy")
        if exists(index_file1):
            dict1 = np.load(index_file1).item()
        else:
            print(index_file1, 'not exists')
        if exists(index_file2):
            dict2 = np.load(index_file2).item()
        else:
            print(index_file2, 'not exists')
        new_tuples = list()
        for i in range(len(file_rename)):
            new_tuples.append([])
        for i in range(len(file_rename)):
            if i not in [file_idx0, file_idx1]:
                third_table_idx = i
        if len(tuples[third_table_idx]) == len(tuples[file_idx0]):
            for i in range(len(tuples[file_idx0])):
                if get_truth(dict1[tuples[file_idx0][i]], dict2[tuples[file_idx1][i]], op):
                    new_tuples[file_idx0].append(tuples[file_idx0][i])
                    new_tuples[file_idx1].append(tuples[file_idx1][i])
                    new_tuples[third_table_idx].append(tuples[third_table_idx][i])
        else:
            for i in range(len(tuples[file_idx0])):
                if get_truth(dict1[tuples[file_idx0][i]], dict2[tuples[file_idx1][i]], op):
                    new_tuples[file_idx0].append(tuples[file_idx0][i])
                    new_tuples[file_idx1].append(tuples[file_idx1][i])
            new_tuples[third_table_idx] = tuples[third_table_idx]
        return new_tuples
    return tuples


def merge(tuple1, tuple2, keyword):
    """
    One thing needs to be concerned. When tuple2 contains duplicate tuples, merge fails on adding duplicate.
    Easy way to solve, build a new tuple, store temporary, push new tuple into tuple1
    :param tuple1:
    :param tuple2:
    :param keyword:
    :return:
    """
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


def generate_map(file):
    """

    :param file:
    :return: file map store a hash from 'rename' to real file name
    file rename store a list of 'rename'
    """
    file_map = {}
    file_rename = []
    for filename in file:
        if len(filename) == 2:
            file_map[filename[1]] = filename[0]
            file_rename.append(filename[1])
    return file_map, file_rename


def query_one_table(attribute, file, conditions, keyword, DISTINCT):
    tmp = [[]]
    file_map, file_rename = generate_map(file)
    keyword_i = -1
    for cond in conditions:
        file_index = file_rename.index(cond[0][0])
        filename = file_map[cond[0][0]]
        if keyword_i > -1:
            tmp = update_one(tmp, filename, file_index, cond, keyword[keyword_i])
        else:
            tmp = update_one(tmp, filename, file_index, cond, "")
        # print(len(tmp[0]))
        keyword_i += 1
    try:
        res = project(tmp, file_map, file_rename, attribute)
    except:
        print('Tuples rows does not match')
        res = tmp
    if DISTINCT == True:
        res = [list(t) for t in set(map(tuple, res))]
    return res


def query_two_table(attribute, file, conditions, keyword, DISTINCT):
    tmp = [[], []]
    file_map, file_rename = generate_map(file)
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
        # print(len(tmp[0]), len(tmp[1]))
    try:
        res = project(tmp, file_map, file_rename, attribute)
    except:
        print('Tuples rows does not match')
        res = tmp
    if DISTINCT == True:
        res = [list(t) for t in set(map(tuple, res))]
    return res


def query_three_table(attribute, file, conditions, keyword, DISTINCT):
    tmp = [[], [], []]
    file_map, file_rename = generate_map(file)
    keyword_i = -1
    conditions = reorder_condition(file_map, conditions, keyword)
    for cond in conditions:
        # start = time.time()
        if keyword_i == -1:
            tmp = select(tmp, file_rename, file_map, '', cond)
        else:
            tmp = select(tmp, file_rename, file_map, keyword[keyword_i], cond)
        keyword_i += 1
        # print(len(tmp[0]), len(tmp[1]), len(tmp[2]))
        # print(cond, time.time() - start)
    start = time.time()
    try:
        res = project(tmp, file_map, file_rename, attribute)
    except:
        res = tmp
    # print('Projection', time.time() - start)
    if DISTINCT == True:
        res = [list(t) for t in set(map(tuple, res))]
    return res


def execute_query(input_query, path):
    global file_path
    file_path = path
    global idx_path
    idx_path = path + 'index/'
    attribute, file, conditions, keyword, DISTINCT = parse.sql_preprocess(input_query)
    # print('SELECT:', attribute)
    # print('FROM:', file)
    # print('WHERE conditions:', conditions)
    # print('WHERE KEY:', keyword)
    if len(file) == 1:
        return query_one_table(attribute, file, conditions, keyword, DISTINCT)
    elif len(file) == 2:
        return query_two_table(attribute, file, conditions, keyword, DISTINCT)
    elif len(file) == 3:
        return query_three_table(attribute, file, conditions, keyword, DISTINCT)


# start = time.time()
# sample_query = "SELECT B.name, B.postal_code, R.review_id, R.stars, R.useful FROM business.csv B, review.csv R " \
#                "WHERE B.city = 'Champaign' AND B.state = 'IL' AND B.business_id = R.business_id;"
# query_output = execute_query(sample_query)
# end = time.time()
# print('Run time:', end - start)
# print('Length of output', len(query_output))
