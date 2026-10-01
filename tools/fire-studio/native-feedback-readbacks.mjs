// QA transport only: production mapAsync continuations consume actual native
// readback bytes. A delay holds the original slot; it never invents telemetry.
export class NativeFeedbackReadbacks {
  constructor(lag = 0) {
    if (![0, 4, 8].includes(lag)) throw Error('Readback lag must be 0, 4 or 8 completed frames.');
    this.lag = lag; this.frame = 0; this.nextId = 1; this.jobs = []; this.deliveries = [];
  }
  attach(buffer, size) {
    buffer.mapState = 'unmapped';
    buffer.mapAsync = (mode, offset = 0, length = size - offset) => {
      if (mode !== 1 || buffer.mapState !== 'unmapped' || offset < 0 || length < 1 || offset + length > size)
        return Promise.reject(Error('Invalid recorded MAP_READ request.'));
      buffer.mapState = 'pending';
      return new Promise((resolve, reject) => this.jobs.push({request: this.nextId++, buffer: buffer.__rid,
        offset, size: length, requestedFrame: this.frame, dueFrame: this.frame + this.lag,
        sent: false, bytes: null, resolve: bytes => {
          buffer.mapState = 'mapped'; buffer.mappedBytes = bytes; buffer.mappedOffset = offset; resolve();
        }, reject}));
    };
    buffer.getMappedRange = (offset = 0, length = size - offset) => {
      if (buffer.mapState !== 'mapped' || offset < buffer.mappedOffset || offset + length > buffer.mappedOffset + buffer.mappedBytes.byteLength)
        throw Error('Recorded readback is not mapped at the requested range.');
      return buffer.mappedBytes.slice(offset - buffer.mappedOffset, offset - buffer.mappedOffset + length);
    };
    buffer.unmap = () => {buffer.mapState = 'unmapped'; buffer.mappedBytes = null;};
    return buffer;
  }
  requests() {
    return this.jobs.filter(j => !j.sent).map(j => {
      j.sent = true; return {request:j.request, buffer:j.buffer, offset:j.offset, size:j.size, requestedFrame:j.requestedFrame};
    });
  }
  accept(request, bytes) {
    const job = this.jobs.find(j => j.request === request);
    if (!job || !job.sent || job.bytes || bytes.byteLength !== job.size) throw Error('Unexpected native readback payload.');
    job.bytes = bytes instanceof ArrayBuffer ? bytes.slice(0) : bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  }
  async deliver(completedFrame, flush = false) {
    this.frame = completedFrame;
    const ready = this.jobs.filter(j => j.bytes && (flush || j.dueFrame <= completedFrame));
    for (const job of ready) {
      this.deliveries.push({request:job.request, buffer:job.buffer, requestedFrame:job.requestedFrame,
        dueFrame:job.dueFrame, deliveredFrame:completedFrame, size:job.size, finalFlush:flush});
      job.resolve(job.bytes);
    }
    this.jobs = this.jobs.filter(j => !ready.includes(j));
    // Production collectors execute their mapped-range read and finally block
    // before the next actual production frame chooses its CFL substeps.
    await Promise.resolve(); await Promise.resolve();
  }
  fail(error) {for (const job of this.jobs) job.reject(error); this.jobs = [];}
}
