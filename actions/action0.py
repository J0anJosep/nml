import ast
from action0properties import properties
from generic import *
from action4 import *
from action6 import *
from actionD import *

class Action0:
    def __init__(self, feature, id):
        self.feature = feature
        self.id = id
        self.prop_list = []
        self.num_ids = None
    
    def write(self, file):
        file.write("-1 * 0 00 ")
        print_bytex(file, self.feature)
        print_byte(file, len(self.prop_list))
        if self.num_ids == None: self.num_ids = 1
        print_bytex(file, self.num_ids)
        file.write("FF ")
        print_wordx(file, self.id)
        file.write("\n")
        for prop in self.prop_list:
            prop.write(file)
        file.write("\n")
    
    def skip_action7(self):
        return True
    
    def skip_action9(self):
        return True
    
    def skip_needed(self):
        return True

first_free_id = 0x12 * [0]

def get_free_id(feature):
    global first_free_id
    first_free_id[feature] += 1
    return first_free_id[feature] - 1

class Action0Property:
    def __init__(self, num, value, size):
        self.num = num
        self.value = value
        self.size = size
        
    def write(self, file):
        print_bytex(file, self.num)
        self.value.write(file, self.size)
        file.write("\n")
    
    def get_size(self):
        return self.size + 1


def parse_property(feature, name, value, id, unit):
    global properties
    prop = None
    action_list = []
    action_list_append = []
    mods = []
    
    if isinstance(name, str):
        if not name in properties[feature]: raise ScriptError("Unkown property name: " + name)
        prop = properties[feature][name]
    elif isinstance(name, ast.ConstantNumeric):
        for p in properties[feature]:
            if 'num' in p and p['num'] != name.value: continue
            prop = p
        if prop == None: raise ScriptError("Unkown property number: " + name.value)
    else: raise ScriptError("Invalid type as property identifier")
    
    mul = 1
    if 'unit_conversion' in prop: mul = prop['unit_conversion']
    if unit != None:
        if not 'unit_type' in prop or unit.type != prop['unit_type']:
            raise ScriptError("Invalid unit for property: " + name)
        mul = mul / unit.convert
    if mul != 1:
        if not isinstance(value, ast.ConstantNumeric):
            raise ScriptError("Unit conversion specified for property, but no constant value found")
        value = ast.ConstantNumeric(int(value.value * mul))
    
    if 'custom_function' in prop:
        props = prop['custom_function'](value)
    else:
        if isinstance(value, ast.ConstantNumeric):
            pass
        elif isinstance(value, ast.Parameter) and isinstance(value.num, ast.ConstantNumeric):
            mods.append((value.num.value, size, 1))
            value = ast.ConstantNumeric(0)
        elif isinstance(value, ast.String):
            if not 'string' in prop: raise ScriptError("String used as value for non-string property: " + str(prop['num']))
            string_range = prop['string']
            stringid, prepend, string_actions = get_string_action4s(feature, string_range, value, id)
            value = ast.ConstantNumeric(stringid)
            if prepend:
                action_list.extend(string_actions)
            else:
                action_list_append.extend(string_actions)
        else:
            tmp_param, tmp_param_actions = get_tmp_parameter(value)
            mods.append((tmp_param, size, 1))
            action_list.extend(tmp_param_actions)
            value = ast.ConstantNumeric(0)
        if prop['num'] != -1:
            props = [Action0Property(prop['num'], value, prop['size'])]
        else:
            props = []
    
    return (props, action_list, mods, action_list_append)

def parse_property_block(prop_list, feature, id):
    global free_parameters
    free_parameters_backup = free_parameters[:]
    action_list = []
    action_list_append = []
    action6 = Action6()
    if isinstance(id, ast.ConstantNumeric):
        action0 = Action0(feature, id.value)
    else:
        tmp_param, tmp_param_actions = get_tmp_parameter(id)
        action6.modify_bytes(tmp_param, 2, 5)
        action_list.extend(tmp_param_actions)
        action0 = Action0(feature, 0)
    
    offset = 7
    for prop in prop_list:
        properties, extra_actions, mods, extra_append_actions = parse_property(feature, prop.name, prop.value, id.value, prop.unit)
        action_list.extend(extra_actions)
        action_list_append.extend(extra_append_actions)
        for mod in mods:
            action6.modify_bytes(mod[0], mod[1], mod[2] + offset)
        for p in properties:
            offset += p.get_size()
        action0.prop_list.extend(properties)
    
    if len(action6.modifications) > 0: action_list.append(action6)
    action_list.append(action0)
    action_list.extend(action_list_append)
    
    free_parameters.extend([item for item in free_parameters_backup if not item in free_parameters])
    return action_list

class CargoListProp:
    def __init__(self, cargo_list):
        self.cargo_list = cargo_list
    
    def write(self, file):
        print_bytex(file, 0x09)
        for i in range(0, len(self.cargo_list)):
            if i > 0 and i % 5 == 0: file.write("\n")
            print_string(file, self.cargo_list[i], False, True)
        file.write("\n")

def get_cargolist_action(cargo_list):
    action0 = Action0(0x08, 0)
    action0.prop_list.append(CargoListProp(cargo_list))
    action0.num_ids = len(cargo_list)
    return [action0]