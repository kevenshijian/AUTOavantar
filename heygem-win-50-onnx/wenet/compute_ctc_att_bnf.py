# decompyle3 version 3.9.2
# Python bytecode version base 3.8.0 (3413)
# Decompiled from: Python 3.8.19 (default, Mar 20 2024, 15:27:52) 
# [Clang 14.0.6 ]
# Embedded file name: /code/wenet/compute_ctc_att_bnf.py
# Compiled at: 2024-04-01 10:28:36
# Size of source mod 2**32: 7255 bytes
"""
Compute CTC-Attention Seq2seq ASR encoder bottle-neck features (BNF).
MODIFIED FOR FP16 (HALF-PRECISION) INFERENCE.
REMOVED dependency on wenet.utils.checkpoint for better compatibility.
"""
import os, time, argparse, torch
from pathlib import Path
import yaml, numpy as np
from wenet.tools._extract_feats import wav2mfcc_v2, load_wav

# ==================== ADDED FOR FP16 ====================
from torch.cuda.amp import autocast

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

hparams1 = {
  'sample_rate': 16000,
  'preemphasis': 0.97,
  'n_fft': 1024,
  'hop_length': 160,
  'win_length': 800,
  'num_mels': 80,
  'n_mfcc': 13,
  'window': "hann",
  'fmin': 0.0,
  'fmax': 8000.0,
  'ref_db': 20,
  'min_db': -80.0,
  'iterations': 100,
  'silence_db': -28.0,
  'center': True}
SAMPLE_RATE = 16000

# Assuming these are available in your wenet environment
from wenet.transformer.encoder import ConformerEncoder

# Dummy init_model for compatibility. It will be created but its weights will be
# overwritten by the loaded checkpoint.
def init_model(configs):
    encoder = ConformerEncoder(input_size=configs.get('input_dim', 80), **configs['encoder_conf'])
    model = PPGModel(encoder)
    return model

class PPGModel(torch.nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, feats, feats_lengths):
        encoder_out, _ = self.encoder(feats, feats_lengths)
        return encoder_out

# ==================== MODIFIED FUNCTION (NO CHECKPOINT.PY) ====================
def load_ppg_model(train_config, model_file, device='cpu', fp16=False):
    """
    Loads the WeNet model using state_dict, without depending on wenet.utils.checkpoint.
    """
    config_file = Path(train_config)
    with config_file.open("r", encoding="utf-8") as f:
        configs = yaml.safe_load(f)
    
    # We build a model with the right architecture
    model = init_model(configs)
    
    # Load the checkpoint state dictionary
    ckpt_state_dict = torch.load(model_file, map_location="cpu")

    # Get the current model's state dictionary
    model_state_dict = model.state_dict()
    
    # Filter the checkpoint keys to match the model's expected keys
    # This is the original logic from your decompiled code, which is robust.
    filtered_ckpt_state_dict = {
        k: v for k, v in ckpt_state_dict.items() 
        if "encoder" in k and "encoder.global_cmvn" not in k and k in model_state_dict
    }

    # Update the model's state dictionary with the filtered checkpoint weights
    model_state_dict.update(filtered_ckpt_state_dict)
    
    # Load the updated state dictionary into the model
    model.load_state_dict(model_state_dict)
    print("WeNet checkpoint loaded successfully using state_dict.")

    model.to(device)
    
    if fp16 and device == 'cuda':
        model.half()
        print("WeNet model converted to FP16 (half-precision).")
    
    model.eval()
    return model, configs

# ==================== MODIFIED FUNCTION ====================
def _compute_internal(wav_arr, wenet_model_and_configs, section=560000, fp16=False):
    """
    Internal computation logic, handles numpy arrays with FP16 support.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ppg_model, configs = wenet_model_and_configs

    ppg_model.to(device)
    
    zero = np.zeros(6400, dtype=np.float32)
    wav_arr = np.concatenate((zero, wav_arr, zero))
    
    result = []
    
    with autocast(enabled=(fp16 and device == 'cuda')):
        for i in range(len(wav_arr) // section + 1):
            wav_arr_ = wav_arr[section * i:section * (i + 1)]
            
            if len(wav_arr_) == 0:
                continue

            add_silence_flag = False
            if len(wav_arr_) < hparams1["sample_rate"]:
                silence_to_add = hparams1["sample_rate"] - len(wav_arr_)
                wav_arr_ = np.append(wav_arr_, np.zeros(silence_to_add, dtype=np.float32))
                add_silence_flag = True
            
            (mel, _) = wav2mfcc_v2(wav_arr_, sr=(hparams1["sample_rate"]), n_mfcc=(hparams1["n_mfcc"]),
                                   n_fft=(hparams1["n_fft"]),
                                   hop_len=(hparams1["hop_length"]),
                                   win_len=(hparams1["win_length"]),
                                   window=(hparams1["window"]),
                                   num_mels=(hparams1["num_mels"]),
                                   center=(hparams1["center"]))
            
            wav_tensor = torch.from_numpy(mel).float().to(device).unsqueeze(0)
            wav_length = torch.LongTensor([mel.shape[0]]).to(device)

            start_time = time.time()
            with torch.no_grad():
                bnf = ppg_model(wav_tensor, wav_length)
            
            bnf_npy = bnf.float().squeeze(0).cpu().numpy()
            
            print(f"Time for chunk {i}: {time.time() - start_time:.4f}s, Shape: {bnf.shape}")

            if add_silence_flag:
                # This logic seems to be a fixed trim, which might be what's intended
                bnf_npy = bnf_npy[:-25] 

            result.append(bnf_npy)

    if not result:
        return np.array([])
        
    bnf_npy_final = np.concatenate(result, 0)
    return bnf_npy_final

# ==================== MODIFIED FUNCTION ====================
def get_weget(audio_input, wenet_model_and_configs, section=560000, fp16=False):
    """
    Unified function to compute WeNet features from a file path or numpy array.
    """
    if isinstance(audio_input, str):
        wav_arr = load_wav(audio_input, sr=hparams1["sample_rate"])
    elif isinstance(audio_input, np.ndarray):
        wav_arr = audio_input
    else:
        raise TypeError("audio_input must be a file path (str) or a numpy array.")
        
    return _compute_internal(wav_arr, wenet_model_and_configs, section, fp16)


# Example/testing entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute WeNet features with FP16 support")
    parser.add_argument("--config", default="wenet/examples/aishell/aidata/conf/train_conformer_multi_cn.yaml", help="Path to model config file")
    parser.add_argument("--checkpoint", default="wenet/examples/aishell/aidata/exp/conformer/wenetmodel.pt", help="Path to model checkpoint")
    parser.add_argument("--wav", required=True, help="Path to test audio file")
    parser.add_argument("--fp16", action='store_true', help="Enable FP16 inference")
    args = parser.parse_args()

    model, configs = load_ppg_model(args.config, args.checkpoint, device='cuda', fp16=True)
    
    print(f"\n--- Testing with FP16 {'Enabled' if args.fp16 else 'Disabled'} ---")
    start_total = time.time()
    result = get_weget(args.wav, (model, configs), fp16=args.fp16)
    end_total = time.time()

    print(f"Final shape: {result.shape}")
    print(f"Total processing time: {end_total - start_total:.4f}s")