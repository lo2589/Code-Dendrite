// dsh-cdd-lens-pcb — main-thread handle to the index worker.
//
// The only thing that ever happens on the harness's thread here is
// `postMessage` and settling a promise. Every byte of JSON, every index build
// and every query runs on the worker, so a cold 9.6MB index build cannot cost
// the chat a single frame.
//
// One worker for the whole process, restarted if it ever dies. Requests are
// correlated by a monotonic seq because a worker answers out of order.
'use strict'

const path = require('node:path')
const { Worker } = require('node:worker_threads')

const WORKER = path.join(__dirname, 'index_worker.js')
/** A query that has not answered by now is a bug, not a slow disk. */
const TIMEOUT_MS = 30_000

class IndexStore {
  #worker = null
  #pending = new Map()
  #seq = 0

  #spawn() {
    const worker = new Worker(WORKER)
    worker.on('message', (message) => {
      const entry = this.#pending.get(message.seq)
      if (entry === undefined) return
      this.#pending.delete(message.seq)
      clearTimeout(entry.timer)
      if (message.ok) entry.resolve(message.data)
      else entry.reject(Object.assign(new Error(message.error), { code: message.code }))
      this.#idle()
    })
    const fail = (error) => {
      // A dead worker must reject every in-flight request. Leaving them pending
      // would hang the page on a spinner that never resolves, which reads as
      // "the plugin is broken" with nothing in any log to say why.
      this.#worker = null
      for (const [seq, entry] of this.#pending) {
        clearTimeout(entry.timer)
        entry.reject(new Error(`index worker died: ${error && error.message ? error.message : error}`))
        this.#pending.delete(seq)
      }
    }
    worker.on('error', fail)
    worker.on('exit', code => { if (code !== 0) fail(new Error(`exit ${code}`)) })
    // Idle, the worker must not hold the process open; in flight, it must. An
    // always-unref'd worker lets the process exit out from under a pending
    // query — invisible inside the harness (something else keeps it alive) and
    // instantly fatal to any script that uses this store on its own.
    worker.unref()
    this.#worker = worker
    return worker
  }

  /** Release the event loop once nothing is in flight. */
  #idle() {
    if (this.#pending.size === 0 && this.#worker !== null) this.#worker.unref()
  }

  /**
   * Ask the worker one question.
   * @param op - handler name on the worker.
   * @param root - absolute repository root whose index answers.
   * @param query - handler arguments.
   */
  ask(op, root, query = {}) {
    const worker = this.#worker ?? this.#spawn()
    const seq = ++this.#seq
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.#pending.delete(seq)
        reject(new Error(`index worker timed out on ${op}`))
        this.#idle()
      }, TIMEOUT_MS)
      // `unref` so a pending query never keeps the harness alive at shutdown.
      if (typeof timer.unref === 'function') timer.unref()
      this.#pending.set(seq, { resolve, reject, timer })
      worker.ref()
      worker.postMessage({ seq, op, root, query })
    })
  }

  close() {
    const worker = this.#worker
    this.#worker = null
    if (worker !== null) void worker.terminate()
  }
}

module.exports = { IndexStore }
