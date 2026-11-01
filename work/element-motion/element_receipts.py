"""Bounded readback shared by production runtime and differential film proof."""
import hashlib

def state_digest(state):
    """Hash C-order state bytes with bounded host memory (under 13 MiB/slab).

    Iteration follows batch, channel, z, y, x, exactly matching the original
    contiguous whole-state readback. No quantization or numerical conversion.
    """
    digest=hashlib.sha256()
    for batch in state:
        for channel in batch:
            for start in range(0,channel.shape[0],64):
                slab=channel[start:start+64].contiguous().cpu()
                digest.update(memoryview(slab.numpy()))
                del slab
    return digest.hexdigest()
