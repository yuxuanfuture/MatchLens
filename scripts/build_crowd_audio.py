"""Build the local 120-second crowd soundtrack without changing source recordings.

Requires numpy and soundfile>=0.13.1 (libsndfile with MP3 support).
python scripts/build_crowd_audio.py --source-dir <audition folder/音频原始素材>
The generated audio is deliberately excluded from Git; see dist/audio/.gitignore.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(source_dir, output_dir):
    import numpy as np
    import soundfile as sf

    manifest = json.loads((ROOT / 'data/stream-04-audio.json').read_text(encoding='utf-8'))
    rate = manifest['sample_rate']
    total = round(manifest['duration_seconds'] * rate)
    mix = np.zeros((total, 2), dtype=np.float64)
    coverage = np.zeros(total, dtype=bool)
    loaded = {}
    source_info = {}
    for key, item in manifest['sources'].items():
        path = source_dir / item['file']
        samples, source_rate = sf.read(path, dtype='float64', always_2d=True)
        if samples.shape[1] != 2:
            raise ValueError(f'{path.name}: expected a stereo source')
        if source_rate != rate:
            # Selected WAVs are 44.1 kHz; the MP3 sources are already 48 kHz.
            if source_rate > rate:
                raise ValueError('Downsampling requires an anti-aliasing resampler')
            positions = np.arange(round(len(samples) * rate / source_rate)) * source_rate / rate
            samples = np.column_stack([np.interp(positions, np.arange(len(samples)), samples[:, channel]) for channel in range(2)])
        loaded[key] = samples
        source_info[key] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'duration_seconds': len(samples) / rate}

    for cue in manifest['cues']:
        start, end = (round(cue[name] * rate) for name in ('start', 'end'))
        first, last = (round(cue[name] * rate) for name in ('in', 'out'))
        source = loaded[cue['source']]
        if not (0 <= start < end <= total and 0 <= first < last <= len(source)):
            raise ValueError(f'Invalid cue bounds: {cue}')
        clip = source[first:last].copy()
        if cue.get('repeat'):
            # Equal-length crossfades avoid a hard seam in the opening chant.
            overlap = round(.25 * rate)
            unit = clip.copy()
            while len(clip) < end - start:
                blend = np.linspace(0, 1, overlap)[:, None]
                clip[-overlap:] = clip[-overlap:] * (1 - blend) + unit[:overlap] * blend
                clip = np.concatenate([clip, unit[overlap:]])
        if len(clip) < end - start:
            raise ValueError(f'Source excerpt too short: {cue}')
        clip = clip[:end-start]
        rms = np.sqrt(np.mean(clip * clip))
        if rms < 1e-6:
            raise ValueError(f'Silent source excerpt: {cue}')
        clip *= (10 ** (manifest['target_rms_db'] / 20)) / rms
        envelope = np.linspace(cue['gain_from'], cue['gain_to'], len(clip))
        fade_in, fade_out = (round(cue[name] * rate) for name in ('fade_in', 'fade_out'))
        envelope[:fade_in] *= np.linspace(0, 1, fade_in)
        envelope[-fade_out:] *= np.linspace(1, 0, fade_out)
        mix[start:end] += clip * envelope[:, None]
        coverage[start:end] = True

    audible_seconds = float(np.count_nonzero(coverage) / rate)
    if audible_seconds != manifest['audible_seconds']:
        raise ValueError(f"Expected {manifest['audible_seconds']} audible seconds; got {audible_seconds}")
    peak = float(np.max(np.abs(mix)))
    attenuation = min(1, .89 / max(peak, 1e-9))
    mix *= attenuation
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / 'stream-04-crowd.mp3'
    sf.write(destination, mix, rate, format='MP3', subtype='MPEG_LAYER_III', compression_level=.25)
    decoded, decoded_rate = sf.read(destination, always_2d=True)
    if abs(len(decoded) / decoded_rate - 120) > .05:
        raise ValueError('Encoded soundtrack duration is incorrect')
    for start, end in ((95.1, 103.9), (114.1, 114.9)):
        if np.max(np.abs(decoded[round(start*decoded_rate):round(end*decoded_rate)])) > .0001:
            raise ValueError('The gaps around the review discussion must be silent')
    murmur = decoded[round(105*decoded_rate):round(112*decoded_rate)]
    cheer = decoded[round(115.1*decoded_rate):round(119.4*decoded_rate)]
    murmur_rms, cheer_rms = (float(np.sqrt(np.mean(clip*clip))) for clip in (murmur, cheer))
    if murmur_rms < .001 or not .1 < murmur_rms / max(cheer_rms, 1e-9) < .4:
        raise ValueError('Review discussion must be audible and quieter than the goal cheer')
    report = {'duration_seconds':len(decoded)/decoded_rate, 'audible_seconds':audible_seconds,
        'quiet_seconds':120-audible_seconds, 'decoded_peak':float(np.max(np.abs(decoded))),
        'mix_attenuation':attenuation, 'sources':source_info,
        'murmur_to_cheer_db':float(20*np.log10(murmur_rms/cheer_rms)),
        'output_bytes':destination.stat().st_size, 'output_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}
    report_path = ROOT / 'run-output/crowd-audio-validation.json'
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT.parent / '声音素材/音频原始素材')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist/audio')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
