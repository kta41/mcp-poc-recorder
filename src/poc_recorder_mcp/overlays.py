"""Injected browser overlays (virtual cursor, click ripples, HUD captions) and storage scripts."""

from __future__ import annotations

import json
from typing import Any

OVERLAY_INIT_SCRIPT = """
(() => {
  const installOverlay = () => {
    if (document.getElementById('__mcp_poc_overlay_root')) return;
    const root = document.createElement('div');
    root.id = '__mcp_poc_overlay_root';
    Object.assign(root.style, {
      position: 'fixed',
      inset: '0',
      pointerEvents: 'none',
      zIndex: '2147483647',
      overflow: 'hidden'
    });

    const cursor = document.createElement('div');
    cursor.id = '__mcp_poc_cursor';
    Object.assign(cursor.style, {
      position: 'fixed',
      top: '-40px',
      left: '-40px',
      width: '20px',
      height: '20px',
      borderRadius: '50%',
      background: 'rgba(56, 189, 248, 0.88)',
      border: '2.5px solid #ffffff',
      boxShadow: '0 0 14px rgba(56, 189, 248, 0.95), 0 2px 6px rgba(0,0,0,0.45)',
      pointerEvents: 'none',
      transform: 'translate(-50%, -50%)',
      transition: 'left 0.06s linear, top 0.06s linear, transform 0.12s ease, background 0.12s ease',
      display: window.__mcpShowCursor === false ? 'none' : 'block'
    });
    root.appendChild(cursor);

    const hud = document.createElement('div');
    hud.id = '__mcp_poc_hud';
    Object.assign(hud.style, {
      position: 'fixed',
      bottom: '22px',
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'rgba(15, 23, 42, 0.92)',
      color: '#f8fafc',
      border: '1px solid rgba(56, 189, 248, 0.65)',
      borderRadius: '999px',
      padding: '8px 20px',
      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      fontSize: '13.5px',
      fontWeight: '600',
      letterSpacing: '0.01em',
      boxShadow: '0 10px 28px rgba(0, 0, 0, 0.55)',
      pointerEvents: 'none',
      opacity: '0',
      transition: 'opacity 0.2s ease',
      whiteSpace: 'nowrap',
      maxWidth: '90vw',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    });
    root.appendChild(hud);
    document.documentElement.appendChild(root);

    document.addEventListener('mousemove', (e) => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
    }, true);

    document.addEventListener('mousedown', (e) => {
      cursor.style.transform = 'translate(-50%, -50%) scale(0.72)';
      cursor.style.background = 'rgba(16, 185, 129, 0.95)';
      if (window.__mcpShowCursor === false) return;
      const ripple = document.createElement('div');
      Object.assign(ripple.style, {
        position: 'fixed',
        left: e.clientX + 'px',
        top: e.clientY + 'px',
        width: '12px',
        height: '12px',
        borderRadius: '50%',
        border: '2px solid rgba(56, 189, 248, 0.95)',
        transform: 'translate(-50%, -50%) scale(1)',
        opacity: '0.95',
        pointerEvents: 'none',
        transition: 'transform 0.42s ease-out, opacity 0.42s ease-out'
      });
      root.appendChild(ripple);
      requestAnimationFrame(() => {
        ripple.style.transform = 'translate(-50%, -50%) scale(3.4)';
        ripple.style.opacity = '0';
      });
      setTimeout(() => ripple.remove(), 450);
    }, true);

    document.addEventListener('mouseup', () => {
      cursor.style.transform = 'translate(-50%, -50%) scale(1)';
      cursor.style.background = 'rgba(56, 189, 248, 0.88)';
    }, true);
  };

  window.__mcpSetCaption = (text) => {
    installOverlay();
    if (window.__mcpShowHud === false) return;
    const hud = document.getElementById('__mcp_poc_hud');
    if (!hud) return;
    if (!text) {
      hud.style.opacity = '0';
    } else {
      hud.textContent = text;
      hud.style.opacity = '1';
    }
  };

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', installOverlay);
  } else {
    installOverlay();
  }
})();
"""


def build_overlay_script(show_cursor: bool = True, show_hud: bool = True) -> str:
    """Return the JavaScript snippet that configures and installs the recording overlay."""
    flags = f"window.__mcpShowCursor = {'true' if show_cursor else 'false'}; window.__mcpShowHud = {'true' if show_hud else 'false'};\n"
    return flags + OVERLAY_INIT_SCRIPT


def build_storage_script(
    local_storage: dict[str, Any] | None = None,
    session_storage: dict[str, Any] | None = None,
) -> str | None:
    """Build an init script that populates localStorage and sessionStorage before page scripts execute."""
    if not local_storage and not session_storage:
        return None

    def normalize(mapping: dict[str, Any] | None) -> dict[str, str]:
        if not mapping:
            return {}
        out: dict[str, str] = {}
        for key, value in mapping.items():
            out[str(key)] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return out

    ls_json = json.dumps(normalize(local_storage), ensure_ascii=False)
    ss_json = json.dumps(normalize(session_storage), ensure_ascii=False)
    return (
        "(() => {\n"
        f"  const ls = {ls_json};\n"
        f"  const ss = {ss_json};\n"
        "  try { for (const [k, v] of Object.entries(ls)) window.localStorage.setItem(k, v); } catch (e) {}\n"
        "  try { for (const [k, v] of Object.entries(ss)) window.sessionStorage.setItem(k, v); } catch (e) {}\n"
        "})();"
    )
