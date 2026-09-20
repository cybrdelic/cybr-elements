"""CPU execution adapters for the *existing* CYBR ELEMENTS production drivers.

Adapters are generated inside a disposable work directory. No repository file is
rewritten. Rendering and simulation functions are preserved except for a narrow,
recorded device change; diagnostic sizing is an explicit separate option.
"""
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

GAS = {"sigil_02_fire_v2.py", "sigil_02_air_v2.py"}
BLENDER = {"sigil_02_ground_earth_render.py", "sigil_02_active_water_render.py",
           "sigil_02_new_materials.py"}
IO_ONLY = {"sigil_02_active_mesh.py"}
CORE = ("advect", "derivative", "divergence", "step", "radiance")
GATES = ("continue", "continue-air-v2", "hero-approved.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def signature(tree: ast.AST) -> str:
    return ast.dump(tree, include_attributes=False)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + "." + node.attr
    return ""


def functions(tree: ast.Module) -> dict[str, str]:
    return {node.name: signature(node) for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


@dataclass(frozen=True)
class Diagnostic:
    """Deliberate smoke-test changes; never used for production runs."""
    frames: int = 72
    width: int = 320
    height: int = 180
    x: int = 128
    y: int = 16
    z: int = 72

    def __post_init__(self) -> None:
        if self.frames < 1 or self.frames > 294:
            raise ValueError("Diagnostic frames must be in 1..294")
        if self.width < 16 or self.height < 16 or self.width % 2 or self.height % 2:
            raise ValueError("Video dimensions must be even and at least 16")
        if min(self.x, self.y, self.z) < 8:
            raise ValueError("Diagnostic grid axes must each contain at least 8 cells")


class CPUAdapter(ast.NodeTransformer):
    def __init__(self, filename: str, threads: int, diagnostic: Diagnostic | None):
        self.filename, self.threads, self.diagnostic = filename, threads, diagnostic
        self.changes: list[dict[str, Any]] = []

    def record(self, node: ast.AST, reason: str) -> None:
        self.changes.append({"line": getattr(node, "lineno", None), "change": reason})

    def visit_If(self, node: ast.If) -> Any:
        # Delete precisely the CUDA availability guard, not arbitrary conditionals.
        if (self.filename in GAS and
                isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                and isinstance(node.test.operand, ast.Call)
                and dotted(node.test.operand.func) == "torch.cuda.is_available"):
            if len(node.body) != 1 or not isinstance(node.body[0], ast.Raise):
                raise ValueError("Unexpected CUDA guard: review the new upstream driver")
            self.record(node, "remove CUDA-only availability rejection")
            return None
        return self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:
        constants = [n.value for n in ast.walk(node.test)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        if any(value.replace('\\', '/').rsplit('/', 1)[-1] in GATES for value in constants):
            # Unattended execution is not a human approval. No approval file is made.
            self.record(node, "skip interactive pause; visual acceptance remains pending")
            return ast.copy_location(ast.parse(
                "print('CPU workflow: unattended review pause skipped; '"
                " 'visual acceptance remains pending', flush=True)").body[0], node)
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        targets = [dotted(t) for t in node.targets]
        if self.filename in GAS and targets == ["device"]:
            if not isinstance(node.value, ast.Constant) or node.value.value != "cuda":
                raise ValueError("Unexpected gas device declaration")
            node.value = ast.Constant("cpu")
            self.record(node, "torch tensors allocated on CPU")
        elif self.filename in BLENDER:
            for target in targets:
                if target.endswith(".cycles.device"):
                    node.value = ast.Constant("CPU")
                    self.record(node, "Cycles CPU path tracing")
                elif target.endswith(".cycles.denoiser"):
                    node.value = ast.Constant("OPENIMAGEDENOISE")
                    self.record(node, "CPU OpenImageDenoise replaces OptiX denoiser")
                elif target.endswith(".compute_device_type"):
                    node.value = ast.Constant("NONE")
                    self.record(node, "disable all Cycles accelerator backends")
                elif target.endswith(".use") and target.split(".")[0] in {"d", "device"}:
                    node.value = ast.Compare(
                        left=ast.Attribute(value=ast.Name(target.split(".")[0], ast.Load()),
                                           attr="type", ctx=ast.Load()),
                        ops=[ast.Eq()], comparators=[ast.Constant("CPU")])
                    self.record(node, "enable CPU device only")
                elif target.endswith(".render.threads"):
                    node.value = ast.Constant(self.threads)
                    self.record(node, "explicit CPU thread budget")
        if self.filename in GAS and self.diagnostic:
            if targets == ["TOTAL"]:
                node.value = ast.Constant(self.diagnostic.frames)
                self.record(node, "DIAGNOSTIC: bounded frame count")
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
                names = [dotted(t) for t in node.targets[0].elts]
                if names == ["W", "H"]:
                    node.value = ast.Tuple(elts=[ast.Constant(self.diagnostic.width),
                                                ast.Constant(self.diagnostic.height)], ctx=ast.Load())
                    self.record(node, "DIAGNOSTIC: smaller film dimensions")
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        name = dotted(node.func)
        if self.filename in IO_ONLY and isinstance(node.func, ast.Attribute) and node.func.attr == "write_text":
            constants = [n.value for n in ast.walk(node.func.value) if isinstance(n, ast.Constant)]
            if "manifest.json" in constants:
                self.record(node, "atomic manifest publication for concurrent cache readers")
                node.args.insert(0, node.func.value)
                node.func = ast.Name(id="_cpu_atomic_write_text", ctx=ast.Load())
        if name == "torch.set_num_threads":
            node.args = [ast.Constant(self.threads)]
            self.record(node, "explicit PyTorch CPU thread budget")
        elif name == "torch.cuda.max_memory_allocated":
            self.record(node, "CUDA telemetry is zero; CPU RSS recorded separately")
            return ast.copy_location(ast.Constant(0), node)
        elif name == "torch.cuda.synchronize":
            self.record(node, "remove unnecessary CUDA synchronization")
            return ast.copy_location(ast.Constant(None), node)
        if self.filename in GAS and self.diagnostic and name == "F.interpolate":
            for keyword in node.keywords:
                if (keyword.arg == "size" and isinstance(keyword.value, ast.Tuple)
                        and signature(keyword.value) == signature(ast.parse("(1080,1920)", mode="eval").body)):
                    keyword.value = ast.Tuple(elts=[ast.Constant(self.diagnostic.height),
                                                   ast.Constant(self.diagnostic.width)], ctx=ast.Load())
                    self.record(node, "DIAGNOSTIC: match render dimensions to encoder")
        # Every Blender render is checked immediately before execution. Handlers
        # alone would not cover initial device selection or headless probing.
        if self.filename in BLENDER and name == "bpy.ops.render.render":
            self.record(node, "assert CPU policy before every render")
            node.func = ast.Name(id="_cpu_checked_render", ctx=ast.Load())
        return self.generic_visit(node)


BLENDER_GUARD = '''
# CPU workflow runtime guard. The scene/material/geometry builders below are original.
def _cpu_checked_render(*args, **kwargs):
    scene = bpy.context.scene
    if scene.render.engine == 'CYCLES':
        if scene.cycles.device != 'CPU':
            raise RuntimeError('CPU contract violated: Cycles accelerator requested')
        if hasattr(scene.cycles, 'denoising_use_gpu'):
            scene.cycles.denoising_use_gpu = False
    elif scene.render.engine == 'BLENDER_EEVEE_NEXT':
        import os
        if os.environ.get('CYBR_EEVEE_SOFTWARE_VERIFIED') != '1':
            raise RuntimeError('Eevee requires a verified llvmpipe/softpipe CPU probe')
    else:
        raise RuntimeError('Unexpected renderer: ' + scene.render.engine)
    if hasattr(scene.render, 'compositor_device'):
        scene.render.compositor_device = 'CPU'
    return bpy.ops.render.render(*args, **kwargs)
'''


ATOMIC_TEXT = """
def _cpu_atomic_write_text(path, text, *args, **kwargs):
    temporary = path.with_name(path.name + '.cpu-partial')
    result = temporary.write_text(text, *args, **kwargs)
    temporary.replace(path)
    return result
"""


def adapt_javascript_manifest(source: str) -> tuple[str, dict[str, Any]]:
    old = "fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));"
    if source.count(old) != 2:
        raise ValueError("Native water manifest writer changed; review the adapter")
    result = source.replace(old, "_cpuWriteManifest();") + "\n" + (
        "function _cpuWriteManifest(){const temp=new URL('manifest.json.cpu-partial',out);"
        "fs.writeFileSync(temp,JSON.stringify(manifest));"
        "fs.renameSync(temp,new URL('manifest.json',out));}\n")
    return result, {"file": "sigil_02_active_water.mjs",
                    "sourceSha256": hashlib.sha256(source.encode()).hexdigest(),
                    "adaptedSha256": hashlib.sha256(result.encode()).hexdigest(),
                    "changes": ["Atomic manifest publication only; solver source unchanged"],
                    "visualAcceptance": "pending"}


def adapt(source: str, filename: str, threads: int = 2,
          diagnostic: Diagnostic | None = None) -> tuple[str, dict[str, Any]]:
    if filename not in GAS | BLENDER | IO_ONLY:
        raise ValueError(f"Not an approved CPU adapter target: {filename}")
    if not 1 <= threads <= 1024:
        raise ValueError("threads must be in 1..1024")
    if diagnostic and filename not in GAS:
        raise ValueError("Diagnostic sizing is supported only for fire and air")
    before = ast.parse(source, filename=filename)
    original_functions = functions(before)
    transformer = CPUAdapter(filename, threads, diagnostic)
    result = transformer.visit(before)
    ast.fix_missing_locations(result)
    modified_functions = functions(result)
    if filename in GAS:
        for name in CORE:
            if original_functions.get(name) != modified_functions.get(name):
                raise ValueError(f"CPU adapter changed numerical function {name}")
        if not diagnostic and original_functions.get("render") != modified_functions.get("render"):
            raise ValueError("Production volume renderer changed")
        changes = [c["change"] for c in transformer.changes]
        if changes.count("torch tensors allocated on CPU") != 1:
            raise ValueError("Expected exactly one gas device declaration")
        if changes.count("remove CUDA-only availability rejection") != 1:
            raise ValueError("Expected exactly one CUDA-only guard")
    elif filename in BLENDER:
        if not any(c["change"] == "Cycles CPU path tracing" for c in transformer.changes):
            raise ValueError("No recognized Cycles device setting")
        # Add the helper after imports; it references bpy only when called.
        insertion = 1 if (isinstance(result.body[0], ast.Expr) and isinstance(result.body[0].value, ast.Constant) and isinstance(result.body[0].value.value, str)) else 0
        result.body[insertion:insertion] = ast.parse(BLENDER_GUARD).body
    if filename in IO_ONLY:
        insertion = 1 if ast.get_docstring(result) is not None else 0
        result.body[insertion:insertion] = ast.parse(ATOMIC_TEXT).body
        if not transformer.changes:
            raise ValueError("Expected a recognized cache manifest writer")
    text = ast.unparse(result) + "\n"
    compile(text, filename, "exec")
    forbidden = ("torch.cuda.is_available()", "device = 'cuda'", "compute_device_type = 'OPTIX'")
    if any(token in text for token in forbidden):
        raise ValueError("Residual GPU requirement in generated driver")
    receipt = {"file": filename, "sourceSha256": hashlib.sha256(source.encode()).hexdigest(),
               "adaptedSha256": hashlib.sha256(text.encode()).hexdigest(),
               "diagnostic": asdict(diagnostic) if diagnostic else None,
               "changes": transformer.changes, "visualAcceptance": "pending",
               "preservedNumericalFunctions": [n for n in CORE if n in original_functions],
               "productionVolumeRendererPreserved": filename in GAS and diagnostic is None}
    return text, receipt
