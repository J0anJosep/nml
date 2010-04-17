from generic import *
from actions.action0 import *
from actions.action1 import *
from actions.real_sprite import *
from actions.action2var import *
from actions.action7 import *
from actions.action8 import *
from actions.actionB import *
from actions.actionD import *
from actions.actionE import *
import global_constants
import operator

def print_script(script, indent):
    for r in script:
        r.debug_print(indent)

class Operator:
    ADD     = 0
    SUB     = 1
    DIV     = 2
    MOD     = 3
    MUL     = 4
    AND     = 5
    OR      = 6
    XOR     = 7
    VAL2    = 8
    CMP_EQ  = 9
    CMP_NEQ = 10
    CMP_LT  = 11
    CMP_GT  = 12
    MIN     = 13
    MAX     = 14
    STO_TMP = 15
    STO_PERM = 16

feature_ids = {
    'FEAT_TRAINS': 0x00,
    'FEAT_ROADVEHS': 0x01,
    'FEAT_SHIPS': 0x02,
    'FEAT_PLANES': 0x03,
    'FEAT_STATIONS': 0x04,
    'FEAT_CANALS': 0x05,
    'FEAT_BRIDGES': 0x06,
    'FEAT_HOUSES': 0x07,
    'FEAT_GLOBALVARS': 0x08,
    'FEAT_INDUSTRYTILES': 0x09,
    'FEAT_INDUSTRIES': 0x0A,
    'FEAT_CARGOS': 0x0B,
    'FEAT_SOUNDEFFECTS': 0x0C,
    'FEAT_AIRPORTS': 0x0D,
    'FEAT_SIGNALS': 0x0E,
    'FEAT_NEWOBJECTS': 0x0F,
    'FEAT_RAILTYPES': 0x10,
    'FEAT_AIRPORTTILES': 0x11,
}

########### expressions ###########
class Expr:
    def debug_print(self, indentation):
        print indentation*' ' + 'Expression'

class BinOp(Expr):
    def __init__(self, op, expr1, expr2):
        self.op = op
        self.expr1 = expr1
        self.expr2 = expr2
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Binary operator, op = ', self.op
        if isinstance(self.expr1, str):
            print (indentation+2)*' ' + 'ID:', self.expr1
        else:
            self.expr1.debug_print(indentation + 2)
        if isinstance(self.expr2, str):
            print (indentation+2)*' ' + 'ID:', self.expr2
        else:
            self.expr2.debug_print(indentation + 2)

class TernaryOp(Expr):
    def __init__(self, guard, expr1, expr2):
        self.guard = guard
        self.expr1 = expr1
        self.expr2 = expr2
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Ternary operator'
        print indentation*' ' + 'Guard:'
        self.guard.debug_print(indentation + 2)
        print indentation*' ' + 'Expression 1:'
        self.expr1.debug_print(indentation + 2)
        print indentation*' ' + 'Expression 2:'
        self.expr2.debug_print(indentation + 2)

class Assignment:
    def __init__(self, name, value):
        self.name = name
        self.value = value
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Assignment, name = ', self.name
        self.value.debug_print(indentation + 2)

class Parameter(Expr):
    def __init__(self, num):
        self.num = num
    def debug_print(self, indentation):
        print indentation*' ' + 'Parameter:'
        self.num.debug_print(indentation + 2)

class ParameterAssignment:
    def __init__(self, param, value):
        self.param = param
        self.value = reduce_expr(value, [global_constants.const_table])
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Parameter assignment'
        self.param.debug_print(indentation + 2)
        self.value.debug_print(indentation + 2)
    
    def get_action_list(self):
        return parse_actionD(self)

class Variable:
    def __init__(self, num, shift = None, mask = None, param = None):
        self.num = num
        self.shift = shift if shift != None else ConstantNumeric(0)
        self.mask = mask if mask != None else ConstantNumeric(0xFFFFFFFF)
        self.param = param
        self.add = None
        self.div = None
        self.mod = None
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Action2 variable'
        self.num.debug_print(indentation + 2)
        if self.param != None:
            print (indentation+2)*' ' + 'Parameter:'
            if isinstance(self.param, str):
                print (indentation+4)*' ' + 'Procedure call:', self.param
            else:
                self.param.debug_print(indentation + 4)

class String:
    def __init__(self, name, params = []):
        self.name = name
        self.params = params
    def debug_print(self, indentation):
        print indentation*' ' + 'String: ' + self.name
        for param in self.params:
            print (indentation+2)*' ' + 'Parameter:'
            param.debug_print(indentation + 4)

class ConstantNumeric(Expr):
    def __init__(self, value):
        self.value = truncate_int32(value)
    def debug_print(self, indentation):
        print indentation*' ' + 'Int:', self.value
    def write(self, file, size):
        print_varx(file, self.value, size)

# compile-time expression evaluation
compile_time_operator = {
    Operator.ADD:     operator.add,
    Operator.SUB:     operator.sub,
    Operator.DIV:     operator.div,
    Operator.MOD:     operator.mod,
    Operator.MUL:     operator.mul,
    Operator.AND:     operator.and_,
    Operator.OR:      operator.or_,
    Operator.XOR:     operator.xor,
    Operator.VAL2:    lambda a, b: b,
    Operator.CMP_EQ:  operator.eq,
    Operator.CMP_NEQ: operator.ne,
    Operator.CMP_LT:  operator.lt,
    Operator.CMP_GT:  operator.gt,
    Operator.MIN:     lambda a, b: min(a, b),
    Operator.MAX:     lambda a, b: max(a, b)
}

commutative_operators = [
    Operator.ADD,
    Operator.MUL,
    Operator.AND,
    Operator.OR,
    Operator.XOR,
    Operator.CMP_EQ,
    Operator.CMP_NEQ,
    Operator.MIN,
    Operator.MAX,
]

# note: id_dicts is a *list* of dictionaries or (dictionary, function)-tuples
def reduce_expr(expr, id_dicts = []):
    global compile_time_operator
    if isinstance(expr, BinOp):
        expr.expr1 = reduce_expr(expr.expr1, id_dicts)
        expr.expr2 = reduce_expr(expr.expr2, id_dicts)
        if isinstance(expr.expr1, ConstantNumeric) and isinstance(expr.expr2, ConstantNumeric):
            return ConstantNumeric(compile_time_operator[expr.op](expr.expr1.value, expr.expr2.value))
        simple_expr1 = isinstance(expr.expr1, ConstantNumeric) or isinstance(expr.expr1, Parameter) or isinstance(expr.expr1, Variable)
        simple_expr2 = isinstance(expr.expr2, ConstantNumeric) or isinstance(expr.expr2, Parameter) or isinstance(expr.expr2, Variable)
        if expr.op in commutative_operators and ((simple_expr1 and not simple_expr2) or (isinstance(expr.expr2, Variable) and isinstance(expr.expr1, ConstantNumeric))):
            expr.expr1, expr.expr2 = expr.expr2, expr.expr1
        if isinstance(expr.expr1, Variable) and isinstance(expr.expr2, ConstantNumeric):
            if expr.op == Operator.AND and isinstance(expr.expr1.mask, ConstantNumeric):
                expr.expr1.mask = ConstantNumeric(expr.expr1.mask.value & expr.expr2.value)
                return expr.expr1
            if expr.op == Operator.ADD and expr.expr1.div == None and expr.expr1.mod == None:
                if expr.expr1.add == None: expr.expr1.add = expr.expr2
                else: expr.expr1.add = ConstantNumeric(expr.expr1.add + expr.expr2.value)
                return expr.expr1
            if expr.op == Operator.SUB and expr.expr1.div == None and expr.expr1.mod == None:
                if expr.expr1.add == None: expr.expr1.add = ConstantNumeric(-expr.expr2.value)
                else: expr.expr1.add = ConstantNumeric(expr.expr1.add - expr.expr2.value)
                return expr.expr1
            if expr.op == Operator.DIV and expr.expr1.div == None and expr.expr1.mod == None:
                if expr.expr1.add == None: expr.expr1.add = ConstantNumeric(0)
                expr.expr1.div = expr.expr2
                return expr.expr1
            if expr.op == Operator.MOD and expr.expr1.div == None and expr.expr1.mod == None:
                if expr.expr1.add == None: expr.expr1.add = ConstantNumeric(0)
                expr.expr1.mod = expr.expr2
                return expr.expr1
    elif isinstance(expr, Parameter):
        expr.num = reduce_expr(expr.num, id_dicts)
    elif isinstance(expr, Variable):
        expr.num = reduce_expr(expr.num, id_dicts)
        expr.shift = reduce_expr(expr.shift, id_dicts)
        expr.mask = reduce_expr(expr.mask, id_dicts)
        expr.param = reduce_expr(expr.param, id_dicts)
    elif isinstance(expr, str):
        for id_dict in id_dicts:
            id_d, func = (id_dict, lambda x: ConstantNumeric(x)) if not isinstance(id_dict, tuple) else id_dict
            if expr in id_d:
                return func(id_d[expr])
        raise ScriptError("Unrecognized identifier '" + expr + "' encountered")
    return expr

def reduce_constant(expr, id_dicts = []):
    expr = reduce_expr(expr, id_dicts)
    if not isinstance(expr, ConstantNumeric):
        raise ConstError()
    return expr

########### code blocks ###########
class GRF:
    def __init__(self, alist):
        self.name = None
        self.desc = None
        self.grfid = None
        for assignment in alist:
            if not isinstance(assignment.value, String):
                raise ScriptError("Assignments in GRF-block must be constant strings")
            if assignment.name == "name": self.name = assignment.value
            elif assignment.name == "desc": self.desc = assignment.value
            elif assignment.name == "grfid": self.grfid = assignment.value
            else: raise ScriptError("Unkown item in GRF-block: " + assignment.name)
    
    def debug_print(self, indentation):
        print indentation*' ' + 'GRF'
        if self.grfid != None:
            print (2+indentation)*' ' + 'grfid:'
            self.grfid.debug_print(indentation + 4)
        if self.name != None:
            print (2+indentation)*' ' + 'Name:'
            self.name.debug_print(indentation + 4)
        if self.desc != None:
            print (2+indentation)*' ' + 'Description:'
            self.desc.debug_print(indentation + 4)
    
    def get_action_list(self):
        return [Action8(self.grfid, self.name, self.desc)]

class Conditional:
    def __init__(self, expr, block, else_block = None):
        self.expr = expr
        self.block = block
        self.else_block = else_block
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Conditional'
        if self.expr != None:
            print (2+indentation)*' ' + 'Expression:'
            self.expr.debug_print(indentation + 4)
        print (2+indentation)*' ' + 'Block:'
        print_script(self.block, indentation + 4)
        if self.else_block != None:
            print (indentation)*' ' + 'Else block:'
            self.else_block.debug_print(indentation)
    
    def get_action_list(self):
        return parse_conditional_block(self)

class Loop:
    def __init__(self, expr, block):
        self.expr = expr
        self.block = block
    
    def debug_print(self, indentation):
        print indentation*' ' + 'While loop'
        print (2+indentation)*' ' + 'Expression:'
        self.expr.debug_print(indentation + 4)
        print (2+indentation)*' ' + 'Block:'
        print_script(self.block, indentation + 4)
    
    def get_action_list(self):
        return parse_loop_block(self)

class Switch:
    def __init__(self, feature, var_range, name, expr, body):
        self.feature = reduce_constant(feature, [feature_ids])
        self.var_range = var_range
        self.name = name
        self.expr = expr
        self.body = body
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Switch, Feature =',self.feature.value,', name =', self.name
        print (2+indentation)*' ' + 'Expression:'
        self.expr.debug_print(indentation + 4)
        print (2+indentation)*' ' + 'Body:'
        self.body.debug_print(indentation + 4)
    
    def get_action_list(self):
        return parse_varaction2(self)

class SwitchBody:
    def __init__(self, default):
        self.default = default
        self.ranges = []
    
    def add_range(self, switch_range):
        self.ranges.append(switch_range)
        return self
    
    def debug_print(self, indentation):
        for r in self.ranges:
            r.debug_print(indentation)
        print indentation*' ' + 'Default:'
        if isinstance(self.default, str):
            print (indentation+2)*' ' + 'Go to switch:', self.default
        else:
            self.default.debug_print(indentation + 2)

class SwitchRange:
    def __init__(self, min, max, result):
        self.min = min
        self.max = max
        self.result = result
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Min:'
        self.min.debug_print(indentation + 2)
        print indentation*' ' + 'Max:'
        self.max.debug_print(indentation + 2)
        print indentation*' ' + 'Result:'
        if isinstance(self.result, str):
            print (indentation+2)*' ' + 'Go to switch:', self.result
        else:
            self.result.debug_print(indentation + 2)

class DeactivateBlock:
    def __init__(self, grfid_list):
        self.grfid_list = [reduce_expr(grfid) for grfid in grfid_list]
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Deactivate other newgrfs:'
        for grfid in self.grfid_list:
            grfid.debug_print(indentation + 2)
    
    def get_action_list(self):
        return parse_deactivate_block(self)

def validate_item_block(block_list):
    for block in block_list:
        if isinstance(block, PropertyBlock): continue
        if isinstance(block, GraphicsBlock): continue
        if isinstance(block, Conditional):
            while block != None:
                validate_item_block(block.block)
                block = block.else_block
            continue
        if isinstance(block, Loop):
            validate_item_block(block.body)
            continue
        raise ScriptError("Invalid block type inside 'Item'-block")

item_feature = None
item_id = None

class Item:
    def __init__(self, feature, body, id = None):
        self.feature = reduce_constant(feature, [feature_ids])
        self.body = body
        self.id = id
        validate_item_block(body)
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Item, feature', hex(self.feature.value)
        for b in self.body: b.debug_print(indentation + 2)
    
    def get_action_list(self):
        global item_feature, item_id
        if self.id != None:
            item_id = self.id
        else:
            item_id = ConstantNumeric(get_free_id(self.feature.value))
        item_feature = self.feature.value
        action_list = []
        for b in self.body:
            action_list.extend(b.get_action_list())
        return action_list

class Property:
    def __init__(self, name, value):
        self.name = name
        self.value = reduce_expr(value, [global_constants.const_table])
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Property:', self.name
        if isinstance(self.value, str):
            print (indentation + 2)*' ' + 'String: ', self.value
        else:
            self.value.debug_print(indentation + 2)

class PropertyBlock:
    def __init__(self, prop_list):
        self.prop_list = prop_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Property block:'
        for prop in self.prop_list:
            prop.debug_print(indentation + 2)
    
    def get_action_list(self):
        global item_feature, item_id
        return parse_property_block(self.prop_list, item_feature, item_id)

class GraphicsBlock:
    def __init__(self, graphics_list):
        self.graphics_list = graphics_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Graphics block:'
        for graphics in self.graphics_list:
            graphics.debug_print(indentation + 2)

class SpriteBlock:
    def __init__(self, feature, spriteset_list):
        self.feature = reduce_constant(feature, [feature_ids])
        self.spriteset_list = spriteset_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite block, feature', hex(self.feature.value)
        for spriteset in self.spriteset_list:
            spriteset.debug_print(indentation + 2)
    def get_action_list(self):
        return parse_sprite_block(self)

class SpriteSet:
    def __init__(self, name, pcx, sprite_list):
        self.name = name
        self.pcx = pcx
        self.sprite_list = sprite_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite set:', self.name
        print (indentation+2)*' ' + 'Source:  ', self.pcx
        print (indentation+2)*' ' + 'Sprites:'
        for sprite in self.sprite_list:
            sprite.debug_print(indentation + 4)

class RealSprite:
    def __init__(self, param_list):
        if not 6 <= len(param_list) <= 7:
            raise ScriptError("Invalid number of arguments for real sprite. Expected 6 or 7.")
        try:
            self.xpos  = reduce_constant(param_list[0])
            self.ypos  = reduce_constant(param_list[1])
            self.xsize = reduce_constant(param_list[2])
            self.ysize = reduce_constant(param_list[3])
            self.xrel  = reduce_constant(param_list[4])
            self.yrel  = reduce_constant(param_list[5])
            
            check_range(self.xpos.value,  0, 0x7fffFFFF,   "Real sprite paramater 'xpos'")
            check_range(self.ypos.value,  0, 0x7fffFFFF,   "Real sprite paramater 'ypos'")
            check_range(self.xsize.value, 1, 0xFFFF,       "Real sprite paramater 'xsize'")
            check_range(self.ysize.value, 1, 0xFF,         "Real sprite paramater 'ysize'")
            check_range(self.xrel.value, -0x8000, 0x7fff,  "Real sprite paramater 'xrel'")
            check_range(self.yrel.value, -0x8000, 0x7fff,  "Real sprite paramater 'yrel'")
            
            if len(param_list) == 7:
                self.compression = reduce_constant(param_list[6], [real_sprite_compression_flags])
                self.compression.value |= 0x01
            else:
                self.compression = ConstantNumeric(0x01)
            # only bits 0, 1, 3, and 6 can be set
            if (self.compression.value & ~0x4B) != 0:
                raise ScriptError("Real sprite compression is invalid; can only have bit 0, 1, 3 and/or 6 set, encountered " + str(self.compression.value))
        except ConstError:
            raise ScriptError("Real sprite parameters should be compile-time constants.")
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Real sprite'
        print (indentation+2)*' ' + 'position: (', self.xpos.value,  ',', self.ypos.value,  ')'
        print (indentation+2)*' ' + 'size:     (', self.xsize.value, ',', self.ysize.value, ')'
        print (indentation+2)*' ' + 'offset:   (', self.xrel.value,  ',', self.yrel.value,  ')'
        print (indentation+2)*' ' + 'compression: ', self.compression.value

class SpriteGroup:
    def __init__(self, name, spriteview_list):
        self.name = name
        self.spriteview_list = spriteview_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite group:', self.name
        for spriteview in self.spriteview_list:
            spriteview.debug_print(indentation + 2)

class SpriteView:
    def __init__(self, name, spriteset_list):
        self.name = name
        self.spriteset_list = spriteset_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite view:', self.name
        print (indentation+2)*' ' + 'Sprite sets:'
        for spriteset in self.spriteset_list:
            print (indentation+4)*' ' + spriteset

class LayoutSpriteGroup:
    def __init__(self, name, layout_sprite_list):
        self.name = name
        self.layout_sprite_list = layout_sprite_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Tile layout sprite group:', self.name
        for layout_sprite in self.layout_sprite_list:
            layout_sprite.debug_print(indentation + 2)

class LayoutSprite:
    def __init__(self, type, param_list):
        self.type = type
        self.param_list = param_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Tile layout sprite of type:', self.type
        for layout_param in self.param_list:
            layout_param.debug_print(indentation + 2)

class LayoutParam:
    def __init__(self, name, value):
        self.name = name
        self.value = value
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Layout parameter:', self.name
        if isinstance(self.value, str):
            print (indentation + 2)*' ' + 'String: ', self.value
        else:
            self.value.debug_print(indentation + 2)

class Error:
    def __init__(self, param_list):
        self.params = []
        if not 2 <= len(param_list) <= 5:
            raise ScriptError("'error' expects between 2 and 5 parameters, got " + str(len(param_list)))
        self.severity = reduce_expr(param_list[0], [error_severity])
        self.msg      = param_list[1]
        self.data     = param_list[2] if len(param_list) >= 3 else None
        self.params.append(reduce_expr(param_list[3]) if len(param_list) >= 4 else None)
        self.params.append(reduce_expr(param_list[4]) if len(param_list) >= 5 else None)
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Error, msg = ', self.msg
        print (indentation+2)*' ' + 'Severity:'
        self.severity.debug_print(indentation + 4)
        print (indentation+2)*' ' + 'Data: ', self.data
        print (indentation+2)*' ' + 'Param1: '
        if self.params[0] is not None: self.params[0].debug_print(indentation + 4)
        print (indentation+2)*' ' + 'Param2: '
        if self.params[1] is not None: self.params[1].debug_print(indentation + 4)
    
    def get_action_list(self):
        return parse_error_block(self)

class CargoTable:
    def __init__(self, cargo_list):
        self.cargo_list = cargo_list
    
    def debug_print(self, indentation):
        print indentation*' ' + 'Cargo table'
        for cargo in self.cargo_list:
            print (indentation+2)*' ' + 'Cargo:', cargo
    
    def get_action_list(self):
        return get_cargolist_action(self.cargo_list)
