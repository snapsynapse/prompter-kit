"""
Elgato Prompter Tools -- local web GUI
Run: python3 elgato_prompter_tools_gui.py
"""
import io
import os
import sys
import tempfile
import threading
import webbrowser
import zipfile

from flask import (
    Flask,
    flash,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)

from elgato_prompter_tools import (
    delete_script,
    export_script,
    import_script,
    list_scripts,
    load_script_json,
    reindex_scripts,
    rename_script,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Elgato Prompter Tools</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f5f7; color: #1d1d1f; font-size: 14px; }
  a { color: #0071e3; text-decoration: none; }
  a:hover { text-decoration: underline; }

  header { background: #1d1d1f; color: #f5f5f7; padding: 14px 24px;
           display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 16px; font-weight: 600; letter-spacing: -.2px; }
  header span { font-size: 12px; color: #86868b; }

  .container { max-width: 1100px; margin: 0 auto; padding: 24px; }

  .flash-list { list-style: none; margin-bottom: 16px; }
  .flash-list li { padding: 10px 14px; border-radius: 8px; margin-bottom: 8px;
                   font-size: 13px; }
  .flash-list li.success { background: #d1fae5; color: #065f46; }
  .flash-list li.error   { background: #fee2e2; color: #991b1b; }

  .card { background: #fff; border-radius: 12px; padding: 20px 24px;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 20px; }
  .card h2 { font-size: 14px; font-weight: 600; margin-bottom: 14px;
             padding-bottom: 10px; border-bottom: 1px solid #e5e5ea; }

  /* import form */
  .import-grid { display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px;
                 align-items: end; }
  @media (max-width: 700px) { .import-grid { grid-template-columns: 1fr; } }
  .form-group label { display: block; font-size: 12px; color: #86868b;
                      margin-bottom: 4px; font-weight: 500; }
  .form-group input[type=text], .form-group input[type=number] {
    width: 100%; padding: 8px 10px; border: 1px solid #d2d2d7;
    border-radius: 8px; font-size: 13px; background: #fafafa;
    transition: border-color .15s; }
  .form-group input:focus { outline: none; border-color: #0071e3;
                             background: #fff; }

  .drop-zone { border: 2px dashed #d2d2d7; border-radius: 8px;
               padding: 18px 16px; text-align: center; cursor: pointer;
               transition: border-color .15s, background .15s;
               font-size: 13px; color: #86868b; }
  .drop-zone.dragover { border-color: #0071e3; background: #f0f6ff; }
  .drop-zone .filename { color: #1d1d1f; font-weight: 500; margin-top: 4px; }
  #file-input { display: none; }

  /* buttons */
  .btn { display: inline-block; padding: 8px 14px; border-radius: 8px;
         font-size: 13px; font-weight: 500; cursor: pointer; border: none;
         transition: opacity .15s; }
  .btn:hover { opacity: .85; }
  .btn-primary { background: #0071e3; color: #fff; }
  .btn-secondary { background: #e5e5ea; color: #1d1d1f; }
  .btn-danger  { background: #ff3b30; color: #fff; }
  .btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 6px; }

  /* table */
  .script-table { width: 100%; border-collapse: collapse; }
  .script-table th { text-align: left; font-size: 11px; font-weight: 600;
                     color: #86868b; text-transform: uppercase;
                     letter-spacing: .5px; padding: 6px 10px;
                     border-bottom: 1px solid #e5e5ea; }
  .script-table td { padding: 10px 10px; border-bottom: 1px solid #f2f2f7;
                     vertical-align: middle; }
  .script-table tr:last-child td { border-bottom: none; }
  .script-table tr:hover td { background: #fafafa; }

  .guid-cell { font-family: monospace; font-size: 11px; color: #86868b; }
  .missing-badge { font-size: 11px; color: #fff; background: #ff9f0a;
                   padding: 2px 6px; border-radius: 4px; }

  .actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

  /* inline rename form */
  .rename-form { display: none; align-items: center; gap: 6px; margin-top: 6px; }
  .rename-form.open { display: flex; }
  .rename-form input { padding: 5px 8px; border: 1px solid #d2d2d7;
                       border-radius: 6px; font-size: 12px; width: 200px; }

  .toolbar { display: flex; justify-content: space-between; align-items: center;
             margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
  .toolbar-left { display: flex; gap: 8px; }
  .empty-state { text-align: center; color: #86868b; padding: 32px;
                 font-size: 13px; }
</style>
</head>
<body>

<header>
  <h1>Elgato Prompter Tools</h1>
  <span>local GUI</span>
</header>

<div class="container">

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
    <ul class="flash-list">
      {% for cat, msg in messages %}
      <li class="{{ cat }}">{{ msg }}</li>
      {% endfor %}
    </ul>
    {% endif %}
  {% endwith %}

  <!-- Import form -->
  <div class="card">
    <h2>Import Script</h2>
    <form method="post" action="{{ url_for('do_import') }}" enctype="multipart/form-data" id="import-form">
      <div class="import-grid">
        <div class="form-group">
          <label>Script file (.txt or .md)</label>
          <div class="drop-zone" id="drop-zone">
            <div>Drop file here or <a href="#" id="drop-zone-link">click to browse</a></div>
            <div class="filename" id="drop-zone-name"></div>
          </div>
          <input type="file" id="file-input" name="file" accept=".txt,.md">
        </div>
        <div>
          <div class="form-group" style="margin-bottom:10px">
            <label>Friendly name</label>
            <input type="text" name="name" id="name-input" placeholder="My Script" required>
          </div>
          <div class="form-group">
            <label>Index (sort order)</label>
            <input type="number" name="index" value="0" min="0">
          </div>
        </div>
        <div>
          <button type="submit" class="btn btn-primary">Import</button>
        </div>
      </div>
    </form>
  </div>

  <!-- Script list -->
  <div class="card">
    <div class="toolbar">
      <h2 style="border:none;padding:0;margin:0">
        Scripts
        {% if scripts %}
          <span style="color:#86868b;font-weight:400;font-size:13px">&nbsp;({{ scripts|length }})</span>
        {% endif %}
      </h2>
      <div class="toolbar-left">
        {% if scripts %}
        <form method="post" action="{{ url_for('do_reindex') }}" style="display:inline">
          <button type="submit" class="btn btn-secondary btn-sm">Normalize indexes</button>
        </form>
        <a href="{{ url_for('do_export_all') }}" class="btn btn-secondary btn-sm">Export all (.zip)</a>
        {% endif %}
      </div>
    </div>

    {% if scripts %}
    <table class="script-table">
      <thead>
        <tr>
          <th style="width:50px">#</th>
          <th>Name</th>
          <th>GUID</th>
          <th style="width:220px">Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for s in scripts %}
        <tr>
          <td>{{ s.index }}</td>
          <td>
            {{ s.friendlyName or "—" }}
            {% if s.missing %}<span class="missing-badge">MISSING</span>{% endif %}
            <!-- inline rename form -->
            <div class="rename-form" id="rename-{{ s.guid }}">
              <form method="post" action="{{ url_for('do_rename', guid=s.guid) }}"
                    style="display:flex;gap:6px;align-items:center">
                <input type="text" name="new_name" value="{{ s.friendlyName }}" required>
                <button type="submit" class="btn btn-primary btn-sm">Save</button>
                <button type="button" class="btn btn-secondary btn-sm"
                        onclick="toggleRename('{{ s.guid }}')">Cancel</button>
              </form>
            </div>
          </td>
          <td class="guid-cell" title="{{ s.guid }}">{{ s.guid[:8] }}…</td>
          <td>
            <div class="actions">
              {% if not s.missing %}
              <a href="{{ url_for('do_export', guid=s.guid) }}" class="btn btn-secondary btn-sm">Export</a>
              {% endif %}
              <button type="button" class="btn btn-secondary btn-sm"
                      onclick="toggleRename('{{ s.guid }}')">Rename</button>
              <form method="post" action="{{ url_for('do_delete', guid=s.guid) }}"
                    style="display:inline"
                    onsubmit="return confirm('Delete &quot;{{ s.friendlyName|replace('\"','') }}&quot;?')">
                <button type="submit" class="btn btn-danger btn-sm">Delete</button>
              </form>
            </div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty-state">No scripts registered. Import one above.</div>
    {% endif %}
  </div>

</div><!-- /container -->

<script>
// Drop zone
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const dropZoneName = document.getElementById('drop-zone-name');
const nameInput = document.getElementById('name-input');

document.getElementById('drop-zone-link').addEventListener('click', e => {
  e.preventDefault();
  fileInput.click();
});

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  // Transfer dropped file to the real input via DataTransfer
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
  dropZoneName.textContent = file.name;
  // Pre-fill name from filename if empty
  if (!nameInput.value.trim()) {
    nameInput.value = file.name.replace(/[.][^.]+$/, '').replace(/[_-]/g, ' ');
  }
}

// Inline rename toggle
function toggleRename(guid) {
  const form = document.getElementById('rename-' + guid);
  form.classList.toggle('open');
  if (form.classList.contains('open')) form.querySelector('input').focus();
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    try:
        scripts = list_scripts()
    except Exception as e:
        flash(str(e), "error")
        scripts = []
    return render_template_string(_TEMPLATE, scripts=scripts)


@app.route("/import", methods=["POST"])
def do_import():
    file = request.files.get("file")
    name = request.form.get("name", "").strip()
    index = int(request.form.get("index", 0) or 0)

    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("index"))
    if not name:
        flash("Friendly name is required.", "error")
        return redirect(url_for("index"))

    suffix = os.path.splitext(file.filename)[1] or ".txt"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            file.save(f)
        script_path, _ = import_script(tmp_path, name, index)
        flash(f'Imported "{name}" successfully.', "success")
    except Exception as e:
        flash(f"Import failed: {e}", "error")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return redirect(url_for("index"))


@app.route("/export/<guid>")
def do_export(guid):
    try:
        data = load_script_json(guid)
        chapters = data.get("chapters", [])
        if not chapters:
            flash("Script has no chapters to export.", "error")
            return redirect(url_for("index"))
        content = "\n".join(chapters) + "\n"
        name = data.get("friendlyName") or guid
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip() or guid
        return send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            as_attachment=True,
            download_name=f"{safe_name}.txt",
        )
    except Exception as e:
        flash(f"Export failed: {e}", "error")
        return redirect(url_for("index"))


@app.route("/export-all")
def do_export_all():
    try:
        scripts = list_scripts()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for s in scripts:
                if s["missing"]:
                    continue
                data = load_script_json(s["guid"])
                chapters = data.get("chapters", [])
                if not chapters:
                    continue
                content = "\n".join(chapters) + "\n"
                safe = "".join(c if c.isalnum() or c in "-_ " else "_"
                               for c in s["friendlyName"]).strip() or s["guid"]
                arc_name = f"{safe}.txt"
                zf.writestr(arc_name, content.encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prompter_scripts.zip",
        )
    except Exception as e:
        flash(f"Export all failed: {e}", "error")
        return redirect(url_for("index"))


@app.route("/delete/<guid>", methods=["POST"])
def do_delete(guid):
    try:
        deleted = delete_script(guid)
        flash(f"Deleted script {deleted[:8]}…", "success")
    except Exception as e:
        flash(f"Delete failed: {e}", "error")
    return redirect(url_for("index"))


@app.route("/rename/<guid>", methods=["POST"])
def do_rename(guid):
    new_name = request.form.get("new_name", "").strip()
    try:
        rename_script(guid, new_name)
        flash(f'Renamed to "{new_name}".', "success")
    except Exception as e:
        flash(f"Rename failed: {e}", "error")
    return redirect(url_for("index"))


@app.route("/reindex", methods=["POST"])
def do_reindex():
    try:
        reindex_scripts()
        flash("Indexes normalized.", "success")
    except Exception as e:
        flash(f"Reindex failed: {e}", "error")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _open_browser(port: int) -> None:
    import time
    time.sleep(0.6)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    print(f"Prompter Tools GUI running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
