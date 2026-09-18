// dsh-cdd-lens — 计算单元 0：一次 read 的窗口。
//
// harness 的 read 结果 `meta.lines` 是 `ReadFileLine[]`（`{ number, text }`），
// **不是行数**（packages/core/tools/src/presentation.ts::ReadResultView）。数组永远
// 过不了 `Number.isInteger`，所以凡是把它当整数判断的地方，判断恒为 false，窗口
// 整个算错。这个文件是那一处算法的唯一实现，两边（compute/evidence、session_trace）
// 都走它，不许再各写一遍。
//
// 浏览器那一半有一份等价实现（src/client/session/position.js）—— 两个运行时不能
// 共享模块，改一边必须同步另一边。
'use strict'

/** 读回来的那几行原文。不是数组就是没有（老记录、非 read、非 meta 事件）。 */
function windowLines(meta) {
  const lines = meta === null || meta === undefined ? undefined : meta.lines
  return Array.isArray(lines) ? lines : null
}

/**
 * 一次 read 的 `[from, to]`。
 *
 * 正常一定走 `meta.lines`：取最后一行的 `number` 当终点。没有数组时才退回 `limit`
 * / 整文件 —— `-1` 是"读到文件尾"在线上各处的写法。
 *
 * @param meta - tool/result 的 meta（`{ path, offset, lines, totalLines }`）。
 * @param args - tool/call 的原始参数（`{ offset, limit, ... }`），作为兜底。
 */
function readWindow(meta, args) {
  const m = meta || {}
  const a = args || {}
  const from = Number.isInteger(m.offset) ? m.offset : (Number.isInteger(a.offset) ? a.offset : 1)
  const lines = windowLines(m)
  if (lines !== null && lines.length > 0) {
    const last = lines[lines.length - 1]
    const to = Number.isInteger(last.number) ? last.number : from + lines.length - 1
    return { from, to }
  }
  if (Number.isInteger(m.lines)) return { from, to: from + m.lines - 1 }
  if (Number.isInteger(a.limit)) return { from, to: from + a.limit - 1 }
  return { from, to: -1 }
}

module.exports = { readWindow, windowLines }
