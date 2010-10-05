from nml import expression, nmlop, generic, free_number_list
from nml.actions import base_action, action6, actionD, action10

free_labels = free_number_list.FreeNumberList(range(0xFF, 0x0F, -1))
free_labels.save() # FreeNumberList needs at least one call to save before the first pop

class SkipAction(base_action.BaseAction):
    def __init__(self, feature, var, varsize, condtype, value, label):
        self.feature = feature
        self.label = label
        self.var = var
        self.varsize = varsize
        self.condtype = condtype
        self.value = value
        self.label = label

    def write(self, file):
        size = 5 + self.varsize
        file.start_sprite(size)
        file.print_bytex(self.feature)
        file.print_bytex(self.var)
        file.print_bytex(self.varsize)
        file.print_bytex(self.condtype[0], self.condtype[1])
        file.print_varx(self.value, self.varsize)
        file.print_bytex(self.label)
        file.newline()
        file.end_sprite()

    def skip_action7(self):
        return self.feature == 7

    def skip_action9(self):
        return self.feature == 9 or self.label == 0

class UnconditionalSkipAction(SkipAction):
    def __init__(self, feature, label):
        SkipAction.__init__(self, feature, 0x9A, 1, (0, r'\71'), 0, label)

def op_to_cond_op(op):
    #The operators are reversed as we want to skip if the expression is true
    #while the nml-syntax wants to execute the block if the expression is true
    if op == nmlop.CMP_NEQ: return (2, r'\7=')
    if op == nmlop.CMP_EQ: return (3, r'\7!')
    if op == nmlop.CMP_GE: return (4, r'\7<')
    if op == nmlop.CMP_LE: return (5, r'\7>')

def parse_conditional(expr):
    '''
    Parse an expression and return enough information to use
    that expression as a conditional statement.
    Return value is a tuple with the following elements:
    - Parameter number (as integer) to use in comparison or None for unconditional skip
    - List of actions needed to set the given parameter to the correct value
    - The type of comparison to be done
    - The value to compare against (as integer)
    - The size of the value (as integer)
    '''
    if expr is None:
        return (None, [], (2, r'\7='), 0, 4)
    if isinstance(expr, expression.BinOp):
        if expr.op == nmlop.HASBIT:
            if isinstance(expr.expr1, expression.Parameter) and isinstance(expr.expr1.num, expression.ConstantNumeric):
                param = expr.expr1.num.value
                actions = []
            else:
                param, actions = actionD.get_tmp_parameter(expr.expr1)
            if isinstance(expr.expr2, expression.ConstantNumeric):
                bit_num = expr.expr2.value
            else:
                if isinstance(expr.expr2, expression.Parameter) and isinstance(expr.expr2.num, expression.ConstantNumeric):
                   param = expr.expr2.num.value
                else:
                    param, tmp_action_list = actionD.get_tmp_parameter(expr.expr2)
                    actions.extend(tmp_action_list)
                act6 = action6.Action6()
                act6.modify_bytes(param, 1, 4)
                actions.append(act6)
                bit_num = 0
            return (param, actions, (1, r'\70'), bit_num , 1)
        elif expr.op in (nmlop.CMP_EQ, nmlop.CMP_NEQ, nmlop.CMP_LE, nmlop.CMP_GE) \
                and isinstance(expr.expr2, expression.ConstantNumeric):
            if isinstance(expr.expr1, expression.Parameter) and isinstance(expr.expr1.num, expression.ConstantNumeric):
                param = expr.expr1.num.value
                actions = []
            else:
                param, actions = actionD.get_tmp_parameter(expr.expr1)
            op = op_to_cond_op(expr.op)
            return (param, actions, op, expr.expr2.value, 4)

    param, actions = actionD.get_tmp_parameter(expr)
    return (param, actions, (2, r'\7='), 0, 4)

def cond_skip_actions(action_list, param, condtype, value, value_size):
    actions = []
    start, length = 0, 0
    allow7, allow9 = True, True
    for i, action in enumerate(action_list):
        if length == 0 and not action.skip_needed():
            actions.append(action)
            start += 1
            continue
        if allow7 and action.skip_action7():
            allow9 = allow9 and action.skip_action9()
            length += 1
            continue
        if allow9 and action.skip_action9():
            # If action7 was ok, we wouldn't be in this block.
            # Set allow7 to False in here so in case both
            # action7 and action9 don't work at least one
            # of allow7/allow9 is True. This is possible because
            # all previous actions could be skipped at least one.
            allow7 = False
            length += 1
            continue
        # neither action7 nor action9 can be used. add all
        # previous actions to the list and start a new block
        feature = 7 if allow7 else 9
        if length < 0x10:
            target = length
            label = None
        else:
            target = free_labels.pop()
            label = action10.Action10(target)
        actions.append(SkipAction(feature, param, value_size, condtype, value, target))
        actions.extend(action_list[start:start+length])
        if label is not None: actions.append(label)
        start = i
        length = 1
        allow7, allow9 = action.skip_action7(), action.skip_action9()

    if length > 0:
        feature = 7 if allow7 else 9
        if length < 0x10:
            target = length
            label = None
        else:
            target = free_labels.pop()
            label = action10.Action10(target)
        actions.append(SkipAction(feature, param, value_size, condtype, value, target))
        actions.extend(action_list[start:start+length])
        if label is not None: actions.append(label)
    return actions

def parse_conditional_block(cond):
    action6.free_parameters.save()

    multiple_blocks = cond.else_block is not None
    if multiple_blocks:
        # the skip all parameter is used to skip all blocks after one
        # of the conditionals was true. We can't always skip directly
        # to the end of the blocks since action7/action9 can't always
        # be mixed
        param_skip_all, action_list = actionD.get_tmp_parameter(expression.ConstantNumeric(0xFFFFFFFF))
    else:
        action_list = []

    blocks = []
    while cond is not None:
        end_label = free_labels.pop()
        blocks.append({'expr': cond.expr, 'statements': cond.block, 'last_block': cond.else_block is None})
        cond = cond.else_block

    # use parse_conditional here, we also need to know if all generated
    # actions (like action6) can be skipped safely
    for block in blocks:
        block['param_dst'], block['cond_actions'], block['cond_type'], block['cond_value'], block['cond_value_size'] = parse_conditional(block['expr'])
        if not block['last_block']:
            block['action_list'] = [actionD.ActionD(expression.ConstantNumeric(param_skip_all), expression.ConstantNumeric(0xFF), nmlop.ASSIGN, expression.ConstantNumeric(0), expression.ConstantNumeric(0))]
        else:
            block['action_list'] = []
        for stmt in block['statements']:
            block['action_list'].extend(stmt.get_action_list())

    # Main problem: action10 can't be skipped by action9, so we're
    # nearly forced to use action7, but action7 can't safely skip action6
    # Solution: use temporary parameter, set to 0 for not skip, !=0 for skip.
    # then skip every block of actions (as large as possible) with either
    # action7 or action9, depending on which of the two works.

    for i, block in enumerate(blocks):
        param = block['param_dst']
        if i == 0: action_list.extend(block['cond_actions'])
        else:
            action_list.extend(cond_skip_actions(block['cond_actions'], param_skip_all, (2, r'\7='), 0, 4))
            if param is None:
                param = param_skip_all
            else:
                action_list.append(actionD.ActionD(expression.ConstantNumeric(block['param_dst']), expression.ConstantNumeric(block['param_dst']), nmlop.AND, expression.ConstantNumeric(param_skip_all)))
        action_list.extend(cond_skip_actions(block['action_list'], param, block['cond_type'], block['cond_value'], block['cond_value_size']))

    action6.free_parameters.restore()
    return action_list

def parse_loop_block(loop):
    action6.free_parameters.save()
    begin_label = free_labels.pop_unique()
    action_list = [action10.Action10(begin_label)]

    cond_param, cond_actions, cond_type, cond_value, cond_value_size = parse_conditional(loop.expr)
    block_actions = []
    for stmt in loop.block:
        block_actions.extend(stmt.get_action_list())

    action_list.extend(cond_actions)
    block_actions.append(UnconditionalSkipAction(9, begin_label))
    action_list.extend(cond_skip_actions(block_actions, cond_param, cond_type, cond_value, cond_value_size))

    action6.free_parameters.restore()
    return action_list
