"""CPU Blender execution with fresh frame destinations and truthful receipts."""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import sys
import uuid
from flow import CPUAdapter, force_cycles_cpu, sha, write_json


class BlenderAdapter(CPUAdapter):
    def __init__(self, threads=2):
        super().__init__(threads)
        self.function_depth = 0
        self.output_assignments = 0

    def visit_FunctionDef(self, node):
        self.function_depth += 1
        try:
            return self.generic_visit(node)
        finally:
            self.function_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):
        if not self.function_depth and any(isinstance(target, ast.Name) and target.id == 'out' for target in node.targets):
            if len(node.targets) != 1:
                raise RuntimeError('Unsupported chained output assignment')
            node.value = ast.Name('_cpu_frame_dir', ast.Load())
            self.output_assignments += 1
            self.log(node, 'fresh CPU-only frame directory; no old GPU frame reuse')
        return super().visit_Assign(node)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('script_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    script = args.script.resolve()
    workspace = next((parent for parent in script.parents if (parent / 'cpu-workspace.json').is_file()), None)
    if workspace is None:
        raise RuntimeError('Scene script is not inside a prepared CPU workspace')
    tree = ast.parse(script.read_text(encoding='utf-8'))
    adapter = BlenderAdapter(args.threads)
    tree = adapter.visit(tree)
    if not adapter.output_assignments:
        raise RuntimeError('Unknown scene output convention; expected top-level out assignment. No scene executed.')
    ast.fix_missing_locations(tree)
    output = workspace / 'cpu-results' / 'blender' / (script.stem + '-' + uuid.uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    frames = output / 'frames'
    frames.mkdir()
    import bpy
    native_render = bpy.ops.render.render
    receipt = {'schema': 1, 'source': str(script.relative_to(workspace)), 'sourceSha256': sha(script),
               'device': 'CPU', 'renderer': 'CYCLES', 'denoiser': 'OPENIMAGEDENOISE',
               'completed': False, 'renderCalls': 0, 'visualParityVerified': False,
               'humanReviewed': False, 'hardwareAndOutputEdits': adapter.edits, 'frames': []}
    write_json(output / 'receipt.json', receipt)

    def render(*positional, **keywords):
        force_cycles_cpu(bpy)
        for scene in bpy.data.scenes:
            scene.render.threads_mode = 'FIXED'
            scene.render.threads = args.threads
        scene = bpy.context.scene
        target = Path(scene.render.filepath).resolve()
        if frames not in target.parents:
            raise RuntimeError(f'Render attempted outside the new CPU frame directory: {target}')
        value = native_render(*positional, **keywords)
        receipt['renderCalls'] += 1
        receipt['frames'].append({'frame': scene.frame_current, 'path': str(target),
                                  'samples': scene.cycles.samples, 'width': scene.render.resolution_x,
                                  'height': scene.render.resolution_y, 'percentage': scene.render.resolution_percentage})
        write_json(output / 'receipt.json', receipt)
        return value

    extra = args.script_args[1:] if args.script_args[:1] == ['--'] else args.script_args
    original_argv, original_path = sys.argv[:], sys.path[:]
    try:
        sys.argv = ['blender', '--', *extra]
        sys.path.insert(0, str(script.parent))
        namespace = {'__name__': '__main__', '__file__': str(script), '_cpu_render': render,
                     '_cpu_frame_dir': frames}
        exec(compile(tree, str(script), 'exec'), namespace)
        receipt['completed'] = True
    finally:
        sys.argv, sys.path[:] = original_argv, original_path
        write_json(output / 'receipt.json', receipt)
    print(str(output), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
