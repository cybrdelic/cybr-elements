// Keep one live Fire Studio simulation per browser profile. A hidden tab still
// owns its WebGL allocations, so stopping its RAF alone does not free the GPU.
export function createSimulationSession(lockManager = globalThis.navigator?.locks) {
  let releaseLock = null;
  let pending = null;

  async function acquire() {
    if (!lockManager?.request) return true;
    if (releaseLock) return true;
    if (pending) return pending;

    pending = new Promise((resolve) => {
      let resolveAcquired;
      const acquired = new Promise((done) => { resolveAcquired = done; });
      lockManager.request('cybr-fire-studio-gpu', { ifAvailable: true }, async (lock) => {
        if (!lock) {
          resolveAcquired(false);
          return;
        }
        resolveAcquired(true);
        await new Promise((done) => { releaseLock = done; });
        releaseLock = null;
      }).catch(() => resolveAcquired(false));
      acquired.then(resolve);
    }).finally(() => { pending = null; });
    return pending;
  }

  function release() {
    releaseLock?.();
  }

  return { acquire, release };
}
