// dsh-cdd-lens — Stylesheet: the frame the graph sits in.
//
// One module of the browser half. The parts are concatenated in dependency
// order into lib/client.js by scripts/build.js; each registers itself with
// the loader and reaches the others through `require`.
window.__ModuleLoader__.load({
  id: 'dsh-cdd-lens/styles/shell',
  factory: (require) => {
    var module = { exports: {} }

    /** Frame, panel, dock, toolbar and tree. */
    var SHELL_CSS = [
      // The overlay layer is click-through; pointer events are opted back into
      // per element, and deliberately only on the card — never on a wrapper —
      // so the rest of the frame stays clickable.
      '.cddl-root{position:absolute;right:16px;bottom:16px;pointer-events:none;display:flex;flex-direction:column;align-items:flex-end;gap:8px;z-index:400}',
      'body:has(.cddl-view) .cddl-root,body:has(.cddl-trajectory) .cddl-root{display:none}',
      // Header stays above the rail, but below DSH's workbench overlay layer.
      'body:has(.cddl-trajectory) header:has([role="tablist"]){position:relative;z-index:var(--cddl-header-layer,19);width:calc(100% + var(--cddl-trajectory-width,360px))}',
      // Nothing reserves room for the trajectory column any more. Pushing
      // #root aside squeezed the graph — the thing you opened this for —
      // and on any tab where the column did not paint, the reserved band
      // stayed behind as an empty white strip. It overlays the margin
      // beside the conversation instead, the way dsh-lifecycle's rail does.
      '.cddl-dock{position:fixed;right:var(--cddl-trajectory-width,0px);top:var(--cddl-trajectory-top,0);bottom:0;z-index:var(--cddl-dock-layer,18);pointer-events:auto;min-width:420px;max-width:78vw;display:flex;flex-direction:column;background:var(--dsw-alias-bg-layer-1);border-left:1px solid var(--dsw-alias-border-l3);box-shadow:-12px 0 32px rgba(0,0,0,.28)}',
      '.cddl-dock-resize{position:absolute;left:-6px;top:0;bottom:0;width:12px;cursor:ew-resize;z-index:6}',
      '.cddl-dock-resize:hover{background:color-mix(in srgb,var(--dsw-alias-state-business-primary) 28%,transparent)}',
      '.cddl-dock-head{height:38px;box-sizing:border-box;padding:0 10px;display:flex;align-items:center;gap:9px;flex:none;border-bottom:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2)}',
      '.cddl-dock>.cddl-view{flex:1;min-height:0;height:auto;padding-bottom:0}',
      '.cddl-card{pointer-events:auto;position:relative;max-height:min(78vh,760px);display:flex;flex-direction:column;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:11px;box-shadow:var(--dsw-elevation-panel,0 12px 34px rgba(0,0,0,.5));overflow:hidden;color:var(--dsw-alias-label-primary);font-family:var(--dsw-font-family,inherit);font-size:12px;line-height:1.6}',
      '.cddl-pill{pointer-events:auto;cursor:pointer;padding:6px 12px;border-radius:999px;display:flex;gap:6px;align-items:center;background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);box-shadow:var(--dsw-elevation-panel,0 6px 18px rgba(0,0,0,.4));color:var(--dsw-alias-label-secondary);font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddl-pill:hover{color:var(--dsw-alias-label-primary)}',
      '.cddl-pilln{background:var(--dsw-alias-bg-layer-3);border-radius:9px;padding:0 6px;font-size:10px}',

      '.cddl-grip{position:absolute;left:0;top:0;bottom:0;width:6px;cursor:ew-resize;z-index:2}',
      '.cddl-grip:hover{background:var(--dsw-alias-border-l3)}',
      '.cddl-head{cursor:grab;user-select:none;display:flex;align-items:center;gap:8px;padding:9px 12px;border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-title{font-size:12.5px;font-weight:600}',
      '.cddl-meta{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;color:var(--dsw-alias-label-caption);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-spacer{flex:1}',
      '.cddl-bad{color:var(--dsw-alias-state-error-primary);font-size:10.5px}',
      '.cddl-btn{border:1px solid var(--dsw-alias-border-l2);background:transparent;color:var(--dsw-alias-label-tertiary);border-radius:5px;font-size:11px;padding:2px 7px;cursor:pointer;font-family:inherit;white-space:nowrap}',
      '.cddl-btn:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
      '.cddl-primary{border:1px solid var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary);border-radius:6px;font-size:11.5px;padding:4px 12px;cursor:pointer;font-family:inherit;margin-top:8px}',
      '.cddl-primary:disabled{opacity:.5;cursor:default}',

      '.cddl-tabs{display:flex;gap:2px;padding:6px 12px 0;border-bottom:1px solid var(--dsw-alias-border-l1);flex:none}',
      '.cddl-tabs button{background:transparent;border:0;border-bottom:2px solid transparent;cursor:pointer;padding:4px 10px;font-size:11.5px;color:var(--dsw-alias-label-caption);font-family:inherit}',
      '.cddl-tabs button.on{color:var(--dsw-alias-label-primary);border-bottom-color:var(--dsw-alias-state-business-primary)}',

      '.cddl-search{position:relative;padding:8px 12px 0;flex:none}',
      '.cddl-q{width:100%;box-sizing:border-box;background:var(--dsw-alias-bg-layer-1);border:1px solid var(--dsw-alias-border-l2);border-radius:6px;padding:4px 9px;font-size:11.5px;color:var(--dsw-alias-label-primary);font-family:inherit;outline:none}',
      '.cddl-q::placeholder{color:var(--dsw-alias-label-dimmed)}',
      '.cddl-hits{position:absolute;left:12px;right:12px;top:100%;z-index:3;max-height:280px;overflow:auto;background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l2);border-radius:7px;box-shadow:0 8px 22px rgba(0,0,0,.45);padding:4px}',
      '.cddl-hit{display:flex;align-items:baseline;gap:8px;padding:4px 7px;border-radius:5px;cursor:pointer}',
      '.cddl-hit:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-hitfile{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-caption)}',

      '.cddl-body{flex:1;min-height:120px;overflow:auto}',
      '.cddl-tree{padding:8px 10px 10px}',
      '.cddl-filehdr{font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-caption);margin:8px 0 3px}',
      '.cddl-node{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:6px;cursor:pointer}',
      '.cddl-node:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-sel{background:var(--dsw-alias-interactive-bg-active)}',
      '.cddl-ind{flex:none}',
      '.cddl-twist{width:14px;flex:none;color:var(--dsw-alias-label-dimmed);font-size:9px;text-align:center;background:transparent;border:0;cursor:pointer;padding:0;font-family:inherit}',
      '.cddl-twist:hover{color:var(--dsw-alias-label-primary)}',
      '.cddl-dot{width:7px;height:7px;border-radius:50%;flex:none;background:var(--dsw-alias-label-dimmed);display:inline-block}',
      '.cddl-dot.cddl-v{background:var(--dsw-alias-state-business-primary)}',
      '.cddl-dot.cddl-e{background:var(--dsw-alias-state-warn-primary)}',
      '.cddl-dot.cddl-w{background:var(--dsw-alias-state-error-primary);box-shadow:0 0 0 3px rgba(242,90,90,.2)}',
      '.cddl-sym{font-family:var(--ds-font-family-code,monospace);font-size:11.5px;color:var(--dsw-alias-label-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.cddl-sel .cddl-sym{color:var(--dsw-alias-label-primary)}',
      '.cddl-kind{font-size:9.5px;color:var(--dsw-alias-label-caption);flex:none;border:1px solid var(--dsw-alias-border-l2);border-radius:3px;padding:0 3px;white-space:nowrap}',
      '.cddl-turn{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;flex:none;padding:0 5px;border-radius:9px;border:1px solid transparent;white-space:nowrap}',
      '.cddl-turn.cddl-v{color:var(--dsw-alias-state-business-primary);border-color:var(--dsw-alias-state-business-tertiary)}',
      '.cddl-turn.cddl-e{color:var(--dsw-alias-state-warn-primary);border-color:var(--dsw-alias-state-warn-tertiary)}',
      '.cddl-turn.cddl-w{color:var(--dsw-alias-state-error-primary);border-color:var(--dsw-alias-state-error-secondary)}',
      '.cddl-lines{font-family:var(--ds-font-family-code,monospace);font-size:9.5px;color:var(--dsw-alias-label-dimmed);margin-left:auto;flex:none;padding-left:6px;white-space:nowrap}',
      '.cddl-hop{margin-left:auto;display:flex;gap:2px;flex:none;opacity:.55}',
      '.cddl-node:hover .cddl-hop,.cddl-sel .cddl-hop{opacity:1}',
      '.cddl-hop button{font-size:10px;font-family:var(--ds-font-family-code,monospace);cursor:pointer;color:var(--dsw-alias-label-caption);background:transparent;border:1px solid var(--dsw-alias-border-l2);border-radius:4px;padding:0 4px}',
      '.cddl-hop button:hover{color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-hop button.on{color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-border-l4)}',
      // Compaction took the verbatim evidence back: pale, not gone.
      '.cddl-faded{opacity:.4}',
      '.cddl-faded .cddl-sym{font-style:italic}',
      '.cddl-island{border-left:2px dashed var(--dsw-alias-border-l3)}',
      '.cddl-bridge .cddl-sym{color:var(--dsw-alias-label-caption)}',
      '.cddl-bridgetag{border-style:dashed;opacity:.8}',
      '.cddl-gap{display:flex;align-items:center;gap:7px;padding:6px 4px;color:var(--dsw-alias-label-caption);font-size:10px}',
      '.cddl-gap i{flex:1;height:1px;background:repeating-linear-gradient(90deg,var(--dsw-alias-label-dimmed) 0 3px,transparent 3px 7px)}',

      '.cddl-dir,.cddl-fileitem,.cddl-symitem{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:6px;cursor:pointer;font-size:11.5px}',
      '.cddl-dir{color:var(--dsw-alias-label-secondary);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-fileitem{padding-left:20px;color:var(--dsw-alias-label-caption);font-family:var(--ds-font-family-code,monospace)}',
      '.cddl-symitem{padding-left:38px}',
      '.cddl-dir:hover,.cddl-fileitem:hover,.cddl-symitem:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.cddl-count{margin-left:auto;font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-dimmed);flex:none}',
      '.cddl-sub{padding-left:38px;color:var(--dsw-alias-label-dimmed);font-size:11px}',

      '.cddl-empty{padding:18px 14px;color:var(--dsw-alias-label-tertiary);font-size:11.5px;line-height:1.8}',
      '.cddl-path{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;color:var(--dsw-alias-label-caption);word-break:break-all;margin:4px 0}',
      '.cddl-progress{color:var(--dsw-alias-label-caption);font-size:11px;margin-top:6px}',
      '.cddl-tail{font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-dimmed);max-height:90px;overflow:auto;margin-top:8px;white-space:pre-wrap}',

      '.cddl-legend{display:flex;flex-wrap:wrap;gap:12px;padding:8px 12px;flex:none;border-top:1px solid var(--dsw-alias-border-l1);font-size:10.5px;color:var(--dsw-alias-label-caption)}',
      '.cddl-legend b{font-weight:400;display:flex;align-items:center;gap:5px}',
      '.cddl-swatch{display:inline-block;width:18px;height:0;border-top:1.5px solid var(--dsw-alias-border-l4)}',
      '.cddl-swatch.cddl-dataflow{border-top-style:dashed}',
      '.cddl-swatch.cddl-inherit{border-top-style:dotted}',
      '.cddl-swatch.cddl-impact{border-top:2px dotted var(--dsw-alias-border-l3)}',
      '.cddl-swatch.cddl-dispatch{border-top:2px dashed var(--dsw-alias-border-l4)}',

      '.cddl-src{border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex:none}',
      '.cddl-srch{font-family:var(--ds-font-family-code,monospace);font-size:10px;padding:8px 8px 4px 12px;color:var(--dsw-alias-label-caption);word-break:break-all;display:flex;align-items:flex-start;gap:8px}',
      '.cddl-srch>span{min-width:0;flex:1}',
      '.cddl-src-close{flex:none;width:24px;height:24px;border:1px solid var(--dsw-alias-border-l2);border-radius:5px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-caption);cursor:pointer;font-size:16px;line-height:18px}',
      '.cddl-src pre{margin:0;padding:0 12px 10px;font-family:var(--ds-font-family-code,monospace);font-size:10.5px;line-height:1.65;color:var(--dsw-alias-label-tertiary);max-height:180px;overflow:auto}',
      '.cddl-hl{background:var(--dsw-alias-state-warn-tertiary);display:block;margin:0 -12px;padding:0 12px;border-left:2px solid var(--dsw-alias-state-warn-primary)}',
      '.cddl-ln{color:var(--dsw-alias-label-dimmed);user-select:none;display:inline-block;width:34px}',
      '.cddl-code{white-space:pre}',
      '.cddl-hist{border-top:1px solid var(--dsw-alias-border-l1);padding:8px 12px;flex:none}',
      '.cddl-hist h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddl-unres{margin:10px 10px 4px;padding:8px 10px;border-radius:8px;border:1px dashed var(--dsw-alias-border-l3);background:var(--dsw-alias-bg-layer-1)}',
      '.cddl-unres h4{display:flex;align-items:center;gap:6px}',
      '.cddl-rank{font-family:var(--ds-font-family-code,monospace);font-size:9px;flex:none;width:15px;text-align:right;color:var(--dsw-alias-label-dimmed)}',
      '.cddl-rank-none{color:transparent}',
      '.cddl-hop button.cddl-off{opacity:.3;cursor:default}',
      '.cddl-hop button.cddl-off:hover{background:transparent;color:var(--dsw-alias-label-caption)}',
      '.cddl-unres h4{margin:0 0 5px;font-size:10.5px;color:var(--dsw-alias-label-caption);font-weight:500}',
      '.cddl-unrow{display:flex;align-items:center;gap:7px;padding:1px 0;opacity:.75}',
      '.cddl-hrow{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--dsw-alias-label-tertiary);padding:1px 0}',
      '.cddl-agent{font-family:var(--ds-font-family-code,monospace);color:var(--dsw-alias-state-business-primary)}',
      '.cddl-reason{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dsw-alias-label-secondary)}',
      '.cddl-t{font-family:var(--ds-font-family-code,monospace);font-size:10px;color:var(--dsw-alias-label-caption);width:26px;flex:none}',

      // ---- the spread-out view ----
      '.cddl-view{--cddl-bottom-clearance:calc(var(--dsh-composer-height,152px) + 16px);display:flex;flex-direction:column;height:100%;min-height:0;width:100%;box-sizing:border-box;padding-bottom:var(--cddl-bottom-clearance);overflow:hidden;background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary);font-family:var(--dsw-font-family,inherit);font-size:12px}',
      '.cddl-view-docked{--cddl-bottom-clearance:0px}',
      '.cddl-toolbar{display:flex;align-items:center;gap:8px;padding:8px 16px;flex:none;flex-wrap:wrap;border-bottom:1px solid var(--dsw-alias-border-l1)}',
      '.cddl-view-docked .cddl-toolbar{flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;padding:6px 8px}',
      '.cddl-view-docked .cddl-toolbar>*{flex:none}',
      '.cddl-view-docked>.cddl-legend{display:none}',
      '.cddl-toolbar .cddl-search{padding:0;width:240px;flex:none}',
      '.cddl-seg{display:flex;border:1px solid var(--dsw-alias-border-l2);border-radius:6px;overflow:hidden;flex:none}',
      '.cddl-seg button{padding:3px 11px;font-size:11.5px;background:transparent;border:0;cursor:pointer;color:var(--dsw-alias-label-caption);border-right:1px solid var(--dsw-alias-border-l2);font-family:inherit}',
      '.cddl-seg button:last-child{border-right:0}',
      '.cddl-seg button.on{background:var(--dsw-alias-bg-layer-3);color:var(--dsw-alias-label-primary)}',
      '.cddl-relations button{font-family:var(--ds-font-family-code,monospace);font-size:10.5px;padding:3px 8px}',
      '.cddl-relations button.on{box-shadow:inset 0 -2px 0 var(--dsw-alias-state-business-primary)}',
      '.cddl-zoom{display:flex;gap:2px;align-items:center}',
      '.cddl-zoom .cddl-btn:nth-child(2){min-width:46px;font-family:var(--ds-font-family-code,monospace)}',
    ]

    module.exports = { SHELL_CSS }
    return module.exports
  },
})
