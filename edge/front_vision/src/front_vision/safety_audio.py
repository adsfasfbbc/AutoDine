"""Acoustic arousal cues for safety fusion.

A sounddevice InputStream feeds a bounded 2-second ring buffer; once per
second a set of physical features is extracted — RMS loudness vs. an adaptive
baseline, spectral flux, F0 mean/jitter (librosa.yin with a numpy fallback)
and energy-onset rate — and combined into an audio_score in [0, 1]; a
threshold yields the audio_flag.

Privacy: raw PCM lives only in the bounded in-memory ring buffer, is
discarded right after feature extraction, is never written to disk, and no
ASR/speech content is ever derived.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Deque, Optional, Tuple

import numpy as np

logger = logging.getLogger("front_vision.safety_audio")

# Privacy bound: never retain more than this many seconds of raw PCM.
RING_BUFFER_SECONDS = 2.0
FEATURE_HOP_SECONDS = 1.0

FRAME_LENGTH = 1024
HOP_LENGTH = 256
F0_MIN_HZ = 50.0
F0_MAX_HZ = 500.0

# Normalization references; scores are clipped to [0, 1].
LOUDNESS_RANGE_DB = 25.0     # dB above the adaptive baseline that reads as "loud"
SPECTRAL_FLUX_REF = 8.0      # mean positive spectral diff of a shout/clatter
F0_MEAN_REF_HZ = 300.0       # high-arousal speech mean F0
F0_JITTER_REF = 0.15         # relative F0 frame-to-frame jitter
ONSET_RATE_REF_HZ = 1.5      # energy onsets per second

W_LOUD = 0.40
W_FLUX = 0.25
W_F0 = 0.20
W_ONSET = 0.15

_DB_FLOOR = 1e-12


def rms_db(samples: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    return 20.0 * np.log10(max(rms, _DB_FLOOR))


def _f0_track(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """F0 per frame via librosa.yin; numpy autocorrelation fallback."""
    try:
        import librosa

        f0 = librosa.yin(
            samples.astype(np.float32), fmin=F0_MIN_HZ, fmax=F0_MAX_HZ,
            sr=sample_rate, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH,
        )
        return np.asarray(f0, dtype=np.float64)
    except ImportError:
        logger.warning("librosa unavailable; using numpy autocorrelation F0 fallback")
        return _f0_track_numpy(samples, sample_rate)


def _f0_track_numpy(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    frames = []
    step = HOP_LENGTH
    for start in range(0, max(1, len(samples) - FRAME_LENGTH + 1), step):
        frame = samples[start:start + FRAME_LENGTH].astype(np.float64)
        frame = frame - frame.mean()
        if np.max(np.abs(frame)) < 1e-6:
            frames.append(0.0)
            continue
        corr = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
        lo = int(sample_rate / F0_MAX_HZ)
        hi = min(int(sample_rate / F0_MIN_HZ), len(corr) - 1)
        if hi <= lo:
            frames.append(0.0)
            continue
        lag = lo + int(np.argmax(corr[lo:hi]))
        frames.append(sample_rate / lag)
    return np.asarray(frames, dtype=np.float64)


def compute_audio_features(samples: np.ndarray, sample_rate: int) -> dict:
    """Physical features of one analysis window (pure function, no I/O)."""
    samples = np.asarray(samples, dtype=np.float64)
    if samples.size < FRAME_LENGTH:
        return {"rms_db": -120.0, "spectral_flux": 0.0, "f0_mean": 0.0,
                "f0_jitter": 0.0, "onset_rate": 0.0}

    window = np.hanning(FRAME_LENGTH)
    mags = []
    energies = []
    for start in range(0, samples.size - FRAME_LENGTH + 1, HOP_LENGTH):
        frame = samples[start:start + FRAME_LENGTH] * window
        mags.append(np.abs(np.fft.rfft(frame)))
        energies.append(float(np.sum(frame ** 2)))
    mags_arr = np.asarray(mags)
    energies_arr = np.asarray(energies)

    # Spectral flux: mean positive difference between consecutive magnitude spectra.
    if len(mags_arr) > 1:
        flux = float(np.mean(np.maximum(0.0, np.diff(mags_arr, axis=0)).sum(axis=1) / mags_arr.shape[1]))
    else:
        flux = 0.0

    f0 = _f0_track(samples, sample_rate)
    # Gate F0 by frame energy: unvoiced/silent frames produce garbage F0.
    n = min(len(f0), energies_arr.size)
    if n and energies_arr[:n].max() > 1e-9:
        gate = energies_arr[:n] > 0.1 * energies_arr[:n].max()
        f0 = np.where(gate, f0[:n], 0.0)
    else:
        f0 = np.zeros(n)
    voiced = f0[(f0 >= F0_MIN_HZ) & (f0 <= F0_MAX_HZ)]
    if voiced.size >= 2:
        f0_mean = float(np.mean(voiced))
        f0_jitter = float(np.mean(np.abs(np.diff(voiced))) / max(f0_mean, 1e-6))
    else:
        f0_mean, f0_jitter = 0.0, 0.0

    # Onset rate: peaks of the energy envelope above its own mean+std.
    hop_seconds = HOP_LENGTH / sample_rate
    if energies_arr.size >= 4 and energies_arr.max() > 0:
        thresh = energies_arr.mean() + energies_arr.std()
        peaks = int(np.sum((energies_arr[1:-1] > thresh)
                           & (energies_arr[1:-1] > energies_arr[:-2])
                           & (energies_arr[1:-1] >= energies_arr[2:])))
        onset_rate = peaks / max(energies_arr.size * hop_seconds, 1e-6)
    else:
        onset_rate = 0.0

    return {
        "rms_db": rms_db(samples),
        "spectral_flux": flux,
        "f0_mean": f0_mean,
        "f0_jitter": f0_jitter,
        "onset_rate": onset_rate,
    }


class AudioFeatureScorer:
    """Turns per-second features into an arousal score with an adaptive
    loudness baseline (the baseline only adapts while arousal is low)."""

    def __init__(self, score_threshold: float = 0.6, baseline_alpha: float = 0.02) -> None:
        self._threshold = score_threshold
        self._alpha = baseline_alpha
        self._baseline_db: Optional[float] = None

    def update(self, features: dict) -> Tuple[float, bool]:
        if self._baseline_db is None:
            self._baseline_db = features["rms_db"]
        loud_norm = min(1.0, max(0.0, (features["rms_db"] - self._baseline_db) / LOUDNESS_RANGE_DB))
        flux_norm = min(1.0, features["spectral_flux"] / SPECTRAL_FLUX_REF)
        f0_norm = min(1.0, 0.5 * features["f0_mean"] / F0_MEAN_REF_HZ
                      + 0.5 * features["f0_jitter"] / F0_JITTER_REF)
        onset_norm = min(1.0, features["onset_rate"] / ONSET_RATE_REF_HZ)
        score = min(1.0, W_LOUD * loud_norm + W_FLUX * flux_norm
                    + W_F0 * f0_norm + W_ONSET * onset_norm)
        flag = score >= self._threshold
        if not flag:
            self._baseline_db += self._alpha * (features["rms_db"] - self._baseline_db)
        return float(score), flag


class AcousticArousalMonitor:
    """Background microphone capture + per-second feature scoring.

    Owns the bounded PCM ring buffer (privacy: RING_BUFFER_SECONDS max, in
    memory only) and exposes the latest (audio_score, audio_flag).
    """

    def __init__(
        self,
        device=None,
        sample_rate: int = 16000,
        score_threshold: float = 0.6,
        baseline_alpha: float = 0.02,
        hop_seconds: float = FEATURE_HOP_SECONDS,
    ) -> None:
        self._device = device
        self._sample_rate = sample_rate
        self._hop = hop_seconds
        self._scorer = AudioFeatureScorer(score_threshold, baseline_alpha)
        # Each callback block is stored as one chunk; maxlen bounds the total
        # retained PCM to RING_BUFFER_SECONDS regardless of block size.
        self._chunks: Deque[np.ndarray] = deque()
        self._max_samples = int(RING_BUFFER_SECONDS * sample_rate)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stream = None
        self.audio_score = 0.0
        self.audio_flag = False
        self.last_flag_at: Optional[float] = None

    @property
    def buffered_seconds(self) -> float:
        with self._lock:
            return sum(len(c) for c in self._chunks) / float(self._sample_rate)

    def _callback(self, indata, frames, _time_info, status) -> None:
        if status:
            logger.debug("audio input status: %s", status)
        chunk = np.asarray(indata[:, 0], dtype=np.float32).copy()
        with self._lock:
            self._chunks.append(chunk)
            total = sum(len(c) for c in self._chunks)
            while total > self._max_samples and self._chunks:
                total -= len(self._chunks.popleft())

    def start(self) -> bool:
        """Open the input stream; returns False (audio disabled) on failure."""
        import sounddevice as sd

        try:
            self._stream = sd.InputStream(
                device=self._device, samplerate=self._sample_rate,
                channels=1, dtype="float32", callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            logger.warning("audio input unavailable (%s); acoustic channel disabled", exc)
            self._stream = None
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._score_loop, name="front-vision-audio", daemon=True)
        self._thread.start()
        logger.info("audio monitor started (device=%s, sr=%d)", self._device or "default", self._sample_rate)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            self._chunks.clear()

    def _score_loop(self) -> None:
        while not self._stop.wait(self._hop):
            with self._lock:
                if not self._chunks:
                    continue
                samples = np.concatenate(list(self._chunks))
            try:
                features = compute_audio_features(samples, self._sample_rate)
                score, flag = self._scorer.update(features)
                self.audio_score = score
                self.audio_flag = flag
                if flag:
                    self.last_flag_at = time.monotonic()
            except Exception:
                logger.exception("audio feature extraction failed")
