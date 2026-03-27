#!/usr/bin/env python3

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TOPAS_COMMAND = Path("/home/hwijoon/shellScripts/topas")


SIMULATIONS = [
    ("GoldDNAphysic_in_Gold", "GoldDNAphysic_in_Gold.txt"),
    ("GoldDNAphysic_in_SilverDensity", "GoldDNAphysic_in_Silverdensity.txt"),
    ("GoldDNAphysic_in_SilverDensity_v2", "GoldDNAphysic_in_Silverdensity_v2.txt"),
    ("Livermore_Gold", "Livermore_in_Gold.txt"),
    ("Livermore_Silver", "Livermore_in_Silver.txt"),
]

VOLUMES_NM = [50, 300, 500]


def replace_single(text: str, pattern: str, replacement: str, description: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Could not update {description}.")
    return updated


def build_parameter_text(original_text: str, seed: int, volume_nm: int) -> str:
    text = original_text

    if re.search(r"^\s*i:Ts/Seed\s*=", text, flags=re.MULTILINE):
        text = replace_single(
            text,
            r"^\s*i:Ts/Seed\s*=.*$",
            f"i:Ts/Seed = {seed}",
            "seed",
        )
    else:
        text = replace_single(
            text,
            r"^(i:Ts/NumberOfThreads\s*=.*)$",
            rf"\1\ni:Ts/Seed = {seed}",
            "seed insertion",
        )

    text = replace_single(
        text,
        r"^\s*d:Ge/(?:AuShell|AgShell)/RMax\s*=.*$",
        f"d:Ge/{'AgShell' if 'd:Ge/AgShell/RMax' in text else 'AuShell'}/RMax     = {volume_nm}. nm",
        "RMax",
    )

    gamma_match = re.search(
        r"^\s*i:So/I125_Gamma_Core/NumberOfHistoriesInRun\s*=\s*(\d+)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if not gamma_match:
        raise ValueError("Could not find gamma histories.")
    gamma_histories = max(1, int(gamma_match.group(1)) // 10)
    text = replace_single(
        text,
        r"^\s*i:So/I125_Gamma_Core/NumberOfHistoriesInRun\s*=\s*\d+\s*$",
        f"i:So/I125_Gamma_Core/NumberOfHistoriesInRun = {gamma_histories}",
        "gamma histories",
    )

    electron_match = re.search(
        r"^\s*i:So/I125_Electron_Core/NumberOfHistoriesInRun\s*=\s*(\d+)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if not electron_match:
        raise ValueError("Could not find electron histories.")
    electron_histories = max(1, int(electron_match.group(1)) // 10)
    text = replace_single(
        text,
        r"^\s*i:So/I125_Electron_Core/NumberOfHistoriesInRun\s*=\s*\d+\s*$",
        f"i:So/I125_Electron_Core/NumberOfHistoriesInRun = {electron_histories}",
        "electron histories",
    )

    return text


def run_simulation(folder_name: str, parameter_filename: str, folder_index: int) -> None:
    simulation_dir = ROOT / folder_name
    original_parameter_path = simulation_dir / parameter_filename

    if not original_parameter_path.exists():
        raise FileNotFoundError(f"Missing parameter file: {original_parameter_path}")

    original_text = original_parameter_path.read_text(encoding="utf-8")

    for volume_index, volume_nm in enumerate(VOLUMES_NM, start=1):
        seed = folder_index * 100 + volume_index
        output_dir = simulation_dir / f"{volume_nm} nm"
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_parameter_path = output_dir / parameter_filename
        generated_text = build_parameter_text(original_text, seed=seed, volume_nm=volume_nm)
        generated_parameter_path.write_text(generated_text, encoding="utf-8")

        print(f'Started simulation for "{folder_name}" with volume "{volume_nm} nm"', flush=True)

        log_path = output_dir / "topas_run.log"
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.run(
                [str(TOPAS_COMMAND), parameter_filename],
                cwd=output_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            log_file.write(process.stdout)

        if process.stdout:
            print(process.stdout, end="" if process.stdout.endswith("\n") else "\n")

        if process.returncode != 0:
            raise RuntimeError(
                f'TOPAS failed for "{folder_name}" with volume "{volume_nm} nm". '
                f"See {log_path}"
            )

        print(f'Finished simulation for "{folder_name}" with volume "{volume_nm} nm"', flush=True)


def main() -> int:
    if not TOPAS_COMMAND.exists():
        print(f"TOPAS command not found: {TOPAS_COMMAND}", file=sys.stderr)
        return 1

    for folder_index, (folder_name, parameter_filename) in enumerate(SIMULATIONS, start=1):
        run_simulation(folder_name, parameter_filename, folder_index)

    print("All simulations finished successfully.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
