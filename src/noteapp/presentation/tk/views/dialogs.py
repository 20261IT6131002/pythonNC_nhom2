"""Main-thread confirmations for unsaved in-memory content."""

from tkinter import messagebox

from noteapp.presentation.tk.state.editor_state import EditorPhase, EditorState


def confirm_discard(root, state: EditorState) -> bool:
    if not state.unsaved:
        return True
    message = "Nội dung chưa lưu sẽ bị bỏ. Bạn có muốn tiếp tục?"
    if state.phase == EditorPhase.SAVING:
        message = (
            "Thao tác lưu đang xử lý và có thể vẫn hoàn tất. "
            "Nội dung chỉnh sửa chưa lưu sẽ bị bỏ. Bạn có muốn tiếp tục?"
        )
    return messagebox.askyesno("Nội dung chưa lưu", message, parent=root)
