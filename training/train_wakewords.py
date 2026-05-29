#!/usr/bin/env python3
"""Train openWakeWord models for one or more phrases — headless, no GPU required.

    python training/train_wakewords.py "hey claude" "hey agent" "hey computer"

Assumes the dependencies in training/requirements.txt are installed. Downloads
the shared training data (RIRs, background noise, precomputed negative +
validation features, the piper voice) once, then for each phrase synthesizes
positive/negative clips with piper-tts (libritts_r's ~900 speakers for
diversity), augments + extracts features, trains a classifier head, and writes
``wakeword_models/<slug>.onnx``.

This bypasses piper-sample-generator (its piper-phonemize dep has no wheel on
recent Python) and resamples piper's 22.05 kHz output to the 16 kHz openWakeWord
requires. Works on Python 3.10–3.12.
"""
from __future__ import annotations

import glob
import io
import os
import random
import subprocess
import sys
import wave

import numpy as np
import scipy.io.wavfile
import scipy.signal
from pathlib import Path
from tqdm import tqdm
import datasets

import openwakeword
from openwakeword.data import generate_adversarial_texts
from piper import PiperVoice, SynthesisConfig

OUT = "wakeword_models"
DATA = "train_data"
# FAST: validate the whole pipeline cheaply — one phrase, tiny dataset, and the
# small validation feature set as negatives (skips the 16 GB ACAV download).
FAST = os.environ.get("FAST") == "1"
POS_SPEAKERS = int(os.environ.get("POS_SPEAKERS", "40" if FAST else "150"))
N_ADV = int(os.environ.get("N_ADV", "60" if FAST else "200"))
STEPS = int(os.environ.get("STEPS", "3000" if FAST else "12000"))
NEG_FEATURES = "validation_set_features.npy" if FAST else "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
LEN_SCALES = [0.85, 1.0, 1.15]
NEG_GENERIC = [
    "okay google", "hey computer", "turn on the lights", "what time is it", "play some music",
    "thank you very much", "good morning", "hello there", "stop the timer", "set an alarm",
    "how are you today", "open the door", "this is a test", "the quick brown fox", "tell me a joke",
    "hey google", "hey siri", "say cloud out loud", "okay so anyway", "let us begin now",
]


def sh(cmd: str) -> None:
    print("$", cmd[:160], flush=True)
    subprocess.run(cmd, shell=True, check=False)


def row_to_int16(row, key="audio"):
    a = row[key]
    if isinstance(a, dict) and "array" in a:
        arr = np.asarray(a["array"], dtype=np.float32)
    else:  # new torchcodec AudioDecoder
        s = a.get_all_samples()
        arr = s.data.numpy()
        if arr.ndim > 1:
            arr = arr.mean(axis=0)
        arr = np.asarray(arr, dtype=np.float32)
    return (arr * 32767).astype(np.int16)


def download_shared_data() -> None:
    os.makedirs(DATA, exist_ok=True)
    os.chdir(DATA)
    try:
        # openWakeWord base models (download_models is unreliable; fetch the onnx directly)
        res = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
        os.makedirs(res, exist_ok=True)
        rel = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
        for m in ("melspectrogram.onnx", "embedding_model.onnx"):
            p = os.path.join(res, m)
            if not os.path.exists(p) or os.path.getsize(p) < 1000:
                sh(f"wget -q -O '{p}' {rel}/{m}")

        # piper voice (multi-speaker)
        os.makedirs("voices", exist_ok=True)
        base = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/"
                "libritts_r/medium/en_US-libritts_r-medium.onnx")
        if not os.path.exists("voices/lr.onnx"):
            sh(f"wget -q -O voices/lr.onnx '{base}'")
            sh(f"wget -q -O voices/lr.onnx.json '{base}.json'")

        # room impulse responses
        if not (os.path.exists("mit_rirs") and os.listdir("mit_rirs")):
            os.makedirs("mit_rirs", exist_ok=True)
            rir = datasets.load_dataset("davidscripka/MIT_environmental_impulse_responses",
                                        split="train", streaming=True).cast_column(
                                            "audio", datasets.Audio(sampling_rate=16000))
            for i, row in enumerate(tqdm(rir, desc="rir")):
                scipy.io.wavfile.write(f"mit_rirs/rir_{i}.wav", 16000, row_to_int16(row))

        # background noise (one AudioSet shard, capped)
        if not (os.path.exists("background_clips") and os.listdir("background_clips")):
            os.makedirs("background_clips", exist_ok=True)
            if not (os.path.exists("audioset") and list(Path("audioset").glob("**/*.flac"))):
                os.makedirs("audioset", exist_ok=True)
                sh("wget -q -O audioset/bal_train09.tar https://huggingface.co/datasets/agkphysics/AudioSet/resolve/main/data/bal_train09.tar")
                sh("cd audioset && tar -xf bal_train09.tar")
            flacs = [str(i) for i in Path("audioset").glob("**/*.flac")][:400]
            ds = datasets.Dataset.from_dict({"audio": flacs}).cast_column("audio", datasets.Audio(sampling_rate=16000))
            for i, row in enumerate(tqdm(ds, desc="bg")):
                scipy.io.wavfile.write(f"background_clips/bg_{i}.wav", 16000, row_to_int16(row))

        # precomputed negative (16 GB) + validation features
        if not FAST and not os.path.exists("openwakeword_features_ACAV100M_2000_hrs_16bit.npy"):
            sh("wget -q https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy")
        if not os.path.exists("validation_set_features.npy"):
            sh("wget -q https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/validation_set_features.npy")

        # stub so train.py's top-level piper-sample-generator import succeeds
        os.makedirs("psg", exist_ok=True)
        open("psg/generate_samples.py", "w").write("def generate_samples(*a, **k):\n    raise RuntimeError('stub')\n")
    finally:
        os.chdir("..")


VOICE = None
NSPK = 0


def load_voice() -> None:
    global VOICE, NSPK
    VOICE = PiperVoice.load(os.path.join(DATA, "voices/lr.onnx"))
    NSPK = VOICE.config.num_speakers
    print("piper speakers:", NSPK, flush=True)


def synth(text: str, path: str, spk: int, ls: float) -> bool:
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            VOICE.synthesize_wav(text, wf, syn_config=SynthesisConfig(speaker_id=int(spk), length_scale=ls))
        buf.seek(0)
        sr, data = scipy.io.wavfile.read(buf)
        data = data.astype(np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != 16000:
            data = scipy.signal.resample(data, int(round(len(data) * 16000 / sr)))
        scipy.io.wavfile.write(path, 16000, np.clip(data, -32768, 32767).astype(np.int16))
        return True
    except Exception:
        return False


def gen_clips(phrase: str, name: str) -> dict:
    d = {k: os.path.join(DATA, OUT, name, k)
         for k in ("positive_train", "positive_test", "negative_train", "negative_test")}
    for v in d.values():
        os.makedirs(v, exist_ok=True)
    if len(os.listdir(d["positive_train"])) > 50:
        print("clips present, skipping generation", flush=True)
        return d
    rng = random.Random(7)
    for i, s in enumerate(tqdm(rng.sample(range(NSPK), min(POS_SPEAKERS, NSPK)), desc=f"pos:{name}")):
        for ls in LEN_SCALES:
            synth(phrase, f"{d['positive_train']}/{i}_{ls}.wav", s, ls)
    for i, s in enumerate(rng.sample(range(NSPK), 40)):
        synth(phrase, f"{d['positive_test']}/{i}.wav", s, 1.0)
    adv = generate_adversarial_texts(input_text=phrase, N=N_ADV, include_partial_phrase=1.0, include_input_words=0.2)
    for i, txt in enumerate(tqdm(adv + NEG_GENERIC * 5, desc=f"neg:{name}")):
        synth(txt, f"{d['negative_train']}/{i}.wav", rng.randrange(NSPK), rng.choice(LEN_SCALES))
    for i, txt in enumerate(generate_adversarial_texts(input_text=phrase, N=40,
                            include_partial_phrase=1.0, include_input_words=0.2) + NEG_GENERIC):
        synth(txt, f"{d['negative_test']}/{i}.wav", rng.randrange(NSPK), 1.0)
    print(f"clips: pos_train={len(os.listdir(d['positive_train']))} "
          f"neg_train={len(os.listdir(d['negative_train']))}", flush=True)
    return d


def train_phrase(phrase: str) -> str | None:
    import yaml
    name = phrase.replace(" ", "_")
    print("=" * 60, f"\nTRAIN {phrase!r} -> {name}.onnx\n", "=" * 60, flush=True)
    gen_clips(phrase, name)
    out_abs = os.path.abspath(os.path.join(DATA, OUT))
    cfg = {
        "model_name": name, "target_phrase": [phrase], "custom_negative_phrases": [],
        "n_samples": 1000, "n_samples_val": 200, "tts_batch_size": 50, "augmentation_batch_size": 16,
        "piper_sample_generator_path": os.path.abspath(os.path.join(DATA, "psg")),
        "output_dir": out_abs,
        "rir_paths": [os.path.abspath(os.path.join(DATA, "mit_rirs"))],
        "background_paths": [os.path.abspath(os.path.join(DATA, "background_clips"))],
        "background_paths_duplication_rate": [1],
        "false_positive_validation_data_path": os.path.abspath(os.path.join(DATA, "validation_set_features.npy")),
        "augmentation_rounds": 1,
        "feature_data_files": {"ACAV100M_sample": os.path.abspath(os.path.join(DATA, NEG_FEATURES))},
        "batch_n_per_class": {"ACAV100M_sample": 1024, "adversarial_negative": 50, "positive": 50},
        "model_type": "dnn", "layer_size": 32, "steps": STEPS,
        "max_negative_weight": 1500, "target_false_positives_per_hour": 0.2,
    }
    cfgpath = os.path.abspath(f"{name}.yaml")
    yaml.dump(cfg, open(cfgpath, "w"))
    for f in glob.glob(os.path.join(out_abs, name, "*.npy")):
        os.remove(f)
    trainpy = os.path.join(os.path.dirname(openwakeword.__file__), "train.py")
    sh(f"python {trainpy} --training_config {cfgpath} --augment_clips --train_model")
    found = glob.glob(os.path.join(out_abs, f"{name}.onnx"))
    if not found:
        print(f"ERROR: no onnx produced for {phrase}", flush=True)
        return None
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f"{name}.onnx")
    subprocess.run(f"cp '{found[0]}' '{dest}'", shell=True, check=False)
    print(f"OK: {dest}", flush=True)
    return dest


def main() -> int:
    phrases = sys.argv[1:] or ["hey claude"]
    if FAST:
        phrases = phrases[:1]
    print("phrases:", phrases, "FAST=", FAST, flush=True)
    download_shared_data()
    load_voice()
    os.makedirs(OUT, exist_ok=True)
    done = []
    for phrase in phrases:
        try:
            r = train_phrase(phrase)
            if r:
                done.append((phrase, r))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"FAILED {phrase}: {e}", flush=True)
    print("=" * 60, flush=True)
    for phrase, path in done:
        print(f"TRAINED\t{phrase}\t{path}", flush=True)
    print(f"DONE {len(done)}/{len(phrases)} models", flush=True)
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
