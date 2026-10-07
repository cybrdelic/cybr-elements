import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import {spawn} from 'node:child_process';

// JSON control messages contain only file paths. Recorded commands, native
// logs, readback bytes and images remain on disk.
export class NativeVolumeStream {
  constructor({python = 'python', script, recording, adapter = 'integrated', output = 'native-feedback', profile = false, fieldSummaries = false}) {
    this.folder = recording; this.output = output; this.messages = []; this.waiters = []; this.failure = null;
    this.log = fs.openSync(path.join(recording, 'native-stream.log'), 'w');
    this.child = spawn(python, [script, recording, '--stream', '--adapter', adapter, '--output', output,
      ...(profile ? ['--profile'] : []), ...(fieldSummaries ? ['--field-summaries'] : [])],
      {windowsHide:true, stdio:['pipe','pipe',this.log]});
    readline.createInterface({input:this.child.stdout}).on('line', line => {
      try {
        if (line.length > 20000) throw Error('Native stream returned an oversized control message.');
        const message = JSON.parse(line);
        const waiter = this.waiters.shift(); if (waiter) {clearTimeout(waiter.timer);waiter.resolve(message);} else this.messages.push(message);
      } catch (error) {this.abort(error);}
    });
    // close follows stdout drain; an expected numerical-rejection exit must
    // not discard the final JSON acknowledgement still buffered in the pipe.
    this.exit = new Promise(resolve => this.child.on('close', (code, signal) => {
      this.closed = true; fs.closeSync(this.log);
      if (code !== 0) this.abort(Error(`Native stream exited (${code ?? signal}); see native-stream.log.`));
      else if (this.waiters.length) this.abort(Error('Native stream closed before its acknowledgement; see native-stream.log.'));
      resolve({code,signal});
    }));
    this.child.on('error', error => this.abort(error));
    this.child.stdin.on('error', error => this.abort(error));
  }
  abort(error) {this.failure = error; for (const w of this.waiters.splice(0)) {clearTimeout(w.timer);w.reject(error);}}
  next() {
    if (this.messages.length) return Promise.resolve(this.messages.shift());
    if (this.failure) return Promise.reject(this.failure);
    if (this.closed) return Promise.reject(Error('Native stream closed before acknowledgement.'));
    return new Promise((resolve,reject) => {
      const waiter={resolve,reject,timer:setTimeout(()=>this.abort(Error('Native acknowledgement timed out after 120 seconds; see native-stream.log.')),120000)};
      this.waiters.push(waiter);
    });
  }
  async request(message) {
    if (this.failure) throw this.failure;
    this.child.stdin.write(JSON.stringify(message)+'\n');
    const reply = await this.next();
    if (reply.kind === 'error') throw Error(reply.error?.message || 'Native stream failed; see its report.');
    return reply;
  }
  async start() {
    const reply = await this.next();
    if (reply.kind !== 'ready') throw Error(reply.error?.message || 'Native stream did not become ready.');
    return reply;
  }
  async finish(hostError = null) {
    if (this.closed) return null;
    const reply = await this.request({kind:'finish',hostError});
    if(reply.kind !== 'finished') throw Error('Native stream did not acknowledge its final host result.');
    this.child.stdin.end(); await this.exit; return reply;
  }
  terminate() {this.child.kill();}
}
