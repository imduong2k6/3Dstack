"""Expose the adapter scripts to Epic's MCP server as the PipelineTools toolset.

Epic's execute_tool_script runs in a sandbox that can't `import unreal`, so the scripts
in this folder are registered as toolset tools instead. The Unreal project loads this
file at editor start from <Project>/Content/Python/init_unreal.py:

    import sys
    sys.path.append(r"<repo>/.claude/skills/unreal-adapter/scripts")
    import pipeline_toolset
    pipeline_toolset.register()

Then over MCP: call_tool(toolset_name="pipeline_toolset.PipelineTools", tool_name=..., arguments=...).
Each call re-reads the script file, so fixes to capture.py, stats.py and import_layout.py
apply without restarting the editor. Changes to this file need a restart.
"""
import importlib.util
import os

import unreal

import toolset_registry
from toolset_registry.registration import Registration

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(f"pipeline_{name}", os.path.join(_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unreal.uclass()
class PipelineTools(unreal.ToolsetDefinition):
    """Scene pipeline adapter scripts: review captures, gate stats and the Blender layout transfer."""

    @toolset_registry.tool_call
    @staticmethod
    def capture_set(out_dir: str, labels: list[str], view_modes: list[str],
                    width: int = 1920, height: int = 1080) -> str:
        """Queues high-res screenshots from review cameras (capture.py).

        Args:
            out_dir: Absolute folder for the PNGs, written as <label>_<mode>.png.
            labels: Outliner labels of the CameraActor or CineCameraActor review cameras.
            view_modes: Any of "lit", "lighting_only".
            width: Image width in pixels.
            height: Image height in pixels.

        Returns:
            What was queued. Files appear over the next frames; poll for them.
        """
        return _load("capture").capture_set(out_dir, labels, width, height, tuple(view_modes))

    @toolset_registry.tool_call
    @staticmethod
    def write_stats(path: str) -> str:
        """Writes stats.json for the open level (stats.py).

        Args:
            path: Absolute path of the stats.json to write.

        Returns:
            A one-line summary.
        """
        return _load("stats").write_stats(path)

    @toolset_registry.tool_call
    @staticmethod
    def place_layout(layout_path: str, mesh_root: str = "/Game/Transfer/Meshes",
                     folder: str = "Transfer") -> str:
        """Spawns the Blender layout from transfer/layout.json, replacing the previous transfer (import_layout.py).

        Args:
            layout_path: Absolute path to layout.json.
            mesh_root: Content folder that holds the imported meshes.
            folder: Outliner folder for the placed actors.

        Returns:
            How many instances were placed.
        """
        return _load("import_layout").place(layout_path, mesh_root, folder)


_registration = Registration([PipelineTools])


def register():
    return _registration.register()
