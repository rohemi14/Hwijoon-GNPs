#!/usr/bin/env python3

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent

SIMULATION_FOLDERS = [
    "GoldDNAphysic_in_Gold",
    "GoldDNAphysic_in_SilverDensity",
    "GoldDNAphysic_in_SilverDensity_v2",
    "Livermore_Gold",
    "Livermore_Silver",
]

VOLUME_FOLDERS = ["50 nm", "300 nm", "500 nm"]

ENERGY_COL = 5
PARTICLE_COL = 7
CREATOR_COL = 13
ROW_NUMBER = 10
E_MIN_KEV = 0.0
E_MAX_KEV = 40.0
N_BINS = 400
GAMMA_CODE = 11
ELECTRON_CODE = 22


def is_primary_creator(value: object) -> bool:
    value_str = str(value).strip().lower()
    return ("primary" in value_str) or (value_str == "0")


def find_first_file(directory: Path, patterns: list[str]) -> Path:
    for pattern in patterns:
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"No file found in {directory} for patterns: {patterns}")


def load_phsp_spectra(phsp_path: Path) -> dict[str, np.ndarray]:
    energies_keV: list[float] = []
    particle_types: list[int] = []
    creator_processes: list[str] = []

    with phsp_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) <= CREATOR_COL:
                continue

            try:
                energy_mev = float(parts[ENERGY_COL])
                particle_type = int(float(parts[PARTICLE_COL]))
            except ValueError:
                continue

            energies_keV.append(energy_mev * 1000.0)
            particle_types.append(particle_type)
            creator_processes.append(parts[CREATOR_COL])

    energies_array = np.array(energies_keV)
    particle_array = np.array(particle_types)
    creator_array = np.array(creator_processes)

    energy_mask = (energies_array >= E_MIN_KEV) & (energies_array <= E_MAX_KEV)
    primary_mask = np.array([is_primary_creator(item) for item in creator_array], dtype=bool)

    gamma_mask = (particle_array == GAMMA_CODE) & energy_mask
    electron_mask = (particle_array == ELECTRON_CODE) & energy_mask

    return {
        "gamma_primary": energies_array[gamma_mask & primary_mask],
        "gamma_other": energies_array[gamma_mask & ~primary_mask],
        "electron_primary": energies_array[electron_mask & primary_mask],
        "electron_other": energies_array[electron_mask & ~primary_mask],
    }


def read_counts_from_row(csv_path: Path, row_number_1based: int) -> np.ndarray:
    target_index = row_number_1based - 1

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    if target_index >= len(rows):
        raise ValueError(
            f"{csv_path} does not have row {row_number_1based}. It only has {len(rows)} rows."
        )

    counts: list[float] = []
    for item in rows[target_index]:
        item = item.strip()
        if not item:
            continue
        try:
            counts.append(float(item))
        except ValueError:
            continue

    if not counts:
        raise ValueError(f"No numeric data found in row {row_number_1based} of {csv_path}")

    return np.array(counts, dtype=float)


def plot_phsp_panel(axis: plt.Axes, primary: np.ndarray, other: np.ndarray, title: str) -> None:
    bins = np.linspace(E_MIN_KEV, E_MAX_KEV, N_BINS + 1)
    axis.hist(primary, bins=bins, histtype="step", linewidth=1.5, label="Primary")
    axis.hist(other, bins=bins, histtype="step", linewidth=1.5, label="Other")
    axis.set_title(title, fontsize=10)
    axis.set_xlim(E_MIN_KEV, E_MAX_KEV)
    axis.set_yscale("log")
    axis.set_xlabel("Energy (keV)")
    axis.set_ylabel("Counts")
    axis.grid(True, alpha=0.3)
    axis.legend(fontsize=8)


def plot_trackcount_panel(axis: plt.Axes, counts: np.ndarray, title: str) -> None:
    edges = np.linspace(E_MIN_KEV, E_MAX_KEV, len(counts) + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    width = edges[1] - edges[0]
    axis.bar(centers, counts, width=width, align="center", alpha=0.8)
    axis.set_title(title, fontsize=10)
    axis.set_xlim(E_MIN_KEV, E_MAX_KEV)
    axis.set_yscale("log")
    axis.set_xlabel("Energy (keV)")
    axis.set_ylabel("Counts")
    axis.grid(True, alpha=0.3)


def make_figure_for_folder(folder_name: str) -> Path:
    folder_path = ROOT / folder_name
    fig, axes = plt.subplots(
        nrows=len(VOLUME_FOLDERS),
        ncols=4,
        figsize=(22, 14),
        constrained_layout=True,
    )
    fig.suptitle(f"{folder_name} Output Summary", fontsize=18)

    for row_index, volume_folder in enumerate(VOLUME_FOLDERS):
        output_dir = folder_path / volume_folder
        phsp_path = find_first_file(output_dir, ["*.phsp"])
        electron_csv = find_first_file(output_dir, ["Spec_Electron_At*.csv"])
        gamma_csv = find_first_file(output_dir, ["Spec_Gamma_At*.csv"])

        spectra = load_phsp_spectra(phsp_path)
        electron_counts = read_counts_from_row(electron_csv, ROW_NUMBER)
        gamma_counts = read_counts_from_row(gamma_csv, ROW_NUMBER) 

        plot_phsp_panel(
            axes[row_index, 0],
            spectra["gamma_primary"],
            spectra["gamma_other"],
            f"{volume_folder} PHSP Gamma",
        )
        plot_phsp_panel(
            axes[row_index, 1],
            spectra["electron_primary"],
            spectra["electron_other"],
            f"{volume_folder} PHSP Electron",
        )
        plot_trackcount_panel(
            axes[row_index, 2],
            electron_counts,
            f"{volume_folder} TrackCount Electron",
        )
        plot_trackcount_panel(
            axes[row_index, 3],
            gamma_counts,
            f"{volume_folder} TrackCount Gamma",
        )

    output_path = folder_path / "all_output_spectra.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def main() -> int:
    for folder_name in SIMULATION_FOLDERS:
        print(f'Creating summary figure for "{folder_name}"', flush=True)
        output_path = make_figure_for_folder(folder_name)
        print(f'Saved "{output_path}"', flush=True)

    print("All summary figures created.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
