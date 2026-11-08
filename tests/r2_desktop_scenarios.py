"""FR-15/16 through the Tk menu and worker bridge against isolated Mongo."""

import os
from pathlib import Path
from traceback import print_exception
from unittest.mock import patch

from pypdf import PdfReader

from noteapp.application.dto.local_draft import RecoveryDecision, RecoveryKind
from noteapp.bootstrap import build_runtime
from noteapp.infrastructure.config import Config
from noteapp.presentation.tk.state.editor_state import EditorPhase
from tests.desktop_scenarios import wait_for
from tests.draft_fakes import draft

WINDOW = "noteapp.presentation.tk.views.app_window."
TITLE = "Sổ tay tiếng Việt"
CONTENT = "Đường Nguyễn Trãi và những ghi chú."


def main():
    target = Path(os.environ["NOTEAPP_R2_TEST_EXPORTS"])
    runtime = build_runtime(Config.from_env())
    app = runtime.window
    app.root.withdraw()
    callbacks = []

    def capture(*error):
        callbacks.append(error)
        print_exception(*error)

    app.root.report_callback_exception = capture
    try:
        wait_for(app, lambda: app.sidebar._categories_ready)
        app.sidebar.statistics_button.invoke()
        wait_for(app, lambda: app._statistics_dialog is not None)
        labels = app._statistics_dialog.winfo_children()[0].winfo_children()
        assert any(
            widget.cget("text") == "Chưa có ghi chú đang hoạt động."
            for widget in labels
            if widget.winfo_class() == "TLabel"
        )

        app.note_editor.title.set(TITLE)
        app.note_editor.content.insert("end", CONTENT)
        app.root.update()
        app.save()
        wait_for(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
        with (
            patch(WINDOW + "ask_export_directory", return_value=str(target)),
            patch(WINDOW + "messagebox.showinfo") as success,
        ):
            for menu_item in ("Markdown và ảnh", "PDF"):
                app.note_editor.export_menu.invoke(menu_item)
                wait_for(app, lambda: app._export_request is None)
            assert success.call_count == 2
        md = next(target.glob("*/note.md"))
        pdf = next(target.glob("*/note.pdf"))
        assert CONTENT in md.read_text(encoding="utf-8")
        assert CONTENT in PdfReader(pdf).pages[0].extract_text()

        old_dialog = app._statistics_dialog
        app.sidebar.statistics_button.invoke()
        wait_for(app, lambda: app._statistics_dialog is not old_dialog)
        panel = app._statistics_dialog.winfo_children()[0]
        assert panel.winfo_children()[0].cget("text") == "Ghi chú đang hoạt động: 1"

        with patch(WINDOW + "ask_passphrase", return_value="synthetic R2 passphrase"):
            app.lock_selected()
        wait_for(app, lambda: app.editor.state.locked_closed)
        with (
            patch(WINDOW + "ask_export_directory") as chooser,
            patch(WINDOW + "messagebox.showwarning") as warning,
        ):
            app.note_editor.export_menu.invoke("PDF")
            chooser.assert_not_called()
            warning.assert_called_once()
        assert len(tuple(target.iterdir())) == 2
        snapshot = draft(source_locked=True)
        with patch(WINDOW + "ask_passphrase", return_value="synthetic R2 recovery phrase"):
            app.draft_recovered(RecoveryDecision(RecoveryKind.SAFE_NEW, snapshot))
        assert app.editor.state.note_id is None and app.editor.state.source_locked
        assert app.editor.state.operation_id == snapshot.client_operation_id
        app.save()
        wait_for(app, lambda: app.editor.state.locked_closed)
        records = runtime.client[Config.from_env().db_name].notes
        recovered = records.find_one({"client_operation_id": snapshot.client_operation_id})
        assert recovered["is_locked"] and "content_plain" not in recovered
        assert not callbacks
    finally:
        runtime.close()
    print("SCENARIO PASSED")


if __name__ == "__main__":
    main()
