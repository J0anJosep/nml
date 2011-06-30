from nml.actions import action2, action6, actionD, action2var_variables, action4
from nml import expression, generic, global_constants, nmlop, unit
from nml.ast import switch_range

class Action2Var(action2.Action2):
    """
    Variational Action2. This is the NFO equivalent of a switch-block in NML.
    It computes a single integer from one or more variables and picks it's
    return value based on the result of the computation. The return value can
    be either a 15bit integer or a reference to another action2.

    @ivar type_byte: The size (byte, word, double word) and access type (own 
                     object or related object). 0x89 (own object, double word)
                     and 0x8A (related object, double word) and the only
                     supported values.
    @type type_byte: C{int}

    @ivar ranges: List of return value ranges. Each range contains a minimum and
                  a maximum value and a return value. The list is checked in order,
                  if the result of the computation is between the miminum and
                  maximum (inclusive) of one range the result of that range is
                  returned. The result can be either an integer of another
                  action2.
    @ivar ranges: C{list} of L{SwitchRange}
    """
    def __init__(self, feature, name, type_byte):
        action2.Action2.__init__(self, feature, name)
        self.type_byte = type_byte
        self.ranges = []

    def resolve_tmp_storage(self):
        for var in self.var_list:
            if isinstance(var, VarAction2StoreTempVar):
                location = self.tmp_locations[0]
                self.remove_tmp_location(location, False)
                var.set_register(location)

    def prepare_output(self):
        action2.Action2.prepare_output(self)
        for i in range(0, len(self.var_list) - 1, 2):
            self.var_list[i].shift |= 0x20

        for r in self.ranges:
            if isinstance(r.result, expression.SpriteGroupRef):
                r.result = r.result.get_action2_id()
            else:
                r.result = r.result.value | 0x8000
        if isinstance(self.default_result, expression.SpriteGroupRef):
            self.default_result = self.default_result.get_action2_id()
        else:
            self.default_result = self.default_result.value | 0x8000

    def write(self, file):
        #type_byte, num_ranges, default_result = 4
        #2 bytes for the result, 8 bytes for the min/max range.
        size = 4 + (2 + 8) * len(self.ranges)
        for var in self.var_list:
            if isinstance(var, nmlop.Operator):
                size += 1
            else:
                size += var.get_size()

        self.write_sprite_start(file, size)
        file.print_bytex(self.type_byte)
        file.newline()
        for var in self.var_list:
            if isinstance(var, nmlop.Operator):
                file.print_bytex(var.act2_num, var.act2_str)
            else:
                var.write(file, 4)
                file.newline(var.comment)
        file.print_byte(len(self.ranges))
        file.newline()
        for r in self.ranges:
            file.print_wordx(r.result)
            file.print_varx(r.min.value, 4)
            file.print_varx(r.max.value, 4)
            file.newline(r.comment)
        file.print_wordx(self.default_result)
        file.comment(self.default_comment)
        file.end_sprite()

class VarAction2Var(object):
    """
    Represents a variable for use in a (advanced) variational action2.

    @ivar var_num: Number of the variable to use.
    @type var_num: C{int}

    @ivar shift: The number of bits to shift the value of the given variable to the right.
    @type shift: C{int}

    @ivar mask: Bitmask to use on the value after shifting it.
    @type mask: C{int}

    @ivar parameter: Parameter to be used as argument for the variable.
    @type parameter: C{int} or C{None}
    @precondition: (0x60 <= var_num <= 0x7F) == (parameter is not None)

    @ivar add: If not C{None}, add this value to the result.
    @type add: C{int} or C{None}

    @ivar div: If not C{None}, divide the result by this.
    @type add: C{int} or C{None}

    @ivar mod: If not C{None}, compute (result module mod).
    @type add: C{int} or C{None}

    @ivar comment: Textual description of this variable.
    @type comment: C{basestr}
    """
    def __init__(self, var_num, shift, mask, parameter = None):
        self.var_num = var_num
        self.shift = shift
        self.mask = mask
        self.parameter = parameter
        self.add = None
        self.div = None
        self.mod = None
        self.comment = ""

    def write(self, file, size):
        file.print_bytex(self.var_num)
        if self.parameter is not None:
            file.print_bytex(self.parameter)
        if self.mod is not None:
            self.shift |= 0x80
        elif self.add is not None or self.div is not None:
            self.shift |= 0x40
        file.print_bytex(self.shift)
        file.print_varx(self.mask, size)
        if self.add is not None:
            file.print_varx(self.add, size)
            if self.div is not None:
                file.print_varx(self.div, size)
            elif self.mod is not None:
                file.print_varx(self.mod, size)
            else:
                #no div or add, just divide by 1
                file.print_varx(1, size)

    def get_size(self):
        #var number (1) [+ parameter (1)] + shift num (1) + and mask (4) [+ add (4) + div/mod (4)]
        size = 6
        if self.parameter is not None: size += 1
        if self.add is not None or self.div is not None or self.mod is not None: size += 8
        return size

    def supported_by_actionD(self, raise_error):
        assert not raise_error
        return False

class VarAction2StoreTempVar(VarAction2Var):
    def __init__(self):
        VarAction2Var.__init__(self, 0x1A, 0, 0)
        #mask holds the number, it's resolved in Action2Var.resolve_tmp_storage
        self.load_vars = []

    def set_register(self, register):
        self.mask = register
        for load_var in self.load_vars:
            load_var.parameter = register

    def get_size(self):
        return 6

def get_mask(size):
    if size == 1: return 0xFF
    elif size == 2: return 0xFFFF
    return 0xFFFFFFFF

class VarAction2LoadTempVar(VarAction2Var, expression.Expression):
    def __init__(self, tmp_var):
        VarAction2Var.__init__(self, 0x7D, 0, 0)
        expression.Expression.__init__(self, None)
        assert isinstance(tmp_var, VarAction2StoreTempVar)
        tmp_var.load_vars.append(self)

    def write(self, file, size):
        self.mask = get_mask(size)
        VarAction2Var.write(self, file, size)

    def get_size(self):
        return 7

    def reduce(self, id_dicts = [], unknown_id_fatal = True):
        return self

    def supported_by_action2(self, raise_error):
        return True

    def supported_by_actionD(self, raise_error):
        assert not raise_error
        return False

class Modification(object):
    def __init__(self, param, size, offset):
        self.param = param
        self.size = size
        self.offset = offset

def pow2(expr):
    #2**x = (1 ror (32 - x))
    if isinstance(expr, expression.ConstantNumeric):
        return expression.ConstantNumeric(1 << expr.value)
    expr = expression.BinOp(nmlop.SUB, expression.ConstantNumeric(32), expr)
    expr = expression.BinOp(nmlop.ROT_RIGHT, expression.ConstantNumeric(1), expr)
    return expr

class Varaction2Parser(object):
    def __init__(self, feature):
        self.feature = feature # Depends on feature and var_range
        self.extra_actions = []
        self.mods = []
        self.var_list = []
        self.var_list_size = 0


    def preprocess_binop(self, expr):
        """
        Several nml operators are not directly support by nfo so we have to work
        around that by implementing those operators in terms of others.

        @return: A pre-processed version of the expression.
        @rtype:  L{Expression}
        """
        assert isinstance(expr, expression.BinOp)
        if expr.op == nmlop.CMP_LT:
            #return value is 0, 1 or 2, we want to map 0 to 1 and the others to 0
            expr = expression.BinOp(nmlop.VACT2_CMP, expr.expr1, expr.expr2)
            #reduce the problem to 0/1
            expr = expression.BinOp(nmlop.MIN, expr, expression.ConstantNumeric(1))
            #and invert the result
            expr = expression.BinOp(nmlop.XOR, expr, expression.ConstantNumeric(1))
        elif expr.op == nmlop.CMP_GT:
            #return value is 0, 1 or 2, we want to map 2 to 1 and the others to 0
            expr = expression.BinOp(nmlop.VACT2_CMP, expr.expr1, expr.expr2)
            #subtract one
            expr = expression.BinOp(nmlop.SUB, expr, expression.ConstantNumeric(1))
            #map -1 and 0 to 0
            expr = expression.BinOp(nmlop.MAX, expr, expression.ConstantNumeric(0))
        elif expr.op == nmlop.CMP_LE:
            #return value is 0, 1 or 2, we want to map 2 to 0 and the others to 1
            expr = expression.BinOp(nmlop.VACT2_CMP, expr.expr1, expr.expr2)
            #swap 0 and 2
            expr = expression.BinOp(nmlop.XOR, expr, expression.ConstantNumeric(2))
            #map 1/2 to 1
            expr = expression.BinOp(nmlop.MIN, expr, expression.ConstantNumeric(1))
        elif expr.op == nmlop.CMP_GE:
            #return value is 0, 1 or 2, we want to map 1/2 to 1
            expr = expression.BinOp(nmlop.VACT2_CMP, expr.expr1, expr.expr2)
            expr = expression.BinOp(nmlop.MIN, expr, expression.ConstantNumeric(1))
        elif expr.op == nmlop.CMP_EQ:
            #return value is 0, 1 or 2, we want to map 1 to 1, other to 0
            expr = expression.BinOp(nmlop.VACT2_CMP, expr.expr1, expr.expr2)
            expr = expression.BinOp(nmlop.AND, expr, expression.ConstantNumeric(1))
        elif expr.op == nmlop.CMP_NEQ:
            #same as CMP_EQ but invert the result
            expr = expression.BinOp(nmlop.VACT2_CMP, expr.expr1, expr.expr2)
            expr = expression.BinOp(nmlop.AND, expr, expression.ConstantNumeric(1))
            expr = expression.BinOp(nmlop.XOR, expr, expression.ConstantNumeric(1))

        elif expr.op == nmlop.SHIFT_LEFT:
            #a << b ==> a * (2**b)
            expr = expression.BinOp(nmlop.MUL, expr.expr1, pow2(expr.expr2))
        elif expr.op == nmlop.SHIFT_RIGHT:
            #a >> b ==> a / (2**b)
            expr = expression.BinOp(nmlop.DIV, expr.expr1, pow2(expr.expr2))
        elif expr.op == nmlop.SHIFTU_RIGHT:
            #a >>> b ==> (uint)a / (2**b)
            expr = expression.BinOp(nmlop.DIVU, expr.expr1, pow2(expr.expr2))
        elif expr.op == nmlop.HASBIT:
            # hasbit(x, n) ==> (x >> n) & 1
            expr = expression.BinOp(nmlop.DIV, expr.expr1, pow2(expr.expr2))
            expr = expression.BinOp(nmlop.AND, expr, expression.ConstantNumeric(1))
        elif expr.op == nmlop.NOTHASBIT:
            # !hasbit(x, n) ==> ((x >> n) & 1) ^ 1
            expr = expression.BinOp(nmlop.DIV, expr.expr1, pow2(expr.expr2))
            expr = expression.BinOp(nmlop.AND, expr, expression.ConstantNumeric(1))
            expr = expression.BinOp(nmlop.XOR, expr, expression.ConstantNumeric(1))

        return expr.reduce()


    def preprocess_ternaryop(self, expr):
        assert isinstance(expr, expression.TernaryOp)
        guard = expression.Boolean(expr.guard).reduce()
        self.parse(guard)
        guard_var = VarAction2StoreTempVar()
        guard_var.comment = "guard"
        inverted_guard_var = VarAction2StoreTempVar()
        inverted_guard_var.comment = "!guard"
        self.var_list.append(nmlop.STO_TMP)
        self.var_list.append(guard_var)
        self.var_list.append(nmlop.XOR)
        var = VarAction2Var(0x1A, 0, 1)
        self.var_list.append(var)
        self.var_list.append(nmlop.STO_TMP)
        self.var_list.append(inverted_guard_var)
        self.var_list.append(nmlop.VAL2)
        # the +4 is for the 4 operators added above (STO_TMP, XOR, STO_TMP, VAL2)
        self.var_list_size += 4 + guard_var.get_size() + inverted_guard_var.get_size() + var.get_size()
        expr1 = expression.BinOp(nmlop.MUL, expr.expr1, VarAction2LoadTempVar(guard_var))
        expr2 = expression.BinOp(nmlop.MUL, expr.expr2, VarAction2LoadTempVar(inverted_guard_var))
        return expression.BinOp(nmlop.ADD, expr1, expr2)


    def preprocess_storageop(self, expr):
        assert isinstance(expr, expression.StorageOp)
        max = 0xF if expr.info['perm'] else 0x10F
        if isinstance(expr.register, expression.ConstantNumeric) and expr.register.value > max:
            raise generic.ScriptError("Register number must be in range 0..%d, encountered %d." % (max, expr.register.value), expr.pos)
        if expr.info['perm'] and self.feature not in (0x08, 0x0A, 0x0D):
            raise generic.ScriptError("Persistent storage is not supported for feature '%02X'" % self.feature, expr.pos)

        if expr.info['store']:
            op = nmlop.STO_PERM if expr.info['perm'] else nmlop.STO_TMP
            ret = expression.BinOp(op, expr.value, expr.register, expr.pos)
        else:
            var_num = 0x7C if expr.info['perm'] else 0x7D
            ret = expression.Variable(expression.ConstantNumeric(var_num), param=expr.register, pos=expr.pos)

        if expr.info['perm'] and self.feature == 0x08:
            # store grfid in register 0x100 for town persistent storage
            grfid = expression.ConstantNumeric(0xFFFFFFFF) if expr.grfid is None else expr.grfid
            store_op = expression.BinOp(nmlop.STO_TMP, grfid, expression.ConstantNumeric(0x100), expr.pos)
            ret = expression.BinOp(nmlop.VAL2, store_op, ret, expr.pos)
        elif expr.grfid is not None:
            raise generic.ScriptError("Specifying a grfid is only possible for town persistent storage.", expr.pos)
        return ret

    def parse_expr_to_constant(self, expr, offset):
        if isinstance(expr, expression.ConstantNumeric): return expr.value

        tmp_param, tmp_param_actions = actionD.get_tmp_parameter(expr)
        self.extra_actions.extend(tmp_param_actions)
        self.mods.append(Modification(tmp_param, 4, self.var_list_size + offset))
        return 0

    def parse_variable(self, expr):
        if not isinstance(expr.num, expression.ConstantNumeric):
            raise generic.ScriptError("Variable number must be a constant number", expr.num.pos)
        if not (expr.param is None or isinstance(expr.param, expression.ConstantNumeric)):
            raise generic.ScriptError("Variable parameter must be a constant number", expr.param.pos)

        if len(expr.extra_params) > 0:
            first_var = len(self.var_list) == 0
            backup_op = None
            value_backup = None
            if not first_var:
                backup_op = self.var_list.pop()
                value_backup = VarAction2StoreTempVar()
                self.var_list.append(nmlop.STO_TMP)
                self.var_list.append(value_backup)
                self.var_list.append(nmlop.VAL2)
                self.var_list_size += value_backup.get_size() + 1

            #Last value == 0, and this is right before we're going to use
            #the extra parameters. Set them to their correct value here.
            for extra_param in expr.extra_params:
                self.parse(extra_param[1])
                self.var_list.append(nmlop.STO_TMP)
                var = VarAction2Var(0x1A, 0, extra_param[0])
                self.var_list.append(var)
                self.var_list.append(nmlop.VAL2)
                self.var_list_size += var.get_size() + 2

            if not first_var:
                value_loadback = VarAction2LoadTempVar(value_backup)
                self.var_list.append(value_loadback)
                self.var_list.append(backup_op)
                self.var_list_size += value_loadback.get_size() + 1

        if expr.param is None:
            offset = 2
            param = None
        else:
            offset = 3
            param = expr.param.value
        mask = self.parse_expr_to_constant(expr.mask, offset)

        var = VarAction2Var(expr.num.value, expr.shift.value, mask, param)

        if expr.add is not None:
            var.add = self.parse_expr_to_constant(expr.add, offset + 4)
        if expr.div is not None:
            var.div = self.parse_expr_to_constant(expr.div, offset + 8)
        if expr.mod is not None:
            var.mod = self.parse_expr_to_constant(expr.mod, offset + 8)
        self.var_list.append(var)
        self.var_list_size += var.get_size()


    def parse_binop(self, expr):
        if expr.op.act2_num is None: expr.supported_by_action2(True)

        if isinstance(expr.expr2, (expression.ConstantNumeric, expression.Variable)) or \
                isinstance(expr.expr2, VarAction2LoadTempVar) or \
                (isinstance(expr.expr2, expression.Parameter) and isinstance(expr.expr2.num, expression.ConstantNumeric)) or \
                expr.op == nmlop.VAL2:
            expr2 = expr.expr2
        elif expr.expr2.supported_by_actionD(False):
            tmp_param, tmp_param_actions = actionD.get_tmp_parameter(expr.expr2)
            self.extra_actions.extend(tmp_param_actions)
            expr2 = expression.Parameter(expression.ConstantNumeric(tmp_param))
        else:
            #The expression is so complex we need to compute it first, store the
            #result and load it back later.
            self.parse(expr.expr2)
            tmp_var = VarAction2StoreTempVar()
            self.var_list.append(nmlop.STO_TMP)
            self.var_list.append(tmp_var)
            self.var_list.append(nmlop.VAL2)
            #the +2 is for both operators
            self.var_list_size += tmp_var.get_size() + 2
            expr2 = VarAction2LoadTempVar(tmp_var)

        #parse expr1
        self.parse(expr.expr1)
        self.var_list.append(expr.op)
        self.var_list_size += 1

        self.parse(expr2)


    def parse_constant(self, expr):
        var = VarAction2Var(0x1A, 0, expr.value)
        self.var_list.append(var)
        self.var_list_size += var.get_size()


    def parse_param(self, expr):
        self.mods.append(Modification(expr.num.value, 4, self.var_list_size + 2))
        var = VarAction2Var(0x1A, 0, 0)
        var.comment = str(expr)
        self.var_list.append(var)
        self.var_list_size += var.get_size()


    def parse_string(self, expr):
        str_id, actions = action4.get_string_action4s(0, 0xD0, expr)
        self.extra_actions.extend(actions)
        self.parse_constant(expression.ConstantNumeric(str_id))


    def parse_via_actionD(self, expr):
        tmp_param, tmp_param_actions = actionD.get_tmp_parameter(expr)
        self.extra_actions.extend(tmp_param_actions)
        num = expression.ConstantNumeric(tmp_param)
        self.parse(expression.Parameter(num))


    def parse_expr(self, expr):
        if isinstance(expr, expression.Array):
            for expr2 in expr.values:
                self.parse(expr2)
                self.var_list.append(nmlop.VAL2)
            self.var_list.pop()
        else:
            self.parse(expr)

    def parse(self, expr):
        #Preprocess the expression
        if isinstance(expr, expression.SpecialParameter):
            #do this first, since it may evaluate to a BinOp
            expr = expr.to_reading()

        if isinstance(expr, expression.BinOp):
            expr = self.preprocess_binop(expr)

        elif isinstance(expr, expression.Boolean):
            expr = expression.BinOp(nmlop.MINU, expr.expr, expression.ConstantNumeric(1))

        elif isinstance(expr, expression.Not):
            expr = expression.BinOp(nmlop.XOR, expr.expr, expression.ConstantNumeric(1))

        elif isinstance(expr, expression.BinNot):
            expr = expression.BinOp(nmlop.XOR, expr.expr, expression.ConstantNumeric(0xFFFFFFFF))

        elif isinstance(expr, expression.TernaryOp) and not expr.supported_by_actionD(False):
            expr = self.preprocess_ternaryop(expr)

        elif isinstance(expr, expression.StorageOp):
            expr = self.preprocess_storageop(expr)

        #Try to parse the expression to a list of variables+operators
        if isinstance(expr, expression.ConstantNumeric):
            self.parse_constant(expr)

        elif isinstance(expr, expression.Parameter) and isinstance(expr.num, expression.ConstantNumeric):
            self.parse_param(expr)

        elif isinstance(expr, expression.Variable):
            self.parse_variable(expr)

        elif expr.supported_by_actionD(False):
            self.parse_via_actionD(expr)

        elif isinstance(expr, expression.BinOp):
            self.parse_binop(expr)

        elif isinstance(expr, expression.String):
            self.parse_string(expr)

        elif isinstance(expr, VarAction2LoadTempVar):
            self.var_list.append(expr)
            self.var_list_size += expr.get_size()

        else:
            expr.supported_by_action2(True)
            assert False #supported_by_action2 should have raised the correct error already

def parse_var(info, pos):
    res = expression.Variable(expression.ConstantNumeric(info['var']), expression.ConstantNumeric(info['start']), expression.ConstantNumeric((1 << info['size']) - 1), None, pos)
    if 'function' in info:
        return info['function'](res, info)
    return res


def parse_60x_var(name, args, pos, info):
    if 'function' in info:
        # Special function to extract parameters if there is more than one
        param, extra_params = info['function'](name, args, pos, info)
    else:
        # Default function to extract parameters
        param, extra_params = action2var_variables.default_60xvar(name, args, pos, info)

    if isinstance(param, expression.ConstantNumeric):
        var = expression.Variable(expression.ConstantNumeric(info['var']), expression.ConstantNumeric(info['start']), \
                expression.ConstantNumeric((1 << info['size']) - 1), param, pos)

        var.extra_params.extend(extra_params)
        return var
    else:
        # Make use of var 7B to pass non-constant parameters
        var = expression.Variable(expression.ConstantNumeric(0x7B), expression.ConstantNumeric(info['start']), \
                expression.ConstantNumeric((1 << info['size']) - 1), expression.ConstantNumeric(info['var']), pos)

        var.extra_params.extend(extra_params)
        # Set the param in the accumulator beforehand
        return expression.BinOp(nmlop.VAL2, param, var, pos)

def parse_minmax(value, unit_str, action_list, act6, offset):
    """
    Parse a min or max value in a switch block.

    @param value: Value to parse
    @type value: L{Expression}

    @param unit_str: Unit to use
    @type unit_str: C{str} or C{None}

    @param action_list: List to append any extra actions to
    @type action_list: C{list} of L{BaseAction}

    @param act6: Action6 to add any modifications to
    @type act6: L{Action6}

    @param offset: Current offset to use for action6
    @type offset: C{int}

    @return: A tuple of two values:
                - The value to use as min/max
                - Whether the resulting range may need a sanity check
    @rtype: C{tuple} of (L{ConstantNumeric} or L{SpriteGroupRef}), C{bool}
    """
    check_range = True
    if unit_str is not None:
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Using a unit is only allowed in combination with a compile-time constant", value.pos)
        assert unit_str in unit.units
        result = expression.ConstantNumeric(int(value.value / unit.units[unit_str]['convert']))
    elif isinstance(value, expression.ConstantNumeric):
        result = value
    elif isinstance(value, expression.Parameter) and isinstance(value.num, expression.ConstantNumeric):
        act6.modify_bytes(value.num.value, 4, offset)
        result = expression.ConstantNumeric(0)
        check_range = False
    else:
        tmp_param, tmp_param_actions = actionD.get_tmp_parameter(value)
        action_list.extend(tmp_param_actions)
        act6.modify_bytes(tmp_param, 4, offset)
        result = expression.ConstantNumeric(0)
        check_range = False
    return (result, check_range)

def parse_result(value, action_list, act6, offset, varaction2, repeat_result = 1):
    """
    Parse a result (another switch or CB result) in a switch block.

    @param value: Value to parse
    @type value: L{Expression} or L{SpriteGroupRef}

    @param action_list: List to append any extra actions to
    @type action_list: C{list} of L{BaseAction}

    @param act6: Action6 to add any modifications to
    @type act6: L{Action6}

    @param offset: Current offset to use for action6
    @type offset: C{int}

    @param varaction2: Reference to the resulting varaction2
    @type varaction2: L{Action2Var}

    @param repeat_result: Repeat any action6 modifying of the next sprite this many times.
    @type repeat_result: C{int}

    @return: A tuple of two values:
                - The value to use as return value
                - Comment to add to this value
    @rtype: C{tuple} of (L{ConstantNumeric} or L{SpriteGroupRef}), C{str}
    """
    if isinstance(value, expression.SpriteGroupRef):
        comment = value.name.value + ';'
        action2.add_ref(value, varaction2)
        result = value
    elif isinstance(value, expression.ConstantNumeric):
        comment = "return %d;" % value.value
        result = value
    elif isinstance(value, expression.Parameter) and isinstance(value.num, expression.ConstantNumeric):
        comment = "return %s;" % str(value)
        for i in range(repeat_result):
            act6.modify_bytes(value.num.value, 2, offset + 2*i)
        result = expression.ConstantNumeric(0)
    elif isinstance(value, expression.String):
        comment = "return %s;" % str(value)
        str_id, actions = action4.get_string_action4s(0, 0xD0, value)
        action_list.extend(actions)
        result = expression.ConstantNumeric(str_id - 0xD000 + 0x8000)
    else:
        tmp_param, tmp_param_actions = actionD.get_tmp_parameter(expression.BinOp(nmlop.OR, value, expression.ConstantNumeric(0x8000)).reduce())
        comment = "return param[%d];" % tmp_param
        action_list.extend(tmp_param_actions)
        for i in range(repeat_result):
            act6.modify_bytes(tmp_param, 2, offset + 2*i)
        result = expression.ConstantNumeric(0)
    return (result, comment)

def get_feature(switch_block):
    feature = switch_block.feature.value if switch_block.var_range == 0x89 else action2var_variables.varact2parent_scope[switch_block.feature.value]
    if feature is None:
        raise generic.ScriptError("Parent scope for this feature not available, feature: " + str(switch_block.feature), switch_block.pos)
    return feature

def reduce_varaction2_expr(expr, feature):
    # 'normal' and 60+x variables to use
    vars_normal = action2var_variables.varact2vars[feature]
    vars_60x = action2var_variables.varact2vars60x[feature]

    # lambda function to convert (value, pos) to a function pointer
    # since we need the variable name later on, a reverse lookup is needed
    # TODO pass the function name along to avoid this
    func60x = lambda value, pos: expression.FunctionPtr(expression.Identifier(generic.reverse_lookup(vars_60x, value), pos), parse_60x_var, value)

    # make sure, that variables take precedence about global constants / parameters
    # this way, use the current climate instead of the climate at load time.
    return expr.reduce([(action2var_variables.varact2_globalvars, parse_var), \
        (vars_normal, parse_var), \
        (vars_60x, func60x)] + \
        global_constants.const_list)

def parse_varaction2(switch_block):
    action6.free_parameters.save()
    act6 = action6.Action6()

    varaction2 = Action2Var(switch_block.feature.value, switch_block.name.value, switch_block.var_range)

    expr = reduce_varaction2_expr(switch_block.expr, get_feature(switch_block))

    offset = 4 #first var

    parser = Varaction2Parser(get_feature(switch_block))
    parser.parse_expr(expr)
    action_list = parser.extra_actions
    for mod in parser.mods:
        act6.modify_bytes(mod.param, mod.size, mod.offset + offset)
    varaction2.var_list = parser.var_list
    offset += parser.var_list_size + 1 # +1 for the byte num-ranges

    used_ranges = []
    for r in switch_block.body.ranges:
        comment = str(r.min) + " .. " + str(r.max) + ": "

        range_result, range_comment = parse_result(r.result, action_list, act6, offset, varaction2)
        comment += range_comment
        offset += 2 # size of result

        range_min, check_min = parse_minmax(r.min, r.unit, action_list, act6, offset)
        offset += 4
        range_max, check_max = parse_minmax(r.max, r.unit, action_list, act6, offset)
        offset += 4

        range_overlap = False
        if check_min and check_max:
            for existing_range in used_ranges:
                if existing_range[0] <= range_min.value and range_max.value <= existing_range[1]:
                    generic.print_warning("Range overlaps with existing ranges so it'll never be reached", r.min.pos)
                    range_overlap = True
                    break
            if not range_overlap:
                used_ranges.append([range_min.value, range_max.value])
                used_ranges.sort()
                i = 0
                while i + 1 < len(used_ranges):
                    if used_ranges[i + 1][0] <= used_ranges[i][1] + 1:
                        used_ranges[i][1] = max(used_ranges[i][1], used_ranges[i + 1][1])
                        used_ranges.pop(i + 1)
                    else:
                        i += 1

        if not range_overlap:
            varaction2.ranges.append(switch_range.SwitchRange(range_min, range_max, range_result, comment=comment))

    default, default_comment = parse_result(switch_block.body.default, action_list, act6, offset, varaction2)
    varaction2.default_result = default
    varaction2.default_comment = 'Return computed value' if len(switch_block.body.ranges) == 0 else 'default: ' + default_comment

    if len(act6.modifications) > 0: action_list.append(act6)

    action_list.append(varaction2)
    switch_block.set_action2(varaction2)

    action6.free_parameters.restore()
    return action_list
