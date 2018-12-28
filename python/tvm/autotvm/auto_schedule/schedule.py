from ... import schedule
from ..task.task import get_config
from .stage_analysis import build_stage_graph, annotate_compute_location, \
    print_stage_graph, StageEdgeType, StageNodeType, ComputeAtType
from .backend.generic import schedule_complex_reduce, schedule_simple_reduce, \
    schedule_other_root


class GlobalInfo:
    """global cached analysis results"""
    def __init__(self):
        self.node_dict = None      # dict (op -> StageNode)
        self.root_to_master = None # dict (StageNode -> StageNode)
        self.bufs = []             # arguments bufs


def call_schedule_func(ginfo, cfg):
    """call corresponding schedule func"""
    node_dict = ginfo.node_dict
    s = schedule.create_schedule([x.op for x in node_dict.values() if len(x.write_edges) == 0])

    root_to_master = dict()

    # inline, fuse
    for node in node_dict.values():
        if node.compute_at_type == ComputeAtType.COMPUTE_INLINE:
            s[node.op].compute_inline()
        elif node.compute_at_type == ComputeAtType.COMPUTE_FUSE:
            dst = node.compute_at_loc
            assert dst not in root_to_master, "Fuse multiple complex compute nodes into a single one"
            root_to_master[dst] = node
        elif node.compute_at_type == ComputeAtType.COMPUTE_TUNE:
            raise NotImplementedError()

    # call real schedule
    for node in node_dict.values():
        if node.compute_at_type == ComputeAtType.COMPUTE_ROOT:
            master = root_to_master.get(node, node)

            if master.type == StageNodeType.COMPLEX_REDUCTION:
                schedule_complex_reduce(s, cfg, master)
            elif master.type == StageNodeType.SIMPLE_REDUCTION:
                schedule_simple_reduce(s, cfg, master)
            elif master.type == StageNodeType.PLACEHOLDER:
                pass
            else:
                schedule_other_root(s, cfg, master)

    return s


def create_schedule(bufs):
    # stage analysis
    node_dict = build_stage_graph(bufs)

    # annotate compute location
    annotate_compute_location(node_dict, bufs)

    # DEBUG # print_stage_graph(node_dict)

    # compute rewrite
    pass

    # cache analysis results
    ginfo = GlobalInfo()
    ginfo.node_dict = node_dict
    ginfo.bufs = bufs

    # autotvm part
    s = call_schedule_func(ginfo, get_config())

    return s
