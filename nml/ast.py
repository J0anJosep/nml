import string
from expression import *
from actions.action0 import *
from actions.action1 import *
from actions.real_sprite import *
from actions.action2var import *
from actions.action3 import *
from actions.action7 import *
from actions.action8 import *
from actions.actionA import *
from actions.actionB import *
from actions.actionD import *
from actions.actionE import *
from actions.sprite_count import SpriteCountAction
import global_constants
import unit

def print_script(script, indent):
    for r in script:
        r.debug_print(indent)

feature_ids = {
    'FEAT_TRAINS': 0x00,
    'FEAT_ROADVEHS': 0x01,
    'FEAT_SHIPS': 0x02,
    'FEAT_AIRCRAFTS': 0x03,
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
    'FEAT_OBJECTS': 0x0F,
    'FEAT_RAILTYPES': 0x10,
    'FEAT_AIRPORTTILES': 0x11,
}

class ParameterAssignment(object):
    def __init__(self, param, value):
        self.param = param
        self.value = reduce_expr(value, [global_constants.const_table, cargo_numbers])

    def debug_print(self, indentation):
        print indentation*' ' + 'Parameter assignment'
        self.param.debug_print(indentation + 2)
        self.value.debug_print(indentation + 2)

    def get_action_list(self):
        return parse_actionD(self)

    def __str__(self):
        return 'param[%s] = %s;\n' % (str(self.param), str(self.value))

########### code blocks ###########
class GRF(object):
    def __init__(self, alist):
        self.name = None
        self.desc = None
        self.grfid = None
        for assignment in alist:
            if assignment.name == "grfid":
                if not isinstance(assignment.value, basestring):
                    raise ScriptError("GRFID must be a string literal")
            elif not isinstance(assignment.value, String):
                raise ScriptError("Assignments in GRF-block must be constant strings")
            if assignment.name == "name": self.name = assignment.value
            elif assignment.name == "desc": self.desc = assignment.value
            elif assignment.name == "grfid": self.grfid = assignment.value
            else: raise ScriptError("Unkown item in GRF-block: " + assignment.name)

    def debug_print(self, indentation):
        print indentation*' ' + 'GRF'
        if self.grfid is not None:
            print (2+indentation)*' ' + 'grfid:', self.grfid
        if self.name is not None:
            print (2+indentation)*' ' + 'Name:'
            self.name.debug_print(indentation + 4)
        if self.desc is not None:
            print (2+indentation)*' ' + 'Description:'
            self.desc.debug_print(indentation + 4)

    def get_action_list(self):
        return [Action8(self.grfid, self.name, self.desc)]

    def __str__(self):
        ret = 'grf {\n'
        ret += '\tgrfid: "%s";\n' % str(self.grfid)
        if self.name is not None:
            ret += '\tname: %s;\n' % str(self.name)
        if self.desc is not None:
            ret += '\tdesc: %s;\n' % str(self.desc)
        ret += '}\n'
        return ret

class Conditional(object):
    def __init__(self, expr, block, else_block = None):
        self.expr = expr
        self.block = block
        self.else_block = else_block

    def debug_print(self, indentation):
        print indentation*' ' + 'Conditional'
        if self.expr is not None:
            print (2+indentation)*' ' + 'Expression:'
            self.expr.debug_print(indentation + 4)
        print (2+indentation)*' ' + 'Block:'
        print_script(self.block, indentation + 4)
        if self.else_block is not None:
            print (indentation)*' ' + 'Else block:'
            self.else_block.debug_print(indentation)

    def get_action_list(self):
        return parse_conditional_block(self)

    def __str__(self):
        ret = ''
        if self.expr is not None:
            ret += 'if (%s) {\n' % str(self.expr)
        for b in self.block:
            ret += '\t' + (string.replace(str(b), '\n', '\n\t'))[0:-1]
        if self.expr is not None:
            if self.else_block is not None:
                ret += '} else {\n'
                ret += str(self.else_block)
            ret += '}\n'
        return ret

class Loop(object):
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

    def __str__(self):
        ret = 'while(%s) {\n' % self.expr
        for b in self.block:
            ret += '\t' + (string.replace(str(b), '\n', '\n\t'))[0:-1]
        ret += '}\n'
        return ret

class Switch(object):
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

    def __str__(self):
        var_range = 'SELF' if self.var_range == 0x89 else 'PARENT'
        return 'switch(%s, %s, %s, %s) {\n%s}\n' % (str(self.feature), var_range, str(self.name), str(self.expr), str(self.body))


class SwitchBody(object):
    def __init__(self, ranges, default):
        self.ranges = ranges
        self.default = default

    def debug_print(self, indentation):
        for r in self.ranges:
            r.debug_print(indentation)
        print indentation*' ' + 'Default:'
        if isinstance(self.default, basestring):
            print (indentation+2)*' ' + 'Go to switch:', self.default
        elif self.default is None:
            print (indentation+2)*' ' + 'Return computed value'
        else:
            self.default.debug_print(indentation + 2)

    def __str__(self):
        ret = ''
        for r in self.ranges:
            ret += '\t%s\n' % str(r)
        if self.default is None:
            ret += '\treturn;\n'
        elif isinstance(self.default, basestring):
            ret += '\t%s;\n' % self.default
        else:
            ret += '\t%s;\n' % str(self.default)
        return ret

class SwitchRange(object):
    def __init__(self, min, max, result):
        self.min = reduce_constant(min)
        self.max = reduce_constant(max)
        self.result = result

    def debug_print(self, indentation):
        print indentation*' ' + 'Min:'
        self.min.debug_print(indentation + 2)
        print indentation*' ' + 'Max:'
        self.max.debug_print(indentation + 2)
        print indentation*' ' + 'Result:'
        if isinstance(self.result, basestring):
            print (indentation+2)*' ' + 'Go to switch:', self.result
        elif self.result is None:
            print (indentation+2)*' ' + 'Return computed value'
        else:
            self.result.debug_print(indentation + 2)

    def __str__(self):
        ret = str(self.min)
        if self.max.value != self.min.value:
            ret += '..' + str(self.max)
        if isinstance(self.result, basestring):
            ret += ': %s;' % self.result
        elif self.result is None:
            ret += ': return;'
        else:
            ret += ': return %s;' % str(self.result)
        return ret

class DeactivateBlock(object):
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
        if isinstance(block, LiveryOverride): continue
        if isinstance(block, Conditional):
            while block is not None:
                validate_item_block(block.block)
                block = block.else_block
            continue
        if isinstance(block, Loop):
            validate_item_block(block.body)
            continue
        raise ScriptError("Invalid block type inside 'Item'-block")

item_feature = None
item_id = None

class Item(object):
    def __init__(self, feature, body, name = None, id = None):
        global item_names
        self.feature = reduce_constant(feature, [feature_ids])
        self.body = body
        self.name = name
        if name is not None and name in item_names:
            self.id = ConstantNumeric(item_names[name])
        elif id is None: self.id = ConstantNumeric(get_free_id(self.feature.value))
        else: self.id = reduce_constant(id)
        if name is not None:
            item_names[name] = self.id.value
        validate_item_block(body)

    def debug_print(self, indentation):
        print indentation*' ' + 'Item, feature', hex(self.feature.value)
        for b in self.body: b.debug_print(indentation + 2)

    def get_action_list(self):
        global item_feature, item_id
        item_id = self.id
        item_feature = self.feature.value
        action_list = []
        for b in self.body:
            action_list.extend(b.get_action_list())
        return action_list

    def __str__(self):
        ret = 'item(%d' % self.feature.value
        if self.name is not None:
            ret += ', %s, %s' % (self.name, str(self.id))
        ret += ') {\n'
        for b in self.body:
            ret += '\t' + (string.replace(str(b), '\n', '\n\t'))[0:-1]
        ret += '}\n'
        return ret

class Unit(object):
    def __init__(self, name):
        assert name in unit.units
        self.name = name
        self.type = unit.units[name]['type']
        self.convert = unit.units[name]['convert']

    def __str__(self):
        return self.name

class Property(object):
    def __init__(self, name, value, unit):
        self.name = name
        self.value = reduce_expr(value, [global_constants.const_table, cargo_numbers])
        self.unit = unit
        if unit is not None and not (isinstance(self.value, ConstantNumeric) or isinstance(self.value, ConstantFloat)):
            raise ScriptError("Using a unit for a property is only allowed if the value is constant")

    def debug_print(self, indentation):
        print indentation*' ' + 'Property:', self.name
        if isinstance(self.value, basestring):
            print (indentation + 2)*' ' + 'String: ', self.value
        else:
            self.value.debug_print(indentation + 2)

    def __str__(self):
        unit = '' if self.unit is None else ' ' + str(self.unit)
        return '\t%s: %s%s;' % (self.name, self.value, unit)

class PropertyBlock(object):
    def __init__(self, prop_list):
        self.prop_list = prop_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Property block:'
        for prop in self.prop_list:
            prop.debug_print(indentation + 2)

    def get_action_list(self):
        global item_feature, item_id
        return parse_property_block(self.prop_list, item_feature, item_id)

    def __str__(self):
        ret = 'property {\n'
        for prop in self.prop_list:
            ret += '%s\n' % str(prop)
        ret += '}\n'
        return ret

class LiveryOverride(object):
    def __init__(self, wagon_id, graphics_block):
        self.graphics_block = graphics_block
        self.wagon_id = wagon_id

    def debug_print(self, indentation):
        print indentation*' ' + 'Liverry override, wagon id:'
        self.wagon_id.debug_print(indentation + 2)
        for graphics in self.graphics_block.graphics_list:
            graphics.debug_print(indentation + 2)

    def get_action_list(self):
        global item_feature, item_names
        wagon_id = reduce_constant(self.wagon_id, [item_names])
        return parse_graphics_block(self.graphics_block.graphics_list, self.graphics_block.default_graphics, item_feature, wagon_id, True)

class GraphicsBlock(object):
    def __init__(self, default_graphics):
        self.default_graphics = default_graphics
        self.graphics_list = []

    def append_definition(self, graphics_assignment):
        self.graphics_list.append(graphics_assignment)
        return self

    def debug_print(self, indentation):
        print indentation*' ' + 'Graphics block:'
        for graphics in self.graphics_list:
            graphics.debug_print(indentation + 2)

    def get_action_list(self):
        global item_feature, item_id
        return parse_graphics_block(self.graphics_list, self.default_graphics, item_feature, item_id)

class GraphicsDefinition(object):
    def __init__(self, cargo_id, action2_id):
        self.cargo_id = cargo_id
        self.action2_id = action2_id

    def debug_print(self, indentation):
        print indentation*' ' + 'Graphics:'
        print (indentation+2)*' ' + 'Cargo:', self.cargo_id
        print (indentation+2)*' ' + 'Linked to action2:', self.action2_id

class ReplaceSprite(object):
    def __init__(self, start_id, pcx, sprite_list):
        self.start_id = reduce_constant(start_id)
        self.pcx = pcx
        self.sprite_list = sprite_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Replace sprites starting at', self.start_id
        print (indentation+2)*' ' + 'Source:  ', self.pcx
        print (indentation+2)*' ' + 'Sprites:'
        for sprite in self.sprite_list:
            sprite.debug_print(indentation + 4)

    def get_action_list(self):
        return parse_actionA(self)

class SpriteBlock(object):
    def __init__(self, feature, spriteset_list):
        self.feature = reduce_constant(feature, [feature_ids])
        self.spriteset_list = spriteset_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite block, feature', hex(self.feature.value)
        for spriteset in self.spriteset_list:
            spriteset.debug_print(indentation + 2)
    def get_action_list(self):
        return parse_sprite_block(self)

class TemplateDeclaration(object):
    def __init__(self, name, param_list, sprite_list):
        self.name = name
        if name not in sprite_template_map:
            sprite_template_map[name] = self
        else:
            raise ScriptError("Template named '" + name + "' is already defined")
        self.param_list = param_list
        self.sprite_list = sprite_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Template declaration:', self.name
        print (indentation+2)*' ' + 'Parameters:'
        for param in self.param_list:
            print (indentation+4)*' ' + param
        print (indentation+2)*' ' + 'Sprites:'
        for sprite in self.sprite_list:
            sprite.debug_print(indentation + 4)

    def get_action_list(self):
        return []

class TemplateUsage(object):
    def __init__(self, name, param_list):
        self.name = name
        self.param_list = param_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Template used:', self.name
        print (indentation+2)*' ' + 'Parameters:'
        for param in self.param_list:
            if isinstance(param, basestring):
                print (indentation+4)*' ' + 'ID:', param
            else:
                param.debug_print(indentation + 4)

class SpriteSet(object):
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

class RealSprite(object):
    def __init__(self, param_list = None):
        self.param_list = param_list
        self.is_empty = False

    def debug_print(self, indentation):
        print indentation*' ' + 'Real sprite, parameters:'
        for param in self.param_list:
            if isinstance(param, basestring):
                print (indentation+2)*' ' + 'ID:', param
            else:
                param.debug_print(indentation + 2)

class SpriteGroup(object):
    def __init__(self, name, spriteview_list):
        self.name = name
        self.spriteview_list = spriteview_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite group:', self.name
        for spriteview in self.spriteview_list:
            spriteview.debug_print(indentation + 2)

class SpriteView(object):
    def __init__(self, name, spriteset_list):
        self.name = name
        self.spriteset_list = spriteset_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite view:', self.name
        print (indentation+2)*' ' + 'Sprite sets:'
        for spriteset in self.spriteset_list:
            print (indentation+4)*' ' + spriteset

class LayoutSpriteGroup(object):
    def __init__(self, name, layout_sprite_list):
        self.name = name
        self.layout_sprite_list = layout_sprite_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Tile layout sprite group:', self.name
        for layout_sprite in self.layout_sprite_list:
            layout_sprite.debug_print(indentation + 2)

class LayoutSprite(object):
    def __init__(self, type, param_list):
        self.type = type
        self.param_list = param_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Tile layout sprite of type:', self.type
        for layout_param in self.param_list:
            layout_param.debug_print(indentation + 2)

class LayoutParam(object):
    def __init__(self, name, value):
        self.name = name
        self.value = reduce_expr(value, [global_constants.const_table], False)

    def debug_print(self, indentation):
        print indentation*' ' + 'Layout parameter:', self.name
        if isinstance(self.value, basestring):
            print (indentation + 2)*' ' + 'String: ', self.value
        else:
            self.value.debug_print(indentation + 2)

class Error(object):
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

class CargoTable(object):
    def __init__(self, cargo_list):
        global cargo_numbers;
        self.cargo_list = cargo_list
        i = 0
        for cargo in cargo_list:
            cargo_numbers[cargo] = i
            i += 1

    def debug_print(self, indentation):
        print indentation*' ' + 'Cargo table'
        for cargo in self.cargo_list:
            print (indentation+2)*' ' + 'Cargo:', cargo

    def get_action_list(self):
        return get_cargolist_action(self.cargo_list)

    def __str__(self):
        ret = 'cargotable {\n'
        ret += ', '.join(self.cargo_list)
        ret += '\n}\n'
        return ret

class SpriteCount(object):
    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite count'

    def get_action_list(self):
        return [SpriteCountAction()]
