# AUTOGENERATED! DO NOT EDIT! File to edit: ../00_core.ipynb.

# %% auto 0
__all__ = ['is_tool', 'normalize_audio', 'load_audio', 'get_dbmax', 'audio_float_to_int', 'is_silence', 'batch_it_crazy',
           'makedir', 'fast_scandir', 'get_audio_filenames', 'untuple']

# %% ../00_core.ipynb 4
import torch
import torchaudio
from torchaudio import transforms as T
from torch.nn import functional as F
from torch import Tensor
import numpy as np
import librosa
import os
import math
from einops import rearrange

# %% ../00_core.ipynb 5
def is_tool(name):
    """Check whether `name` is on PATH and marked as executable."""

    # from whichcraft import which
    from shutil import which

    return which(name) is not None

# %% ../00_core.ipynb 7
def normalize_audio(
    audio_in,           # input array/tensor  (numpy or Pytorch)
    norm='global', # global (use max-abs of whole clip) | channel (per-channel norm'd individually) | ''/None
    ):
    "normalize audio, based on the max of the absolute value"
    audio_out = audio_in.clone() if torch.is_tensor(audio_in) else audio_in.copy()  # rudimentary PyTorch/NumPy support
    if ('global' == norm) or  len(audio_in.shape)< 2:
        absmax = abs(audio_in).max()
        audio_out = 0.99*audio_in/absmax if absmax != 0 else audio_in  # 0.99 = just below clipping
    elif 'channel' == norm:
        for c in range(audio_in.shape[0]):  # this loop is slow but sure. TODO: do it fast but still avoid div by zero
            absmax = abs(audio_in[c]).max()
            audio_out[c] = 0.99*audio_in[c]/absmax if absmax != 0 else audio_in[c]  # 0.99 = just below clipping
      #anything else, pass unchanged
    return audio_out

# %% ../00_core.ipynb 16
def load_audio(
    filename:str,     # name of file to load
    sr=48000,         # sample rate in Hz
    verbose=True,     # whether or not to print notices of resampling
    norm='',     # passedto normalize_audio(), see above
    )->torch.tensor:
    "this loads an audio file as a torch tensor"
    if '.mp3' in filename.lower():  # don't rely on torchaudio for mp3s, librosa is more 'kind'
        audio, in_sr = librosa.load(filename, mono=False, sr=sr) # why librosa defaults to mono is beyond me
        audio = torch.tensor(audio)
    else:
        audio, in_sr = torchaudio.load(filename)
    if in_sr != sr:
        if verbose: print(f"Resampling {filename} from {in_sr} Hz to {sr} Hz",flush=True)
        resample_tf = T.Resample(in_sr, sr)
        audio = resample_tf(audio)
        
    if norm != '': audio = normalize_audio(audio, norm=norm)
    return audio

# %% ../00_core.ipynb 23
def get_dbmax(
    audio,       # torch tensor of (multichannel) audio
    ):
    "finds the loudest value in the entire clip and puts that into dBs"
    return 20*torch.log10(torch.flatten(audio.abs()).max()).cpu().numpy()

# %% ../00_core.ipynb 25
def audio_float_to_int(waveform):
    "converts torch float to numpy int16 (for playback in notebooks)"
    return np.clip( waveform.cpu().numpy()*32768 , -32768, 32768).astype('int16')

# %% ../00_core.ipynb 27
def is_silence(
    audio,       # torch tensor of (multichannel) audio
    thresh=-60,  # threshold in dB below which we declare to be silence
    ):
    "checks if entire clip is 'silence' below some dB threshold"
    dBmax = get_dbmax(audio)
    return dBmax < thresh

# %% ../00_core.ipynb 31
def batch_it_crazy(
    x,        # a time series as a PyTorch tensor, e.g. stereo or mono audio
    win_len,  # length of each "window", i.e. length of each element in new batch
    ):
    "(pun intended) Chop up long sequence into a batch of win_len windows"
    if len(x.shape) < 2: x = x.unsqueeze(0)  # guard against 1-d arrays
    x_len = x.shape[-1]
    n_windows = (x_len // win_len) + 1
    pad_amt = win_len * n_windows - x_len  # pad end w. zeros to make lengths even when split
    xpad = F.pad(x, (0, pad_amt))
    return rearrange(xpad, 'd (b n) -> b d n', n=win_len)

# %% ../00_core.ipynb 38
def makedir(
    path:str,              # directory or nested set of directories
    ):
    "creates directories where they don't exist"
    if os.path.isdir(path): return  # don't make it if it already exists
    #print(f"  Making directory {path}")
    try:
        os.makedirs(path)  # recursively make all dirs named in path
    except:                # don't really care about errors
        pass

# %% ../00_core.ipynb 40
def fast_scandir(
    dir:str,  # top-level directory at which to begin scanning
    ext:list  # list of allowed file extensions
    ):
    "very fast `glob` alternative. from https://stackoverflow.com/a/59803793/4259243"
    subfolders, files = [], []
    ext = ['.'+x if x[0]!='.' else x for x in ext]  # add starting period to extensions if needed
    try: # hope to avoid 'permission denied' by this try
        for f in os.scandir(dir):
            try: # 'hope to avoid too many levels of symbolic links' error
                if f.is_dir():
                    subfolders.append(f.path)
                elif f.is_file():
                    if os.path.splitext(f.name)[1].lower() in ext:
                        files.append(f.path)
            except:
                pass 
    except:
        pass

    for dir in list(subfolders):
        sf, f = fast_scandir(dir, ext)
        subfolders.extend(sf)
        files.extend(f)
    return subfolders, files

# %% ../00_core.ipynb 44
def get_audio_filenames(
    paths:list   # directories in which to search
    ):
    "recursively get a list of audio filenames"
    filenames = []
    if type(paths) is str: paths = [paths]
    for path in paths:               # get a list of relevant filenames
        subfolders, files = fast_scandir(path, ['.wav','.flac','.ogg','.aiff','.aif','.mp3'])
        filenames.extend(files)
    return filenames

# %% ../00_core.ipynb 47
def untuple(x, verbose=False):
    """Recursive.  For when you're sick of tuples and lists: 
    keeps peeling off elements until we get a non-tuple or non-list, 
    i.e., returns the 'first' data element we can 'actually use'"""
    if isinstance(x, tuple) or isinstance(x, list): 
        if verbose: print("yea: x = ",x)
        return untuple(x[0], verbose=verbose)
    else:
        if verbose: print("no: x = ",x)
        return x
