#!/usr/bin/python3
# -*- coding: utf-8 -*-

from difflib import SequenceMatcher

class Diff:
    __change_kinds__ = ["changed-type", "changed-entry", "added-entry", "removed-entry", "added-file", "removed-file"]
    def __init__(self, kind, path, entry_old, entry_new):
        self.kind = kind
        self.path = path
        self.entry_old = entry_old
        self.entry_new = entry_new
    def __str__(self):
        ret = self.kind.replace('-', ' ') + " at " + "/".join([str(k) for k in self.path])
        if self.kind.startswith("changed"):
            ret += " from " + str(self.entry_old) + " to " + str(self.entry_new)
        elif self.kind.startswith("added"):
            ret += " value " + str(self.entry_new)
        elif self.kind.startswith("removed"):
            ret += " value " + str(self.entry_old)
        else:
            ret += ": UNKNOWN CHANGE KIND"
        return ret


def diff_list(list1, list2, path, diff):
    """Calculate the difference between two lists."""
    try:
        # TODO: fails if a list contains unhashable types, e.g. dict
        list_diff = SequenceMatcher(a=list1, b=list2).get_opcodes()
        for opcode, beg1, end1, beg2, end2 in list_diff:
            if opcode == 'equal':
                pass
            elif opcode == 'insert':
                for i in range(beg2, end2):
                    diff.append(Diff("added-entry", path+[i], None, list2[i]))
            elif opcode == 'delete':
                for i in range(beg1, end1):
                    diff.append(Diff("removed-entry", path+[i], list1[i], None))
            elif opcode == 'replace':
                # TODO: 'replace' might actually add/del elements
                # e.g. from [1,2]<->[1,3,4] is reported as change from [2] to [3,4]
                if end1-beg1 == 1 and end2-beg2 == 1:
                    diff.append(Diff("changed-entry", path+[beg1], list1[beg1], list2[beg2]))
                else:
                    diff.append(Diff("changed-entry", path+[beg1], list1[beg1:end1], list2[beg2:end2]))
            else:
                raise Exception("unknown SequenceMatcher opcode: " + opcode)
    except TypeError: # e.g. "unhashable type: dict"
        diff.append(Diff("changed-entry", path, list1, list2))


def diff_tree(tree1, tree2, path=[]):
    """Calculate the difference between two tree-shaped dicts."""
    diff = []
    if type(tree1) != type(tree2):
        diff.append(Diff("changed-type", path, tree1, tree2))
        return diff
    if isinstance(tree1, dict):
        for k in set(tree1.keys()) | set(tree2.keys()):
            if not k in tree1:  # key in tree2 but not in tree1 ==> inserted in tree2
                diff.append(Diff("added-entry", path + [k], None, tree2[k]))
            elif not k in tree2:  # key in tree1 but not in tree2 ==> deleted from tree2
                diff.append(Diff("removed-entry", path + [k], tree1[k], None))
            else:
                diff += diff_tree(tree1[k], tree2[k], path + [k])
    elif isinstance(tree1, list):
        diff_list(tree1, tree2, path, diff)
    else:
        if tree1 != tree2:
            diff.append(Diff("changed-entry", path, tree1, tree2))
    return diff
