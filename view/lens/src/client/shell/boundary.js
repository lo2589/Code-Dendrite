// dsh-cdd-lens — A render that throws must not take the page with it.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/shell/boundary',
  factory: (require) => {
    var module = { exports: {} }
    var React = require('react')
    var h = React.createElement

    /**
     * Show what went wrong instead of showing nothing.
     *
     * A throw anywhere inside a render unmounts the whole subtree, and what is
     * left is a white rectangle that says nothing at all: not which component,
     * not which line, not even that anything failed. Every white screen this
     * plugin has produced was one exception away from being a one-line message,
     * and each of them cost a round trip to find out which one.
     *
     * Written as a class because that is the only thing React will hand an
     * error to. It is also deliberately dumb: no state beyond the error, no
     * retry, nothing that can itself throw.
     */
    function makeBoundary(React) {
      if (typeof React.Component !== 'function') return null
      function Boundary(props) {
        React.Component.call(this, props)
        this.state = { error: null }
      }
      Boundary.prototype = Object.create(React.Component.prototype)
      Boundary.prototype.constructor = Boundary
      Boundary.getDerivedStateFromError = function (error) { return { error: error } }
      Boundary.prototype.componentDidCatch = function (error, info) {
        // Kept where a person can reach it without a debugger attached.
        try {
          window.__cddLensError = {
            message: String(error && error.message),
            stack: String(error && error.stack),
            component: String((info && info.componentStack) || ''),
            at: new Date().toISOString(),
          }
        } catch (e) { /* nothing useful to do here */ }
        try { console.error('[cdd-lens] render failed', error, info) } catch (e) { /* ignore */ }
      }
      Boundary.prototype.render = function () {
        if (this.state.error === null) return this.props.children
        var error = this.state.error
        return h('div', { className: 'cddl-boundary' }, [
          h('strong', { key: 't' }, 'CDD Lens 这一块渲染失败了'),
          h('div', { key: 'm', className: 'cddl-boundary-msg' },
            String(error && error.message ? error.message : error)),
          h('pre', { key: 's', className: 'cddl-boundary-stack' },
            String((error && error.stack) || '').split('\n').slice(0, 6).join('\n')),
          h('div', { key: 'h', className: 'cddl-boundary-hint' },
            '完整信息也放在 window.__cddLensError 里。图没画出来，其余部分不受影响。'),
        ])
      }
      return Boundary
    }

    module.exports = { makeBoundary }
    return module.exports
  },
})
