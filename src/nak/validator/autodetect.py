import os
import shutil

def resolve_executable(name: str) -> str:
    # 1. Search in PATH using shutil.which
    path = shutil.which(name)
    if path:
        return path

    # 2. Search in current virtual environment if VIRTUAL_ENV is set
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        if os.name == "nt":
            # Windows virtualenv bin folder is named 'Scripts'
            candidate_exe = os.path.join(virtual_env, "Scripts", f"{name}.exe")
            candidate_no_exe = os.path.join(virtual_env, "Scripts", name)
            if os.path.exists(candidate_exe):
                return candidate_exe
            if os.path.exists(candidate_no_exe):
                return candidate_no_exe
        else:
            # Unix virtualenv bin folder is named 'bin'
            candidate = os.path.join(virtual_env, "bin", name)
            if os.path.exists(candidate):
                return candidate

    raise FileNotFoundError(f"Executable '{name}' could not be resolved in PATH or VIRTUAL_ENV.")
