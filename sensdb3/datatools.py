# -*- coding: utf-8 -*-
import math
import pytz
import datetime
import sys
from sensdb3.models import Data

import logging
djangolog = logging.getLogger('django')

def is_naive(dt):
    if dt.tzinfo is None:
        return True
    else:
        return False


def check_times(st, et):
    if is_naive(st) or is_naive(et):
        raise ValueError("Start and end times must be timezone aware")


def get_unit_data(unit, st, et, showinvalid=False):
    """
    Return Unit's requested data between st and et.
    :param unit: Unit object or numeric id
    :param st: timezone aware datetime
    :param et: timezone aware datetime
    :return: QuerySet of Data objects
    """
    check_times(st, et)
    data = Data.objects.filter(unit=unit)
    data = data.filter(timestamp__gte=st)
    data = data.filter(timestamp__lte=et)
    if showinvalid is False:
        data = data.filter(valid=True)
    data = data.order_by('timestamp')
    data = data.values('id', 'value', 'timestamp', 'valid')
    return data


def get_unit_data_measuring(unit, st, et):
    """
    Old version.
    Return Unit's requested data between st and et
    """
    check_times(st, et)
    data = Data.objects.filter(unit=unit)
    data = data.filter(measuring__timestamp__gte=st)
    data = data.filter(measuring__timestamp__lte=et)
    data = data.order_by('measuring__timestamp')
    data = data.values('id', 'value', 'measuring__timestamp', 'valid')
    return data


def get_formula_data(formula, st, et, showinvalid=False):
    """
    Depending on Formula's type calculate 'v-weir' or 'polynomial' values.
    """
    if formula.type == 'polynomial':
        data = _calculate_polynomial_formula_data(formula, st, et,
                                                  showinvalid=showinvalid)
    elif formula.type == 'v-weir':
        data = _calculate_v_wier_formula_data(formula, st, et,
                                              showinvalid=showinvalid)
        #raise NotImplementedError('v-weir formula is not implemented yet')
    else:
        raise NotImplementedError(
            '%s formula is not implemented yet' % formula.type)
    return data


def dictionize_by_timestamp(data):
    """
    Convert list of dictionaries to a dictionary, where key is the timestamp
    from source list's dict item.
    """
    _dict = {}
    for d in data:
        ts = d['timestamp']
        _dict[ts] = d
    return _dict


def _calculate_polynomial_formula_data(formula, st, et, showinvalid=False):
    """
    Take a formula, fetch data of all units (which aren't None),
    eval(formula.parameters) with correct data values and return
    result as a single data list containing timestamps and data values.
    """
    # Create a list for all data of units
    # Convert all QuerySets to lists, this speeds up accessing values
    datalists = {}
    datadicts = {}
    max_len = 0
    longest_list = None
    for key, unit in [('c1', formula.unit1), ('c2', formula.unit2),
                      ('c3', formula.unit3), ('c4', formula.unit4)]:
        if unit:
            datalists[key] = list(get_unit_data(unit, st, et))
            datadicts[key] = dictionize_by_timestamp(datalists[key])
            if len(datalists[key]) > max_len:
                max_len = len(datalists[key])
                longest_list = key
    if formula.formula1:  # get f1 data if it is used in formula
        key = 'f1'
        datalists[key] = list(get_formula_data(formula.formula1, st, et,
                              showinvalid=False))
        datadicts[key] = dictionize_by_timestamp(datalists[key])
        if len(datalists[key]) > max_len:
            #max_len = len(datalists[key])
            longest_list = key
    data = []
    # Parameters for eval()
    exp = formula.parameters
    # Compile expression once, eval processes it *much* faster
    compiled = compile(exp, '<string>', 'eval')
    # Add to globals (functions) only keys that are really needed, e.g.
    # {'pi': math.pi, 'sin': math.sin }
    functions = {'__builtins__': None, 'math': math}
    locals_dict = {}
    timeformulas = list(formula.timeformulas.order_by('starttime'))
    multiplier = formula.multiplier
    # Loop through the longest list, it should contain most of timestamps
    # other lists have
    if longest_list is None:
        return []  # No data at all :-O
    eval_failed = False
    # FIXME: create instead a list which contains ALL timestamps!
    for d in datalists[longest_list]:
        fail = False
        # Pick the value from all lists
        # (usually just c1, but also others may exist in more complex formulas)
        for key in datalists.keys():
            if d.get('value') is None:
                fail = True
                continue
            # Use longest list's timestamp to get value from all lists
            try:
                locals_dict[key] = datadicts[key][d['timestamp']]['value']
            except KeyError as err:
                # FIXME: create instead a list which contains ALL timestamps!
                fail = True
        if fail:
            continue
        if timeformulas and d['timestamp'] >= timeformulas[0].starttime:
            #print "UUSI FORMULA", d['timestamp'], timeformulas[0].starttime
            tf = timeformulas.pop(0)
            multiplier = tf.multiplier
            exp = tf.parameters
            compiled = compile(exp, '<string>', 'eval')
        # If data is invalid, don't calculate the value
        if showinvalid or d['valid']:
            # NOTE: eval() is evil!
            try:
                val = eval(compiled, functions,
                           locals_dict) * multiplier
                #print "EVAL", exp, locals_dict
            except ValueError as err:
                # e.g. negative number cannot be raised to a fractional power
                if eval_failed is False:  # log error once
                    msg = (u'Formula eval error in %s: Formula %d: "%s" with '
                           u'values "%s" failed on error "%s"' % (
                               formula.datalogger.idcode, formula.id, exp,
                               str(locals_dict), err))
                    djangolog.warning(msg)
                    eval_failed = True
                val = None
        else:
            val = None
        data.append({'value': val, 'timestamp': d['timestamp'],
                     'valid': d['valid']})
    return data


def _v_wier(val, angle):
    """
    Q = 1381 * H^2,5 * tan(Ø/2)
    """
    val = 1381 * (val / 1000.0) ** 2.5 * math.tan(math.radians(angle) / 2.0)
    return val


def _calculate_v_wier_formula_data(formula, st, et, showinvalid=False):
    """
    """
    v_view_angle = float(formula.parameters)
    multiplier = float(formula.multiplier)
    data = list(get_unit_data(formula.unit1, st, et))
    for d in data:
        try:
            d['value'] = _v_wier(d['value'], v_view_angle) * multiplier
        except ValueError:  # e.g. value was negative
            d['value'] = 0.0
    return data
