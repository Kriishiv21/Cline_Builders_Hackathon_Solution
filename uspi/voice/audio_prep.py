"""Audio preprocessing module (C09, architecture sections 5.2-5.4).

`to_model_waveform()` is the single function used in training and
inference, versioned per detector spec (sample rate, length, pre-emphasis
flag, crop policy). Since this repo does not train detectors (Cline API
replaces that), this module still matters because it defines what gets
sent as *metadata* to the Cline-backed adapters (duration, quality flags),
never raw audio bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from uspi.common.config import load_yaml


@dataclass
class WaveformSpec:
    """Per-detector waveform specification (architecture section 5.3)."""

    detector_name: str
    sample_rate: int
    fixed_length_samples: int
    pre_emphasis: Optional[float]
    crop_policy: str  # "random" (train) | "first" (eval)


@dataclass
class QualityMetadata:
    duration_s: float
    sample_rate: int
    channels: int
    peak_amplitude: float
    quality_flags: List[str]


def load_waveform_specs(config_path: str = "audio.yaml") -> dict:
    cfg = load_yaml(config_path)
    specs = {}
    for name, spec in cfg.get("detector_specs", {}).items():
        specs[name] = WaveformSpec(
            detector_name=name,
            sample_rate=spec["sample_rate"],
            fixed_length_samples=spec["fixed_length_samples"],
            pre_emphasis=spec.get("pre_emphasis"),
            crop_policy=spec.get("crop_policy", "first"),
        )
    return specs


def validate_waveform(samples: np.ndarray, sample_rate: int) -> QualityMetadata:
    """Validate: readable, float32, mono, reject NaN/Inf, flag low peak."""
    flags: List[str] = []
    if samples.ndim > 1:
        samples = samples.mean(axis=1)  # stereo to mono
        flags.append("downmixed_stereo")
    samples = samples.astype(np.float32)
    if not np.all(np.isfinite(samples)):
        raise ValueError("Waveform contains NaN/Inf samples")
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak < 1e-4:
        flags.append("low_peak_amplitude")
    if sample_rate != 16000:
        flags.append("resampled")
    duration_s = len(samples) / float(sample_rate) if sample_rate else 0.0
    if duration_s < 1.0:
        flags.append("short_audio")
    if sample_rate <= 8000:
        flags.append("phone_band")
    return QualityMetadata(
        duration_s=duration_s,
        sample_rate=sample_rate,
        channels=1,
        peak_amplitude=peak,
        quality_flags=flags,
    )


def to_model_waveform(samples: np.ndarray, spec: WaveformSpec, *, is_train: bool = False) -> np.ndarray:
    """The single shared waveform function, applied identically at
    inference time (and, if a detector were ever trained, at training
    time). Pre-emphasis and fixed-length cropping/padding per spec."""
    x = samples.astype(np.float32)
    if spec.pre_emphasis:
        x = np.append(x[0], x[1:] - spec.pre_emphasis * x[:-1])

    target_len = spec.fixed_length_samples
    if len(x) >= target_len:
        if is_train and spec.crop_policy == "random":
            start = np.random.randint(0, len(x) - target_len + 1)
        else:
            start = 0
        x = x[start : start + target_len]
    else:
        reps = int(np.ceil(target_len / max(len(x), 1)))
        x = np.tile(x, reps)[:target_len]
    return x


def simple_vad(samples: np.ndarray, sample_rate: int, frame_ms: int = 30, energy_threshold: float = 1e-3) -> List[tuple]:
    """Minimal energy-based VAD returning (start_s, end_s) speech segments."""
    frame_len = int(sample_rate * frame_ms / 1000)
    if frame_len <= 0:
        return []
    segments = []
    in_speech = False
    seg_start = 0
    for i in range(0, len(samples), frame_len):
        frame = samples[i : i + frame_len]
        energy = float(np.mean(frame ** 2)) if len(frame) else 0.0
        is_speech = energy > energy_threshold
        if is_speech and not in_speech:
            seg_start = i
            in_speech = True
        elif not is_speech and in_speech:
            segments.append((seg_start / sample_rate, i / sample_rate))
            in_speech = False
    if in_speech:
        segments.append((seg_start / sample_rate, len(samples) / sample_rate))
    return segments


def windowize(samples: np.ndarray, sample_rate: int, window_s: float, hop_s: float) -> List[dict]:
    """Overlapping windows, timestamps kept."""
    window_len = int(window_s * sample_rate)
    hop_len = int(hop_s * sample_rate)
    windows = []
    for start in range(0, max(len(samples) - window_len, 0) + 1, hop_len):
        chunk = samples[start : start + window_len]
        windows.append({
            "start_s": start / sample_rate,
            "end_s": (start + len(chunk)) / sample_rate,
            "samples": chunk,
        })
    if not windows and len(samples) > 0:
        windows.append({"start_s": 0.0, "end_s": len(samples) / sample_rate, "samples": samples})
    return windows
