import logging as log
import sys

from deprecation import get_beta_operators
from common import get_all_operators
from fix import fixed


def get_ioports(root_dir):
    # TODO: this does not include any ports set in the actual golang code.
    # API changes in the operator code are therefore not detected.
    """Return the 'signatures' of all operators, i.e. a list of all input and output ports."""
    ports = {}
    operators = get_all_operators(root_dir, "operator.json")
    lineage = get_all_operators(root_dir, "lineage.json")

    # get ports in `operator.json`
    for op in operators:
        ports[op['!path']] = {'in': op.get('inports') or [],
                              'out': op.get('outports') or []}

    # add ports defined in `lineage.json`
    for op in lineage:
        ds = op.get('datasets')
        if ds is None:
            continue
        ports[op['!path']]['in'] += [port for port in ds if ds[port].get('inport')]
        ports[op['!path']]['out'] += [port for port in ds if ds[port].get('outport')]

    if not ports:
        log.fatal("Sanity check failed: I/O Port list empty.")
        sys.exit(-1)

    return ports


def check_ioports(dir_old, dir_new, settings_path):
    """Check if the input / output ports of any operator have changed."""
    ioports_old = get_ioports(dir_old)
    ioports_new = get_ioports(dir_new)
    beta_operators = get_beta_operators(dir_old, settings_path)
    ioports_beta = {op for op in ioports_new if op in beta_operators}
    ioport_keys = ioports_old.keys() & ioports_new.keys() - ioports_beta

    log.info("checking ports of %s operators", len(ioport_keys))

    error_count = 0

    for o in ioport_keys:
        # TODO: Many operators do not have any I/O ports in the JSON files, as they
        # are defined directly in the operator's code
        op_old = ioports_old[o]
        op_new = ioports_new[o]
        if op_new['in'] is None and op_new['out'] is None:
            log.warning("Operator %s has neither input nor output ports", o)
        for io in ['in', 'out']:
            # check if I/O ports are equal (or at least, no port is deleted)
            for idx, old_port in enumerate(op_old[io]):
                # ports can be simple names, or dictionaries
                if isinstance(old_port, dict):
                    port_name = old_port['name']
                else:
                    port_name = old_port
                # check if the port was deleted
                if old_port not in op_new[io] and not fixed("port-del", o, port_name, ""):
                    log.error("Operator %s: %sput port %s removed", o, io.title(), port_name)
                    error_count +=1
                elif old_port != op_new[io][idx] and not fixed("port-chg", o, port_name, ""):
                    log.error("Operator %s: %sput port %s changed",o , io.title(), port_name)
                    log.debug("  FROM: %s\tTO: %s", old_port, op_new[io][idx])
                    error_count += 1

    return error_count
