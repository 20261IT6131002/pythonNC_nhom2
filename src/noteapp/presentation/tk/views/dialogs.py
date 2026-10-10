"""Main-thread confirmations for unsaved in-memory content."""

from tkinter import Misc, messagebox

from noteapp.presentation.tk.state.editor_state import EditorPhase, EditorState


def confirm_discard(root: Misc, state: EditorState) -> bool:
    if not state.unsaved:
        return True
    message = "Nội dung chưa lưu sẽ bị bỏ. Bạn có muốn tiếp tục?"
    if state.phase == EditorPhase.SAVING:
        message = (
            "Thao tác lưu đang xử lý và có thể vẫn hoàn tất. "
            "Nội dung chỉnh sửa chưa lưu sẽ bị bỏ. Bạn có muốn tiếp tục?"
        )
    return messagebox.askyesno("Nội dung chưa lưu", message, parent=root)


def confirm_trash(root: Misc) -> bool:
    return messagebox.askyesno(
        "Chuyển vào thùng rác",
        "Chuyển ghi chú này vào thùng rác? Bạn có thể khôi phục sau.",
        parent=root,
    )


def confirm_purge(root: Misc) -> bool:
    return messagebox.askyesno(
        "Xóa vĩnh viễn",
        "Xóa vĩnh viễn ghi chú này? Thao tác này không thể hoàn tác.",
        parent=root,
        icon="warning",
    )
