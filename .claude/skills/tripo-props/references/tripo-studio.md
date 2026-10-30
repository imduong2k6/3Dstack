# Tripo Studio through Claude in Chrome: details and failure modes

From an earlier project (22 and 23 Oct 2026). The Generator drives Studio; the live worker only imports. Coordinates below are from one window size and **shifted several times** (1512×807 → 1535×784 → 1535×698 →
2463×1258). Prefer `find` refs; re-`find` after every UI change (refs go stale: "No element found").

## Studio facts
- URL `https://studio.tripo3d.ai/workspace/generate`. Modes HD Model / Smart Mesh; model H3.1 ("Best Quality").
- Geometry & Texture popover: Ultra Mesh Quality, AI Complete, Texture 2K/4K/8K, Remove Lighting, PBR,
  Topology Quad/Triangle, Polycount 500–2,000,000. Settings auto-save on the account.
- Cost seen: 55 credits at the 4K / 2M defaults, 45 at 2K / 3,000 tris (smoke test), **30 with Ultra Mesh
  off** (all later props). Ultra Mesh added nothing visible at the polycounts used.
- Time: ~95 s for small props, ~2.5–4 min for bigger ones. Several jobs can run at once in Studio.
- Credits: 3,200 at start → 3,155 (smoke test) → 3,005 (first five) → 2,405 (Phase 9 start) → 2,285 (after
  the four Phase 9 props). Balance is read from the page; credit purchases are the user's.

## Upload
- Mode icons in the Generate panel, left to right: single image, multi-view, **Batch**. Batch makes one model
  per image (4 images = 4 × the cost); it was picked by mistake once and caught on a screenshot.
- `find "image file upload input"` / `find "file input for single image upload"` → `file_upload {ref, paths}`
  with Windows paths (`D:\\...`). Multi-view: `find "image file inputs for Front, Left, Right, Back slots"` →
  one `file_upload` per ref (a `browser_batch` of uploads with 2 s waits works).
- The image slots render only after the mode is chosen; until then `input[type=file]` lists only the
  3D-model upload (accept `.fbx,.obj,.stl,.glb`). Check:
  `[...document.querySelectorAll('input[type=file]')].map(e=>e.accept)` via `javascript_tool`.
- After an upload the image input disappears. To load the next prop: scroll the left panel up, hover the
  image, click its trash icon, `find` the new input. Clicking a slot's trash while the panel is scrolled
  opened an image viewer instead.
- Slot mapping that worked: 2×2 tiles → Front=front, Left=left, Right=right, Back=back. Strip tiles →
  Front=v0, Left=v1, Right=v3, Back=v2. The window-AC original tiles needed Left/Right swapped. Rule noted
  in a summary (not re-verified): the Left slot wants the image showing the object's left side, with the
  front toward the image's right. Check the result in the viewer either way.

## Generate
Open Geometry & Texture (position shifts once an image is loaded) → toggles → triple-click the polycount
field, type the number, **Tab** to commit, `find` it again to read the value → close the popover → Generate
(`find "Generate"`).

## Export and send
1. Open the finished model from the asset list, click **Export** (only then can `find` see the panel).
2. File Name: `find` the field, triple-click (+ ctrl+a), type `SM_<Name>`. It **reverts every time the panel
   closes**, so re-type for each model. Even when set, one import arrived under Tripo's AI title
   ("terracotta plant pot 3d model") — always check the name in Blender.
3. Texture Resolution dropdown → **1k**. Format GLB was used for the smoke test.
4. **Hover "Send to"** (a DCC-logo carousel button) → its submenu opens → click **"Send to Blender"** by
   `find` ref (coordinate clicks were unreliable; the hover chain sometimes needs 2–3 hover steps).
   Reliable alternative (2026-10-23, 9/9 sends): after the name and 1k are set, run in `javascript_tool`
   ```js
   const NAME='SM_<Name>'; const b=[...document.querySelectorAll('button')].find(e=>e.innerText.trim()==='Send to');
   const r=b.getBoundingClientRect(), o={bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2};
   for (const t of ['pointerover','pointerenter','mouseover','mouseenter','pointermove','mousemove'])
     b.dispatchEvent(new (t.startsWith('pointer')?PointerEvent:MouseEvent)(t,o));
   await new Promise(r=>setTimeout(r,700));
   const res=[...document.querySelectorAll('button,[role=combobox]')].map(e=>e.innerText.trim()).filter(t=>/^(512|1k|2k|4k|8k)$/i.test(t));
   const d=[...document.querySelectorAll('div.cursor-pointer')].find(e=>e.textContent.trim()==='Send to Blender');
   const inp=[...document.querySelectorAll('input')].find(i=>i.value===NAME);
   (d&&inp&&res.includes('1k')) ? (d.click(), 'sent '+NAME) : 'NOT sent: menu '+!!d+' name '+!!inp+' res '+res
   ```
   Screenshot frame → CSS px is ~1.58 here, not the 1.667 the frame size suggests; a coordinate click
   one row low hits "Send to 3ds Max".
5. Wait 25–40 s before anything else (the log line "Successfully imported" came 25 s after the click for
   a 50k model, 35 s for an 8k one; Studio shows nothing meanwhile), Escape, close the panel.

## DCC Bridge (Blender side)
- Add-on `Tripo3d_Blender_Bridge` v1.0.34 in
  `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\Tripo3d_Blender_Bridge`
  (`core/ws_server.py` port 60600, keeps only the newest client: "Closing 1 existing client(s)…").
- Log: `%TEMP%\tripo3d_blender_bridge.log` — lines "Received complete model
  name", "Renamed imported root", "Successfully imported <task id>". The Generator reads the file
  directly. Don't `find` across AppData for it (timed out); the live worker can ask Blender:
```python
import sys
st = sys.modules["Tripo3d_Blender_Bridge.core.status_manager"].status
print(st.state, st.client_name)            # want ConnectionState.CONNECTED, "Tripo Studio"
from Tripo3d_Blender_Bridge.utils.logger import logger
f = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
print("".join(open(f, encoding="utf-8", errors="replace").readlines()[-25:]))
```
- `netstat -ano | grep 60600` shows which process holds the client.

## Failure → fix
| Symptom | Fix |
|---|---|
| Clicking "Send to" does nothing | Hover it; pick "Send to Blender" from the submenu (found by the user). |
| No "Successfully imported" 90 s after a send | Stall budget: toggle the DCC Bridge switch (Blender off, on) and resend once. Still nothing after another 90 s: GLB for the rest of the batch (SKILL.md section 4, step 5). On an earlier project the stalls cost 87 min from approval to the last import. |
| "Please open the plugin on DCC Bridge at the top first", or Send silently does nothing although port 60600 listens | Top-bar **DCC Bridge** button → dialog with one switch per DCC (Blender, 3ds Max, Unity, Unreal, Maya, Godot, ZBrush…) → switch **Blender** on (`aria-checked` was false). Page reload did not help. The popover may not show in screenshots; read it with `javascript_tool` (`innerText`, `getBoundingClientRect`). |
| Bridge connected to another tab / browser | Close the other Studio tab; toggling Blender in this tab makes it the newest client. |
| `.001` duplicate in Blender | Sent twice while a big model was still transferring. Check the log before resending; delete the duplicate with its mesh, materials and images when `users == 0`. |
| `browser_batch`: "connection was lost before its result came back" | Inspect state (screenshot, `get_scene_info`) before repeating anything. |
| A batch item with an unknown tool name | Fails the batch after earlier items already ran. |
| Mesh in shards / lumpy | Polycount too low or inconsistent views → re-crop at one scale, raise polycount, or single 3/4 image. |
| Claude in Chrome "not connected" | User installs the extension and signs in with the same account; `tabs_context_mcp {createIfEmpty:true}`. |
| Old tab ids rejected ("not in Claude's tab group") | Call `tabs_context_mcp` for fresh ids. |
| Console/network logs empty | Tracking starts at the first `read_console_messages` / `read_network_requests` call — call before acting. No `(?i)` in their `pattern`. |
| 2–3 failed attempts at the same step | Stop and ask the user (chrome-browser rule); the hover fix came from the user. |

Diagnostic used once (in-page WebSocket tracer, gone after reload):
```js
window.__wsLog=[]; const O=window.WebSocket; window.WebSocket=function(u,p){window.__wsLog.push('new '+u);
  const s=p?new O(u,p):new O(u); s.addEventListener('open',()=>window.__wsLog.push('open '+u)); return s;};
window.WebSocket.prototype=O.prototype;
```
