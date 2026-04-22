import os
import sys
import torch
import torchaudio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indextts.utils.feature_extractors import MelSpectrogramFeatures


def generate_voice_feature(audio_path: str, speaker_name: str, output_dir: str = "voices"):
    audio, sr = torchaudio.load(audio_path)
    if audio.shape[0] > 1:
        audio = torch.mean(audio, dim=0, keepdim=True)
    if sr != 24000:
        audio = torchaudio.transforms.Resample(sr, 24000)(audio)
    mel_extractor = MelSpectrogramFeatures()
    cond_mel = mel_extractor(audio)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{speaker_name}.pt")
    torch.save(cond_mel, output_path)
    print(f">> 特征文件已保存: {output_path}")
    print(f">> 特征形状: {cond_mel.shape}")
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成音色特征文件")
    parser.add_argument("audio_path", type=str, help="音频文件路径 (wav格式)")
    parser.add_argument("-n", "--name", type=str, required=True, help="说话人名称")
    parser.add_argument("-o", "--output_dir", type=str, default="voices", help="输出目录")
    args = parser.parse_args()
    if not os.path.exists(args.audio_path):
        print(f"错误: 音频文件不存在: {args.audio_path}")
        sys.exit(1)
    generate_voice_feature(args.audio_path, args.name, args.output_dir)
