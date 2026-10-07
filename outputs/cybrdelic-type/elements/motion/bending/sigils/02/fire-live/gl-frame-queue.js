// Poll completion without waiting on the CPU or building an unbounded GPU queue.
export function createGLFrameQueue(gl, capacity = 2) {
  const pending = [];
  return {
    ready() {
      while (pending.length) {
        const status = gl.clientWaitSync(pending[0], 0, 0);
        if (status === gl.TIMEOUT_EXPIRED) break;
        if (status === gl.WAIT_FAILED) throw new Error('GPU frame completion failed. Restart the simulation.');
        gl.deleteSync(pending.shift());
      }
      return pending.length < capacity;
    },
    submit() {
      const fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      if (!fence) throw new Error('Could not track GPU frame completion.');
      pending.push(fence);
      gl.flush();
    },
    dispose() { for (const fence of pending) gl.deleteSync(fence); pending.length = 0; },
  };
}
