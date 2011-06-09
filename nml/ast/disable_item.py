from nml import expression, generic, global_constants
from nml.actions import action0
from nml.ast import general

class DisableItem(object):
    """
    Class representing a 'disable_item' statement in the AST.

    @ivar feature: Feature of the items to disable
    @type feature: L{ConstantNumeric}

    @ivar first_id: First item ID to disable
    @type first_id: L{ConstantNumeric}, or C{None} if not set

    @ivar last_id: Last item ID to disable
    @type last_id: L{ConstantNumeric}, or C{None} if not set

    @ivar pos: Position information
    @type pos: L{Position}
    """
    def __init__(self, param_list, pos):
        if not (1 <= len(param_list) <= 3):
            raise generic.ScriptError("disable_item() requires between 1 and 3 parameters, encountered %d." % len(param_list), pos)
        self.feature = general.parse_feature(param_list[0])

        if len(param_list) > 1:
            self.first_id = param_list[1].reduce_constant(global_constants.const_list)
        else:
            self.first_id = None

        if len(param_list) > 2:
            self.last_id = param_list[2].reduce_constant(global_constants.const_list)
            if self.last_id.value < self.first_id.value:
                raise generic.ScriptError("Last id to disable may not be lower than the first id.", pos)
        else:
            self.last_id = None

        self.pos = pos

    def register_names(self):
        pass

    def debug_print(self, indentation):
        print indentation*' ' + 'Disable items, feature=' + str(self.feature.value)
        if self.first_id is not None:
            print (indentation+2)*' ' + 'First ID:'
            self.first_id.debug_print(indentation + 4)
        if self.last_id is not None:
            print (indentation+2)*' ' + 'Last ID:'
            self.last_id.debug_print(indentation + 4)

    def __str__(self):
        ret = str(self.feature)
        if self.first_id is not None: ret += ', ' + str(self.first_id)
        if self.last_id is not None: ret += ', ' + str(self.last_id)
        return 'disable_item(%s);\n' % ret

    def pre_process(self):
        pass

    def get_action_list(self):
        return action0.get_disable_actions(self)
